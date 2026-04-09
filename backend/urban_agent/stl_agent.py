"""
STL Analysis Agent - Standalone Version
Advanced STL file analysis agent with LangGraph workflow for building geometry analysis
"""
import os
import time
from typing import Dict, Any, List, Optional, TYPE_CHECKING
from dataclasses import dataclass
from langgraph.graph import StateGraph, END
from langchain_openai import ChatOpenAI
from langchain_core.messages import BaseMessage, HumanMessage, SystemMessage
from langchain_core.runnables import RunnableConfig
import trimesh
import matplotlib.pyplot as plt
from matplotlib.collections import PolyCollection
import numpy as np
from config import OPENAI_API_KEY

if TYPE_CHECKING:  # pragma: no cover
    from llm_recorder import LLMRecorder

@dataclass
class STLAnalysisState:
    """STL analysis state management"""
    stl_file_path: str = ""
    stl_content: str = ""
    file_size: int = 0
    analysis_result: str = ""
    visualization_code: str = ""
    output_path: str = ""
    error_message: str = ""
    stage: str = "init"  # init -> file_read -> analysis -> visualization -> complete

class STLAnalysisAgent:
    """STL Analysis Agent with LangGraph workflow"""
    
    def __init__(self, api_key: str, recorder: Optional["LLMRecorder"] = None):
        self.llm = ChatOpenAI(
            api_key=api_key,
            model="gpt-5",
            temperature=0.1
        )
        self.graph = self._build_graph()
        self.recorder = recorder

    def _invoke_with_logging(self, stage: str, messages: List[BaseMessage], config: RunnableConfig | None = None):
        start = time.time()
        response = self.llm.invoke(messages, config=config)
        if self.recorder:
            prompt_text = "\n\n".join(
                f"{msg.__class__.__name__}: {getattr(msg, 'content', '')}" for msg in messages
            )
            self.recorder.record(
                stage=stage,
                prompt=prompt_text,
                response=response.content,
                elapsed_time=time.time() - start,
                metadata={"agent": "stl"},
            )
        return response
    
    def _build_graph(self) -> StateGraph:
        """Build LangGraph workflow"""
        workflow = StateGraph(STLAnalysisState)
        
        # Add nodes
        workflow.add_node("file_reader", self._read_stl_file)
        workflow.add_node("content_analyzer", self._analyze_stl_content)
        workflow.add_node("code_generator", self._generate_visualization_code)
        workflow.add_node("code_executor", self._execute_visualization)
        workflow.add_node("error_handler", self._handle_error)
        
        # Set entry point
        workflow.set_entry_point("file_reader")
        
        # Add conditional edges (error handling)
        workflow.add_conditional_edges(
            "file_reader",
            self._check_file_status,
            {
                "success": "content_analyzer",
                "error": "error_handler"
            }
        )
        
        workflow.add_conditional_edges(
            "content_analyzer",
            self._check_analysis_status,
            {
                "success": "code_generator",
                "error": "error_handler"
            }
        )
        
        workflow.add_conditional_edges(
            "code_generator",
            self._check_code_status,
            {
                "success": "code_executor",
                "error": "error_handler"
            }
        )
        
        # Add end edges
        workflow.add_edge("code_executor", END)
        workflow.add_edge("error_handler", END)
        
        return workflow.compile()
    
    def _read_stl_file(self, state: STLAnalysisState) -> STLAnalysisState:
        """Node 1: Read STL file"""
        print("📂 STL Agent: Reading STL file...")
        
        try:
            if not os.path.exists(state.stl_file_path):
                state.error_message = f"File not found: {state.stl_file_path}"
                state.stage = "error"
                return state
            
            # Try to read as ASCII STL first
            try:
                with open(state.stl_file_path, 'r', encoding='utf-8') as f:
                    first_line = f.readline().strip()
                    if first_line.startswith('solid'):
                        # ASCII STL format - read the whole file
                        f.seek(0)
                        state.stl_content = f.read()
                        state.file_size = len(state.stl_content)
                        state.stage = "file_read"
                        print(f"✅ STL Agent: ASCII STL file read successfully ({state.file_size:,} characters)")
                    else:
                        # Not ASCII STL, try binary format with trimesh
                        print("⚠️ ASCII format not detected, trying to read as binary STL...")
                        import trimesh
                        mesh = trimesh.load(state.stl_file_path)
                        # Convert binary STL info to text description
                        state.stl_content = f"""Binary STL File:
Vertices: {len(mesh.vertices)}
Faces: {len(mesh.faces)}
Bounds: {mesh.bounds.tolist()}
Volume: {mesh.volume}
Surface Area: {mesh.area}
"""
                        state.file_size = len(state.stl_content)
                        state.stage = "file_read"
                        print(f"✅ STL Agent: Binary STL file read successfully (converted to description)")
            except UnicodeDecodeError:
                # Binary file, use trimesh
                print("⚠️ Unicode error, reading as binary STL...")
                import trimesh
                mesh = trimesh.load(state.stl_file_path)
                state.stl_content = f"""Binary STL File:
Vertices: {len(mesh.vertices)}
Faces: {len(mesh.faces)}
Bounds: {mesh.bounds.tolist()}
Volume: {mesh.volume}
Surface Area: {mesh.area}
"""
                state.file_size = len(state.stl_content)
                state.stage = "file_read"
                print(f"✅ STL Agent: Binary STL file read successfully (converted to description)")
            
        except Exception as e:
            state.error_message = f"File reading failed: {str(e)}"
            state.stage = "error"
        
        return state
    
    def _analyze_stl_content(self, state: STLAnalysisState) -> STLAnalysisState:
        """Node 2: Analyze STL content"""
        print("🔍 STL Agent: Analyzing STL content...")
        
        try:
            # Create representative sample
            sample_size = 5000
            middle_start = len(state.stl_content) // 2
            sample_content = (
                state.stl_content[:sample_size] + 
                "\n\n... [MIDDLE SECTION] ...\n\n" +
                state.stl_content[middle_start:middle_start + sample_size] +
                "\n\n... [END SECTION] ...\n\n" +
                state.stl_content[-sample_size:]
            )
            
            # Build analysis prompt
            messages = [
                SystemMessage(content="""You are a 3D geometry expert specializing in urban building analysis.
                Analyze STL file content and provide insights about building structure, thermal performance, shading patterns, and urban design implications."""),
                HumanMessage(content=f"""Please analyze this Singapore building's STL file content.
                The file contains {state.file_size:,} characters of 3D geometry data.
                
                Please provide insights on:
                1. Building structure and form
                2. Potential thermal performance characteristics
                3. Shading and solar exposure patterns
                4. Urban design implications
                
                STL file sample (complete file has {state.file_size:,} characters):
                {sample_content}""")
            ]
            
            # Call LLM analysis
            response = self._invoke_with_logging("STL Content Analysis", messages)
            state.analysis_result = response.content
            state.stage = "analysis"
            print("✅ STL Agent: Content analysis completed")
            
        except Exception as e:
            state.error_message = f"Content analysis failed: {str(e)}"
        
        return state
    
    def _generate_visualization_code(self, state: STLAnalysisState) -> STLAnalysisState:
        """Node 3: Generate visualization code"""
        print("🎨 STL Agent: Generating visualization code...")
        
        try:
            messages = [
                SystemMessage(content="""You are a 3D data visualization expert.
                Generate matplotlib code to create traditional architectural orthographic views."""),
                HumanMessage(content=f"""I will execute your Python code locally.
                You have two variables available: stl_path (STL file path) and output_path (PNG save path).
                
                Please generate traditional architectural orthographic view code:
                - Front view (XZ plane)
                - Side view (YZ plane)
                - Top view (XY plane)
                
                Requirements:
                - Only use numpy, matplotlib, trimesh
                - Load STL file from stl_path
                - Project triangles to corresponding planes, draw PolyCollection (filled black)
                - Equal aspect ratio, no grid/ticks, set titles
                - Save PNG to output_path
                - Code should be directly executable, not function definitions
                
                Return one executable Python code block.
                
                STL file size: {state.file_size:,} characters""")
            ]
            
            response = self._invoke_with_logging("STL Visualization Code", messages)
            
            # Extract code
            content = response.content
            if "```python" in content:
                start_idx = content.find("```python") + 9
                end_idx = content.find("```", start_idx)
                if end_idx > start_idx:
                    state.visualization_code = content[start_idx:end_idx].strip()
                    state.stage = "code_generated"
                    print("✅ STL Agent: Visualization code generated")
                else:
                    state.error_message = "Cannot extract valid Python code"
            else:
                state.error_message = "No Python code found in LLM response"
                
        except Exception as e:
            state.error_message = f"Code generation failed: {str(e)}"
        
        return state
    
    def _execute_visualization(self, state: STLAnalysisState) -> STLAnalysisState:
        """Node 4: Execute visualization code"""
        print("⚙️ STL Agent: Executing visualization code...")
        
        try:
            # Prepare execution environment
            exec_globals = {
                "stl_path": state.stl_file_path,
                "output_path": state.output_path,
                "numpy": np,
                "matplotlib": plt,
                "trimesh": trimesh,
                "PolyCollection": PolyCollection,
                "plt": plt,
                "np": np,
                "os": os
            }
            
            # Execute LLM generated code
            exec(state.visualization_code, exec_globals)
            
            # Check if there are generated functions and call them
            function_names = ['plot_orthographic_views', 'create_orthographic_views', 'generate_views', 'main']
            function_called = False
            for func_name in function_names:
                if func_name in exec_globals and callable(exec_globals[func_name]):
                    try:
                        if func_name == 'main':
                            exec_globals[func_name]()
                        else:
                            exec_globals[func_name](state.stl_file_path, state.output_path)
                        function_called = True
                        break
                    except Exception as func_error:
                        print(f"Function {func_name} call failed: {func_error}")
                        continue
            
            if not function_called:
                print("No callable function found, code may have executed directly")
            
            # Verify output file
            if os.path.exists(state.output_path):
                file_size = os.path.getsize(state.output_path)
                state.stage = "complete"
                print(f"✅ STL Agent: Visualization completed ({file_size} bytes)")
            else:
                state.error_message = f"Visualization file not generated: {state.output_path}"
                
        except Exception as e:
            state.error_message = f"Code execution failed: {str(e)}"
        
        return state
    
    def _handle_error(self, state: STLAnalysisState) -> STLAnalysisState:
        """Error handling node"""
        print(f"❌ STL Agent: Error encountered - {state.error_message}")
        state.stage = "error"
        return state
    
    # Conditional check functions
    def _check_file_status(self, state: STLAnalysisState) -> str:
        return "error" if state.error_message else "success"
    
    def _check_analysis_status(self, state: STLAnalysisState) -> str:
        return "error" if state.error_message else "success"
    
    def _check_code_status(self, state: STLAnalysisState) -> str:
        return "error" if state.error_message else "success"
    
    def analyze_stl(self, stl_file_path: str, output_path: str, config: RunnableConfig | None = None) -> Dict[str, Any]:
        """Main analysis method"""
        print("🚀 STL Agent: Starting analysis...")
        
        # Initialize state
        initial_state = STLAnalysisState(
            stl_file_path=stl_file_path,
            output_path=output_path
        )
        
        # Execute workflow
        initial_state.runnable_config = config
        final_state = self.graph.invoke(initial_state)
        
        # Handle both object and dict returns from LangGraph
        if isinstance(final_state, dict):
            stage = final_state.get('stage', 'unknown')
            analysis_result = final_state.get('analysis_result', '')
            output_path = final_state.get('output_path', '')
            error_message = final_state.get('error_message', '')
            file_size = final_state.get('file_size', 0)
        else:
            stage = final_state.stage
            analysis_result = final_state.analysis_result
            output_path = final_state.output_path
            error_message = final_state.error_message
            file_size = final_state.file_size
        
        # Return results
        return {
            "success": stage == "complete",
            "stage": stage,
            "analysis": analysis_result,
            "output_path": output_path if stage == "complete" else None,
            "error": error_message,
            "file_size": file_size
        }

def main():
    """Test STL Analysis Agent standalone"""
    print("🏗️ Testing STL Analysis Agent (Standalone)")
    print("="*60)
    
    # Initialize Agent
    agent = STLAnalysisAgent(api_key=OPENAI_API_KEY)
    
    # Set file paths
    stl_file_path = "/scratch/Urban/small_case_coupling 1/small_case_coupling/stl/building.stl"
    output_path = "/scratch/Urban/small_case_coupling 1/small_case_coupling/stl/stl_agent_views.png"
    
    # Execute analysis
    result = agent.analyze_stl(stl_file_path, output_path)
    
    # Output results
    print("\n" + "="*60)
    print("🎯 STL Analysis Agent Results")
    print("="*60)
    print(f"Status: {'✅ Success' if result['success'] else '❌ Failed'}")
    print(f"Stage: {result['stage']}")
    print(f"File size: {result['file_size']:,} characters")
    
    if result['success']:
        print(f"Output file: {result['output_path']}")
        print("\n📊 Building Analysis Results:")
        print("-" * 50)
        print(result['analysis'])
        print("-" * 50)
    else:
        print(f"Error message: {result['error']}")

if __name__ == "__main__":
    main()

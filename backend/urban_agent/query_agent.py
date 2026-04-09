"""
Building Query Agent - Standalone Version
Advanced building query analysis agent with LangGraph workflow for solar and thermal analysis
"""
import re
import time
from typing import Dict, Any, List, Optional, TYPE_CHECKING
from dataclasses import dataclass
from langgraph.graph import StateGraph, END
from langchain_openai import ChatOpenAI
from langchain_core.messages import BaseMessage, HumanMessage, SystemMessage
from datetime import datetime
from config import OPENAI_API_KEY

if TYPE_CHECKING:  # pragma: no cover
    from llm_recorder import LLMRecorder

@dataclass
class BuildingQueryState:
    """Building query analysis state management"""
    building_analysis: str = ""
    query: str = ""
    location: str = "Singapore"
    season: str = "winter"
    time_of_day: str = "afternoon"
    building_side: str = ""
    query_response: str = ""
    confidence_score: float = 0.0
    reasoning: str = ""
    error_message: str = ""
    stage: str = "init"  # init -> query_analysis -> response_generation -> complete

class BuildingQueryAgent:
    """Building Query Agent for answering common building-related queries"""
    
    def __init__(self, api_key: str, recorder: Optional["LLMRecorder"] = None):
        self.llm = ChatOpenAI(
            api_key=api_key,
            model="gpt-5",
            temperature=0.1
        )
        self.graph = self._build_query_graph()
        self.recorder = recorder

    def _invoke_with_logging(self, stage: str, messages: List[BaseMessage]):
        start = time.time()
        response = self.llm.invoke(messages)
        if self.recorder:
            prompt_text = "\n\n".join(
                f"{msg.__class__.__name__}: {getattr(msg, 'content', '')}" for msg in messages
            )
            self.recorder.record(
                stage=stage,
                prompt=prompt_text,
                response=response.content,
                elapsed_time=time.time() - start,
                metadata={"agent": "query"},
            )
        return response
    
    def _build_query_graph(self) -> StateGraph:
        """Build LangGraph workflow for query processing"""
        workflow = StateGraph(BuildingQueryState)
        
        # Add nodes
        workflow.add_node("query_processor", self._process_query)
        workflow.add_node("solar_analyzer", self._analyze_solar_conditions)
        workflow.add_node("response_generator", self._generate_response)
        workflow.add_node("error_handler", self._handle_query_error)
        
        # Set entry point
        workflow.set_entry_point("query_processor")
        
        # Add edges
        workflow.add_edge("query_processor", "solar_analyzer")
        workflow.add_edge("solar_analyzer", "response_generator")
        workflow.add_edge("response_generator", END)
        workflow.add_edge("error_handler", END)
        
        # Add conditional edges
        workflow.add_conditional_edges(
            "query_processor",
            self._check_query_status,
            {
                "success": "solar_analyzer",
                "error": "error_handler"
            }
        )
        
        workflow.add_conditional_edges(
            "solar_analyzer",
            self._check_analysis_status,
            {
                "success": "response_generator",
                "error": "error_handler"
            }
        )
        
        return workflow.compile()
    
    def _process_query(self, state: BuildingQueryState) -> BuildingQueryState:
        """Node 1: Process and parse the query"""
        print("🔍 Query Agent: Processing building query...")
        
        try:
            # Extract key parameters from query
            query_lower = state.query.lower()
            
            # Determine building side
            if "north" in query_lower:
                state.building_side = "north"
            elif "south" in query_lower:
                state.building_side = "south"
            elif "east" in query_lower:
                state.building_side = "east"
            elif "west" in query_lower:
                state.building_side = "west"
            else:
                state.building_side = "unspecified"
            
            # Determine season
            if "winter" in query_lower:
                state.season = "winter"
            elif "summer" in query_lower:
                state.season = "summer"
            elif "spring" in query_lower:
                state.season = "spring"
            elif "autumn" in query_lower or "fall" in query_lower:
                state.season = "autumn"
            
            # Determine time of day
            if "morning" in query_lower:
                state.time_of_day = "morning"
            elif "afternoon" in query_lower:
                state.time_of_day = "afternoon"
            elif "evening" in query_lower:
                state.time_of_day = "evening"
            elif "noon" in query_lower or "midday" in query_lower:
                state.time_of_day = "noon"
            
            state.stage = "query_processed"
            print(f"✅ Query Agent: Query processed ({state.building_side} side, {state.season}, {state.time_of_day})")
            
        except Exception as e:
            state.error_message = f"Query processing failed: {str(e)}"
        
        return state
    
    def _analyze_solar_conditions(self, state: BuildingQueryState) -> BuildingQueryState:
        """Node 2: Analyze solar conditions based on building analysis and query"""
        print("☀️ Query Agent: Analyzing solar conditions...")
        
        try:
            messages = [
                SystemMessage(content="""You are a building physics and solar analysis expert specializing in tropical architecture.
                You understand sun paths, building orientation, and shading patterns in Singapore's climate.
                Provide accurate, practical advice about solar exposure and shading."""),
                HumanMessage(content=f"""Based on the building analysis and query, analyze the solar conditions:

Building Analysis:
{state.building_analysis}

Query: {state.query}

Extracted Parameters:
- Location: {state.location}
- Building Side: {state.building_side}
- Season: {state.season}
- Time of Day: {state.time_of_day}

Please analyze:
1. Sun position and angle for {state.season} {state.time_of_day} in {state.location}
2. Building orientation and shading potential on the {state.building_side} side
3. Likelihood of avoiding direct sun exposure
4. Confidence level (0-100%) in your assessment
5. Practical recommendations

Consider Singapore's tropical climate:
- Winter: December-February (sun lower in south)
- Summer: June-August (sun higher overhead)
- Afternoon sun: typically from west/southwest
- Building features like overhangs, balconies, neighboring structures""")
            ]
            
            response = self._invoke_with_logging("Query Solar Analysis", messages)
            
            # Parse response for confidence score
            response_text = response.content
            confidence_match = None
            confidence_patterns = [
                r'confidence.*?(\d+)%',
                r'(\d+)%.*confidence',
                r'certainty.*?(\d+)%',
                r'(\d+)%.*certain'
            ]
            
            for pattern in confidence_patterns:
                match = re.search(pattern, response_text.lower())
                if match:
                    confidence_match = match
                    break
            
            if confidence_match:
                state.confidence_score = float(confidence_match.group(1)) / 100.0
            else:
                state.confidence_score = 0.7  # Default moderate confidence
            
            state.reasoning = response_text
            state.stage = "solar_analyzed"
            print(f"✅ Query Agent: Solar analysis completed (confidence: {state.confidence_score:.1%})")
            
        except Exception as e:
            state.error_message = f"Solar analysis failed: {str(e)}"
        
        return state
    
    def _generate_response(self, state: BuildingQueryState) -> BuildingQueryState:
        """Node 3: Generate final user-friendly response"""
        print("📝 Query Agent: Generating response...")
        
        try:
            messages = [
                SystemMessage(content="""You are a helpful building consultant providing clear, practical advice.
                Generate a concise, user-friendly response that directly answers the user's question.
                Be specific about recommendations and include confidence level."""),
                HumanMessage(content=f"""Generate a clear, direct response to this query:

Original Query: {state.query}

Analysis Results:
{state.reasoning}

Confidence Score: {state.confidence_score:.1%}

Please provide:
1. Direct answer (Yes/No with explanation)
2. Key factors affecting the outcome
3. Practical recommendations
4. Confidence level statement

Keep the response conversational but informative, around 3-4 sentences.""")
            ]
            
            response = self._invoke_with_logging("Query Response Generation", messages)
            state.query_response = response.content
            state.stage = "complete"
            print("✅ Query Agent: Response generated successfully")
            
        except Exception as e:
            state.error_message = f"Response generation failed: {str(e)}"
        
        return state
    
    def _handle_query_error(self, state: BuildingQueryState) -> BuildingQueryState:
        """Error handling node for queries"""
        print(f"❌ Query Agent: Error encountered - {state.error_message}")
        state.stage = "error"
        return state
    
    # Conditional check functions
    def _check_query_status(self, state: BuildingQueryState) -> str:
        return "error" if state.error_message else "success"
    
    def _check_analysis_status(self, state: BuildingQueryState) -> str:
        return "error" if state.error_message else "success"
    
    def answer_query(self, query: str, building_analysis: str) -> Dict[str, Any]:
        """Main method to answer building-related queries"""
        print("🏢 Query Agent: Starting analysis...")
        
        # Initialize state
        initial_state = BuildingQueryState(
            query=query,
            building_analysis=building_analysis
        )
        
        # Execute workflow
        final_state = self.graph.invoke(initial_state)
        
        # Handle both object and dict returns from LangGraph
        if isinstance(final_state, dict):
            stage = final_state.get('stage', 'unknown')
            query_response = final_state.get('query_response', '')
            confidence_score = final_state.get('confidence_score', 0.0)
            reasoning = final_state.get('reasoning', '')
            error_message = final_state.get('error_message', '')
            building_side = final_state.get('building_side', '')
            season = final_state.get('season', '')
            time_of_day = final_state.get('time_of_day', '')
        else:
            stage = final_state.stage
            query_response = final_state.query_response
            confidence_score = final_state.confidence_score
            reasoning = final_state.reasoning
            error_message = final_state.error_message
            building_side = final_state.building_side
            season = final_state.season
            time_of_day = final_state.time_of_day
        
        return {
            "success": stage == "complete",
            "stage": stage,
            "response": query_response,
            "confidence": confidence_score,
            "reasoning": reasoning,
            "parameters": {
                "building_side": building_side,
                "season": season,
                "time_of_day": time_of_day
            },
            "error": error_message
        }

def main():
    """Test Building Query Agent standalone"""
    print("🏢 Testing Building Query Agent (Standalone)")
    print("="*60)
    
    # Initialize Agent
    agent = BuildingQueryAgent(api_key=OPENAI_API_KEY)
    
    # Sample building analysis (for testing)
    sample_analysis = """
    This is a Singapore building with podium-and-tower composition:
    - Podium around 12.5m height with north-south orientation
    - Upper tower around 27-28m height with stepbacks
    - Primary facades face north and south
    - Building features overhangs and parapet elements
    """
    
    # Test queries
    test_queries = [
        "If a person is on the north side of this building, can they avoid the afternoon sun in winter?",
        "Is the west side of the building shaded during summer mornings?",
        "Can someone on the south side avoid direct sunlight in the afternoon during winter?"
    ]
    
    for i, query in enumerate(test_queries, 1):
        print(f"\n--- Test Query {i} ---")
        print(f"Q: {query}")
        
        result = agent.answer_query(query, sample_analysis)
        
        if result['success']:
            print(f"A: {result['response']}")
            print(f"Confidence: {result['confidence']:.1%}")
            print(f"Parameters: {result['parameters']}")
        else:
            print(f"❌ Query failed: {result['error']}")

if __name__ == "__main__":
    main()

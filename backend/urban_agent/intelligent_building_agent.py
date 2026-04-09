"""
Intelligent Building Analysis Agent
Orchestrates multiple solvers based on natural language queries
"""
import os
import json
import time
from typing import Dict, Any, List, Optional, Tuple
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
import glob
import re

try:
    from dateutil import parser as date_parser
except ImportError:  # pragma: no cover
    date_parser = None

import numpy as np
import trimesh
import matplotlib
matplotlib.use("Agg")  # ensure headless rendering
import matplotlib.pyplot as plt
from matplotlib.patches import Rectangle
import meshio
from langchain_openai import ChatOpenAI
from langchain_core.messages import BaseMessage, HumanMessage, SystemMessage
from langchain_core.runnables import RunnableConfig
from langgraph.graph import StateGraph, END

from config import OPENAI_API_KEY, LANGSMITH_API_KEY, LANGSMITH_ENDPOINT, LANGSMITH_PROJECT
from stl_agent import STLAnalysisAgent
from query_agent import BuildingQueryAgent
from wrapper.cfd_solver import CFDSolverAgent, CFDParameters, _default_weather_csv
from wrapper import SolarSolverAgent, SolarParameters
from llm_recorder import LLMRecorder
from weather_client import NEAWeatherClient

SINGAPORE_TZ = timezone(timedelta(hours=8))
DEFAULT_SCENARIO_DATETIME = datetime(1989, 12, 22, 15, 0, tzinfo=SINGAPORE_TZ)


def _configure_langsmith():
    """Ensure LangSmith environment variables are set for tracing."""
    api_key = LANGSMITH_API_KEY if 'LANGSMITH_API_KEY' in globals() else None
    endpoint = LANGSMITH_ENDPOINT if 'LANGSMITH_ENDPOINT' in globals() else None
    project = LANGSMITH_PROJECT if 'LANGSMITH_PROJECT' in globals() else None

    if api_key:
        os.environ.setdefault("LANGCHAIN_TRACING_V2", "true")
        os.environ.setdefault("LANGSMITH_API_KEY", api_key)
        os.environ.setdefault("LANGCHAIN_API_KEY", api_key)
        if endpoint:
            os.environ.setdefault("LANGSMITH_ENDPOINT", endpoint)
            os.environ.setdefault("LANGCHAIN_ENDPOINT", endpoint)
        if project:
            os.environ.setdefault("LANGCHAIN_PROJECT", project)
        else:
            os.environ.setdefault("LANGCHAIN_PROJECT", "IntelligentBuildingAgent")


_configure_langsmith()


@dataclass
class AnalysisRequest:
    """User's analysis request"""
    query: str
    stl_directory: str
    user_parameters: Dict[str, Any] = None


@dataclass
class IntelligentAgentState:
    """State for intelligent agent workflow"""
    request: AnalysisRequest = None
    building_analysis: str = ""
    required_solvers: List[str] = None  # ['geometry', 'cfd', 'solar', 'query']
    solver_parameters: Dict[str, Any] = None
    solver_results: Dict[str, Any] = None
    external_parameters: Dict[str, Any] = None
    weather_snapshot: Dict[str, Any] = None
    final_response: str = ""
    error_message: str = ""
    output_directory: str = ""
    stage: str = "init"  # init -> intent_analysis -> geometry -> solvers -> integration -> complete
    llm_log_file: str = ""
    llm_text_log_file: str = ""
    runnable_config: Optional[RunnableConfig] = None
    resolved_time: Optional[str] = None


class IntelligentBuildingAgent:
    """
    Intelligent agent that understands user queries and automatically 
    calls appropriate solvers (CFD, Solar, Geometry analysis)
    """
    
    def __init__(self, api_key: str, config_file: Optional[str] = None, 
                 allow_llm_params: bool = True):
        self.llm = ChatOpenAI(
            api_key=api_key,
            model="gpt-5.1",
            temperature=0.1,
            service_tier="priority"
        )
        
        self.llm_recorder = LLMRecorder()
        
        # Initialize solver agents
        self.stl_agent = STLAnalysisAgent(api_key=api_key, recorder=self.llm_recorder)
        self.query_agent = BuildingQueryAgent(api_key=api_key, recorder=self.llm_recorder)
        self.cfd_agent = CFDSolverAgent()
        self.solar_agent = SolarSolverAgent()
        self.weather_client = NEAWeatherClient()
        
        # Load configuration from JSON file if provided
        self.config_file = config_file
        self.solver_config = self._load_config() if config_file else {}
        
        # Control whether LLM can suggest/modify parameters
        self.allow_llm_params = allow_llm_params
        if not allow_llm_params:
            print("🚫 LLM parameter modification is DISABLED")
            print("   Will use only JSON config + user parameters")
        
        self.graph = self._build_graph()
    
    def _load_config(self) -> Dict[str, Any]:
        """Load solver parameters from JSON configuration file"""
        try:
            with open(self.config_file, 'r', encoding='utf-8') as f:
                config = json.load(f)
            print(f"✅ Loaded configuration from: {self.config_file}")
            return config
        except FileNotFoundError:
            print(f"⚠️  Configuration file not found: {self.config_file}")
            return {}
        except json.JSONDecodeError as e:
            print(f"⚠️  Invalid JSON in configuration file: {e}")
            return {}
        except Exception as e:
            print(f"⚠️  Error loading configuration: {e}")
            return {}
    
    def _save_parameters_json(self, params: Dict[str, Any], filename: str, output_dir: str):
        """Save parameters to JSON file for review"""
        try:
            os.makedirs(output_dir, exist_ok=True)
            filepath = os.path.join(output_dir, filename)
            with open(filepath, 'w', encoding='utf-8') as f:
                json.dump(params, f, indent=2, ensure_ascii=False)
            print(f"   💾 Saved parameters to: {filepath}")
            return filepath
        except Exception as e:
            print(f"   ⚠️  Failed to save parameters: {e}")
            return None

    def _parse_datetime_string(self, value: Optional[str]) -> Optional[datetime]:
        if not value or not isinstance(value, str):
            return None
        cleaned = value.strip()
        if not cleaned:
            return None
        dt = None
        try:
            dt = datetime.fromisoformat(cleaned.replace("Z", "+00:00"))
        except ValueError:
            pass
        if not dt and date_parser:
            try:
                dt = date_parser.parse(cleaned)
            except Exception:
                dt = None
        if not dt:
            match = re.search(r"(\d{4}-\d{2}-\d{2})(?:[ T](\d{2}:\d{2}))?", cleaned)
            if match:
                date_part = match.group(1)
                time_part = match.group(2) or "00:00"
                try:
                    dt = datetime.fromisoformat(f"{date_part}T{time_part}:00")
                except ValueError:
                    dt = None
        if dt:
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=SINGAPORE_TZ)
            else:
                dt = dt.astimezone(SINGAPORE_TZ)
        return dt

    def _extract_datetime_from_query(self, query: str) -> Optional[datetime]:
        if not query:
            return None
        if date_parser and re.search(r"\d{4}", query):
            try:
                dt = date_parser.parse(query, fuzzy=True)
                if dt:
                    if dt.tzinfo is None:
                        dt = dt.replace(tzinfo=SINGAPORE_TZ)
                    else:
                        dt = dt.astimezone(SINGAPORE_TZ)
                    return dt
            except Exception:
                return None
        match = re.search(
            r"(\d{4})[/-](\d{1,2})[/-](\d{1,2})(?:[ T](\d{1,2}):(\d{2}))?", query
        )
        if match:
            year, month, day = map(int, match.group(1, 2, 3))
            hour = int(match.group(4)) if match.group(4) else 12
            minute = int(match.group(5)) if match.group(5) else 0
            try:
                return datetime(year, month, day, hour, minute, tzinfo=SINGAPORE_TZ)
            except ValueError:
                return None
        return None

    def _llm_choose_datetime(self, query: str) -> Optional[datetime]:
        if not query:
            return None
        try:
            prompt = f"""The user submitted this building-analysis request:

{query}

Infer the most relevant Singapore local timestamp (YYYY-MM-DD HH:MM) for simulating weather conditions.
Prefer a date/time that matches the described season or scenario. If the query has no temporal cues,
pick a reasonable representative period (e.g., late May afternoon) and still produce a timestamp.

Respond ONLY with JSON in this form:
{{"timestamp": "YYYY-MM-DD HH:MM"}}
"""
            response = self._invoke_llm("Timestamp Selection", [
                SystemMessage(content="You translate natural-language requests into concrete timestamps for Singapore-based environmental simulations."),
                HumanMessage(content=prompt)
            ])
            content = response.content.strip()
            if "```" in content:
                parts = content.split("```")
                for chunk in parts:
                    chunk = chunk.strip()
                    if chunk.startswith("{") and chunk.endswith("}"):
                        content = chunk
                        break
            data = json.loads(content)
            ts = data.get("timestamp")
            if ts:
                dt = self._parse_datetime_string(ts)
                if dt:
                    return dt
        except Exception as e:
            print(f"⚠️ LLM timestamp selection failed: {e}")
        return None

    def _infer_weather_datetime(self, request: AnalysisRequest | None) -> Optional[datetime]:
        # 1. Check user_parameters for explicit timestamp (highest priority)
        if request and request.user_parameters:
            user_ts = request.user_parameters.get("timestamp") or request.user_parameters.get("datetime")
            if user_ts:
                user_dt = self._parse_datetime_string(user_ts)
                if user_dt:
                    print(f"   📅 Using user-specified timestamp: {user_dt.isoformat()}")
                    return user_dt

        # 2. Try to parse datetime from query text
        query_text = request.query if request else ""
        query_dt = self._extract_datetime_from_query(query_text)
        if query_dt:
            print(f"   📅 Parsed timestamp from query: {query_dt.isoformat()}")
            return query_dt

        # 3. Use LLM to infer timestamp from query context
        llm_dt = self._llm_choose_datetime(query_text)
        if llm_dt:
            print(f"   📅 LLM selected timestamp: {llm_dt.isoformat()}")
            return llm_dt

        print(f"   📅 Falling back to default scenario timestamp: {DEFAULT_SCENARIO_DATETIME.isoformat()}")
        return DEFAULT_SCENARIO_DATETIME

    @staticmethod
    def _extract_target_coordinates(state: IntelligentAgentState) -> Tuple[Optional[float], Optional[float]]:
        params = state.request.user_parameters or {}
        location = params.get("location") or {}

        lat_candidates = [
            params.get("latitude"),
            params.get("lat"),
            location.get("latitude"),
            location.get("lat"),
        ]
        lon_candidates = [
            params.get("longitude"),
            params.get("lon"),
            location.get("longitude"),
            location.get("lon"),
        ]

        def _first_valid(candidates):
            for value in candidates:
                if value is None:
                    continue
                try:
                    return float(value)
                except (TypeError, ValueError):
                    continue
            return None

        return _first_valid(lat_candidates), _first_valid(lon_candidates)
    
    def _apply_external_weather_data(self, state: IntelligentAgentState):
        """Fetch live weather data and store derived solver parameters."""
        if not self.weather_client:
            return None
        try:
            start_time = time.time()
            target_dt = self._parse_datetime_string(state.resolved_time) if state.resolved_time else DEFAULT_SCENARIO_DATETIME
            user_lat, user_lon = self._extract_target_coordinates(state)
            snapshot = self.weather_client.fetch_weather_snapshot(target_dt)
            if not snapshot:
                return None
            derived = self.weather_client.build_solver_parameters(
                snapshot, target_lat=user_lat, target_lon=user_lon
            )
            derived = derived or {}
            ext_time = (
                derived.get("time")
                or (snapshot.get("requested_time_sgt"))
                or (snapshot.get("measurements") or {}).get("timestamp_local")
            )
            if ext_time:
                derived.setdefault("time", ext_time)
            state.external_parameters = derived
            state.weather_snapshot = snapshot
            elapsed = time.time() - start_time
            payload = {
                "source": "NEA Realtime Weather Readings",
                "requested_time": snapshot.get("requested_time_sgt") or (target_dt.isoformat() if target_dt else None),
                "snapshot": snapshot,
                "derived_solver_parameters": derived,
                "target_coordinates": {
                    "latitude": user_lat,
                    "longitude": user_lon,
                },
            }
            if state.output_directory:
                self._save_parameters_json(
                    payload,
                    "external_weather_snapshot.json",
                    state.output_directory,
                )
            if self.llm_recorder:
                self.llm_recorder.record(
                    stage="External Weather Data",
                    prompt=json.dumps(
                        {
                            "metadata_url": self.weather_client.METADATA_URL.format(
                                collection_id=self.weather_client.COLLECTION_ID
                            ),
                            "dataset_endpoints": self.weather_client.DATASET_ENDPOINTS,
                        },
                        ensure_ascii=False,
                    ),
                    response=json.dumps(payload, ensure_ascii=False)[:2000],
                    elapsed_time=elapsed,
                    metadata={"agent": "weather_client"},
                )
            else:
                print("   🌤️ Live weather data applied from NEA API")
            return snapshot
        except Exception as e:
            print(f"⚠️ Live weather fetch failed: {e}")
            return None
    
    def _build_graph(self) -> StateGraph:
        """Build LangGraph workflow"""
        workflow = StateGraph(IntelligentAgentState)
        
        # Add nodes
        workflow.add_node("intent_analyzer", self._analyze_intent)
        workflow.add_node("geometry_analyzer", self._run_geometry_analysis)
        workflow.add_node("solver_orchestrator", self._run_solvers)
        workflow.add_node("result_integrator", self._integrate_results)
        workflow.add_node("error_handler", self._handle_error)
        
        # Set entry point
        workflow.set_entry_point("intent_analyzer")
        
        # Add edges
        workflow.add_conditional_edges(
            "intent_analyzer",
            self._check_intent_status,
            {
                "success": "geometry_analyzer",
                "error": "error_handler"
            }
        )
        
        workflow.add_conditional_edges(
            "geometry_analyzer",
            self._check_geometry_status,
            {
                "success": "solver_orchestrator",
                "error": "error_handler"
            }
        )
        
        workflow.add_conditional_edges(
            "solver_orchestrator",
            self._check_solver_status,
            {
                "success": "result_integrator",
                "skip": "result_integrator",
                "error": "error_handler"
            }
        )
        
        workflow.add_edge("result_integrator", END)
        workflow.add_edge("error_handler", END)
        
        return workflow.compile()

    @staticmethod
    def _clean_mesh(mesh: trimesh.Trimesh, min_height: float = 1e-6) -> None:
        """Remove degenerate faces using the new trimesh API, with fallback."""
        mesh.remove_unreferenced_vertices()
        if hasattr(mesh, "nondegenerate_faces"):
            mask = mesh.nondegenerate_faces(height=min_height)
            mesh.update_faces(mask)
        else:  # pragma: no cover - legacy fallback
            mesh.remove_degenerate_faces()
        mesh.remove_unreferenced_vertices()

    @staticmethod
    def _generate_topview_with_ids(
        footprints: List[Tuple[float, float, float, float, float, float, str]],
        output_path: str,
        title: str = "Top View with Building IDs"
    ) -> None:
        """Render a simple top-view plot with building ID labels."""
        if not footprints:
            return

        min_x = min(f[0] for f in footprints)
        min_y = min(f[1] for f in footprints)
        max_x = max(f[2] for f in footprints)
        max_y = max(f[3] for f in footprints)
        margin_x = max(1.0, 0.05 * (max_x - min_x))
        margin_y = max(1.0, 0.05 * (max_y - min_y))

        fig, ax = plt.subplots(figsize=(48, 48))
        ax.set_aspect("equal", adjustable="box")
        ax.set_xlim(min_x - margin_x, max_x + margin_x)
        ax.set_ylim(min_y - margin_y, max_y + margin_y)
        ax.set_title(title, fontsize=36, weight="bold")
        ax.set_xlabel("X (m)", fontsize=24)
        ax.set_ylabel("Y (m)", fontsize=24)
        ax.tick_params(axis="both", labelsize=18)

        for minx, miny, maxx, maxy, cx, cy, bid in footprints:
            width = maxx - minx
            height = maxy - miny
            rect = Rectangle(
                (minx, miny),
                width,
                height,
                linewidth=2.0,
                edgecolor="steelblue",
                facecolor="lightblue",
                alpha=0.35,
            )
            ax.add_patch(rect)
            ax.text(
                cx,
                cy,
                bid,
                ha="center",
                va="center",
                fontsize=48,
                color="darkblue",
                weight="bold",
            )

        ax.grid(True, linestyle="--", linewidth=0.3, alpha=0.5)
        ax.tick_params(axis='both', labelsize=10)
        plt.tight_layout()
        fig.savefig(output_path, dpi=200)
        plt.close(fig)

    @staticmethod
    def _assign_building_id(footprints: List[Dict[str, float]], x: float, y: float) -> Optional[str]:
        """Return building id if point lies within footprint; else nearest by centroid."""
        inside_ids = [
            fp["id"] for fp in footprints
            if fp["minx"] <= x <= fp["maxx"] and fp["miny"] <= y <= fp["maxy"]
        ]
        if inside_ids:
            return inside_ids[0]
        if not footprints:
            return None
        # nearest centroid
        dists = [
            ((fp["cx"] - x) ** 2 + (fp["cy"] - y) ** 2, fp["id"])
            for fp in footprints
        ]
        dists.sort()
        return dists[0][1]

    def _summarize_scalar_timeseries(
        self,
        vtk_dir: str,
        prefix: str,
        footprints: List[Dict[str, float]],
        label: str
    ) -> List[Dict[str, Any]]:
        """Compute per-timestamp maxima for a scalar field (e.g., PET/MRT) with optional building lookup."""
        summaries: List[Dict[str, Any]] = []
        pattern = os.path.join(vtk_dir, f"{prefix}_*.vtk")
        has_pv = False
        pv_mod = None
        try:
            import pyvista as pv  # type: ignore
            has_pv = True
            pv_mod = pv
        except Exception:
            has_pv = False
            pv_mod = None

        for vtk_path in sorted(glob.glob(pattern)):
            ts_token = Path(vtk_path).stem.split("_")[-1]
            try:
                arr = None
                pts = None

                # Try pyvista first if available (handles POLYDATA)
                if has_pv and pv_mod:
                    try:
                        pvmesh = pv_mod.read(vtk_path)
                        if pvmesh.point_data:
                            first_key = list(pvmesh.point_data.keys())[0]
                            arr = np.asarray(pvmesh.point_data[first_key])
                            pts = np.asarray(pvmesh.points)
                        elif pvmesh.cell_data:
                            first_key = list(pvmesh.cell_data.keys())[0]
                            arr = np.asarray(pvmesh.cell_data[first_key])
                            pts = np.asarray(pvmesh.cell_centers().points)
                    except BaseException:
                        arr = None
                        pts = None

                # Fallback to meshio for standard VTK grids
                if arr is None or pts is None:
                    try:
                        mesh = meshio.read(vtk_path)
                        arrays = list(mesh.point_data.values())
                        if arrays:
                            arr = np.asarray(arrays[0])
                            pts = np.asarray(mesh.points)
                        else:
                            # Try cell data
                            cd = mesh.cell_data_dict
                            if cd:
                                first_block = next(iter(cd.values()))
                                if first_block:
                                    first_name = next(iter(first_block.keys()))
                                    arr_vals = first_block[first_name]
                                    arr = np.asarray(arr_vals[0])
                                    # Compute crude cell centers
                                    cells = mesh.cells[0].data
                                    pts_all = np.asarray(mesh.points)
                                    centers = []
                                    for cell in cells:
                                        centers.append(np.mean(pts_all[cell], axis=0))
                                    pts = np.asarray(centers)
                    except BaseException:
                        arr = None
                        pts = None

                if arr is None or pts is None or arr.size == 0 or pts.size == 0:
                    continue

                idx = int(np.argmax(arr))
                max_val = float(arr[idx])
                pt = pts[idx]
                bid = self._assign_building_id(footprints, float(pt[0]), float(pt[1]))
                summaries.append({
                    "time_token": ts_token,
                    "max_value": max_val,
                    "location": [float(pt[0]), float(pt[1]), float(pt[2])],
                    "building_id": bid,
                    "file": vtk_path,
                    "field": label,
                })
            except Exception as e:
                print(f"⚠️ Failed to summarize {vtk_path}: {e}")
                continue
        return summaries

    @staticmethod
    def _bucket_time_summary(summaries: List[Dict[str, Any]]) -> Dict[str, Optional[Dict[str, Any]]]:
        """
        Bucket time summaries into morning / noon / afternoon / evening using time_token (HHMM).
        Buckets:
          - morning: 00:00–09:59
          - noon: 12:00
          - afternoon: 15:00
          - evening: 18:00–23:59
        """
        buckets = {
            "morning": None,
            "noon": None,
            "afternoon": None,
            "evening": None,
        }
        for item in summaries:
            token = item.get("time_token", "0000")
            try:
                hh = int(token[:2])
            except Exception:
                hh = 0
            # Determine bucket
            if hh < 10:  # 00, 03, 06, 09
                key = "morning"
            elif hh == 12:
                key = "noon"
            elif hh == 15:
                key = "afternoon"
            else:
                key = "evening"  # includes 18, 21, others
            # Keep max within bucket
            if buckets[key] is None or item.get("max_value", -1e9) > buckets[key].get("max_value", -1e9):
                buckets[key] = item
        return buckets
    
    def _invoke_llm(self, stage: str, messages: List[BaseMessage]):
        """Call the LLM and persist prompt/response metadata."""
        start = time.time()
        response = self.llm.invoke(messages)
        if self.llm_recorder:
            prompt_text = "\n\n".join(
                f"{msg.__class__.__name__}: {getattr(msg, 'content', '')}" for msg in messages
            )
            self.llm_recorder.record(
                stage=stage,
                prompt=prompt_text,
                response=response.content,
                elapsed_time=time.time() - start,
                metadata={"agent": "intelligent_building_agent"},
            )
        return response
    
    @staticmethod
    def _sanitize_solver_result(result: Dict[str, Any]) -> Dict[str, Any]:
        """Convert solver payloads into JSON-friendly structures."""
        drop_keys = {
            "dataframe",
            "building_dataframe",
            "surface_snapshot",
            "building_summary",
            # Large file listings / artifacts that bloat prompts
            "visualization_files",
            "vtk_files",
            "data_files",
            "log_files",
            "all_files",
        }
        sanitized: Dict[str, Any] = {}
        for key, value in result.items():
            if key in drop_keys:
                continue
            if isinstance(value, (str, int, float, bool)) or value is None:
                sanitized[key] = value
            elif isinstance(value, (list, dict)):
                sanitized[key] = value
            else:
                sanitized[key] = str(value)
        return sanitized
    
    def _analyze_intent(self, state: IntelligentAgentState) -> IntelligentAgentState:
        """Analyze user intent and determine required solvers"""
        print("🤔 Analyzing user intent...")
        
        try:
            import re

            prompt = f"""Analyze this building analysis request and determine what solvers are needed.

User Query: "{state.request.query}"

Available Solvers:
1. geometry - Basic STL geometry analysis (always required first)
2. cfd - Wind flow, temperature, and humidity simulation
3. solar - Solar irradiance, shading, and Sky View Factor analysis
4. query - Answer specific questions about building orientation and solar conditions

For each solver, determine:
1. Is it needed for this query?
2. What parameters should be used?

Consider these keywords:
- Wind, ventilation, airflow, thermal comfort → cfd
- Sun, solar, shading, irradiance, daylight → solar
- Specific questions about building sides and sun avoidance → query
- General building analysis → geometry only

Return JSON format:
{{
    "required_solvers": ["geometry", "cfd", ...],
    "parameters": {{
        "cfd": {{"wind_speed": 1.5, "wind_direction": 45, ...}},
        "solar": {{"time": "2025-12-21 14:00:00+08:00", "DNI": 800, ...}},
        "query": {{"specific_question": "..."}}
    }},
    "reasoning": "Why these solvers are needed..."
}}
"""
            
            response = self._invoke_llm("Intent Analysis", [
                SystemMessage(content="You are an expert in building performance analysis."),
                HumanMessage(content=prompt)
            ])
            
            # Parse response
            content = response.content
            if "```json" in content:
                content = content.split("```json")[1].split("```")[0]
            elif "```" in content:
                content = content.split("```")[1].split("```")[0]
            
            def _sanitize_intent_json(txt: str) -> str:
                # Fix common LLM mishap: dates: [ "design_summer": {...} ] -> dates: {"design_summer": {...}}
                pattern = r'"dates"\s*:\s*\[\s*"design_summer"\s*:\s*\{(.*?)\}\s*\]'
                return re.sub(pattern, r'"dates": {"design_summer": {\1}}', txt, flags=re.S)

            try:
                try:
                    result = json.loads(content.strip())
                except json.JSONDecodeError:
                    content_fixed = _sanitize_intent_json(content.strip())
                    result = json.loads(content_fixed)
            except Exception as e:
                # Robust fallback: if intent JSON is malformed, use default solvers
                print(f"⚠️ Intent JSON parse failed ({e}); using default solvers geometry+cfd+solar.")
                result = {
                    "required_solvers": ["geometry", "cfd", "solar"],
                    "parameters": {}
                }
            
            state.required_solvers = result.get("required_solvers", ["geometry"])
            state.solver_parameters = result.get("parameters", {})
            state.stage = "intent_analyzed"

            print(f"✅ Intent analyzed:")
            print(f"   Required solvers: {', '.join(state.required_solvers)}")
            print(f"   Reasoning: {result.get('reasoning', 'N/A')[:100]}...")
            
            self._apply_external_weather_data(state)
            
            # Save LLM-suggested parameters for review
            if state.solver_parameters and state.output_directory:
                llm_params = {
                    "source": "LLM Analysis",
                    "timestamp": datetime.now().isoformat(),
                    "query": state.request.query,
                    "reasoning": result.get('reasoning', 'N/A'),
                    "required_solvers": state.required_solvers,
                    "parameters": state.solver_parameters
                }
                self._save_parameters_json(
                    llm_params, 
                    "llm_suggested_parameters.json",
                    state.output_directory
                )
            
        except Exception as e:
            print(f"❌ Intent analysis failed: {e}")
            state.error_message = f"Intent analysis error: {e}"
            state.stage = "error"
        
        return state
    
    def _run_geometry_analysis(self, state: IntelligentAgentState) -> IntelligentAgentState:
        """Run basic geometry analysis (always required)"""
        print("🏗️ Running geometry analysis...")
        
        try:
            output_dir = state.output_directory or os.path.join(
                os.path.dirname(state.request.stl_directory), "results"
            )
            os.makedirs(output_dir, exist_ok=True)

            # Optional fast path: reuse prior geometry artifacts to avoid duplicate viz/LLM calls
            reuse_dir = (state.request.user_parameters or {}).get("reuse_geometry_from")
            if reuse_dir:
                cache_path = os.path.join(reuse_dir, "geometry_cache.json")
                try:
                    with open(cache_path, "r", encoding="utf-8") as f:
                        cache = json.load(f)
                    cached_result = cache.get("solver_result") or cache.get("solver_results")
                    if cached_result and cached_result.get("success"):
                        state.solver_results = state.solver_results or {}
                        state.solver_results["geometry"] = cached_result
                        state.building_analysis = cache.get("building_analysis", state.building_analysis)
                        state.stage = "geometry_analyzed"
                        print(f"♻️ Reused geometry results from {cache_path}")
                        return state
                    else:
                        print(f"ℹ️ geometry_cache.json found but invalid; rerunning geometry")
                except FileNotFoundError:
                    print(f"ℹ️ No geometry_cache.json in {reuse_dir}; running geometry")
                except Exception as e:
                    print(f"⚠️ Failed to reuse geometry from {reuse_dir}: {e}. Running fresh.")

            stl_files = sorted(glob.glob(os.path.join(state.request.stl_directory, "*.stl")))
            if not stl_files:
                state.error_message = "No STL files found in directory"
                state.stage = "error"
                return state

            meshes: List[trimesh.Trimesh] = []
            footprints: List[Tuple[float, float, float, float, float, float, str]] = []
            building_envelopes: List[Dict[str, float]] = []
            for stl_path in stl_files:
                mesh = trimesh.load(stl_path, force="mesh")
                bid = Path(stl_path).stem.split("_")[0]
                if isinstance(mesh, trimesh.Trimesh):
                    self._clean_mesh(mesh)
                    meshes.append(mesh)
                    bounds = mesh.bounds
                    minx, miny, minz = bounds[0]
                    maxx, maxy, maxz = bounds[1]
                    cx = (minx + maxx) / 2
                    cy = (miny + maxy) / 2
                    footprints.append((minx, miny, maxx, maxy, cx, cy, bid))
                    dx = maxx - minx
                    dy = maxy - miny
                    dz = maxz - minz
                    roof_area = max(dx, 0.0) * max(dy, 0.0)
                    wall_area = 2.0 * (max(dx, 0.0) + max(dy, 0.0)) * max(dz, 0.0)
                    building_envelopes.append({
                        "id": bid,
                        "dx": float(dx),
                        "dy": float(dy),
                        "height": float(dz),
                        "roof_area": float(roof_area),
                        "wall_area": float(wall_area),
                        "envelope_area": float(roof_area + wall_area),
                    })
                elif isinstance(mesh, trimesh.Scene):
                    parts = [g for g in mesh.dump(concatenate=True)]
                    for part in parts:
                        self._clean_mesh(part)
                        meshes.append(part)
                        bounds = part.bounds
                        minx, miny, minz = bounds[0]
                        maxx, maxy, maxz = bounds[1]
                        cx = (minx + maxx) / 2
                        cy = (miny + maxy) / 2
                        footprints.append((minx, miny, maxx, maxy, cx, cy, bid))
                        dx = maxx - minx
                        dy = maxy - miny
                        dz = maxz - minz
                        roof_area = max(dx, 0.0) * max(dy, 0.0)
                        wall_area = 2.0 * (max(dx, 0.0) + max(dy, 0.0)) * max(dz, 0.0)
                        building_envelopes.append({
                            "id": bid,
                            "dx": float(dx),
                            "dy": float(dy),
                            "height": float(dz),
                            "roof_area": float(roof_area),
                            "wall_area": float(wall_area),
                            "envelope_area": float(roof_area + wall_area),
                        })

            if not meshes:
                state.error_message = "Unable to load STL meshes for geometry analysis"
                state.stage = "error"
                return state

            combined_mesh = trimesh.util.concatenate(meshes)
            combined_mesh.remove_unreferenced_vertices()

            combined_path = os.path.join(output_dir, "combined_geometry.stl")
            combined_mesh.export(combined_path)

            viz_path = os.path.join(output_dir, "geometry_overview.png")
            run_config = getattr(state, "runnable_config", None)
            result = self.stl_agent.analyze_stl(combined_path, viz_path, config=run_config)

            topview_path = os.path.join(output_dir, "geometry_topview_ids.png")
            try:
                if footprints:
                    self._generate_topview_with_ids(
                        footprints,
                        topview_path,
                        title="Top View with Building IDs"
                    )
                    print(f"✅ Generated top view with IDs: {topview_path}")
            except Exception as e:
                print(f"⚠️ Failed to generate top view with IDs: {e}")

            if result["success"]:
                bounds = combined_mesh.bounds
                extents = bounds[1] - bounds[0]
                centroid = combined_mesh.centroid
                stats_summary = (
                    "District geometry summary:\n"
                    f"- Buildings analysed: {len(stl_files)}\n"
                    f"- Site bounds min (m): {np.round(bounds[0], 2).tolist()}\n"
                    f"- Site bounds max (m): {np.round(bounds[1], 2).tolist()}\n"
                    f"- Plan extents (Δx, Δy) m: {np.round(extents[:2], 2).tolist()}\n"
                    f"- Height range (m): {round(bounds[0][2], 2)} – {round(bounds[1][2], 2)}\n"
                    f"- Combined centroid (m): {np.round(centroid, 2).tolist()}"
                )

                state.building_analysis = f"{stats_summary}\n\nLLM insights:\n{result['analysis']}"
                state.stage = "geometry_analyzed"
                state.solver_results = state.solver_results or {}
                state.solver_results["geometry"] = {
                    "success": True,
                    "output_file": combined_path,
                    "visualization_file": result.get("output_path"),
                    "topview_file": topview_path if os.path.exists(topview_path) else None,
                    "footprints": [
                        {
                            "id": fp[6],
                            "minx": fp[0],
                            "miny": fp[1],
                            "maxx": fp[2],
                            "maxy": fp[3],
                            "cx": fp[4],
                            "cy": fp[5],
                        }
                        for fp in footprints
                    ],
                    "building_envelopes": building_envelopes,
                    "statistics": {
                        "building_count": len(stl_files),
                        "bounds_min": bounds[0].tolist(),
                        "bounds_max": bounds[1].tolist(),
                        "extent": extents.tolist(),
                        "centroid": centroid.tolist(),
                    },
                }
                cache_path = os.path.join(output_dir, "geometry_cache.json")
                try:
                    with open(cache_path, "w", encoding="utf-8") as f:
                        json.dump(
                            {
                                "solver_result": state.solver_results["geometry"],
                                "building_analysis": state.building_analysis,
                            },
                            f,
                            indent=2,
                            ensure_ascii=False,
                        )
                    print(f"🗄️ Cached geometry to {cache_path}")
                except Exception as e:
                    print(f"⚠️ Failed to write geometry cache: {e}")
                print("✅ Geometry analysis complete")
            else:
                state.error_message = result["error"]
                state.stage = "error"
                
        except Exception as e:
            print(f"❌ Geometry analysis failed: {e}")
            state.error_message = f"Geometry analysis error: {e}"
            state.stage = "error"
        
        return state
    
    def _run_solvers(self, state: IntelligentAgentState) -> IntelligentAgentState:
        """Run required physics solvers (CFD, Solar)"""
        print("⚙️ Running physics solvers...")
        
        state.solver_results = state.solver_results or {}
        resolved_time = state.resolved_time
        
        try:
            # Run CFD solver if needed
            if "cfd" in state.required_solvers:
                print("\n🌬️ Running CFD simulation...")
                # Priority: JSON config < LLM parameters < user parameters
                cfd_params_dict = {}
                
                # 1. Load from JSON config file
                if self.solver_config.get("cfd"):
                    cfd_params_dict.update(self.solver_config["cfd"])
                    # IWEC-first: do not pre-fill wind from JSON so that the solver falls back to IWEC CSV.
                    cfd_params_dict.pop("wind_speed", None)
                    cfd_params_dict.pop("wind_direction", None)
                    print(f"   📄 Loaded CFD params from config (wind left for IWEC): {self.config_file}")
                
                # Prefer IWEC; allow NEA only if IWEC/config did not set the field
                if state.external_parameters and state.external_parameters.get("cfd"):
                    ext_cfd = state.external_parameters.get("cfd", {})
                    for key, val in ext_cfd.items():
                        if key in ("wind_speed", "wind_direction", "temperature", "humidity"):
                            if cfd_params_dict.get(key) is None:
                                cfd_params_dict[key] = val
                        else:
                            cfd_params_dict[key] = val
                    print(f"   🌤️ Applied live weather CFD params (NEA) only where IWEC/config missing")
                
                user_cfd_params = (state.request.user_parameters or {}).get("cfd", {})
                user_set_wind = any(k in user_cfd_params for k in ("wind_speed", "wind_direction"))
                user_set_temp = "temperature" in user_cfd_params
                user_set_rh = "humidity" in user_cfd_params
                user_set_met_all = user_set_wind and user_set_temp and user_set_rh

                if self.allow_llm_params and state.solver_parameters.get("cfd"):
                    llm_cfd = state.solver_parameters.get("cfd", {})
                    for key, val in llm_cfd.items():
                        if key in ("wind_speed", "wind_direction", "temperature", "humidity"):
                            # Use LLM met suggestions only if still missing
                            if cfd_params_dict.get(key) is None:
                                cfd_params_dict[key] = val
                        else:
                            cfd_params_dict[key] = val
                    print(f"   🤖 Merged LLM-suggested CFD params (met fields only if missing)")
                elif not self.allow_llm_params:
                    print(f"   🚫 Skipped LLM parameter suggestions (disabled)")
                
                # 3. Merge with user parameters (highest priority)
                if state.request.user_parameters:
                    cfd_params_dict.update(user_cfd_params)
                    print(f"   👤 Merged user-provided CFD params")

                # 4. Material/property overrides (optional, user- or pipeline-provided)
                material_overrides = (state.request.user_parameters or {}).get("materials", {})
                material_key_map = {
                    "albedo_ground": "rad_albedo_ground",
                    "albedo_wall": "rad_albedo_wall",
                    "albedo_roof": "rad_albedo_roof",
                    "emissivity_ground": "rad_emissivity_ground",
                    "emissivity_wall": "rad_emissivity_wall",
                    "emissivity_roof": "rad_emissivity_roof",
                    "thickness_ground": "rad_thickness_ground",
                    "thickness_wall": "rad_thickness_wall",
                    "thickness_roof": "rad_thickness_roof",
                    "c_face_ground": "rad_C_face_ground",
                    "c_face_wall": "rad_C_face_wall",
                    "c_face_roof": "rad_C_face_roof",
                    "k_ground": "rad_k_ground",
                    "k_wall": "rad_k_wall",
                    "k_roof": "rad_k_roof",
                    "rho_ground": "rad_rho_ground",
                    "rho_wall": "rad_rho_wall",
                    "rho_roof": "rad_rho_roof",
                    "cp_ground": "rad_cp_ground",
                    "cp_wall": "rad_cp_wall",
                    "cp_roof": "rad_cp_roof",
                    "k_concrete": "be_concrete_k",
                    "rho_concrete": "be_concrete_rho",
                    "cp_concrete": "be_concrete_cp",
                    "thickness_concrete": "be_concrete_l",
                }
                for short_key, long_key in material_key_map.items():
                    if short_key in material_overrides:
                        cfd_params_dict[long_key] = material_overrides[short_key]
                if material_overrides:
                    print(f"   🧱 Applied material overrides: {list(material_overrides.keys())}")

                # If the user did not explicitly set meteorology, clear overrides so IWEC time series is used
                if not user_set_met_all:
                    if "wind_speed" in cfd_params_dict:
                        cfd_params_dict["wind_speed"] = None
                    if "wind_direction" in cfd_params_dict:
                        cfd_params_dict["wind_direction"] = None
                    if "temperature" in cfd_params_dict:
                        cfd_params_dict["temperature"] = None
                    if "humidity" in cfd_params_dict:
                        cfd_params_dict["humidity"] = None
                    print("   🌬️🌡️ CFD met overrides cleared (wind/temp/RH from IWEC time series unless user-specified)")

                if resolved_time:
                    cfd_params_dict["simulation_time"] = resolved_time
                    print(f"   ⏱️  Using resolved timestamp for CFD: {resolved_time}")
                
                cfd_defaults = {
                    name: field.default
                    for name, field in CFDParameters.__dataclass_fields__.items()  # type: ignore[attr-defined]
                }
                cfd_output_dir = cfd_params_dict.get(
                    "output_dir",
                    os.path.join(state.output_directory, "cfd_solar") if state.output_directory else None
                )

                cfd_params = CFDParameters(
                    stl_directory=state.request.stl_directory,
                    u_inflow=cfd_params_dict.get(
                        "wind_speed",
                        cfd_defaults["u_inflow"]
                    ),
                    wind_direction_deg=cfd_params_dict.get(
                        "wind_direction",
                        cfd_defaults["wind_direction_deg"]
                    ),
                    z_slice=cfd_params_dict.get(
                        "height",
                        cfd_defaults["z_slice"]
                    ),
                    T2m_C=cfd_params_dict.get(
                        "temperature",
                        cfd_defaults["T2m_C"]
                    ),
                    RH2m_percent=cfd_params_dict.get(
                        "humidity",
                        cfd_defaults["RH2m_percent"]
                    ),
                    voxel_pitch=cfd_params_dict.get(
                        "voxel_pitch",
                        cfd_defaults["voxel_pitch"]
                    ),
                    buffer_ratio=cfd_params_dict.get(
                        "buffer_ratio",
                        cfd_defaults["buffer_ratio"]
                    ),
                    alpha_T=cfd_params_dict.get(
                        "alpha_t",
                        cfd_defaults["alpha_T"]
                    ),
                    alpha_RH=cfd_params_dict.get(
                        "alpha_rh",
                        cfd_defaults["alpha_RH"]
                    ),
                    building_radius=cfd_params_dict.get(
                        "building_radius",
                        cfd_defaults["building_radius"]
                    ),
                    output_dir=cfd_output_dir,
                    simulation_time=cfd_params_dict.get("simulation_time") or cfd_params_dict.get("time"),
                    weather_csv_path=cfd_params_dict.get("weather_csv_path") or cfd_params_dict.get("weather_csv"),
                    dt_hours=cfd_params_dict.get("dt_hours", cfd_defaults["dt_hours"]),
                    vedo_display_mode=cfd_params_dict.get("vedo_display_mode", cfd_defaults["vedo_display_mode"]),
                    cfd_log_z0=cfd_params_dict.get("roughness_length", cfd_defaults["cfd_log_z0"]),
                    work_dir=cfd_params_dict.get("work_dir"),
                    rad_albedo_ground=cfd_params_dict.get("rad_albedo_ground", cfd_defaults["rad_albedo_ground"]),
                    rad_albedo_wall=cfd_params_dict.get("rad_albedo_wall", cfd_defaults["rad_albedo_wall"]),
                    rad_albedo_roof=cfd_params_dict.get("rad_albedo_roof", cfd_defaults["rad_albedo_roof"]),
                    rad_emissivity_ground=cfd_params_dict.get("rad_emissivity_ground", cfd_defaults["rad_emissivity_ground"]),
                    rad_emissivity_wall=cfd_params_dict.get("rad_emissivity_wall", cfd_defaults["rad_emissivity_wall"]),
                    rad_emissivity_roof=cfd_params_dict.get("rad_emissivity_roof", cfd_defaults["rad_emissivity_roof"]),
                    rad_thickness_ground=cfd_params_dict.get("rad_thickness_ground", cfd_defaults["rad_thickness_ground"]),
                    rad_thickness_wall=cfd_params_dict.get("rad_thickness_wall", cfd_defaults["rad_thickness_wall"]),
                    rad_thickness_roof=cfd_params_dict.get("rad_thickness_roof", cfd_defaults["rad_thickness_roof"]),
                    rad_C_face_ground=cfd_params_dict.get("rad_C_face_ground", cfd_defaults["rad_C_face_ground"]),
                    rad_C_face_wall=cfd_params_dict.get("rad_C_face_wall", cfd_defaults["rad_C_face_wall"]),
                    rad_C_face_roof=cfd_params_dict.get("rad_C_face_roof", cfd_defaults["rad_C_face_roof"]),
                    rad_k_ground=cfd_params_dict.get("rad_k_ground", cfd_defaults["rad_k_ground"]),
                    rad_k_wall=cfd_params_dict.get("rad_k_wall", cfd_defaults["rad_k_wall"]),
                    rad_k_roof=cfd_params_dict.get("rad_k_roof", cfd_defaults["rad_k_roof"]),
                    rad_rho_ground=cfd_params_dict.get("rad_rho_ground", cfd_defaults["rad_rho_ground"]),
                    rad_rho_wall=cfd_params_dict.get("rad_rho_wall", cfd_defaults["rad_rho_wall"]),
                    rad_rho_roof=cfd_params_dict.get("rad_rho_roof", cfd_defaults["rad_rho_roof"]),
                    rad_cp_ground=cfd_params_dict.get("rad_cp_ground", cfd_defaults["rad_cp_ground"]),
                    rad_cp_wall=cfd_params_dict.get("rad_cp_wall", cfd_defaults["rad_cp_wall"]),
                    rad_cp_roof=cfd_params_dict.get("rad_cp_roof", cfd_defaults["rad_cp_roof"]),
                    be_concrete_k=cfd_params_dict.get("be_concrete_k", cfd_defaults["be_concrete_k"]),
                    be_concrete_l=cfd_params_dict.get("be_concrete_l", cfd_defaults["be_concrete_l"]),
                    be_concrete_rho=cfd_params_dict.get("be_concrete_rho", cfd_defaults["be_concrete_rho"]),
                    be_concrete_cp=cfd_params_dict.get("be_concrete_cp", cfd_defaults["be_concrete_cp"]),
                )
                
                # Save final CFD parameters used (after all merging)
                if state.output_directory:
                    priority_order = []
                    priority_order.append(f"{len(priority_order)+1}. JSON config file (IWEC baseline)")
                    if state.external_parameters and state.external_parameters.get("cfd"):
                        priority_order.append(f"{len(priority_order)+1}. NEA live weather (override)")
                    if self.allow_llm_params and state.solver_parameters.get("cfd"):
                        priority_order.append(f"{len(priority_order)+1}. LLM suggestions (override)")
                    priority_order.append(f"{len(priority_order)+1}. User parameters (final override)")
                    final_cfd_params = {
                        "source": "Final Merged Parameters",
                        "timestamp": datetime.now().isoformat(),
                        "priority_order": priority_order,
                        "cfd": {
                            "wind_speed": cfd_params.u_inflow,
                            "wind_direction": cfd_params.wind_direction_deg,
                            "height": cfd_params.z_slice,
                            "temperature": cfd_params.T2m_C,
                            "humidity": cfd_params.RH2m_percent,
                            "voxel_pitch": cfd_params.voxel_pitch,
                            "buffer_ratio": cfd_params.buffer_ratio,
                            "alpha_t": cfd_params.alpha_T,
                            "alpha_rh": cfd_params.alpha_RH,
                            "building_radius": cfd_params.building_radius
                        }
                    }
                    self._save_parameters_json(
                        final_cfd_params,
                        "final_cfd_parameters.json",
                        state.output_directory
                    )
                
                cfd_result = self.cfd_agent.run_analysis(cfd_params)
                state.solver_results["cfd"] = cfd_result

                # Summarize PET/MRT maxima over the day, if geometry footprints are available
                footprints = state.solver_results.get("geometry", {}).get("footprints", [])
                vtk_dir = os.path.join(cfd_output_dir, "vtk_files") if cfd_output_dir else None
                if footprints and vtk_dir and os.path.isdir(vtk_dir):
                    pet_summary = self._summarize_scalar_timeseries(vtk_dir, "pet_on_mesh", footprints, "PET")
                    mrt_summary = self._summarize_scalar_timeseries(vtk_dir, "mrt_on_mesh", footprints, "MRT")
                    state.solver_results["cfd"]["pet_time_summary"] = pet_summary
                    state.solver_results["cfd"]["mrt_time_summary"] = mrt_summary
                    # Bucket summaries into morning/noon/afternoon/evening
                    pet_buckets = self._bucket_time_summary(pet_summary)
                    mrt_buckets = self._bucket_time_summary(mrt_summary)
                    state.solver_results["cfd"]["pet_time_buckets"] = pet_buckets
                    state.solver_results["cfd"]["mrt_time_buckets"] = mrt_buckets

                    # Persist to disk for downstream consumption
                    bucket_payload = {
                        "pet_time_summary": pet_summary,
                        "mrt_time_summary": mrt_summary,
                        "pet_time_buckets": pet_buckets,
                        "mrt_time_buckets": mrt_buckets,
                    }
                    if state.output_directory:
                        buckets_json = os.path.join(state.output_directory, "pet_mrt_time_buckets.json")
                        buckets_txt = os.path.join(state.output_directory, "pet_mrt_time_buckets.txt")
                        try:
                            with open(buckets_json, "w", encoding="utf-8") as f:
                                json.dump(bucket_payload, f, indent=2, ensure_ascii=False)
                        except Exception as e:
                            print(f"⚠️ Failed to write {buckets_json}: {e}")
                        try:
                            def fmt_bucket(title: str, bucket: Dict[str, Any]) -> str:
                                if bucket is None:
                                    return f"{title}: (no data)"
                                return (
                                    f"{title}: {bucket.get('max_value')} at {bucket.get('time_token')} "
                                    f"loc={bucket.get('location')} "
                                    f"bid={bucket.get('building_id')} "
                                    f"file={bucket.get('file')}"
                                )
                            lines = []
                            lines.append("PET time buckets:")
                            for k in ("morning", "noon", "afternoon", "evening"):
                                lines.append(fmt_bucket(f"  {k}", pet_buckets.get(k)))
                            lines.append("")
                            lines.append("MRT time buckets:")
                            for k in ("morning", "noon", "afternoon", "evening"):
                                lines.append(fmt_bucket(f"  {k}", mrt_buckets.get(k)))
                            with open(buckets_txt, "w", encoding="utf-8") as f:
                                f.write("\n".join(lines))
                        except Exception as e:
                            print(f"⚠️ Failed to write {buckets_txt}: {e}")
                    print("   🧭 PET/MRT time-series maxima summarized.")
            
            # Run Solar solver if needed
            if "solar" in state.required_solvers:
                # If CFD already executed a coupled run (run_radiation=True), skip duplicate solar pass
                if state.solver_results.get("cfd", {}).get("coupled_run"):
                    print("\n☀️ Skipping solar pass (CFD already ran coupled radiation).")
                    state.solver_results["solar"] = {
                        "success": True,
                        "mode": "skipped",
                        "note": "Solar step skipped because CFD already ran with radiation (coupled run).",
                        "artifacts": state.solver_results["cfd"].get("artifacts", {}),
                        "visualization_files": state.solver_results["cfd"].get("visualization_files", []),
                        "data_files": state.solver_results["cfd"].get("data_files", []),
                        "log_files": state.solver_results["cfd"].get("log_files", []),
                        "all_files": state.solver_results["cfd"].get("all_files", []),
                        "analysis_metrics": state.solver_results["cfd"].get("analysis_metrics"),
                        "analysis_summary_file": state.solver_results["cfd"].get("analysis_summary_file"),
                    }
                else:
                    print("\n☀️ Running solar analysis...")
                    # Priority: JSON config < LLM parameters < user parameters
                    solar_params_dict = {}
                    baseline_dni = None
                    baseline_dhi = None
                    
                    # 1. Load from JSON config file
                    if self.solver_config.get("solar"):
                        solar_params_dict.update(self.solver_config["solar"])
                        print(f"   📄 Loaded Solar params from config: {self.config_file}")
                        baseline_dni = solar_params_dict.get("DNI")
                        baseline_dhi = solar_params_dict.get("DHI")
                    
                    if state.external_parameters and state.external_parameters.get("solar"):
                        solar_params_dict.update(state.external_parameters.get("solar", {}))
                        print(f"   🌤️ Applied live weather Solar params (NEA)")
                    
                    if self.allow_llm_params and state.solver_parameters.get("solar"):
                        solar_params_dict.update(state.solver_parameters.get("solar", {}))
                        print(f"   🤖 Merged LLM-suggested Solar params")
                    elif not self.allow_llm_params:
                        print(f"   🚫 Skipped LLM parameter suggestions (disabled)")
                    
                    # 3. Merge with user parameters (highest priority)
                    if state.request.user_parameters:
                        solar_params_dict.update(state.request.user_parameters.get("solar", {}))
                        print(f"   👤 Merged user-provided Solar params")

                    if resolved_time:
                        solar_params_dict["time"] = resolved_time
                        print(f"   ⏱️  Using resolved timestamp for Solar: {resolved_time}")
                    
                    solar_defaults = {
                        name: field.default
                        for name, field in SolarParameters.__dataclass_fields__.items()  # type: ignore[attr-defined]
                    }
                    
                    # IWEC-first for radiation: lock in IWEC DNI/DHI unless unavailable; allow user to override later
                    if baseline_dni is None:
                        baseline_dni = solar_params_dict.get("DNI") or solar_defaults["dni_peak"]
                    if baseline_dhi is None:
                        baseline_dhi = solar_params_dict.get("DHI") or solar_defaults["dhi_peak"]
                    if baseline_dni is not None:
                        solar_params_dict["DNI"] = baseline_dni
                    if baseline_dhi is not None:
                        solar_params_dict["DHI"] = baseline_dhi

                    # Default IWEC weather file unless user explicitly overrides
                    if not solar_params_dict.get("weather_csv_path") and not solar_params_dict.get("weather_csv"):
                        solar_params_dict["weather_csv_path"] = str(_default_weather_csv())

                    solar_output_dir = solar_params_dict.get(
                        "output_dir",
                        os.path.join(state.output_directory, "solar") if state.output_directory else None
                    )
                    solar_work_dir = solar_params_dict.get(
                        "work_dir",
                        os.path.join(state.output_directory, "solar_cache") if state.output_directory else None
                    )

                    solar_params = SolarParameters(
                        stl_directory=state.request.stl_directory,
                        time_str=solar_params_dict.get(
                            "time",
                            solar_defaults["time_str"]
                        ),
                        latitude=solar_params_dict.get(
                            "latitude",
                            solar_defaults["latitude"]
                        ),
                        longitude=solar_params_dict.get(
                            "longitude",
                            solar_defaults["longitude"]
                        ),
                        elevation=solar_params_dict.get(
                            "elevation",
                            solar_defaults["elevation"]
                        ),
                        dni_peak=solar_params_dict.get(
                            "DNI",
                            solar_defaults["dni_peak"]
                        ),
                        dhi_peak=solar_params_dict.get(
                            "DHI",
                            solar_defaults["dhi_peak"]
                        ),
                        rays_per_receiver=solar_params_dict.get(
                            "rays_per_receiver",
                            solar_defaults["rays_per_receiver"]
                        ),
                        ground_buffer=solar_params_dict.get(
                            "ground_buffer",
                            solar_defaults["ground_buffer"]
                        ),
                        ground_res=solar_params_dict.get(
                            "ground_res",
                            solar_defaults["ground_res"]
                        ),
                        ground_radius=solar_params_dict.get(
                            "ground_radius",
                            solar_defaults["ground_radius"]
                        ),
                        shading_threshold=solar_params_dict.get(
                            "shading_threshold",
                            solar_defaults["shading_threshold"]
                        ),
                        batch_size=solar_params_dict.get(
                            "batch_size",
                            solar_defaults["batch_size"]
                        ),
                        rng_seed=solar_params_dict.get(
                            "rng_seed",
                            solar_defaults["rng_seed"]
                        ),
                        receiver_offset=solar_params_dict.get(
                            "receiver_offset",
                            solar_defaults["receiver_offset"]
                        ),
                        z_refine_factor=solar_params_dict.get(
                            "z_refine_factor",
                            solar_defaults["z_refine_factor"]
                        ),
                        z_refine_max_iters=solar_params_dict.get(
                            "z_refine_max_iters",
                            solar_defaults["z_refine_max_iters"]
                        ),
                        tair_morning_c=solar_params_dict.get(
                            "tair_morning_c",
                            solar_defaults["tair_morning_c"]
                        ),
                        tair_peak_c=solar_params_dict.get(
                            "tair_peak_c",
                            solar_defaults["tair_peak_c"]
                        ),
                        tair_peak_hour=solar_params_dict.get(
                            "tair_peak_hour",
                            solar_defaults["tair_peak_hour"]
                        ),
                        tair_width_hours=solar_params_dict.get(
                            "tair_width_hours",
                            solar_defaults["tair_width_hours"]
                        ),
                        sky_longwave=solar_params_dict.get(
                            "sky_longwave",
                            solar_defaults["sky_longwave"]
                        ),
                        emissivity_ground=solar_params_dict.get(
                            "emissivity_ground",
                            solar_defaults["emissivity_ground"]
                        ),
                        emissivity_wall=solar_params_dict.get(
                            "emissivity_wall",
                            solar_defaults["emissivity_wall"]
                        ),
                        emissivity_roof=solar_params_dict.get(
                            "emissivity_roof",
                            solar_defaults["emissivity_roof"]
                        ),
                        dt_hours=solar_params_dict.get(
                            "dt_hours",
                            solar_defaults["dt_hours"]
                        ),
                        output_dir=solar_output_dir,
                        work_dir=solar_work_dir,
                        weather_csv_path=solar_params_dict.get("weather_csv_path") or solar_params_dict.get("weather_csv"),
                        vedo_display_mode=solar_params_dict.get("vedo_display_mode", solar_defaults["vedo_display_mode"])
                    )
                    
                    # Save final Solar parameters used (after all merging)
                    if state.output_directory:
                        solar_priority = []
                        solar_priority.append(f"{len(solar_priority)+1}. JSON config file (IWEC baseline)")
                        if state.external_parameters and state.external_parameters.get("solar"):
                            solar_priority.append(f"{len(solar_priority)+1}. NEA live weather (override)")
                        if self.allow_llm_params and state.solver_parameters.get("solar"):
                            solar_priority.append(f"{len(solar_priority)+1}. LLM suggestions (override)")
                        solar_priority.append(f"{len(solar_priority)+1}. User parameters (final override)")
                        final_solar_params = {
                            "source": "Final Merged Parameters",
                            "timestamp": datetime.now().isoformat(),
                            "priority_order": solar_priority,
                            "solar": {
                                "time": solar_params.time_str,
                                "latitude": solar_params.latitude,
                                "longitude": solar_params.longitude,
                                "elevation": solar_params.elevation,
                                "DNI": solar_params.dni_peak,
                                "DHI": solar_params.dhi_peak,
                                "rays_per_receiver": solar_params.rays_per_receiver,
                                "ground_buffer": solar_params.ground_buffer,
                                "ground_res": solar_params.ground_res,
                                "receiver_offset": solar_params.receiver_offset,
                                "ground_radius": solar_params.ground_radius,
                                "shading_threshold": solar_params.shading_threshold
                            }
                        }
                        self._save_parameters_json(
                            final_solar_params,
                            "final_solar_parameters.json",
                            state.output_directory
                        )
                    
                    solar_result = self.solar_agent.run_analysis(solar_params)
                    state.solver_results["solar"] = solar_result
            
            # Run Query agent if needed
            if "query" in state.required_solvers:
                print("\n💬 Running query analysis...")
                query_result = self.query_agent.answer_query(
                    state.request.query,
                    state.building_analysis
                )
                state.solver_results["query"] = query_result
            
            state.stage = "solvers_complete"
            print("✅ All solvers complete")
            
        except Exception as e:
            print(f"❌ Solver execution failed: {e}")
            state.error_message = f"Solver error: {e}"
            state.stage = "error"
        
        return state
    
    def _integrate_results(self, state: IntelligentAgentState) -> IntelligentAgentState:
        """Integrate all results and generate final response"""
        print("📊 Integrating results...")
        solver_outputs = state.solver_results or {}
        analysis_insights: List[str] = []
        metrics_payload = None
        comparison_ctx = (state.request.user_parameters or {}).get("comparison") if state.request else None
        comparison_block: Dict[str, Any] = {}

        def _safe_load_json(path: Optional[str]) -> Optional[Dict[str, Any]]:
            if not path:
                return None
            try:
                with open(path, "r", encoding="utf-8") as f:
                    return json.load(f)
            except Exception as e:
                print(f"⚠️ Failed to load JSON from {path}: {e}")
                return None

        for key in ("solar", "cfd"):
            solver_entry = solver_outputs.get(key)
            if isinstance(solver_entry, dict) and solver_entry.get("analysis_metrics"):
                metrics_payload = solver_entry.get("analysis_metrics")
                break

        if metrics_payload:
            hotspot_note = self._render_hotspot_insight(metrics_payload)
            energy_note = self._render_energy_insight(metrics_payload)
            if hotspot_note:
                analysis_insights.append(hotspot_note)
            if energy_note:
                analysis_insights.append(energy_note)

        try:
            # Prepare summary of all results
            summary = {
                "query": state.request.query,
                "building_analysis": state.building_analysis[:500] + "..." if len(state.building_analysis) > 500 else state.building_analysis,
                "solver_results": {},
                "output_directory": state.output_directory
            }
            # Explicit PET/MRT buckets (if computed)
            pet_buckets = solver_outputs.get("cfd", {}).get("pet_time_buckets")
            mrt_buckets = solver_outputs.get("cfd", {}).get("mrt_time_buckets")
            # Geometry envelopes for area-based normalization
            geom_env = solver_outputs.get("geometry", {}).get("building_envelopes")
            
            viz_files = []
            for solver_name, result in solver_outputs.items():
                if isinstance(result, dict):
                    if solver_name == "geometry" and result.get("statistics"):
                        geo_stats = result.get("statistics", {})
                        summary["solver_results"]["geometry"] = {
                            "building_count": geo_stats.get("building_count"),
                            "bounds_min": geo_stats.get("bounds_min"),
                            "bounds_max": geo_stats.get("bounds_max"),
                            "extents": geo_stats.get("extent"),
                            "centroid": geo_stats.get("centroid"),
                            # Reduce payload: keep only counts, not full footprints/envelopes
                            "footprint_count": len(result.get("footprints") or []),
                            "envelope_count": len(result.get("building_envelopes") or []),
                        }
                    else:
                        summary["solver_results"][solver_name] = self._sanitize_solver_result(result)
                        # Attach PET/MRT bucket summaries explicitly for LLM
                        if solver_name == "cfd":
                            if result.get("pet_time_buckets") or result.get("mrt_time_buckets"):
                                summary["solver_results"]["cfd"]["pet_mrt_time_buckets"] = {
                                    "pet": result.get("pet_time_buckets"),
                                    "mrt": result.get("mrt_time_buckets"),
                                }
                            # Cooling normalization by envelope area
                            if metrics_payload and geom_env:
                                ce = metrics_payload.get("cooling_energy", {})
                                per_bld = ce.get("per_building_kWh") or ce.get("per_building_kwh")
                                per_peak = ce.get("per_building_max_hourly_kw") or ce.get("per_building_max_hourly_kW")
                                env_map = {env["id"]: env.get("envelope_area") for env in geom_env if env.get("envelope_area", 0) > 0}
                                if per_bld and env_map:
                                    norm_list = []
                                    for bid, kwh in per_bld.items():
                                        area = env_map.get(bid)
                                        if not area or area <= 0:
                                            continue
                                        norm = kwh / area
                                        peak_norm = None
                                        peak_val = per_peak.get(bid) if per_peak else None
                                        if peak_val is not None and area:
                                            peak_norm = peak_val / area
                                        norm_list.append({
                                            "id": bid,
                                            "total_kWh": kwh,
                                            "envelope_area": area,
                                            "kWh_per_m2_envelope": norm,
                                            "peak_kW": peak_val,
                                            "peak_kW_per_m2_envelope": peak_norm,
                                        })
                                    norm_list_sorted = sorted(norm_list, key=lambda x: x["kWh_per_m2_envelope"], reverse=True)
                                    summary["solver_results"]["cfd"]["cooling_normalized_envelope_top"] = norm_list_sorted[:15]
                    if result.get("success") and result.get("visualization_file"):
                        viz_files.append({
                            "solver": solver_name,
                            "file": result["visualization_file"]
                        })
                    if result.get("success") and result.get("visualization_files"):
                        for path in result["visualization_files"]:
                            viz_files.append({
                                "solver": solver_name,
                                "file": path
                            })
                else:
                    summary["solver_results"][solver_name] = {"raw_result": str(result)}

            if analysis_insights:
                summary["analysis_insights"] = analysis_insights
            if pet_buckets or mrt_buckets:
                summary["pet_mrt_time_buckets"] = {
                    "pet": pet_buckets,
                    "mrt": mrt_buckets,
                }

            # Baseline vs tuned comparison context (for material tuning)
            if comparison_ctx:
                baseline_metrics = comparison_ctx.get("baseline_metrics") or _safe_load_json(
                    comparison_ctx.get("baseline_metrics_path")
                )
                baseline_materials = comparison_ctx.get("baseline_materials") or _safe_load_json(
                    comparison_ctx.get("baseline_cfd_parameters_path")
                )
                baseline_vtk_files: List[str] = []
                try:
                    vtk_dir = os.path.join(comparison_ctx.get("baseline_dir", ""), "cfd_solar", "vtk_files")
                    if os.path.isdir(vtk_dir):
                        baseline_vtk_files = sorted(glob.glob(os.path.join(vtk_dir, "*.vtk")))
                except Exception as e:
                    print(f"⚠️ Failed to list baseline VTK files: {e}")

                tuned_metrics = solver_outputs.get("cfd", {}).get("analysis_metrics")
                if tuned_metrics is None:
                    tuned_metrics = _safe_load_json(
                        os.path.join(state.output_directory or "", "cfd_solar", "analysis_metrics.json")
                    )
                tuned_materials = _safe_load_json(
                    os.path.join(state.output_directory or "", "final_cfd_parameters.json")
                )
                tuned_vtk_files: List[str] = []
                try:
                    tuned_vtk_dir = os.path.join(state.output_directory or "", "cfd_solar", "vtk_files")
                    if os.path.isdir(tuned_vtk_dir):
                        tuned_vtk_files = sorted(glob.glob(os.path.join(tuned_vtk_dir, "*.vtk")))
                except Exception as e:
                    print(f"⚠️ Failed to list tuned VTK files: {e}")

                comparison_json = _safe_load_json(comparison_ctx.get("comparison_file"))
                comparison_block = {
                    "baseline_dir": comparison_ctx.get("baseline_dir"),
                    "baseline_metrics": baseline_metrics,
                    "baseline_materials": baseline_materials,
                    "baseline_metrics_path": comparison_ctx.get("baseline_metrics_path"),
                    "baseline_cfd_parameters_path": comparison_ctx.get("baseline_cfd_parameters_path"),
                    "baseline_vtk_files": baseline_vtk_files,
                    "tuned_dir": state.output_directory,
                    "tuned_metrics": tuned_metrics,
                    "tuned_materials": tuned_materials,
                    "tuned_metrics_path": os.path.join(state.output_directory or "", "cfd_solar", "analysis_metrics.json"),
                    "tuned_cfd_parameters_path": os.path.join(state.output_directory or "", "final_cfd_parameters.json"),
                    "tuned_vtk_files": tuned_vtk_files,
                    "comparison_file": comparison_ctx.get("comparison_file"),
                    "comparison_json": comparison_json,
                    "plan_file": comparison_ctx.get("plan_file"),
                }
                summary["material_comparison"] = comparison_block
            
            # Trim visualization list to avoid oversized prompts
            if len(viz_files) > 50:
                viz_files = viz_files[:50]
            
            # Generate comprehensive response using LLM
            prompt = f"""Generate a comprehensive answer to the user's query based on all analysis results.

User Query: "{state.request.query}"

Analysis Results:
{json.dumps(summary, indent=2)}

Available Visualizations:
{json.dumps(viz_files, indent=2) if viz_files else "None"}

Provide a clear, professional response that:
1. Directly answers the user's question
2. Cites specific metrics from the analysis
3. Mentions available visualization files
4. Provides actionable recommendations
5. Maintains technical accuracy
6. Highlights specific hotspot locations (mention surrounding buildings/coordinates and current meteorology)
7. Summarizes building energy/cooling impacts for the highest-load buildings
8. Explicitly list morning / noon / afternoon / evening maxima for PET and MRT (value, time, coordinates, building ID, and the VTK file path), using pet_mrt_time_buckets if available.
9. Include normalized cooling rankings (kWh/m²-envelope, peak kW/m²-envelope) using geometry-derived envelope areas when provided.
10. At the end of each major subsection, add a line “Reference files: ...” listing all relevant PNG/VTK paths from the available visualizations (no limit; include the most pertinent ones).

Format your response in a clear, structured way."""
            
            response = self._invoke_llm("Result Integration", [
                SystemMessage(content="You are an expert building performance analyst."),
                HumanMessage(content=prompt)
            ])
            
            state.final_response = response.content
            state.stage = "complete"
            
            print("✅ Results integrated")
            
        except Exception as e:
            print(f"❌ Integration failed: {e}")
            state.error_message = f"Integration error: {e}"
            state.stage = "error"
        
        return state
    
    def _handle_error(self, state: IntelligentAgentState) -> IntelligentAgentState:
        """Handle errors"""
        print(f"❌ Error: {state.error_message}")
        state.final_response = f"Analysis failed: {state.error_message}"
        return state
    
    def _check_intent_status(self, state: IntelligentAgentState) -> str:
        return "error" if state.error_message else "success"
    
    def _check_geometry_status(self, state: IntelligentAgentState) -> str:
        return "error" if state.error_message else "success"
    
    def _check_solver_status(self, state: IntelligentAgentState) -> str:
        if state.error_message:
            return "error"
        return "skip" if not state.solver_results else "success"
    
    def analyze(self, query: str, stl_directory: str, 
                user_parameters: Optional[Dict[str, Any]] = None,
                output_directory: Optional[str] = None) -> Dict[str, Any]:
        """Main analysis method"""
        print("="*80)
        print("🤖 Intelligent Building Analysis Agent")
        print("="*80)
        print(f"Query: {query}")
        print(f"STL Directory: {stl_directory}")
        print("="*80)
        if output_directory is None:
            results_root = Path(__file__).resolve().parent / "results"
            results_root.mkdir(parents=True, exist_ok=True)
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            output_dir_path = results_root / f"analysis_{timestamp}"
        else:
            output_dir_path = Path(output_directory).expanduser().resolve()
        output_dir_path.mkdir(parents=True, exist_ok=True)
        print(f"Output directory: {output_dir_path}")
        self.llm_recorder.start_session(output_dir_path)

        # Create request
        request = AnalysisRequest(
            query=query,
            stl_directory=stl_directory,
            user_parameters=user_parameters
        )
        resolved_dt = self._infer_weather_datetime(request)
        resolved_time_str = resolved_dt.isoformat() if resolved_dt else None
        
        # Initialize state
        initial_state = IntelligentAgentState(
            request=request,
            required_solvers=[],
            solver_parameters={},
            solver_results={},
            external_parameters={},
            output_directory=str(output_dir_path),
            llm_log_file=self.llm_recorder.get_log_file() or "",
            llm_text_log_file=self.llm_recorder.get_text_log_file() or "",
            resolved_time=resolved_time_str,
        )
        
        # Execute workflow
        tags = [token for token in [Path(stl_directory).name, query[:40]] if token]
        config = RunnableConfig(
            tags=tags,
            metadata={
                "stl_directory": stl_directory,
                "user_query": query,
                "output_directory": str(output_dir_path),
            },
        )
        initial_state.runnable_config = config
        final_state = self.graph.invoke(initial_state)
        
        # Handle dict or object return
        if isinstance(final_state, dict):
            success = final_state.get('stage') == 'complete'
            response = final_state.get('final_response', '')
            error = final_state.get('error_message', '')
            solver_results = final_state.get('solver_results', {})
            building_analysis = final_state.get('building_analysis', '')
            output_dir_value = final_state.get('output_directory', str(output_dir_path))
        else:
            success = final_state.stage == 'complete'
            response = final_state.final_response
            error = final_state.error_message
            solver_results = final_state.solver_results
            building_analysis = final_state.building_analysis
            output_dir_value = final_state.output_directory
        
        # Collect all output files
        output_files = {
            "csv_files": [],
            "visualization_files": [],
            "artifact_files": []
        }
        artifacts_summary: Dict[str, Dict[str, Any]] = {}
        
        if isinstance(solver_results, dict):
            for solver_name, result in solver_results.items():
                if isinstance(result, dict) and result.get("success"):
                    if result.get("output_file"):
                        output_files["csv_files"].append({
                            "solver": solver_name,
                            "file": result["output_file"]
                        })
                    if result.get("visualization_file"):
                        output_files["visualization_files"].append({
                            "solver": solver_name,
                            "file": result["visualization_file"]
                        })
                    if result.get("visualization_files"):
                        for path in result["visualization_files"]:
                            output_files["visualization_files"].append({
                                "solver": solver_name,
                                "file": path
                            })
                    if result.get("artifacts"):
                        artifacts_summary[solver_name] = result["artifacts"]
                        for path in result["artifacts"].get("all_files", []):
                            output_files["artifact_files"].append({
                                "solver": solver_name,
                                "file": path
                            })
        
        return {
            "success": success,
            "response": response,
            "building_analysis": building_analysis,
            "solver_results": solver_results,
            "output_files": output_files,
            "artifacts": artifacts_summary,
            "error": error,
            "output_directory": output_dir_value,
            "llm_log_file": self.llm_recorder.get_log_file(),
            "llm_text_log_file": self.llm_recorder.get_text_log_file()
        }
    
    def get_llm_log_file(self) -> Optional[str]:
        """Public accessor for the most recent LLM log path."""
        return self.llm_recorder.get_log_file()
    
    def get_llm_text_log_file(self) -> Optional[str]:
        """Return the plaintext verbose log path."""
        return self.llm_recorder.get_text_log_file()
    
    def get_llm_interactions(self) -> List[Dict[str, Any]]:
        """Return the recorded LLM interactions for the latest run."""
        return self.llm_recorder.get_interactions()

    @staticmethod
    def _render_hotspot_insight(metrics: Dict[str, Any]) -> str:
        hotspots = metrics.get("ground_hotspots") or []
        if not hotspots:
            return ""
        hotspot = hotspots[0]
        buildings = hotspot.get("nearest_buildings") or []
        location = hotspot.get("location") or []
        coord_str = (
            f"({location[0]:.1f}, {location[1]:.1f})"
            if isinstance(location, (list, tuple)) and len(location) >= 2
            else "the highlighted plaza"
        )
        met = hotspot.get("meteorology") or {}
        wind_speed = met.get("wind_speed_ms")
        wind_dir = met.get("wind_direction_deg")
        dni = met.get("dni")
        desc_parts = []
        if wind_speed is not None and wind_dir is not None:
            desc_parts.append(f"winds {wind_speed:.1f} m/s from {wind_dir:.0f}°")
        if dni is not None:
            desc_parts.append(f"DNI {dni:.0f} W/m²")
        met_desc = ", ".join(desc_parts) if desc_parts else "prevailing ambient conditions"
        building_label = " & ".join(buildings) if buildings else coord_str
        return (
            f"Peak pedestrian heat stress of {hotspot.get('pet_c', 0):.1f} °C PET "
            f"around {building_label} at {hotspot.get('time', 'the reported hour')} "
            f"under {met_desc}."
        )

    @staticmethod
    def _render_energy_insight(metrics: Dict[str, Any]) -> str:
        energy = metrics.get("cooling_energy") or {}
        per_building = energy.get("per_building_kWh") or {}
        if not per_building:
            return ""
        top_name, top_value = max(per_building.items(), key=lambda kv: kv[1])
        peak_info = (energy.get("per_building_max_hourly_kw") or {}).get(top_name, {})
        peak_kw = peak_info.get("value")
        peak_time = peak_info.get("time")
        parts = [
            f"Building '{top_name}' accumulated {top_value:.1f} kWh of façade/roof cooling over the scenario"
        ]
        if peak_kw is not None and peak_time:
            parts.append(f"peaking at {peak_kw:.1f} kW around {peak_time}")
        total_energy = energy.get("total_kWh")
        if total_energy:
            parts.append(f"(district total ≈ {total_energy:.1f} kWh)")
        return "; ".join(parts) + "."


def main():
    """Test the intelligent agent"""
    agent = IntelligentBuildingAgent(api_key=OPENAI_API_KEY)
    
    stl_dir = "/scratch/Urban/intelligent_agent_package/example_stl/town_00001_500_1.379_103.893_14553_1532"
    
    # Test queries
    test_queries = [
        {
            "query": "Analyze the wind flow and thermal comfort around this building at 2 meters height with wind from northeast at 2 m/s",
            "params": {
                "cfd": {
                    "wind_speed": 2.0,
                    "wind_direction": 45.0,
                    "height": 2.0
                }
            }
        },
        {
            "query": "What is the solar irradiance and shading pattern on December 21st at 2pm?",
            "params": {
                "solar": {
                    "time": "2025-12-21 14:00:00+08:00"
                }
            }
        },
        {
            "query": "Can someone on the north side of the building avoid afternoon sun in winter?",
            "params": None
        }
    ]
    
    for i, test in enumerate(test_queries[:1], 1):  # Run first test only
        print(f"\n{'='*80}")
        print(f"TEST {i}")
        print(f"{'='*80}")
        
        result = agent.analyze(
            query=test["query"],
            stl_directory=stl_dir,
            user_parameters=test["params"]
        )
        
        print(f"\n{'='*80}")
        print("RESULTS")
        print(f"{'='*80}")
        print(f"Success: {result['success']}")
        print(f"\nResponse:\n{result['response']}")
        
        if result['solver_results']:
            print(f"\n{'='*60}")
            print("Solver Outputs:")
            print(f"{'='*60}")
            for solver, res in result['solver_results'].items():
                if res.get('success'):
                    print(f"  ✅ {solver}:")
                    if res.get('output_file'):
                        print(f"     📄 Data: {res.get('output_file')}")
                    if res.get('visualization_file'):
                        print(f"     🎨 Visualization: {res.get('visualization_file')}")
                else:
                    print(f"  ❌ {solver}: {res.get('error', 'failed')}")
        
        # Summary of output files
        if result.get('output_files'):
            files = result['output_files']
            if files['csv_files'] or files['visualization_files']:
                print(f"\n{'='*60}")
                print("Output Files Summary:")
                print(f"{'='*60}")
                print(f"📊 CSV Files: {len(files['csv_files'])}")
                for f in files['csv_files']:
                    print(f"   • {f['solver']}: {f['file']}")
                print(f"🎨 Visualizations: {len(files['visualization_files'])}")
                for f in files['visualization_files']:
                    print(f"   • {f['solver']}: {f['file']}")


if __name__ == "__main__":
    main()

# Intelligent Building Agent - Implementation Details

> A comprehensive technical document describing the multi-agent architecture for urban microclimate analysis

---

## Table of Contents

1. [System Architecture Overview](#1-system-architecture-overview)
2. [Core Agent: IntelligentBuildingAgent](#2-core-agent-intelligentbuildingagent)
3. [LangGraph Workflow Implementation](#3-langgraph-workflow-implementation)
4. [Sub-Agent System](#4-sub-agent-system)
5. [Parameter Management System](#5-parameter-management-system)
6. [Weather Integration (NEA API)](#6-weather-integration-nea-api)
7. [LLM Interaction & Recording](#7-llm-interaction--recording)
8. [Material Tuning Pipeline](#8-material-tuning-pipeline)
9. [Data Structures & State Management](#9-data-structures--state-management)
10. [Solver Backends](#10-solver-backends)
11. [Visualization Pipeline](#11-visualization-pipeline)
12. [Configuration System](#12-configuration-system)

---

## 1. System Architecture Overview

### 1.1 High-Level Architecture

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                    IntelligentBuildingAgent (Orchestrator)                   │
│                         LangGraph State Machine                              │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                              │
│  ┌──────────────┐    ┌──────────────┐    ┌──────────────┐    ┌───────────┐ │
│  │    Intent    │───►│   Geometry   │───►│    Solver    │───►│  Result   │ │
│  │   Analyzer   │    │   Analyzer   │    │ Orchestrator │    │ Integrator│ │
│  └──────────────┘    └──────────────┘    └──────────────┘    └───────────┘ │
│        │                    │                   │                    │      │
│        ▼                    ▼                   ▼                    ▼      │
│  ┌──────────────────────────────────────────────────────────────────────┐  │
│  │                        LLM (GPT-5.1)                                  │  │
│  │                   via LangChain ChatOpenAI                            │  │
│  └──────────────────────────────────────────────────────────────────────┘  │
│                                                                              │
├─────────────────────────────────────────────────────────────────────────────┤
│                              Sub-Agents                                      │
│  ┌────────────┐  ┌────────────┐  ┌────────────┐  ┌────────────┐            │
│  │ STLAnalysis│  │  Building  │  │    CFD     │  │   Solar    │            │
│  │   Agent    │  │QueryAgent  │  │SolverAgent │  │SolverAgent │            │
│  └────────────┘  └────────────┘  └────────────┘  └────────────┘            │
│        │                │                │                │                 │
│        ▼                ▼                ▼                ▼                 │
│  ┌──────────────────────────────────────────────────────────────────────┐  │
│  │                    coupled_UrGen_v1 Backend                           │  │
│  │              (CFD + Radiation Physics Simulation)                     │  │
│  └──────────────────────────────────────────────────────────────────────┘  │
│                                                                              │
├─────────────────────────────────────────────────────────────────────────────┤
│                         Supporting Services                                  │
│  ┌────────────────┐  ┌────────────────┐  ┌────────────────┐                │
│  │ NEAWeather     │  │  LLMRecorder   │  │  Artifact      │                │
│  │ Client         │  │                │  │  Collector     │                │
│  └────────────────┘  └────────────────┘  └────────────────┘                │
└─────────────────────────────────────────────────────────────────────────────┘
```

### 1.2 Technology Stack

| Component | Technology | Purpose |
|-----------|------------|---------|
| LLM | OpenAI GPT-5.1 | Natural language understanding & generation |
| LLM Framework | LangChain | LLM abstraction and message handling |
| Workflow Engine | LangGraph | State machine-based agent orchestration |
| Observability | LangSmith | Tracing and debugging LLM calls |
| Physics Backend | coupled_UrGen_v1 | CFD and radiation simulation |
| 3D Processing | trimesh | STL geometry parsing and analysis |
| Visualization | matplotlib, vedo | Plot generation |
| Weather API | data.gov.sg (NEA) | Real-time weather data |

### 1.3 File Structure

```
intelligent_agent_package/
├── intelligent_building_agent.py    # Main orchestrator agent
├── stl_agent.py                     # STL geometry analysis agent
├── query_agent.py                   # Building query Q&A agent
├── weather_client.py                # NEA weather API client
├── llm_recorder.py                  # LLM interaction logging
├── config.py                        # API keys and configuration
├── solver_parameters.json           # Default solver parameters
├── full_analysis_with_recording_en.py  # Test runner with recording
│
├── wrapper/                         # Solver wrappers
│   ├── __init__.py
│   ├── cfd_solver.py               # CFD parameter adapter
│   ├── solar_solver.py             # Solar parameter adapter
│   └── artifact_utils.py           # Output file collection
│
└── coupled_UrGen_v1/               # Physics simulation backend
    ├── coupled_UrGen_.py           # Main simulation engine
    └── SGP_Singapore_486980_IWEC.csv  # IWEC weather data
```

---

## 2. Core Agent: IntelligentBuildingAgent

### 2.1 Class Definition

```python
class IntelligentBuildingAgent:
    """
    Intelligent agent that understands user queries and automatically 
    calls appropriate solvers (CFD, Solar, Geometry analysis)
    """
```

**Location**: `intelligent_building_agent.py`

### 2.2 Initialization

```python
def __init__(self, api_key: str, config_file: Optional[str] = None, 
             allow_llm_params: bool = True):
    # LLM Setup
    self.llm = ChatOpenAI(
        api_key=api_key,
        model="gpt-5.1",
        temperature=0.1,
        service_tier="priority"
    )
    
    # Sub-agents
    self.stl_agent = STLAnalysisAgent(api_key=api_key, recorder=self.llm_recorder)
    self.query_agent = BuildingQueryAgent(api_key=api_key, recorder=self.llm_recorder)
    self.cfd_agent = CFDSolverAgent()
    self.solar_agent = SolarSolverAgent()
    self.weather_client = NEAWeatherClient()
    
    # Configuration
    self.solver_config = self._load_config() if config_file else {}
    self.allow_llm_params = allow_llm_params  # Toggle LLM parameter suggestions
    
    # Build workflow graph
    self.graph = self._build_graph()
```

### 2.3 Key Attributes

| Attribute | Type | Description |
|-----------|------|-------------|
| `llm` | ChatOpenAI | LangChain LLM interface |
| `llm_recorder` | LLMRecorder | Records all LLM interactions |
| `stl_agent` | STLAnalysisAgent | Geometry analysis sub-agent |
| `query_agent` | BuildingQueryAgent | Q&A sub-agent |
| `cfd_agent` | CFDSolverAgent | CFD simulation wrapper |
| `solar_agent` | SolarSolverAgent | Solar simulation wrapper |
| `weather_client` | NEAWeatherClient | Live weather data fetcher |
| `solver_config` | Dict | Loaded JSON configuration |
| `allow_llm_params` | bool | Enable/disable LLM parameter suggestions |
| `graph` | StateGraph | Compiled LangGraph workflow |

### 2.4 Main Entry Point

```python
def analyze(self, query: str, stl_directory: str, 
            user_parameters: Optional[Dict[str, Any]] = None,
            output_directory: Optional[str] = None) -> Dict[str, Any]:
    """
    Main analysis method - entry point for all building analysis requests
    
    Args:
        query: Natural language query from user
        stl_directory: Path to directory containing STL building files
        user_parameters: Optional override parameters for solvers
        output_directory: Optional custom output path
        
    Returns:
        Dictionary containing:
        - success: bool
        - response: str (LLM-generated analysis)
        - building_analysis: str (geometry insights)
        - solver_results: Dict (per-solver outputs)
        - output_files: Dict (generated file paths)
        - artifacts: Dict (all output artifacts)
        - error: str (error message if failed)
    """
```

---

## 3. LangGraph Workflow Implementation

### 3.1 Workflow Graph Structure

```python
def _build_graph(self) -> StateGraph:
    """Build LangGraph workflow"""
    workflow = StateGraph(IntelligentAgentState)
    
    # Add nodes (processing stages)
    workflow.add_node("intent_analyzer", self._analyze_intent)
    workflow.add_node("geometry_analyzer", self._run_geometry_analysis)
    workflow.add_node("solver_orchestrator", self._run_solvers)
    workflow.add_node("result_integrator", self._integrate_results)
    workflow.add_node("error_handler", self._handle_error)
    
    # Set entry point
    workflow.set_entry_point("intent_analyzer")
    
    # Add conditional edges
    workflow.add_conditional_edges(
        "intent_analyzer",
        self._check_intent_status,
        {"success": "geometry_analyzer", "error": "error_handler"}
    )
    
    workflow.add_conditional_edges(
        "geometry_analyzer",
        self._check_geometry_status,
        {"success": "solver_orchestrator", "error": "error_handler"}
    )
    
    workflow.add_conditional_edges(
        "solver_orchestrator",
        self._check_solver_status,
        {"success": "result_integrator", "skip": "result_integrator", "error": "error_handler"}
    )
    
    workflow.add_edge("result_integrator", END)
    workflow.add_edge("error_handler", END)
    
    return workflow.compile()
```

### 3.2 Workflow Diagram

```
                    ┌─────────────────┐
                    │      START      │
                    └────────┬────────┘
                             │
                             ▼
                    ┌─────────────────┐
                    │ Intent Analyzer │◄──── LLM: Determine required solvers
                    └────────┬────────┘      and suggest parameters
                             │
              ┌──────────────┼──────────────┐
              │ success      │              │ error
              ▼              │              ▼
     ┌─────────────────┐     │     ┌─────────────────┐
     │Geometry Analyzer│     │     │  Error Handler  │
     └────────┬────────┘     │     └────────┬────────┘
              │              │              │
              │ success      │              │
              ▼              │              │
     ┌─────────────────┐     │              │
     │Solver Orchestra.│     │              │
     └────────┬────────┘     │              │
              │              │              │
     ┌────────┼────────┐     │              │
     │success │  skip  │     │              │
     ▼        ▼        │     │              │
     ┌─────────────────┐     │              │
     │Result Integrator│◄────┘              │
     └────────┬────────┘                    │
              │                             │
              ▼                             ▼
                    ┌─────────────────┐
                    │       END       │
                    └─────────────────┘
```

### 3.3 Stage Details

#### Stage 1: Intent Analyzer (`_analyze_intent`)

**Purpose**: Parse user query to determine which solvers are needed and extract initial parameters.

**LLM Prompt Structure**:
```python
prompt = f"""Analyze this building analysis request and determine what solvers are needed.

User Query: "{state.request.query}"

Available Solvers:
1. geometry - Basic STL geometry analysis (always required first)
2. cfd - Wind flow, temperature, and humidity simulation
3. solar - Solar irradiance, shading, and Sky View Factor analysis
4. query - Answer specific questions about building orientation

Return JSON format:
{{
    "required_solvers": ["geometry", "cfd", ...],
    "parameters": {{
        "cfd": {{"wind_speed": 1.5, "wind_direction": 45, ...}},
        "solar": {{"time": "2025-12-21 14:00:00+08:00", "DNI": 800, ...}}
    }},
    "reasoning": "Why these solvers are needed..."
}}
"""
```

**Output**: Updates `state.required_solvers` and `state.solver_parameters`

#### Stage 2: Geometry Analyzer (`_run_geometry_analysis`)

**Purpose**: Load and analyze STL building geometry files.

**Key Operations**:
1. Load all STL files from directory using `trimesh`
2. Clean mesh (remove degenerate faces)
3. Extract building footprints and envelopes
4. Generate combined geometry file
5. Call `STLAnalysisAgent` for LLM-powered geometry insights
6. Generate top-view visualization with building IDs
7. Cache results for potential reuse

**Output**: Updates `state.building_analysis` and `state.solver_results["geometry"]`

#### Stage 3: Solver Orchestrator (`_run_solvers`)

**Purpose**: Execute required physics solvers (CFD, Solar, Query).

**Parameter Priority System** (lowest to highest):
1. JSON config file (`solver_parameters.json`)
2. LLM suggestions (if `allow_llm_params=True`)
3. NEA live weather data (external API)
4. User parameters (highest priority override)

**Solver Execution Flow**:
```python
if "cfd" in state.required_solvers:
    # 1. Load from JSON config
    # 2. Merge LLM suggestions (if enabled)
    # 3. Apply NEA weather overrides
    # 4. Apply user parameters
    # 5. Execute CFD solver
    cfd_result = self.cfd_agent.run_analysis(cfd_params)

if "solar" in state.required_solvers:
    # Skip if CFD already ran coupled radiation
    if not state.solver_results.get("cfd", {}).get("coupled_run"):
        solar_result = self.solar_agent.run_analysis(solar_params)

if "query" in state.required_solvers:
    query_result = self.query_agent.answer_query(query, building_analysis)
```

#### Stage 4: Result Integrator (`_integrate_results`)

**Purpose**: Combine all solver results and generate final LLM response.

**Key Operations**:
1. Sanitize solver results (remove large dataframes)
2. Extract analysis insights (hotspots, energy metrics)
3. Prepare summary with PET/MRT time buckets
4. Generate comprehensive LLM response with:
   - Direct answer to user query
   - Specific metrics citations
   - Visualization file references
   - Actionable recommendations

---

## 4. Sub-Agent System

### 4.1 STLAnalysisAgent

**Location**: `stl_agent.py`

**Purpose**: Analyze 3D building geometry from STL files.

**Workflow (LangGraph)**:
```
file_reader → content_analyzer → code_generator → code_executor
```

**State Definition**:
```python
@dataclass
class STLAnalysisState:
    stl_file_path: str = ""
    stl_content: str = ""
    file_size: int = 0
    analysis_result: str = ""
    visualization_code: str = ""
    output_path: str = ""
    error_message: str = ""
    stage: str = "init"
```

**Key Methods**:

| Method | Description |
|--------|-------------|
| `_read_stl_file` | Load STL (ASCII or binary via trimesh) |
| `_analyze_stl_content` | LLM analysis of geometry |
| `_generate_visualization_code` | LLM generates matplotlib code |
| `_execute_visualization` | Execute generated code to create PNG |
| `analyze_stl` | Main entry point |

### 4.2 BuildingQueryAgent

**Location**: `query_agent.py`

**Purpose**: Answer natural language questions about buildings (solar exposure, orientation, etc.)

**Workflow (LangGraph)**:
```
query_processor → solar_analyzer → response_generator
```

**State Definition**:
```python
@dataclass
class BuildingQueryState:
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
    stage: str = "init"
```

**Key Features**:
- Extracts parameters from query text (north/south/east/west, season, time)
- Analyzes solar conditions for Singapore's tropical climate
- Returns confidence score (0-100%)
- Generates professional recommendations

### 4.3 CFDSolverAgent

**Location**: `wrapper/cfd_solver.py`

**Purpose**: Thin wrapper that forwards CFD parameters to the coupled_UrGen_v1 backend.

**Parameter Structure**:
```python
@dataclass
class CFDParameters:
    stl_directory: str
    wind_direction_deg: Optional[float] = None
    u_inflow: Optional[float] = None
    z_slice: float = 2.0
    voxel_pitch: float = 4.0
    buffer_ratio: float = 0.10
    T2m_C: Optional[float] = None
    RH2m_percent: Optional[float] = None
    alpha_T: float = 1.5
    alpha_RH: float = 8.0
    building_radius: float = 100.0
    cfd_log_z0: float = 0.5
    simulation_time: Optional[str] = None
    weather_csv_path: Optional[str] = None
    output_dir: Optional[str] = None
    work_dir: Optional[str] = None
    dt_hours: float = 1.0
    vedo_display_mode: str = "off"
    # Material overrides (rad_albedo_*, rad_emissivity_*, etc.)
    ...
```

**Key Behavior**:
- Loads IWEC weather time series from CSV
- Calls `main_coupled_run()` with `run_cfd=True, run_radiation=True`
- Collects output artifacts (VTK, PNG, CSV, logs)
- Returns analysis metrics if available

### 4.4 SolarSolverAgent

**Location**: `wrapper/solar_solver.py`

**Purpose**: Thin wrapper for solar/radiation simulation.

**Parameter Structure**:
```python
@dataclass
class SolarParameters:
    stl_directory: str
    time_str: Optional[str] = None
    latitude: float = 1.3521          # Singapore default
    longitude: float = 103.8198
    elevation: float = 15.0
    dni_peak: Optional[float] = None
    dhi_peak: Optional[float] = None
    rays_per_receiver: int = 64
    ground_buffer: float = 20.0
    ground_res: float = 25.0
    shading_threshold: float = 5.0
    emissivity_ground: float = 0.95
    emissivity_wall: float = 0.92
    emissivity_roof: float = 0.9
    dt_hours: float = 1.0
    output_dir: Optional[str] = None
    work_dir: Optional[str] = None
    weather_csv_path: Optional[str] = None
    ...
```

---

## 5. Parameter Management System

### 5.1 Parameter Priority Chain

The system implements a strict priority chain for parameter resolution:

```
Priority (lowest → highest):
┌─────────────────────────────────────────────────────────────┐
│ 1. JSON Config File (solver_parameters.json)                │
│    └─ Baseline defaults loaded at agent initialization      │
├─────────────────────────────────────────────────────────────┤
│ 2. LLM Suggestions (if allow_llm_params=True)               │
│    └─ GPT-5.1 suggests parameters based on query context    │
├─────────────────────────────────────────────────────────────┤
│ 3. NEA Live Weather (external_parameters)                   │
│    └─ Real-time weather from data.gov.sg API                │
├─────────────────────────────────────────────────────────────┤
│ 4. User Parameters (user_parameters dict)                   │
│    └─ Explicit overrides from API caller (highest priority) │
└─────────────────────────────────────────────────────────────┘
```

### 5.2 Parameter Merging Logic

```python
# CFD Parameter Merging Example
cfd_params_dict = {}

# 1. Load from JSON config
if self.solver_config.get("cfd"):
    cfd_params_dict.update(self.solver_config["cfd"])

# 2. Merge LLM suggestions (if enabled)
if self.allow_llm_params and state.solver_parameters.get("cfd"):
    for key, val in state.solver_parameters.get("cfd", {}).items():
        if key in ("wind_speed", "wind_direction", "temperature", "humidity"):
            if cfd_params_dict.get(key) is None:  # Only if missing
                cfd_params_dict[key] = val

# 3. Apply NEA weather (only where config/LLM didn't set)
if state.external_parameters and state.external_parameters.get("cfd"):
    ext_cfd = state.external_parameters.get("cfd", {})
    for key, val in ext_cfd.items():
        if cfd_params_dict.get(key) is None:
            cfd_params_dict[key] = val

# 4. Apply user parameters (highest priority)
if state.request.user_parameters:
    cfd_params_dict.update(user_cfd_params)
```

### 5.3 Parameter Tracking Files

The system saves parameter provenance at each stage:

| File | Content |
|------|---------|
| `llm_suggested_parameters.json` | LLM-suggested parameters with reasoning |
| `external_weather_snapshot.json` | Raw NEA API response + derived parameters |
| `final_cfd_parameters.json` | Final merged CFD parameters with priority order |
| `final_solar_parameters.json` | Final merged solar parameters |

### 5.4 IWEC Weather Integration

The system uses IWEC (International Weather for Energy Calculations) time series:

```python
# Default weather file
def _default_weather_csv() -> Path:
    return Path(__file__).parent.parent / "coupled_UrGen_v1" / "SGP_Singapore_486980_IWEC.csv"

# Time series columns loaded:
# - Wind direction, Wind Speed
# - Air Temperature, Relative Humidity
# - Direct Normal Radiation (DNI)
# - Diffuse Horizontal Radiation (DHI)
```

---

## 6. Weather Integration (NEA API)

### 6.1 NEAWeatherClient

**Location**: `weather_client.py`

**Purpose**: Fetch real-time or historical weather data from Singapore's NEA (data.gov.sg).

### 6.2 API Endpoints

```python
DATASET_ENDPOINTS = {
    "temperature": "https://api.data.gov.sg/v1/environment/air-temperature",
    "humidity": "https://api.data.gov.sg/v1/environment/relative-humidity",
    "wind_speed": "https://api.data.gov.sg/v1/environment/wind-speed",
    "wind_direction": "https://api.data.gov.sg/v1/environment/wind-direction",
}
```

### 6.3 Key Methods

```python
class NEAWeatherClient:
    def fetch_weather_snapshot(self, target_datetime: Optional[datetime] = None) -> Optional[Dict]:
        """
        Fetch metadata and readings near target_datetime (SGT).
        Returns snapshot with measurements from all stations.
        """
        
    def build_solver_parameters(self, snapshot: Dict, target_lat: float, target_lon: float) -> Dict:
        """
        Map snapshot measurements into solver parameter format.
        Uses nearest station if coordinates provided.
        
        Returns:
            {
                "cfd": {"wind_speed": ..., "wind_direction": ..., "temperature": ..., "humidity": ...},
                "solar": {"ambient_temperature": ..., "time": ...}
            }
        """
```

### 6.4 Timestamp Resolution

The agent resolves simulation timestamps in priority order:

```python
def _infer_weather_datetime(self, request: AnalysisRequest) -> Optional[datetime]:
    # 1. Check user_parameters for explicit timestamp
    if request.user_parameters.get("timestamp"):
        return parse(user_parameters["timestamp"])
    
    # 2. Parse datetime from query text
    if date_pattern_found_in_query:
        return extracted_datetime
    
    # 3. Use LLM to infer timestamp
    llm_dt = self._llm_choose_datetime(query)
    if llm_dt:
        return llm_dt
    
    # 4. Fall back to default scenario datetime
    return DEFAULT_SCENARIO_DATETIME  # 1989-12-22 15:00 SGT
```

---

## 7. LLM Interaction & Recording

### 7.1 LLMRecorder

**Location**: `llm_recorder.py`

**Purpose**: Track all LLM prompts and responses for debugging and audit.

### 7.2 Data Structure

```python
@dataclass
class LLMRecorder:
    log_path: Optional[Path] = None
    verbose_log_path: Optional[Path] = None
    session_timestamp: Optional[str] = None
    interactions: List[Dict[str, object]] = field(default_factory=list)
```

### 7.3 Recording Format

**JSON Log** (`llm_interactions_*.json`):
```json
{
  "session_info": {
    "timestamp": "20251014_103000",
    "total_interactions": 4,
    "total_time": 180.5
  },
  "interactions": [
    {
      "timestamp": "2025-10-14T10:30:00",
      "stage": "Intent Analysis",
      "prompt": "Analyze this building analysis request...",
      "response": "{\"required_solvers\": [\"geometry\", \"cfd\"]}",
      "elapsed_time": 45.2,
      "prompt_length": 1099,
      "response_length": 1167,
      "metadata": {"agent": "intelligent_building_agent"}
    }
  ]
}
```

**Verbose Text Log** (`llm_verbose_log_*.txt`):
```
[Stage] Intent Analysis @ 2025-10-14T10:30:00
[Prompt]
SystemMessage: You are an expert in building performance analysis.
HumanMessage: Analyze this building analysis request...

[Inference]
Why these solvers are needed...

[Response]
{"required_solvers": ["geometry", "cfd"], ...}
--------------------------------------------------------------------------------
```

### 7.4 Recording Integration

Each agent uses `_invoke_llm` or `_invoke_with_logging` to record interactions:

```python
def _invoke_llm(self, stage: str, messages: List[BaseMessage]):
    """Call the LLM and persist prompt/response metadata."""
    start = time.time()
    response = self.llm.invoke(messages)
    if self.llm_recorder:
        prompt_text = "\n\n".join(
            f"{msg.__class__.__name__}: {getattr(msg, 'content', '')}" 
            for msg in messages
        )
        self.llm_recorder.record(
            stage=stage,
            prompt=prompt_text,
            response=response.content,
            elapsed_time=time.time() - start,
            metadata={"agent": "intelligent_building_agent"},
        )
    return response
```

---

## 8. Material Tuning Pipeline

### 8.1 Overview

The material tuning pipeline enables automated optimization of building surface materials (albedo, emissivity) to improve thermal comfort and reduce cooling loads.

**Location**: `full_analysis_with_recording_en.py` → `run_material_tuning_test()`

### 8.2 Pipeline Flow

```
┌──────────────────────────────────────────────────────────────┐
│                   Material Tuning Pipeline                    │
├──────────────────────────────────────────────────────────────┤
│                                                               │
│  1. BASELINE PASS                                             │
│     └─► Run CFD+Solar with default materials                  │
│     └─► Collect baseline_metrics (cooling_kWh, PET hotspots)  │
│                                                               │
│  2. PROPOSAL GENERATION                                       │
│     └─► _propose_material_overrides(baseline_metrics)         │
│     └─► Increase albedo (roof: 0.72, wall: 0.55, ground: 0.25)│
│     └─► Maintain high emissivity (≥0.93)                      │
│     └─► Identify target buildings from hotspots               │
│                                                               │
│  3. TUNED PASS                                                │
│     └─► Run CFD+Solar with proposed materials                 │
│     └─► Reuse geometry/RT cache from baseline                 │
│     └─► Collect tuned_metrics                                 │
│                                                               │
│  4. COMPARISON                                                │
│     └─► _compare_material_runs(baseline, tuned)               │
│     └─► Calculate Δ cooling kWh, Δ PET max                    │
│     └─► Per-building delta analysis                           │
│                                                               │
└──────────────────────────────────────────────────────────────┘
```

### 8.3 Material Override Heuristics

```python
def _propose_material_overrides(metrics: dict, baseline_materials: dict) -> dict:
    """Heuristic: raise albedo on roofs/walls/ground and emissivity on roofs/walls."""
    reco = dict(baseline_materials)
    
    # Boost reflectance to cut solar gains
    reco["albedo_roof"] = max(baseline["albedo_roof"], 0.72)   # Cool roof
    reco["albedo_wall"] = max(baseline["albedo_wall"], 0.55)   # Light façade
    reco["albedo_ground"] = max(baseline["albedo_ground"], 0.25)  # Light pavers
    
    # Maintain high emissivity for longwave release
    reco["emissivity_roof"] = max(baseline["emissivity_roof"], 0.93)
    reco["emissivity_wall"] = max(baseline["emissivity_wall"], 0.94)
    
    # Identify target buildings from cooling load + hotspot analysis
    targets = _material_targets_from_metrics(metrics)
    
    return {
        "materials": reco,
        "targets": targets,
        "rationale": [...],
        "material_selection": {...}
    }
```

### 8.4 Output Files

| File | Content |
|------|---------|
| `material_tuning_plan.json` | Proposed materials, targets, rationale |
| `material_tuning_comparison.json` | Before/after metrics delta |
| `material_tuning_diff.txt` | Human-readable diff summary |

---

## 9. Data Structures & State Management

### 9.1 IntelligentAgentState

**Location**: `intelligent_building_agent.py`

```python
@dataclass
class IntelligentAgentState:
    """State for intelligent agent workflow"""
    request: AnalysisRequest = None
    building_analysis: str = ""
    required_solvers: List[str] = None      # ['geometry', 'cfd', 'solar', 'query']
    solver_parameters: Dict[str, Any] = None # LLM-suggested params
    solver_results: Dict[str, Any] = None    # Results from each solver
    external_parameters: Dict[str, Any] = None  # NEA weather-derived params
    weather_snapshot: Dict[str, Any] = None  # Raw NEA API response
    final_response: str = ""
    error_message: str = ""
    output_directory: str = ""
    stage: str = "init"  # init → intent_analysis → geometry → solvers → integration → complete
    llm_log_file: str = ""
    llm_text_log_file: str = ""
    runnable_config: Optional[RunnableConfig] = None
    resolved_time: Optional[str] = None      # ISO timestamp for simulation
```

### 9.2 AnalysisRequest

```python
@dataclass
class AnalysisRequest:
    """User's analysis request"""
    query: str
    stl_directory: str
    user_parameters: Dict[str, Any] = None
```

### 9.3 Solver Result Structure

```python
# Example solver_results["cfd"]
{
    "success": True,
    "backend": "coupled_UrGen_v1",
    "mode": "cfd",
    "output_directory": "/path/to/output",
    "work_directory": "/path/to/rt_cache",
    "parameters": {...},  # CFDParameters as dict
    "artifacts": {
        "screenshots": [...],
        "vtk_files": [...],
        "data_files": [...],
        "log_files": [...],
        "all_files": [...]
    },
    "visualization_files": [...],
    "data_files": [...],
    "analysis_metrics": {
        "cooling_energy": {
            "total_kWh": 1234.5,
            "per_building_kWh": {"b000": 100, "b001": 200, ...},
            "per_building_max_hourly_kw": {...}
        },
        "ground_hotspots": [
            {
                "pet_c": 42.5,
                "location": [10.0, 20.0, 2.0],
                "time": "15:00",
                "nearest_buildings": ["b005", "b006"],
                "meteorology": {"wind_speed_ms": 2.0, "dni": 800}
            }
        ]
    },
    "pet_time_summary": [...],
    "mrt_time_summary": [...],
    "pet_time_buckets": {
        "morning": {...},
        "noon": {...},
        "afternoon": {...},
        "evening": {...}
    },
    "coupled_run": True
}
```

---

## 10. Solver Backends

### 10.1 coupled_UrGen_v1

**Location**: `coupled_UrGen_v1/coupled_UrGen_.py`

**Purpose**: High-fidelity coupled CFD + radiation simulation engine.

**Key Function**:
```python
def main_coupled_run(
    sim_year: int,
    sim_month: int,
    sim_day: int,
    dt_hours: float,
    common_stl_dir: str,
    weather_csv_path: str,
    work_dir: str,
    output_dir: str,
    wind_dir_override: Optional[float] = None,
    wind_speed_override: Optional[float] = None,
    air_temp_override: Optional[float] = None,
    rh_override: Optional[float] = None,
    run_cfd: bool = True,
    run_radiation: bool = True,
    vedo_display_mode: str = "off",
    # ... material parameters ...
):
    """
    Main entry point for coupled CFD + radiation simulation.
    
    Outputs:
    - VTK files: PET, MRT, wind speed, temperature fields
    - PNG: Visualization screenshots
    - CSV: Building summaries, receptor data
    - JSON: analysis_metrics.json with aggregated results
    """
```

### 10.2 Output Artifacts

```
output_dir/
├── vtk_files/
│   ├── pet_on_mesh_0900.vtk
│   ├── pet_on_mesh_1200.vtk
│   ├── pet_on_mesh_1500.vtk
│   ├── mrt_on_mesh_*.vtk
│   └── ...
├── screenshots/
│   ├── cfd_field_summary.png
│   └── cfd_distributions.png
├── data/
│   ├── receptors_field.csv
│   └── building_wind_summary.csv
├── analysis_metrics.json
├── iwec_time_series_used.json
└── run.log
```

---

## 11. Visualization Pipeline

### 11.1 Geometry Visualizations

**Top View with Building IDs**:
```python
def _generate_topview_with_ids(
    footprints: List[Tuple[float, float, float, float, float, float, str]],
    output_path: str,
    title: str = "Top View with Building IDs"
):
    """
    Render a top-view plot with building footprints and ID labels.
    Uses matplotlib Rectangle patches for each building.
    """
```

**STL Agent Orthographic Views**:
- Generated by LLM-produced matplotlib code
- Front view (XZ), Side view (YZ), Top view (XY)

### 11.2 CFD Visualizations

| File | Content |
|------|---------|
| `cfd_field_summary.png` | 3-panel heatmap (wind speed, temperature, humidity) |
| `cfd_distributions.png` | Histograms for each field |

### 11.3 Solar Visualizations

| File | Content |
|------|---------|
| `solar_surface_snapshot.png` | Scatter plot colored by shortwave flux |
| `solar_surface_heatmap.png` | Gridded heatmap with building masks |
| `solar_building_summary.png` | Bar charts per building |

### 11.4 PET/MRT Time Buckets

The system summarizes thermal comfort indices across the simulation day:

```python
def _bucket_time_summary(summaries: List[Dict]) -> Dict[str, Optional[Dict]]:
    """
    Bucket time summaries into morning/noon/afternoon/evening.
    
    Returns:
        {
            "morning": {"time_token": "0900", "max_value": 38.5, "location": [...], "building_id": "b005"},
            "noon": {...},
            "afternoon": {...},
            "evening": {...}
        }
    """
```

---

## 12. Configuration System

### 12.1 config.py

```python
# Required
OPENAI_API_KEY = "sk-..."

# LangSmith Observability
LANGSMITH_API_KEY = "lsv2_..."
LANGSMITH_ENDPOINT = "https://api.smith.langchain.com"
LANGSMITH_PROJECT = "IntelligentBuildingAgent"

# Model Configuration
DEFAULT_MODEL = "GPT-5.1"
TEMPERATURE = 0.1
```

### 12.2 solver_parameters.json

```json
{
  "cfd": {
    "wind_speed": 1.0,
    "wind_direction": 45.0,
    "height": 2.0,
    "temperature": 30.0,
    "humidity": 70.0,
    "voxel_pitch": 4.0,
    "buffer_ratio": 0.10,
    "alpha_t": 1.5,
    "alpha_rh": 8.0,
    "building_radius": 100.0
  },
  "solar": {
    "time": "2025-10-04 14:00:00+08:00",
    "latitude": 1.3521,
    "longitude": 103.8198,
    "elevation": 15.0,
    "DNI": 800.0,
    "DHI": 180.0,
    "rays_per_receiver": 64,
    "ground_buffer": 20.0,
    "ground_res": 25.0,
    "receiver_offset": 0.1
  }
}
```

### 12.3 CLI Options

```bash
python full_analysis_with_recording_en.py \
    --config solver_parameters.json \        # Custom config file
    --no-llm-params \                        # Disable LLM suggestions
    --stl-directory /path/to/stl \           # STL file location
    --tests 1 2 5 \                          # Run specific tests
    --material-tuning                        # Enable material optimization
```

---

## Appendix A: Seasonal Test Definitions

| Test | Scenario | Key Parameters |
|------|----------|----------------|
| 1 | NE Monsoon Wet Phase (Dec) | Wind: 12 m/s @ 25°, T=26°C, RH=92% |
| 2 | NE Monsoon Dry Phase (Feb) | DNI=850, DHI=110, Wind: 7 m/s @ 35° |
| 3 | Inter-monsoon (Apr) | T=32°C, RH=75%, Variable winds |
| 4 | SW Monsoon Sumatra Squall (Jul) | Wind: 17 m/s @ 190°, T=28°C |
| 5 | Fully Coupled Audit | Combined CFD+Solar, April conditions |
| 5m | Material Tuning Loop | Test 5 + baseline/tuned comparison |

---

## Appendix B: Key Dependencies

```
langchain-openai>=0.1.0
langgraph>=0.0.1
langsmith>=0.0.1
openai>=1.0.0
numpy>=1.24.0
pandas>=2.0.0
matplotlib>=3.7.0
trimesh>=4.0.0
scipy>=1.10.0
pvlib>=0.10.0
requests>=2.31.0
```

---

## Appendix C: Error Handling

The system implements comprehensive error handling:

1. **Stage-level error routing**: Each LangGraph node can route to `error_handler`
2. **Solver graceful degradation**: Failed solvers return `{"success": False, "error": ...}`
3. **Parameter validation**: Invalid JSON configs are caught at load time
4. **Weather API fallback**: NEA fetch failures use IWEC defaults
5. **LLM parsing recovery**: Malformed LLM JSON responses trigger fallback logic

---

*Document Version: 1.0*  
*Last Updated: January 2026*  
*Author: Xinyu Yang

# Intelligent Building Analysis Agent

An LLM-orchestrated multi-agent system for urban microclimate analysis. The framework interprets natural-language queries, selects appropriate physics solvers (CFD, solar radiation), merges parameters from multiple sources, executes coupled simulations, and generates narrative reports with per-building metrics.

## Architecture

```
                         IntelligentBuildingAgent (Orchestrator)
                              LangGraph State Machine
 ┌───────────────┐   ┌──────────────┐   ┌───────────────┐   ┌────────────────┐
 │ Intent        │──▶│ Geometry     │──▶│ Solver        │──▶│ Result         │
 │ Analyzer      │   │ Analyzer     │   │ Orchestrator  │   │ Integrator     │
 └───────────────┘   └──────────────┘   └───────────────┘   └────────────────┘
       │                    │                  │                     │
       ▼                    ▼                  ▼                     ▼
                         LLM (GPT via LangChain)
                                   │
         ┌─────────────┬───────────┼───────────┬─────────────┐
         ▼             ▼           ▼           ▼             ▼
   STL Analysis   Building    CFD Solver   Solar Solver   NEA Weather
     Agent        Query Agent   Agent        Agent         Client
```

**Agents:** Orchestrator · STL Analysis · Building Query · CFD Solver · Solar Solver

**Backend:** coupled_UrGen_v1 (voxel CFD + Monte Carlo radiation)

## Quick Start

```bash
# 1. Clone and enter the repo
git clone https://github.com/<your-org>/intelligent-building-agent.git
cd intelligent-building-agent

# 2. Create virtual environment and install dependencies
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt

# 3. Configure API key
cp config_template.py config.py
# Edit config.py and set your OPENAI_API_KEY

# 4. Run an analysis
python full_analysis_with_recording_en.py --tests 5
```

## Project Structure

```
├── intelligent_building_agent.py   # Orchestrator agent (LangGraph)
├── stl_agent.py                    # STL geometry analysis agent
├── query_agent.py                  # Building Q&A agent
├── weather_client.py               # NEA weather API client
├── llm_recorder.py                 # LLM interaction logger
├── full_analysis_with_recording_en.py  # CLI test runner
│
├── wrapper/
│   ├── cfd_solver.py               # CFD parameter adapter
│   ├── solar_solver.py             # Solar parameter adapter
│   └── artifact_utils.py           # Output file collector
│
├── coupled_UrGen_v1/               # Physics simulation backend
│   ├── coupled_UrGen_.py           # Coupled CFD + radiation engine
│   └── SGP_Singapore_486980_IWEC.csv  # IWEC weather data (Singapore)
│
├── config_template.py              # API key template (copy to config.py)
├── solver_parameters.json          # Default solver parameters
├── config_examples/                # Seasonal scenario presets
├── parameter_examples/             # Example parameter snapshots
├── example_stl/                    # Example building geometries
│
├── setup.sh                        # Automated setup script
├── requirements.txt                # Python dependencies
└── Agent.md                        # Detailed implementation docs
```

## Parameter Priority Chain

Parameters are resolved through a strict four-level priority (lowest to highest):

| Priority | Source | Snapshot File |
|----------|--------|---------------|
| 1 | JSON config (`solver_parameters.json`) | — |
| 2 | LLM suggestions (intent analysis) | `llm_suggested_parameters.json` |
| 3 | NEA live weather API | `external_weather_snapshot.json` |
| 4 | User overrides (highest) | `final_cfd_parameters.json` |

All parameter snapshots are saved per run for full auditability.

## Usage

### Python API

```python
from intelligent_building_agent import IntelligentBuildingAgent

agent = IntelligentBuildingAgent(
    api_key="sk-...",
    config_file="solver_parameters.json"
)

result = agent.analyze(
    query="Assess wind comfort and solar exposure for this district in April",
    stl_directory="example_stl/town_00002_500_1.352_103.719_-4787_-1522",
    user_parameters={
        "cfd": {"temperature": 32.0, "humidity": 75.0, "height": 2.0},
        "solar": {"DNI": 650.0, "DHI": 260.0}
    }
)

print(result["response"])  # LLM-generated narrative
```

### CLI Test Runner

```bash
# Run all 5 seasonal tests
python full_analysis_with_recording_en.py --tests all

# Run specific tests
python full_analysis_with_recording_en.py --tests 1 5

# Disable LLM parameter suggestions (use only config + user params)
python full_analysis_with_recording_en.py --no-llm-params --tests 5

# Run with material tuning (baseline + tuned comparison)
python full_analysis_with_recording_en.py --material-tuning --tests 5m
```

## Seasonal Test Scenarios

| Test | Scenario | Key Conditions |
|------|----------|----------------|
| 1 | NE Monsoon Wet (Dec) | 12 m/s NE wind, 26 °C, 92% RH |
| 2 | NE Monsoon Dry (Feb) | DNI 850 W/m², 7 m/s, 29 °C |
| 3 | Inter-monsoon (Apr) | Variable winds, 32 °C, thunderstorms |
| 4 | SW Monsoon Squall (Jul) | 17 m/s southerly gusts, 28 °C |
| 5 | Fully Coupled Audit | Combined CFD + Solar, April conditions |
| 5m | Material Tuning | Test 5 + baseline/tuned comparison |

## Output Structure

Each run produces a self-contained directory:

```
<run_output>/
├── llm_interactions_*.json         # All LLM prompts & responses
├── llm_suggested_parameters.json   # LLM parameter suggestions
├── external_weather_snapshot.json  # NEA weather data
├── final_cfd_parameters.json       # Merged CFD params with provenance
├── geometry_cache.json             # Building footprints & envelopes
├── pet_mrt_time_buckets.json       # Thermal comfort time series
└── cfd_solar/
    ├── analysis_metrics.json       # Cooling kWh, hotspots, per-building
    ├── vtk_files/                  # PET, MRT, wind, temperature fields
    └── screenshots/                # Summary heatmaps
```

## Technology Stack

| Component | Technology |
|-----------|------------|
| LLM | OpenAI GPT (via LangChain) |
| Workflow | LangGraph (state-machine orchestration) |
| Observability | LangSmith (optional) |
| Physics | coupled_UrGen_v1 (CFD + radiation) |
| 3D Processing | trimesh |
| Weather API | data.gov.sg (NEA Singapore) |

## License

TBD

## Citation

If you use this work, please cite:

```
@article{yang2026intelligent,
  title={...},
  author={Yang, Xinyu and ...},
  year={2026}
}
```

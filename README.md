<p align="center">
  <h1 align="center">Urban Cooling Agent</h1>
  <p align="center">
    AI-driven urban microclimate simulation platform<br/>
    CFD · Solar Irradiance · Thermal Comfort (PET/MRT)
  </p>
</p>

<p align="center">
  <a href="https://pgupdn.github.io/urban-cooling-agent/">Live Demo</a> ·
  <a href="#getting-started">Getting Started</a> ·
  <a href="#api-reference">API Reference</a>
</p>

---

An end-to-end platform for urban microclimate analysis in Singapore. Describe an analysis scenario in plain English, select a district on an interactive map, and the system automatically resolves live weather, prepares 3D building geometry, runs coupled CFD + solar solvers, and delivers a narrative report with thermal comfort metrics — all through a single conversational interface.

## Demo

| Chat | Map | Dashboard |
|------|-----|-----------|
| Describe a scenario in natural language. The agent classifies intent, asks for missing details, and confirms before running. | Select from 8 preset Singapore districts or draw a custom rectangle. Building count is shown in real time. | PET/MRT heatmaps, temporal profiles, CFD parameters, and downloadable artifacts (VTK, CSV). |

## Key Features

- **Natural language orchestration** — an LLM agent classifies user intent, extracts simulation parameters, and manages the full analysis lifecycle
- **Smart clarification flow** — if the time period is missing, the agent asks before committing compute; the user confirms the scenario summary before execution
- **Interactive region selection** — Leaflet map with 8 Singapore district presets and freehand rectangle drawing over 154k buildings
- **Real-time progress tracking** — live solver status, weather data, geometry statistics, and parameter updates streamed to the UI during simulation
- **Comprehensive results** — PET heatmaps, MRT temporal profiles, wind field visualizations, downloadable VTK meshes and CSV data
- **Scenario comparison** — side-by-side comparison of multiple simulation runs
- **Persistent state** — chat history, selected region, and active tab survive page refreshes

## Architecture

```
                        ┌─────────────────────────────────┐
                        │     Frontend (React + Vite)      │
                        │  Chat · Map · Dashboard · Compare│
                        └──────┬──────────────┬────────────┘
                               │              │
                    REST API   │              │  REST API
                               ▼              ▼
                     ┌──────────────┐  ┌──────────────┐
                     │ urban_agent  │  │ sg-3d-export │
                     │  (FastAPI)   │  │  (FastAPI)   │
                     │              │  │              │
                     │ LangGraph    │  │ BuildingIndex│
                     │ Intent → CFD │  │ 154k STLs   │
                     │ Solar → PET  │  │ Region clip  │
                     │ MRT → Report │  │              │
                     └──────────────┘  └──────────────┘
                        port 8001         port 8000
```

This is a **monorepo** containing all three services:

```
urban-cooling-agent/
│
├── App.tsx, components/, services/    # React frontend
├── vite.config.ts, index.html         # Vite build config
│
└── backend/
    ├── urban_agent/                   # Simulation agent
    │   ├── api_server.py              # FastAPI REST wrapper
    │   ├── intelligent_building_agent.py  # LangGraph multi-node agent
    │   ├── coupled_UrGen_v1/          # CFD, radiation, PET/MRT solver core
    │   ├── wrapper/                   # Solver interface wrappers
    │   ├── weather_client.py          # NEA real-time weather API
    │   ├── example_stl/               # Sample district (95 buildings)
    │   └── config_template.py         # API key template
    │
    └── sg-3d-export/                  # Building geometry service
        ├── main.py                    # FastAPI REST server
        ├── services/
        │   ├── building_index.py      # Spatial index over 154k buildings
        │   ├── stl_processor.py       # Per-building STL clipping
        │   └── stl_service.py         # Merge & export utilities
        └── models.py                  # District / building data models
```

### Simulation Pipeline

```
User prompt
    │
    ▼
Intent Classification (LLM)
    │
    ├── Chat → conversational reply
    ├── Clarify → ask for time period
    └── Analyze → scenario confirmation
                      │
                      ▼  (user confirms)
              ┌───────┴────────┐
              ▼                ▼
      Intent Analyzer    Geometry Analyzer
      · resolve datetime · parse STL files
      · fetch NEA weather· compute envelopes
      · select solvers   · building statistics
              │                │
              └───────┬────────┘
                      ▼
            Solver Orchestrator
            · coupled CFD (wind, temperature)
            · solar irradiance (DNI ray-tracing)
            · PET / MRT thermal comfort
                      │
                      ▼
            Result Integrator
            · narrative report
            · heatmaps & visualizations
            · VTK meshes, CSV exports
```

## Getting Started

### Prerequisites

| Tool | Version | Purpose |
|------|---------|---------|
| Node.js | 18+ | Frontend build |
| Python | 3.10+ | Backend services |
| OpenAI API key | — | LLM agent orchestration |

### 1. Clone

```bash
git clone https://github.com/PgUpDn/urban-cooling-agent.git
cd urban-cooling-agent
```

### 2. Frontend

```bash
npm install
npm run dev                    # → http://localhost:3000
```

### 3. Simulation Backend (`urban_agent`)

```bash
cd backend/urban_agent
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt

cp config_template.py config.py
# Edit config.py → set your OPENAI_API_KEY

python api_server.py           # → http://localhost:8001
```

### 4. Building Geometry Backend (`sg-3d-export`)

```bash
cd backend/sg-3d-export
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt

python main.py                 # → http://localhost:8000
```

> **Note**: The building STL dataset (~730 MB, 154k files) is not included in this repo due to size.
> Contact the author for access, or point `STL_DIR` at your own geometry data.

### Environment Variables

| Variable | Required | Description |
|----------|----------|-------------|
| `OPENAI_API_KEY` | Yes | Set in `backend/urban_agent/config.py` |
| `GEMINI_API_KEY` | No | Optional chat fallback (frontend `.env.local`) |
| `BACKEND_API_URL` | For deployment | Public backend URL (GitHub repo secret) |
| `VITE_BASE_PATH` | For deployment | Base path for GitHub Pages |

## Deployment

### GitHub Pages

Pushes to `main` trigger automatic deployment via GitHub Actions. Set `BACKEND_API_URL` as a repository secret pointing to your hosted backend.

### Self-hosted (nginx)

A reference nginx configuration is included in `nginx-cooling.conf`:

```
/cooling/          →  static frontend (dist/)
/cooling/api/      →  urban_agent:8001
/cooling/geo-api/  →  sg-3d-export:8000
```

## API Reference

### Simulation Service — `urban_agent` (`:8001`)

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/health` | `GET` | Health check and agent readiness |
| `/api/chat` | `POST` | Intent classification → chat / clarify / confirm / analyze |
| `/api/simulation/start` | `POST` | Launch the full simulation pipeline |
| `/api/simulation/{id}/status` | `GET` | Poll execution progress and current stage |
| `/api/simulation/{id}/messages` | `GET` | Incremental status messages |
| `/api/simulation/{id}/params` | `GET` | Live solver parameters as they resolve |
| `/api/simulation/{id}/results` | `GET` | Final results, metrics, and artifact URLs |
| `/api/files/{path}` | `GET` | Serve generated artifacts (images, VTK, CSV) |

### Building Geometry Service — `sg-3d-export` (`:8000`)

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/region/count` | `GET` | Count buildings within lat/lon bounds |
| `/api/region/prepare` | `POST` | Prepare per-building STL directory for simulation |
| `/api/districts` | `GET` | List available Singapore districts |
| `/api/district/{id}/buildings` | `GET` | Query buildings in a specific district |
| `/api/export/clip` | `POST` | Clip and export merged STL for given bounds |

## Tech Stack

| Layer | Technology |
|-------|------------|
| Frontend | React 19 · TypeScript · Tailwind CSS · Vite 6 |
| Maps | Leaflet · Leaflet.draw |
| Charts | Recharts |
| Agent | LangGraph · OpenAI GPT-4o |
| Backends | FastAPI · Python 3.12 |
| Solvers | Custom CFD · Solar irradiance (ray-tracing) · PET/MRT |
| Geometry | 154,667 Singapore building models (STL) |
| CI/CD | GitHub Actions → GitHub Pages |

## How It Works

1. **User describes a scenario** — *"Run a coupled CFD + solar audit for the inter-monsoon period, emphasizing district comfort and energy demand"*

2. **LLM classifies intent** — the agent determines this is a simulation request, extracts temporal parameters (inter-monsoon → March), and checks if enough information is provided

3. **Clarification (if needed)** — if the month/day is missing, the agent asks; otherwise it presents a scenario summary for user confirmation

4. **Pipeline execution** — upon confirmation, the LangGraph agent orchestrates four sequential nodes:
   - **Intent Analyzer** — resolves datetime, fetches live weather from NEA, selects required solvers
   - **Geometry Analyzer** — parses the STL building files, computes footprints and building envelopes
   - **Solver Orchestrator** — runs coupled CFD (wind + temperature) and solar irradiance solvers, computes PET and MRT
   - **Result Integrator** — generates a narrative report, heatmap visualizations, and downloadable artifacts

5. **Results dashboard** — the frontend displays PET/MRT temporal profiles, heatmaps, wind fields, and provides VTK/CSV downloads

## Author

**Dr. Xinyu Yang**
A\*STAR Institute of High Performance Computing (IHPC), Singapore

## License

MIT

# Urban Cooling Agent

AI-driven urban microclimate simulation — **CFD wind analysis**, **solar irradiance modelling**, and **thermal comfort (PET/MRT) assessment** for urban districts in Singapore, all driven through natural language.

**Live demo**: https://pgupdn.github.io/urban-cooling-agent

---

## Overview

1. **Chat with the agent** — describe what you want to analyse (e.g. *"Run a coupled CFD + solar audit for the inter-monsoon period"*)
2. **Select a region** — pick a preset Singapore district or draw a rectangle on the Map tab
3. **Automatic pipeline** — the agent resolves weather data, prepares geometry, runs solvers, and generates a narrative report
4. **Explore results** — interactive dashboard with PET heatmaps, temporal profiles, and downloadable artifacts (VTK, CSV)

## Architecture

```
urban-cooling-agent/
├── frontend/          ← React + Vite (this repo root)
│   ├── App.tsx
│   ├── components/
│   ├── services/
│   └── ...
└── backend/
    ├── urban_agent/   ← LLM orchestration + CFD/solar solvers
    │   ├── api_server.py          FastAPI wrapper (port 8001)
    │   ├── intelligent_building_agent.py   LangGraph agent
    │   ├── coupled_UrGen_v1/      Solver core (CFD, radiation, PET/MRT)
    │   ├── wrapper/               Solver wrappers
    │   └── ...
    └── sg-3d-export/  ← Singapore building index + STL export
        ├── main.py                FastAPI server (port 8000)
        ├── services/
        │   ├── building_index.py  Spatial index for 154k buildings
        │   ├── stl_processor.py   STL clipping & merging
        │   └── ...
        └── ...
```

### Service overview

| Service | Port | Description |
|---------|------|-------------|
| **Frontend** | 3000 | React UI — chat, map, dashboard, comparison |
| **urban_agent** | 8001 | LLM-orchestrated CFD/solar/PET simulation pipeline |
| **sg-3d-export** | 8000 | Singapore building index, per-building STL export, region preparation |

### Request flow

```
User prompt  →  Frontend  →  POST /api/chat (urban_agent:8001)
                                  │
                         LLM classifies intent
                          ├── chat → reply
                          ├── clarify → ask for time period
                          └── analyze → confirm scenario
                                  │
                        POST /api/simulation/start
                                  │
              ┌───────────────────┼───────────────────┐
              ▼                   ▼                   ▼
        Intent Analyzer    Geometry Analyzer    Solver Orchestrator
        (weather, params)  (STL parsing)        (CFD + Solar)
              │                                       │
              └──────────── Result Integrator ─────────┘
                                  │
                          GET /api/simulation/{id}/results
                                  │
                              Dashboard
```

The **Map** tab communicates with `sg-3d-export` to count buildings in a region and prepare a directory of individual STL files that `urban_agent` consumes.

---

## Quick Start

### Prerequisites

- **Node.js** 18+ / npm
- **Python** 3.10+
- **OpenAI API key** (for urban_agent LLM)

### 1. Frontend

```bash
npm install
npm run dev          # http://localhost:3000
```

### 2. urban_agent backend

```bash
cd backend/urban_agent
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt

# Configure API key
cp config_template.py config.py
# Edit config.py — set OPENAI_API_KEY

python api_server.py   # http://localhost:8001
```

### 3. sg-3d-export backend

```bash
cd backend/sg-3d-export
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt

# Download building data (not included due to size):
#   - exported_stls_blender_coords/   (154k individual STL files, ~730MB)
#   - building_data_final.csv         (~19MB)
#   - sg-building-binary.stl          (~275MB, optional merged STL)

python main.py         # http://localhost:8000
```

### All-in-one (on server)

```bash
# Start all three services:
cd backend/sg-3d-export && source .venv/bin/activate && python main.py &
cd backend/urban_agent  && source .venv/bin/activate && python api_server.py &
npm run dev &
```

### Environment Variables

| Variable | Where | Description |
|----------|-------|-------------|
| `OPENAI_API_KEY` | `backend/urban_agent/config.py` | Required for LLM orchestration |
| `GEMINI_API_KEY` | `.env.local` or env | Optional AI chat fallback |
| `BACKEND_API_URL` | GitHub Secret | Public backend URL for GitHub Pages |
| `VITE_BASE_PATH` | GitHub Actions | Base path for deployment (e.g. `/urban-cooling-agent/`) |

---

## Features

- **Natural language interaction** — LLM classifies intent and routes to chat or simulation
- **Temporal clarification** — agent asks for time period if missing before running solvers
- **Scenario confirmation** — user reviews the proposed scenario before committing compute
- **Interactive region selection** — Leaflet map with 8 Singapore district presets and freehand rectangle
- **Real-time progress** — live parameter updates and status messages during simulation
- **Results dashboard** — PET heatmaps, temporal bar charts, CFD parameters, downloadable VTK/CSV
- **Scenario comparison** — side-by-side comparison of different simulation runs
- **State persistence** — chat history, selected region, and active tab survive page refresh
- **Rate limiting** — per-IP request limits on the backend API

## Deployment

### GitHub Pages (frontend only)

Pushes to `main` trigger automatic deployment via GitHub Actions. Set `BACKEND_API_URL` as a repository secret to point at your hosted backend.

### Production with nginx

Use `nginx-cooling.conf` as a reference. It serves the frontend under `/cooling/`, proxies `/cooling/api/` to `urban_agent:8001`, and `/cooling/geo-api/` to `sg-3d-export:8000`.

---

## Backend API Reference

### urban_agent (port 8001)

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/health` | GET | Health check |
| `/api/chat` | POST | Intent classification, clarify, confirm, or chat |
| `/api/simulation/start` | POST | Launch simulation pipeline |
| `/api/simulation/{id}/status` | GET | Poll progress |
| `/api/simulation/{id}/messages` | GET | Stream status messages |
| `/api/simulation/{id}/params` | GET | Live solver parameters |
| `/api/simulation/{id}/results` | GET | Final results and artifacts |
| `/api/files/{path}` | GET | Serve result files (images, VTK, CSV) |
| `/api/stl-directories` | GET | List available STL directories |

### sg-3d-export (port 8000)

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/region/count` | GET | Count buildings in lat/lon bounds |
| `/api/region/prepare` | POST | Create STL directory for simulation |
| `/api/districts` | GET | List Singapore districts |
| `/api/district/{id}/buildings` | GET | Buildings in a district |
| `/api/export/clip` | POST | Clip and export STL for bounds |

## Tech Stack

| Layer | Technology |
|-------|------------|
| UI | React 19, TypeScript, Tailwind CSS |
| Build | Vite 6 |
| Maps | Leaflet + Leaflet.draw |
| Charts | Recharts |
| Agent | LangGraph + OpenAI GPT-4o |
| Backends | FastAPI (Python 3.12) |
| Solvers | Custom CFD, solar irradiance, PET/MRT |
| Data | 154,667 Singapore building STLs |

## Author

**Dr. Xinyu Yang** — A\*STAR Institute of High Performance Computing (IHPC)

## License

MIT

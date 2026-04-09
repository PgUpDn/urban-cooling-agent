<div align="center">

# Urban Cooling Agent

**Talk to your city. Simulate its climate.**

[![Live Demo](https://img.shields.io/badge/demo-live-brightgreen?style=flat-square)](https://pgupdn.github.io/urban-cooling-agent/)
[![License: MIT](https://img.shields.io/badge/license-MIT-blue?style=flat-square)](LICENSE)
[![React](https://img.shields.io/badge/React-19-61dafb?style=flat-square&logo=react&logoColor=white)](https://react.dev)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.115-009688?style=flat-square&logo=fastapi&logoColor=white)](https://fastapi.tiangolo.com)
[![LangGraph](https://img.shields.io/badge/LangGraph-agent-purple?style=flat-square)](https://langchain-ai.github.io/langgraph/)

<br/>

*Describe an urban scenario in plain English. Select a district on the map.*
*The agent fetches live weather, prepares 3D geometry, runs coupled CFD + solar solvers,*
*and delivers a full thermal comfort report — automatically.*

<br/>

[Live Demo](https://pgupdn.github.io/urban-cooling-agent/) · [Quick Start](#quick-start) · [Architecture](#architecture) · [API Docs](#api-reference)

</div>

---

<br/>

## What It Does

> *"Run a coupled CFD + solar audit for the inter-monsoon period, emphasizing district comfort and energy demand"*

That's all it takes. The agent handles the rest:

| Step | What happens |
|:-----|:-------------|
| **Understand** | LLM parses your intent, extracts temporal & spatial parameters |
| **Clarify** | Asks for missing details (time period, location) before committing compute |
| **Confirm** | Presents a scenario summary — you approve before solvers run |
| **Simulate** | Coupled CFD wind field, solar irradiance ray-tracing, PET & MRT computation |
| **Report** | Narrative analysis, heatmaps, temporal profiles, downloadable VTK & CSV |

<br/>

## Features

<table>
<tr>
<td width="50%">

### Conversational Interface
Natural language input with intent classification. The agent knows when to chat, when to clarify, and when to simulate.

### Interactive Map
8 preset Singapore districts + freehand rectangle selection over **154,667 buildings**. Real-time building count as you draw.

### Live Progress
Watch solvers run in real time — weather data, geometry stats, and parameters stream to the UI as each pipeline stage completes.

</td>
<td width="50%">

### Results Dashboard
PET/MRT heatmaps, temporal bar charts, wind field parameters. All artifacts downloadable as VTK meshes or CSV.

### Scenario Comparison
Run multiple simulations and compare them side by side — different time periods, regions, or cooling strategies.

### Persistent Sessions
Chat history, selected region, simulation results, and active tab all survive page refreshes.

</td>
</tr>
</table>

<br/>

## Architecture

```mermaid
graph TB
  subgraph Frontend["Frontend — React · Vite · Tailwind · Leaflet"]
    Chat["💬 Chat"]
    Map["🗺️ Map"]
    Dash["📊 Dashboard"]
    Comp["🔀 Compare"]
  end

  subgraph Agent["urban_agent — FastAPI"]
    LG[LangGraph Agent]
    CFD[CFD Solver]
    Solar[Solar Solver]
    PET[PET / MRT]
    Weather[NEA Weather]
  end

  subgraph Geo["sg-3d-export — FastAPI"]
    Index[Building Index]
    STL["154k STLs"]
    Clip[Region Clip]
  end

  Chat & Map --> Agent
  Map --> Geo
  Agent --> Dash
  Geo --> Agent

  style Frontend fill:#f0f9ff,stroke:#3b82f6,stroke-width:2px
  style Agent fill:#faf5ff,stroke:#8b5cf6,stroke-width:2px
  style Geo fill:#f0fdf4,stroke:#22c55e,stroke-width:2px
```

### Simulation Pipeline

```mermaid
graph LR
  P["User Prompt"] --> IC["Intent\nClassification"]
  IC -->|chat| R1["💬 Reply"]
  IC -->|missing info| R2["❓ Clarify"]
  IC -->|ready| R3["✅ Confirm"]
  R3 --> IA["Intent Analyzer\n· datetime · weather\n· solver selection"]
  R3 --> GA["Geometry Analyzer\n· STL parsing\n· building envelopes"]
  IA & GA --> SO["Solver Orchestrator\n· CFD · Solar\n· PET / MRT"]
  SO --> RI["Result Integrator\n· report · heatmaps\n· VTK / CSV"]

  style P fill:#dbeafe,stroke:#3b82f6
  style IC fill:#f3e8ff,stroke:#8b5cf6
  style R1 fill:#f0fdf4,stroke:#22c55e
  style R2 fill:#fef9c3,stroke:#eab308
  style R3 fill:#f0fdf4,stroke:#22c55e
  style IA fill:#faf5ff,stroke:#8b5cf6
  style GA fill:#faf5ff,stroke:#8b5cf6
  style SO fill:#fef2f2,stroke:#ef4444
  style RI fill:#f0f9ff,stroke:#3b82f6
```

<br/>

## Quick Start

### Prerequisites

- **Node.js** 18+ &nbsp;·&nbsp; **Python** 3.10+ &nbsp;·&nbsp; **OpenAI API key**

### 1 &nbsp; Clone & install

```bash
git clone https://github.com/PgUpDn/urban-cooling-agent.git
cd urban-cooling-agent && npm install
```

### 2 &nbsp; Start the frontend

```bash
npm run dev
```

### 3 &nbsp; Start the simulation backend

```bash
cd backend/urban_agent
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp config_template.py config.py   # then set OPENAI_API_KEY
python api_server.py
```

### 4 &nbsp; Start the geometry backend

```bash
cd backend/sg-3d-export
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
python main.py
```

> [!NOTE]
> The building STL dataset (~730 MB, 154k files) is not bundled in this repo.
> Contact the author for access, or plug in your own geometry.

<br/>

## Configuration

| Variable | Required | Description |
|:---------|:--------:|:------------|
| `OPENAI_API_KEY` | ✅ | Set in `backend/urban_agent/config.py` |
| `GEMINI_API_KEY` | — | Optional chat fallback |
| `BACKEND_API_URL` | Deploy | Public backend URL (GitHub Actions secret) |
| `VITE_BASE_PATH` | Deploy | Subpath for GitHub Pages |

<br/>

## Deployment

**GitHub Pages** — pushes to `main` auto-deploy via GitHub Actions. Set `BACKEND_API_URL` as a repo secret.

**Self-hosted** — reference config in `nginx-cooling.conf`:

```
/cooling/          →  frontend static files
/cooling/api/      →  urban_agent backend
/cooling/geo-api/  →  sg-3d-export backend
```

<br/>

## API Reference

<details>
<summary><strong>Simulation Service</strong> — <code>urban_agent</code></summary>

<br/>

| Endpoint | Method | Description |
|:---------|:------:|:------------|
| `/api/health` | GET | Health check |
| `/api/chat` | POST | Intent classification → chat / clarify / confirm / analyze |
| `/api/simulation/start` | POST | Launch simulation pipeline |
| `/api/simulation/{id}/status` | GET | Poll progress |
| `/api/simulation/{id}/messages` | GET | Incremental status messages |
| `/api/simulation/{id}/params` | GET | Live solver parameters |
| `/api/simulation/{id}/results` | GET | Final results and artifacts |
| `/api/files/{path}` | GET | Serve generated files (images, VTK, CSV) |

</details>

<details>
<summary><strong>Geometry Service</strong> — <code>sg-3d-export</code></summary>

<br/>

| Endpoint | Method | Description |
|:---------|:------:|:------------|
| `/api/region/count` | GET | Count buildings in lat/lon bounds |
| `/api/region/prepare` | POST | Prepare per-building STL directory |
| `/api/districts` | GET | List Singapore districts |
| `/api/district/{id}/buildings` | GET | Buildings in a district |
| `/api/export/clip` | POST | Clip and export STL |

</details>

<br/>

## Tech Stack

| | |
|:--|:--|
| **Frontend** | React 19 · TypeScript · Tailwind CSS · Vite 6 · Leaflet · Recharts |
| **Agent** | LangGraph · OpenAI GPT-4o |
| **Backends** | FastAPI · Python 3.12 |
| **Solvers** | Custom CFD · Solar irradiance (ray-tracing) · PET/MRT |
| **Data** | 154,667 Singapore building models (STL) · NEA real-time weather |
| **CI/CD** | GitHub Actions → GitHub Pages |

<br/>

## Author

Dr. Xinyu Yang from A*STAR IHPC (yang_xinyu@a-star.edu.sg)

</div>

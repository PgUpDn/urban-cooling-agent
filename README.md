# Urban Cooling Agent

An AI-driven urban microclimate simulation platform that combines CFD wind analysis, solar irradiance modelling, and thermal comfort (PET/MRT) assessment for urban districts in Singapore.

Users interact through natural language — describe an analysis scenario, select a region on an interactive map, and the system orchestrates the full simulation pipeline automatically.

**Live demo**: [pgupdn.github.io/urban-cooling-agent](https://pgupdn.github.io/urban-cooling-agent/)

## What It Does

1. **Chat with the agent** — describe what you want to analyse (e.g. *"Run a coupled CFD + solar audit for the inter-monsoon period"*)
2. **Select a region** — pick a preset district or draw a rectangle on the Map tab to choose buildings
3. **Automatic pipeline** — the agent resolves weather data, prepares geometry, runs solvers, and generates a narrative report
4. **Explore results** — interactive dashboard with PET heatmaps, temporal profiles, and downloadable artifacts (VTK, CSV)

## Architecture

```
┌─────────────────────────────────────────────────┐
│  Frontend  (React + Vite, port 3000)            │
│  Chat │ Map (Leaflet) │ Dashboard │ Comparison  │
└──────┬──────────┬───────────────────────────────┘
       │          │
       ▼          ▼
  urban_agent    sg-3d-export
  (port 8001)    (port 8000)
  FastAPI         FastAPI
  LangGraph       BuildingIndex
  CFD / Solar     Per-building STL
  PET / MRT       Region prepare
```

| Service | Port | Role |
|---------|------|------|
| Frontend | 3000 | React UI (Vite dev server) |
| sg-3d-export | 8000 | Building index, region STL preparation |
| urban_agent | 8001 | LLM orchestration, CFD/solar solvers |

## Quick Start

### Prerequisites

- Node.js 18+
- Python 3.10+ with `urban_agent` and `sg-3d-export` backends installed

### Run all three services

```bash
bash ~/start_all.sh
```

Or start individually:

```bash
# 1. Building index backend (port 8000)
cd /home/ubuntu/sg-3d-export/backend && source .venv/bin/activate && python3 main.py

# 2. Simulation backend (port 8001)
cd /home/ubuntu/urban_agent && source .venv/bin/activate && python api_server.py

# 3. Frontend (port 3000)
cd /home/ubuntu/urban-cooling-frontend && npm install && npm run dev
```

Open [http://localhost:3000](http://localhost:3000).

### Environment Variables

Create `.env.local` (git-ignored):

```env
GEMINI_API_KEY=your_key        # Optional — Gemini chat fallback
BACKEND_API_URL=               # Leave empty for local dev (uses Vite proxy)
```

For GitHub Pages deployment, add these as **repository secrets** under Settings → Secrets → Actions.

## Project Structure

```
urban-cooling-frontend/
├── App.tsx                      # Root component, state, routing
├── components/
│   ├── ChatInterface.tsx        # Chat UI with confirm/clarify flow
│   ├── RegionSelect.tsx         # Leaflet map for area selection
│   ├── ParamSidebar.tsx         # Live simulation parameters
│   ├── ResultsDashboard.tsx     # Heatmaps, charts, artifacts
│   ├── ComparisonView.tsx       # Side-by-side scenario comparison
│   └── WorkflowSidebar.tsx      # Pipeline progress tracker
├── services/
│   ├── agentService.ts          # Backend API client
│   └── geminiService.ts         # Gemini AI fallback
├── types.ts                     # TypeScript interfaces
├── nginx-cooling.conf           # Production nginx config snippet
└── .github/workflows/deploy.yml # GitHub Pages CI/CD
```

## Key Features

- **Intent classification** — LLM determines if a message is chat or analysis request
- **Temporal clarification** — agent asks for time period if missing, before running
- **Scenario confirmation** — user reviews proposed scenario before committing compute
- **Custom region selection** — Leaflet map with district presets and freehand rectangle drawing
- **Per-building STL preparation** — symlinks individual building STLs for the solver
- **Real-time progress** — live parameter updates and status messages during simulation
- **State persistence** — chat history, selected region, and active tab survive page refresh

## Deployment

### GitHub Pages (static frontend only)

Pushes to `main` auto-deploy via GitHub Actions. The `VITE_BASE_PATH` in `deploy.yml` must match the repo name (`/urban-cooling-agent/`).

### Production with nginx

Copy `nginx-cooling.conf` into your nginx server block. It serves the built frontend under `/cooling/` and proxies API calls:

- `/cooling/api/` → `127.0.0.1:8001` (urban_agent)
- `/cooling/geo-api/` → `127.0.0.1:8000` (sg-3d-export)

## Tech Stack

- **React 19** + TypeScript + Vite 6
- **Tailwind CSS** (CDN) for styling
- **Leaflet** + Leaflet.draw for interactive maps
- **Recharts** for data visualisation
- **FastAPI** backends (urban_agent + sg-3d-export)
- **LangGraph** for agent orchestration
- **OpenAI GPT-4o** for intent classification and report generation

## Author

Dr. Xinyu Yang — A\*STAR IHPC (yang_xinyu@a-star.edu.sg)

## License

MIT

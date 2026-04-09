# Urban Cooling Agent

An AI-driven urban microclimate simulation platform that combines **CFD wind analysis**, **solar irradiance modelling**, and **thermal comfort (PET/MRT) assessment** for urban districts in Singapore.

Users interact through natural language — describe an analysis scenario, select a region on an interactive map, and the system orchestrates the full simulation pipeline automatically.

**Live demo**: [pgupdn.github.io/urban-cooling-agent](https://pgupdn.github.io/urban-cooling-agent/)

![React](https://img.shields.io/badge/React-19-blue) ![TypeScript](https://img.shields.io/badge/TypeScript-5.8-blue) ![Vite](https://img.shields.io/badge/Vite-6-purple) ![License](https://img.shields.io/badge/License-MIT-green)

## Overview

1. **Chat with the agent** — describe what you want to analyse (e.g. *"Run a coupled CFD + solar audit for the inter-monsoon period"*)
2. **Select a region** — pick a preset Singapore district or draw a rectangle on the Map tab to choose buildings
3. **Automatic pipeline** — the agent resolves weather data, prepares geometry, runs solvers, and generates a narrative report
4. **Explore results** — interactive dashboard with PET heatmaps, temporal profiles, and downloadable artifacts (VTK, CSV)

## Architecture

```
┌──────────────────────────────────────────────────┐
│  Frontend  (React + Vite)                        │
│  Chat  │  Map (Leaflet)  │  Dashboard  │  Compare│
└──────┬───────────┬───────────────────────────────┘
       │           │
       ▼           ▼
  urban_agent     sg-3d-export
  (FastAPI)       (FastAPI)
  LangGraph       BuildingIndex
  CFD / Solar     Per-building STL
  PET / MRT       Region prepare
```

This repository contains the **frontend** only. It communicates with two backend services:

| Service | Description | Repository |
|---------|-------------|------------|
| **urban_agent** | LLM orchestration, CFD/solar solvers, PET/MRT | Private |
| **sg-3d-export** | Singapore building index, STL export | Private |

## Getting Started

### Prerequisites

- Node.js 18+
- npm

### Installation

```bash
git clone https://github.com/PgUpDn/urban-cooling-agent.git
cd urban-cooling-agent
npm install
```

### Development

```bash
npm run dev
```

The app starts at [http://localhost:3000](http://localhost:3000). Without a backend, the UI runs in demo mode with mock data.

### Environment Variables

Create a `.env.local` file (git-ignored) for backend integration:

```env
# Backend simulation server URL (leave empty for demo mode)
BACKEND_API_URL=

# Optional: Gemini API key for AI chat fallback
GEMINI_API_KEY=
```

For GitHub Pages deployment, add these as **repository secrets** under Settings → Secrets → Actions.

### Build for Production

```bash
npm run build    # Output in dist/
npm run preview  # Preview locally
```

## Features

- **Natural language interaction** — LLM classifies intent and routes to chat or simulation
- **Temporal clarification** — agent asks for time period if missing before running solvers
- **Scenario confirmation** — user reviews the proposed scenario before committing compute
- **Interactive region selection** — Leaflet map with 8 Singapore district presets and freehand rectangle drawing
- **Real-time progress** — live parameter updates and status messages during simulation
- **Results dashboard** — PET heatmaps, temporal bar charts, CFD parameters, downloadable VTK/CSV artifacts
- **Scenario comparison** — side-by-side comparison of different simulation runs
- **State persistence** — chat history, selected region, and active tab survive page refresh

## Project Structure

```
├── App.tsx                        # Root component, state management, routing
├── components/
│   ├── ChatInterface.tsx          # Chat UI with confirm/clarify flow
│   ├── RegionSelect.tsx           # Leaflet map for area selection
│   ├── ParamSidebar.tsx           # Live simulation parameters
│   ├── ResultsDashboard.tsx       # Heatmaps, charts, artifact downloads
│   ├── ComparisonView.tsx         # Side-by-side scenario comparison
│   └── WorkflowSidebar.tsx        # Pipeline progress tracker
├── services/
│   ├── agentService.ts            # Backend API client
│   └── geminiService.ts           # Gemini AI fallback service
├── types.ts                       # TypeScript interfaces
├── constants.ts                   # Image URLs, workflow step definitions
├── index.html                     # Entry HTML with CDN dependencies
├── vite.config.ts                 # Vite config with proxy setup
├── nginx-cooling.conf             # Production nginx reverse proxy snippet
└── .github/workflows/deploy.yml   # GitHub Pages CI/CD
```

## Deployment

### GitHub Pages

Pushes to `main` trigger automatic deployment via GitHub Actions. The workflow builds the frontend and deploys to GitHub Pages.

### Self-hosted with nginx

For production deployment alongside the backend services, use the included `nginx-cooling.conf` snippet. It serves the built frontend under a subpath and proxies API calls to the respective backends.

## Tech Stack

| Layer | Technology |
|-------|------------|
| UI Framework | React 19, TypeScript |
| Build Tool | Vite 6 |
| Styling | Tailwind CSS (CDN) |
| Maps | Leaflet + Leaflet.draw |
| Charts | Recharts |
| Backend | FastAPI (Python) |
| Agent | LangGraph + OpenAI GPT-4o |
| Solvers | Custom CFD, solar irradiance, PET/MRT |

## Backend API

The frontend expects the following endpoints from the simulation backend:

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/health` | GET | Health check |
| `/api/chat` | POST | Intent classification and chat |
| `/api/simulation/start` | POST | Start simulation pipeline |
| `/api/simulation/{id}/status` | GET | Poll simulation progress |
| `/api/simulation/{id}/messages` | GET | Stream progress messages |
| `/api/simulation/{id}/params` | GET | Live solver parameters |
| `/api/simulation/{id}/results` | GET | Final results and artifacts |

The region selection feature communicates with the building index backend:

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/region/count` | GET | Count buildings in lat/lon bounds |
| `/api/region/prepare` | POST | Prepare STL directory for simulation |

## Author

**Dr. Xinyu Yang** — A\*STAR Institute of High Performance Computing (IHPC)

## License

MIT

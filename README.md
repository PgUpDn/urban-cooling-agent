# Urban Cooling Agent - Frontend

A modern, beautiful React-based frontend for the Urban Cooling Agent simulation workspace. This application provides an intuitive interface for urban microclimate analysis, CFD simulations, and thermal comfort assessments.

## Features

- **Interactive Chat Interface**: Communicate with the AI agent using natural language
- **Real-time Simulation Dashboard**: View and analyze simulation results with heatmaps
- **Scenario Comparison**: Compare different urban cooling strategies side-by-side
- **Parameter Configuration**: Fine-tune simulation parameters for accurate results
- **Responsive Design**: Works seamlessly on desktop and tablet devices

## Tech Stack

- **React 19** - UI Framework
- **TypeScript** - Type-safe JavaScript
- **Vite** - Fast build tool
- **Tailwind CSS** - Utility-first styling
- **Recharts** - Data visualization
- **Google Gemini API** - AI-powered chat (optional)

## Quick Start

### Prerequisites

- Node.js 18+ 
- npm or yarn

### Installation

```bash
# Clone the repository
git clone https://github.com/YOUR_USERNAME/urban-cooling-agent.git
cd urban-cooling-agent

# Install dependencies
npm install

# Create environment file
cp .env.example .env.local

# Start development server
npm run dev
```

### Environment Variables

Create a `.env.local` file with the following variables:

```env
# Optional: Gemini API Key for AI chat functionality
GEMINI_API_KEY=your_api_key_here

# Backend API URL (leave empty for demo mode)
BACKEND_API_URL=https://your-backend-url.com/api
```

## Connecting to Backend

This frontend is designed to work with the Urban Cooling Agent backend. To connect:

1. Deploy your backend agent
2. Set the `BACKEND_API_URL` environment variable to your backend URL
3. For GitHub Pages deployment, add `BACKEND_API_URL` to your repository secrets

### Backend API Endpoints Expected

The frontend expects the following endpoints from your backend:

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/health` | GET | Health check |
| `/chat` | POST | Send message to agent |
| `/simulation/start` | POST | Start a new simulation |
| `/simulation/{id}/status` | GET | Get simulation progress |
| `/simulation/{id}/results` | GET | Get simulation results |
| `/simulation/{id}/export` | GET | Export report (PDF/CSV/VTK) |

## Deployment to GitHub Pages

This project is configured for automatic deployment to GitHub Pages.

### Setup

1. Push your code to GitHub
2. Go to repository **Settings** > **Pages**
3. Set Source to "GitHub Actions"
4. (Optional) Add secrets in **Settings** > **Secrets and variables** > **Actions**:
   - `GEMINI_API_KEY` - Your Gemini API key
   - `BACKEND_API_URL` - Your deployed backend URL

### Important: Update Base Path

Before deploying, update the `base` path in `vite.config.ts` to match your repository name:

```typescript
base: mode === 'production' ? '/YOUR-REPO-NAME/' : '/',
```

### Manual Build

```bash
# Build for production
npm run build

# Preview the build locally
npm run preview
```

## Project Structure

```
urban-cooling-frontend/
├── components/
│   ├── ChatInterface.tsx    # Main chat UI
│   ├── ComparisonView.tsx   # Scenario comparison
│   ├── ParamSidebar.tsx     # Parameter configuration
│   ├── ResultsDashboard.tsx # Simulation results
│   └── WorkflowSidebar.tsx  # Workflow progress
├── services/
│   ├── agentService.ts      # Backend API client
│   └── geminiService.ts     # Gemini AI service
├── App.tsx                  # Main application
├── types.ts                 # TypeScript types
├── constants.ts             # App constants
└── index.tsx                # Entry point
```

## Demo Mode

The application runs in demo mode when no backend is configured. In this mode:
- Chat responses are simulated
- Simulation results show mock data
- All UI features remain functional for testing

## License

MIT License - Feel free to use and modify for your projects.

## Contributing

Contributions are welcome! Please feel free to submit a Pull Request.

## Author

Yang Xinyu from A*STAR IHPC (yang_xinyu@a-star.edu.sg)


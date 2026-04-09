# SG 3D Export Backend

FastAPI backend for the Singapore 3D Building Export System.

## Features

- **District APIs**: Get Singapore district information and statistics
- **AI Insights**: Gemini-powered urban planning insights
- **STL Export**: Download 3D building models in STL format
- **Async Jobs**: Background processing for large exports

## Quick Start

### 1. Install Dependencies

```bash
cd backend
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
pip install -r requirements.txt
```

### 2. Configure Environment

```bash
cp .env.example .env
# Edit .env and add your GEMINI_API_KEY
```

### 3. Run the Server

```bash
python main.py
# Or with uvicorn directly:
uvicorn main:app --reload --port 8000
```

The API will be available at `http://localhost:8000`

## API Documentation

- **Swagger UI**: http://localhost:8000/api/docs
- **ReDoc**: http://localhost:8000/api/redoc

## API Endpoints

### Districts

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/districts` | List all districts |
| GET | `/api/districts/{id}` | Get district by ID |
| GET | `/api/districts/{id}/stats` | Get selection statistics |
| GET | `/api/districts/{id}/insight` | Get AI urban insight |
| GET | `/api/districts/{id}/stl` | Download district STL |

### STL Export

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/stl/info` | Get STL file info |
| GET | `/api/stl/download` | Download full STL file |
| GET | `/api/stl/stream` | Stream STL file |

### Export Jobs

| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/api/export/start` | Start export job |
| GET | `/api/export/{job_id}` | Check job status |

### Other

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/health` | Health check |
| GET | `/api/insight` | Get insight by name |

## Project Structure

```
backend/
├── main.py              # FastAPI application
├── config.py            # Configuration settings
├── models.py            # Pydantic data models
├── requirements.txt     # Python dependencies
├── .env.example         # Environment template
└── services/
    ├── __init__.py
    ├── gemini_service.py   # Gemini AI integration
    └── stl_service.py      # STL file operations
```

## STL File

Place your `sg-building-binary.stl` file in the project root directory (parent of backend folder).

## Development

### Run with Hot Reload

```bash
uvicorn main:app --reload --host 0.0.0.0 --port 8000
```

### Run Tests

```bash
pytest tests/
```

## License

© 2025 SG-3D Engine v2

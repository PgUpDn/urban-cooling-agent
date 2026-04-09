# Solver Parameters Configuration

## Overview

Read CFD and Solar solver parameters from a JSON configuration file instead of hard-coding them in code.

## Configuration file

### File location
`solver_parameters.json`

### Configuration structure

```json
{
  "cfd": {
    "wind_speed": 2.0,           // Wind speed (m/s)
    "wind_direction": 45.0,       // Wind direction (degrees, 0=north, 90=east)
    "height": 2.0,                // Analysis height (m)
    "temperature": 28.0,          // Ambient temperature (°C)
    "humidity": 70.0,             // Relative humidity (%)
    "voxel_pitch": 1.0,           // Voxel size (m)
    "buffer_ratio": 1.5,          // Buffer zone ratio
    "alpha_t": 0.1,               // Temperature diffusion coefficient
    "alpha_rh": 0.1,              // Humidity diffusion coefficient
    "building_radius": 500.0      // Building influence radius (m)
  },
  "solar": {
    "time": "2025-10-04 14:00:00+08:00",  // Analysis time (ISO + timezone)
    "latitude": 1.379,                     // Latitude (°)
    "longitude": 103.893,                  // Longitude (°)
    "elevation": 14.0,                     // Elevation (m)
    "DNI": 800.0,                          // Direct normal irradiance (W/m²)
    "DHI": 180.0,                          // Diffuse horizontal irradiance (W/m²)
    "rays_per_receiver": 64,               // Rays per receiver point
    "ground_radius": 25.0,                 // Ground radius (m)
    "shading_threshold": 0.1,              // Shading threshold
    "grid_resolution": 32                  // Grid resolution
  }
}
```

## Usage

### 1. Using `intelligent_building_agent.py`

```python
from intelligent_building_agent import IntelligentBuildingAgent

# Specify config file path when creating the agent
agent = IntelligentBuildingAgent(
    api_key=OPENAI_API_KEY,
    config_file="/path/to/solver_parameters.json"
)

# Run analysis — uses parameters from the JSON config
result = agent.analyze(
    query="Analyze wind flow around the building",
    stl_directory="/path/to/stl/files"
)
```

### 2. Using `full_analysis_with_recording_en.py`

The config file is already integrated; simply run:

```bash
python full_analysis_with_recording_en.py
```

By default it uses `/scratch/Urban/intelligent_agent_package/solver_parameters.json`

### 3. Parameter precedence

The system uses three precedence levels (lowest to highest):

1. **JSON config file** — Base defaults
2. **LLM analysis output** — Parameters suggested from the query
3. **User-supplied values** — Highest precedence

Example:

```python
# JSON config + user overrides for some fields
result = agent.analyze(
    query="Analyze wind flow",
    stl_directory="/path/to/stl",
    user_parameters={
        "cfd": {
            "wind_speed": 3.0,  # Overrides wind_speed from JSON
            # Other parameters still come from JSON
        }
    }
)
```

## Editing configuration

### Method 1: Edit the JSON file directly

```bash
nano solver_parameters.json
```

### Method 2: Create multiple config files

Create different config files for different scenarios:

```
solver_parameters_summer.json
solver_parameters_winter.json
solver_parameters_typhoon.json
```

Then specify in code:

```python
agent = IntelligentBuildingAgent(
    api_key=OPENAI_API_KEY,
    config_file="solver_parameters_summer.json"
)
```

## Parameter reference

### CFD parameters

| Parameter | Type | Default | Description |
|------|------|--------|------|
| wind_speed | float | 2.0 | Inflow wind speed (m/s) |
| wind_direction | float | 45.0 | Wind direction (degrees, 0=north, 90=east) |
| height | float | 2.0 | Pedestrian-height analysis layer (m) |
| temperature | float | 28.0 | Ambient temperature (°C) |
| humidity | float | 70.0 | Relative humidity (%) |
| voxel_pitch | float | 1.0 | CFD grid voxel size (m) |
| buffer_ratio | float | 1.5 | Computational domain buffer ratio |
| alpha_t | float | 0.1 | Temperature diffusion coefficient |
| alpha_rh | float | 0.1 | Humidity diffusion coefficient |
| building_radius | float | 500.0 | Building influence radius (m) |

### Solar parameters

| Parameter | Type | Default | Description |
|------|------|--------|------|
| time | string | "2025-10-04 14:00:00+08:00" | Analysis time (ISO + timezone) |
| latitude | float | 1.379 | Latitude (°N) |
| longitude | float | 103.893 | Longitude (°E) |
| elevation | float | 14.0 | Elevation (m) |
| DNI | float | 800.0 | Direct normal irradiance (W/m²) |
| DHI | float | 180.0 | Diffuse horizontal irradiance (W/m²) |
| rays_per_receiver | int | 64 | Ray-tracing density |
| ground_radius | float | 25.0 | Ground reflection radius (m) |
| shading_threshold | float | 0.1 | Shading decision threshold (0–1) |
| grid_resolution | int | 32 | Grid resolution |

## Example configs for common scenarios

### Summer afternoon scenario (Singapore)

```json
{
  "cfd": {
    "wind_speed": 1.5,
    "wind_direction": 135.0,
    "temperature": 32.0,
    "humidity": 75.0
  },
  "solar": {
    "time": "2025-06-21 14:00:00+08:00",
    "DNI": 900.0,
    "DHI": 200.0
  }
}
```

### Winter scenario (Northern Hemisphere)

```json
{
  "cfd": {
    "wind_speed": 3.0,
    "wind_direction": 0.0,
    "temperature": 10.0,
    "humidity": 50.0
  },
  "solar": {
    "time": "2025-12-21 12:00:00+08:00",
    "DNI": 600.0,
    "DHI": 150.0
  }
}
```

### Typhoon scenario

```json
{
  "cfd": {
    "wind_speed": 15.0,
    "wind_direction": 90.0,
    "temperature": 26.0,
    "humidity": 90.0
  }
}
```

## Debugging

If config load fails, the system prints warning messages:

```
⚠️  Configuration file not found: /path/to/config.json
⚠️  Invalid JSON in configuration file: ...
```

The system continues using built-in defaults or LLM-suggested parameters.

## Related files

- `solver_parameters.json` — Default config file
- `intelligent_building_agent.py` — Main agent file; includes config loading logic
- `full_analysis_with_recording_en.py` — Full analysis script with JSON config integrated
- `wrapper/cfd_solver.py` — CFD parameter wrapper
- `wrapper/solar_solver.py` — Solar parameter wrapper


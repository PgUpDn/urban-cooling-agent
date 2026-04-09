# Configuration file examples

This directory contains preset configuration files for different scenarios.

## 📁 Available configurations

### 1. `summer_afternoon.json` - Summer afternoon
For Singapore summer afternoon high-temperature scenarios

**Characteristics:**
- Temperature: 33°C
- Humidity: 75%
- Southeasterly wind (135°), wind speed 1.5 m/s
- High solar radiation (DNI: 850 W/m²)
- Time: June 21, 3:00 PM

**Use cases:**
- Extreme heat analysis
- Afternoon urban heat island studies
- Outdoor comfort assessment

### 2. `winter_morning.json` - Winter morning
For Singapore winter cool mornings

**Characteristics:**
- Temperature: 24°C
- Humidity: 65%
- Northerly wind (0°), wind speed 2.5 m/s
- Moderate solar radiation (DNI: 650 W/m²)
- Time: December 21, 10:00 AM

**Use cases:**
- Coolest annual conditions
- Natural ventilation potential analysis
- Solar angle studies

### 3. `typhoon_conditions.json` - Typhoon conditions
For typhoon or storm weather

**Characteristics:**
- Temperature: 26°C
- Humidity: 90%
- Easterly wind (90°), wind speed 12.0 m/s
- Low solar radiation (DNI: 300 W/m²) — overcast
- Time: September 15, noon

**Use cases:**
- Extreme wind load analysis
- Pedestrian safety in strong wind
- Building wind resistance assessment

## 🚀 Usage

### Method 1: Use an example config directly

```python
from intelligent_building_agent import IntelligentBuildingAgent
from config import OPENAI_API_KEY

# Use summer configuration
agent = IntelligentBuildingAgent(
    api_key=OPENAI_API_KEY,
    config_file="config_examples/summer_afternoon.json"
)

result = agent.analyze(
    query="Analyze thermal comfort",
    stl_directory="/path/to/stl"
)
```

### Method 2: Copy and edit

```bash
# Copy example config as main config
cp config_examples/summer_afternoon.json solver_parameters.json

# Edit parameters
nano solver_parameters.json
```

### Method 3: Batch analysis across scenarios

```python
scenarios = [
    ("summer", "config_examples/summer_afternoon.json"),
    ("winter", "config_examples/winter_morning.json"),
    ("typhoon", "config_examples/typhoon_conditions.json")
]

for name, config in scenarios:
    agent = IntelligentBuildingAgent(
        api_key=OPENAI_API_KEY,
        config_file=config
    )
    
    result = agent.analyze(
        query=f"Environmental analysis - {name} conditions",
        stl_directory="/path/to/stl",
        output_directory=f"results/{name}"
    )
```

## 📊 Parameter comparison

| Parameter | Summer afternoon | Winter morning | Typhoon |
|------|----------|----------|------|
| Temperature (°C) | 33.0 | 24.0 | 26.0 |
| Humidity (%) | 75 | 65 | 90 |
| Wind speed (m/s) | 1.5 | 2.5 | 12.0 |
| Wind direction (°) | 135 (SE) | 0 (N) | 90 (E) |
| DNI (W/m²) | 850 | 650 | 300 |
| DHI (W/m²) | 200 | 160 | 150 |

## ✏️ Custom configuration

Create your own configuration based on these examples:

```bash
# 1. Copy an example
cp config_examples/summer_afternoon.json config_examples/my_custom.json

# 2. Edit parameters
nano config_examples/my_custom.json

# 3. Use it
python your_analysis_script.py --config config_examples/my_custom.json
```

## 🌍 Adapting for other regions

If you use this in other regions, adjust the following parameters:

### Beijing (China)

```json
{
  "solar": {
    "latitude": 39.9,
    "longitude": 116.4,
    "elevation": 43.0
  }
}
```

### New York (USA)

```json
{
  "solar": {
    "latitude": 40.7,
    "longitude": -74.0,
    "elevation": 10.0
  }
}
```

### London (UK)

```json
{
  "solar": {
    "latitude": 51.5,
    "longitude": -0.1,
    "elevation": 11.0
  }
}
```

## 💡 Tips

1. **Time zone**: Ensure time strings include the correct offset, e.g. `+08:00` (Singapore / Beijing)
2. **Wind convention**: 0° = north, 90° = east, 180° = south, 270° = west
3. **Radiation**: DNI (direct) + DHI (diffuse) ≈ GHI (global horizontal irradiance)
4. **Validate config**: Use `verify_config.py` to validate edited configuration files

## 📚 References

- [Solar parameters documentation](../solver_parameters_README.md)
- [Main configuration guide](../USAGE_JSON_CONFIG.md)
- [Intelligent Building Agent](../intelligent_building_agent.py)

---

**Last updated**: 2025-11-03

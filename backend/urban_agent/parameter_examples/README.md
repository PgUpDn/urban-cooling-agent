# Parameter file examples

This directory contains sample JSON files produced by the parameter tracking feature.

## 📁 File descriptions

### 1. `llm_suggested_parameters_example.json`

Parameters suggested by the LLM after analyzing the user query.

**Scenario**: User query "Analyze wind flow around the building with strong typhoon conditions"

**LLM analysis**:
- Detected the keyword "typhoon conditions"
- Suggests a higher wind speed (15.0 m/s)
- Suggests easterly wind direction (90°) — typical for typhoons in Southeast Asia
- Adjusts temperature and humidity to typical values during typhoon conditions

**File contents**:
```json
{
  "source": "LLM Analysis",
  "timestamp": "2025-11-03T14:30:15.123456",
  "query": "Analyze wind flow around the building with strong typhoon conditions",
  "reasoning": "Based on the query mentioning 'strong typhoon conditions'...",
  "required_solvers": ["geometry", "cfd"],
  "parameters": {
    "cfd": {
      "wind_speed": 15.0,
      "wind_direction": 90.0,
      "height": 2.0,
      "temperature": 26.0,
      "humidity": 90.0
    }
  }
}
```

**Key fields**:
- `query`: Original user query
- `reasoning`: LLM reasoning (why these parameters were suggested)
- `required_solvers`: Solvers the LLM determined are needed
- `parameters`: Concrete parameters suggested by the LLM

---

### 2. `final_cfd_parameters_example.json`

Final CFD parameters actually used (after merging).

**Parameter sources**:
1. **JSON configuration file** (`solver_parameters.json`):
   - `voxel_pitch: 1.0`
   - `buffer_ratio: 1.5`
   - `alpha_t: 0.1`
   - `alpha_rh: 0.1`
   - `building_radius: 500.0`

2. **LLM suggestions** (override JSON):
   - `wind_speed: 15.0` → changed by user to 12.0
   - `wind_direction: 90.0` → changed by user to 180.0
   - `height: 2.0`
   - `temperature: 26.0`
   - `humidity: 90.0`

3. **User input** (highest priority):
   - `wind_speed: 12.0` (user felt 15.0 was too strong)
   - `wind_direction: 180.0` (user specified southerly wind)

**File contents**:
```json
{
  "source": "Final Merged Parameters",
  "timestamp": "2025-11-03T14:30:20.654321",
  "priority_order": [
    "1. JSON config file (base)",
    "2. LLM suggestions (override)",
    "3. User parameters (final override)"
  ],
  "cfd": {
    "wind_speed": 12.0,        // User overrode LLM's 15.0
    "wind_direction": 180.0,   // User overrode LLM's 90.0
    "height": 2.0,             // From LLM
    "temperature": 26.0,       // From LLM
    "humidity": 90.0,          // From LLM
    "voxel_pitch": 1.0,        // From JSON config
    "buffer_ratio": 1.5,       // From JSON config
    "alpha_t": 0.1,            // From JSON config
    "alpha_rh": 0.1,           // From JSON config
    "building_radius": 500.0   // From JSON config
  }
}
```

**Key characteristics**:
- Contains all parameters (full parameter set)
- Clearly indicates parameter precedence
- Timestamp records when it was generated

---

### 3. `final_solar_parameters_example.json`

Final Solar parameters actually used.

**Scenario**: Solar analysis on a summer solstice afternoon

**Parameter sources**:
- Mostly from the JSON configuration file
- The LLM may have adjusted the time to the summer solstice
- DNI adjusted for high summer irradiance

**File contents**:
```json
{
  "source": "Final Merged Parameters",
  "timestamp": "2025-11-03T14:30:25.789012",
  "priority_order": [
    "1. JSON config file (base)",
    "2. LLM suggestions (override)",
    "3. User parameters (final override)"
  ],
  "solar": {
    "time": "2025-06-21 14:00:00+08:00",  // Summer solstice, 2 PM
    "latitude": 1.379,                     // Singapore latitude
    "longitude": 103.893,                  // Singapore longitude
    "elevation": 14.0,                     // Elevation above sea level
    "DNI": 850.0,                          // High direct normal irradiance (summer)
    "DHI": 200.0,                          // Diffuse horizontal irradiance
    "rays_per_receiver": 64,               // Ray tracing density
    "ground_radius": 25.0,                 // Ground radius
    "shading_threshold": 0.1               // Shading threshold
  }
}
```

---

## 🔍 How to use these examples

### 1. View the example files

```bash
# View LLM suggestions
cat parameter_examples/llm_suggested_parameters_example.json | jq

# View final CFD parameters
cat parameter_examples/final_cfd_parameters_example.json | jq

# View final Solar parameters
cat parameter_examples/final_solar_parameters_example.json | jq
```

### 2. Compare LLM suggestions and final parameters

```bash
# CFD parameters from LLM suggestion
jq '.parameters.cfd' parameter_examples/llm_suggested_parameters_example.json

# Final CFD parameters in use
jq '.cfd' parameter_examples/final_cfd_parameters_example.json

# Compare differences
diff <(jq '.parameters.cfd' parameter_examples/llm_suggested_parameters_example.json) \
     <(jq '.cfd' parameter_examples/final_cfd_parameters_example.json)
```

### 3. Extract the LLM reasoning

```bash
jq -r '.reasoning' parameter_examples/llm_suggested_parameters_example.json
```

### 4. Inspect parameter change history

```bash
# Wind speed suggested by LLM
jq '.parameters.cfd.wind_speed' parameter_examples/llm_suggested_parameters_example.json
# Output: 15.0

# Wind speed finally used
jq '.cfd.wind_speed' parameter_examples/final_cfd_parameters_example.json
# Output: 12.0

# Note: User overrode the LLM suggestion
```

---

## 📊 Parameter flow example

### Full typhoon scenario

**1. User query**
```
"Analyze wind flow around the building with strong typhoon conditions"
```

**2. LLM analysis** → `llm_suggested_parameters_example.json`
```
Detected keyword: "strong typhoon conditions"
→ Suggest wind_speed: 15.0 m/s
→ Suggest wind_direction: 90.0° (easterly)
→ Suggest temperature: 26.0°C
→ Suggest humidity: 90.0%
```

**3. Load JSON configuration**
```
voxel_pitch: 1.0
buffer_ratio: 1.5
alpha_t: 0.1
...
```

**4. User overrides**
```python
user_parameters = {
    "cfd": {
        "wind_speed": 12.0,      # User felt 15.0 was too strong
        "wind_direction": 180.0  # User wanted to analyze southerly wind
    }
}
```

**5. Final parameters** → `final_cfd_parameters_example.json`
```
wind_speed: 12.0        ← User
wind_direction: 180.0   ← User
height: 2.0             ← LLM
temperature: 26.0       ← LLM
humidity: 90.0          ← LLM
voxel_pitch: 1.0        ← JSON
buffer_ratio: 1.5       ← JSON
...
```

---

## 🎯 Practical usage scenarios

### Scenario 1: Review LLM parameter suggestions

```python
import json

# Read LLM suggestion
with open('parameter_examples/llm_suggested_parameters_example.json') as f:
    llm = json.load(f)

print(f"Query: {llm['query']}")
print(f"\nLLM Reasoning:\n{llm['reasoning']}")
print(f"\nSuggested wind speed: {llm['parameters']['cfd']['wind_speed']} m/s")

# Check if reasonable
if llm['parameters']['cfd']['wind_speed'] > 20.0:
    print("⚠️  Warning: Wind speed seems too high!")
```

### Scenario 2: Validate final parameters

```python
# Read final parameters
with open('parameter_examples/final_cfd_parameters_example.json') as f:
    final = json.load(f)

# Check key parameters
cfd = final['cfd']
print(f"Wind speed: {cfd['wind_speed']} m/s")
print(f"Wind direction: {cfd['wind_direction']}°")
print(f"Temperature: {cfd['temperature']}°C")

# Validate parameter ranges
assert 0 <= cfd['wind_speed'] <= 30, "Wind speed out of range"
assert 0 <= cfd['wind_direction'] < 360, "Wind direction out of range"
print("✅ All parameters validated")
```

### Scenario 3: Save a good parameter set

```python
# If this run produced good results, save as a new config
import shutil

shutil.copy(
    'parameter_examples/final_cfd_parameters_example.json',
    'config_examples/typhoon_scenario_validated.json'
)

print("✅ Saved as new configuration template")
```

---

## 💡 Tips

1. **LLM suggestion files** show how the LLM interpreted your query
2. **Final parameter files** show the parameters actually used at runtime
3. Comparing the two shows where each value ultimately came from
4. Use these examples to understand how parameter tracking works

---

## 📚 Related documentation

- [Parameter tracking details](../PARAMETER_TRACKING.md)
- [JSON configuration usage guide](../USAGE_JSON_CONFIG.md)
- [Parameter reference](../solver_parameters_README.md)

---

**Last updated**: 2025-11-03


# 参数文件示例

本目录包含参数追踪功能生成的JSON文件示例。

## 📁 文件说明

### 1. `llm_suggested_parameters_example.json`

LLM分析用户查询后建议的参数。

**场景**: 用户查询 "Analyze wind flow around the building with strong typhoon conditions"

**LLM的分析**:
- 识别出"typhoon conditions"关键词
- 建议使用较高风速 (15.0 m/s)
- 建议东风方向 (90°) - 东南亚台风典型方向
- 调整温度和湿度到台风期间的典型值

**文件内容**:
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

**关键字段**:
- `query`: 用户原始查询
- `reasoning`: LLM的推理过程（为什么建议这些参数）
- `required_solvers`: LLM判断需要的求解器
- `parameters`: LLM建议的具体参数

---

### 2. `final_cfd_parameters_example.json`

最终实际使用的CFD参数（合并后）。

**参数来源**:
1. **JSON配置文件** (`solver_parameters.json`):
   - `voxel_pitch: 1.0`
   - `buffer_ratio: 1.5`
   - `alpha_t: 0.1`
   - `alpha_rh: 0.1`
   - `building_radius: 500.0`

2. **LLM建议** (覆盖JSON):
   - `wind_speed: 15.0` → 被用户改为 12.0
   - `wind_direction: 90.0` → 被用户改为 180.0
   - `height: 2.0`
   - `temperature: 26.0`
   - `humidity: 90.0`

3. **用户传入** (最高优先级):
   - `wind_speed: 12.0` (用户认为15.0太强)
   - `wind_direction: 180.0` (用户指定南风)

**文件内容**:
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
    "wind_speed": 12.0,        // 用户覆盖了LLM的15.0
    "wind_direction": 180.0,   // 用户覆盖了LLM的90.0
    "height": 2.0,             // 来自LLM
    "temperature": 26.0,       // 来自LLM
    "humidity": 90.0,          // 来自LLM
    "voxel_pitch": 1.0,        // 来自JSON配置
    "buffer_ratio": 1.5,       // 来自JSON配置
    "alpha_t": 0.1,            // 来自JSON配置
    "alpha_rh": 0.1,           // 来自JSON配置
    "building_radius": 500.0   // 来自JSON配置
  }
}
```

**关键特点**:
- 包含所有参数（完整参数集）
- 清楚标注参数优先级
- 时间戳记录生成时间

---

### 3. `final_solar_parameters_example.json`

最终实际使用的Solar参数。

**场景**: 夏至日午后太阳分析

**参数来源**:
- 大部分来自JSON配置文件
- LLM可能调整了时间到夏至日
- DNI值根据夏季高辐射调整

**文件内容**:
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
    "time": "2025-06-21 14:00:00+08:00",  // 夏至日下午2点
    "latitude": 1.379,                     // 新加坡纬度
    "longitude": 103.893,                  // 新加坡经度
    "elevation": 14.0,                     // 海拔高度
    "DNI": 850.0,                          // 高直射辐射（夏季）
    "DHI": 200.0,                          // 散射辐射
    "rays_per_receiver": 64,               // 光线追踪密度
    "ground_radius": 25.0,                 // 地面半径
    "shading_threshold": 0.1               // 遮阳阈值
  }
}
```

---

## 🔍 如何使用这些示例

### 1. 查看示例文件

```bash
# 查看LLM建议
cat parameter_examples/llm_suggested_parameters_example.json | jq

# 查看最终CFD参数
cat parameter_examples/final_cfd_parameters_example.json | jq

# 查看最终Solar参数
cat parameter_examples/final_solar_parameters_example.json | jq
```

### 2. 对比LLM建议和最终参数

```bash
# 查看LLM建议的CFD参数
jq '.parameters.cfd' parameter_examples/llm_suggested_parameters_example.json

# 查看最终使用的CFD参数
jq '.cfd' parameter_examples/final_cfd_parameters_example.json

# 对比差异
diff <(jq '.parameters.cfd' parameter_examples/llm_suggested_parameters_example.json) \
     <(jq '.cfd' parameter_examples/final_cfd_parameters_example.json)
```

### 3. 提取LLM的推理过程

```bash
jq -r '.reasoning' parameter_examples/llm_suggested_parameters_example.json
```

### 4. 查看参数变化历史

```bash
# LLM建议的风速
jq '.parameters.cfd.wind_speed' parameter_examples/llm_suggested_parameters_example.json
# 输出: 15.0

# 最终使用的风速
jq '.cfd.wind_speed' parameter_examples/final_cfd_parameters_example.json
# 输出: 12.0

# 说明: 用户覆盖了LLM的建议
```

---

## 📊 参数流转示例

### 台风场景完整流程

**1. 用户查询**
```
"Analyze wind flow around the building with strong typhoon conditions"
```

**2. LLM分析** → `llm_suggested_parameters_example.json`
```
识别关键词: "strong typhoon conditions"
→ 建议 wind_speed: 15.0 m/s
→ 建议 wind_direction: 90.0° (东风)
→ 建议 temperature: 26.0°C
→ 建议 humidity: 90.0%
```

**3. 加载JSON配置**
```
voxel_pitch: 1.0
buffer_ratio: 1.5
alpha_t: 0.1
...
```

**4. 用户覆盖**
```python
user_parameters = {
    "cfd": {
        "wind_speed": 12.0,      # 用户认为15.0太强
        "wind_direction": 180.0  # 用户要分析南风
    }
}
```

**5. 最终参数** → `final_cfd_parameters_example.json`
```
wind_speed: 12.0        ← 用户
wind_direction: 180.0   ← 用户
height: 2.0             ← LLM
temperature: 26.0       ← LLM
humidity: 90.0          ← LLM
voxel_pitch: 1.0        ← JSON
buffer_ratio: 1.5       ← JSON
...
```

---

## 🎯 实际使用场景

### 场景1: 审查LLM的参数建议

```python
import json

# 读取LLM建议
with open('parameter_examples/llm_suggested_parameters_example.json') as f:
    llm = json.load(f)

print(f"Query: {llm['query']}")
print(f"\nLLM Reasoning:\n{llm['reasoning']}")
print(f"\nSuggested wind speed: {llm['parameters']['cfd']['wind_speed']} m/s")

# 判断是否合理
if llm['parameters']['cfd']['wind_speed'] > 20.0:
    print("⚠️  Warning: Wind speed seems too high!")
```

### 场景2: 验证最终参数

```python
# 读取最终参数
with open('parameter_examples/final_cfd_parameters_example.json') as f:
    final = json.load(f)

# 检查关键参数
cfd = final['cfd']
print(f"Wind speed: {cfd['wind_speed']} m/s")
print(f"Wind direction: {cfd['wind_direction']}°")
print(f"Temperature: {cfd['temperature']}°C")

# 验证参数范围
assert 0 <= cfd['wind_speed'] <= 30, "Wind speed out of range"
assert 0 <= cfd['wind_direction'] < 360, "Wind direction out of range"
print("✅ All parameters validated")
```

### 场景3: 保存优秀的参数组合

```python
# 如果这次分析结果很好，保存为新配置
import shutil

shutil.copy(
    'parameter_examples/final_cfd_parameters_example.json',
    'config_examples/typhoon_scenario_validated.json'
)

print("✅ Saved as new configuration template")
```

---

## 💡 提示

1. **LLM建议文件** 显示LLM如何理解你的查询
2. **最终参数文件** 显示实际运行时使用的参数
3. 对比两者可以了解参数的最终来源
4. 使用这些示例理解参数追踪功能的工作方式

---

## 📚 相关文档

- [参数追踪详细说明](../PARAMETER_TRACKING.md)
- [JSON配置使用指南](../USAGE_JSON_CONFIG.md)
- [参数详细说明](../solver_parameters_README.md)

---

**更新日期**: 2025-11-03


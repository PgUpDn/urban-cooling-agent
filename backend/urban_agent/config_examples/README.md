# 配置文件示例

本目录包含不同场景的预设配置文件。

## 📁 可用配置

### 1. `summer_afternoon.json` - 夏季午后
适用于新加坡夏季午后高温场景

**特点：**
- 温度：33°C
- 湿度：75%
- 东南风 (135°)，风速 1.5 m/s
- 高太阳辐射 (DNI: 850 W/m²)
- 时间：6月21日下午3点

**适用场景：**
- 极端高温分析
- 午后热岛效应研究
- 户外舒适度评估

### 2. `winter_morning.json` - 冬季上午
适用于新加坡冬季凉爽上午

**特点：**
- 温度：24°C
- 湿度：65%
- 北风 (0°)，风速 2.5 m/s
- 中等太阳辐射 (DNI: 650 W/m²)
- 时间：12月21日上午10点

**适用场景：**
- 全年最凉爽条件
- 自然通风潜力分析
- 日照角度研究

### 3. `typhoon_conditions.json` - 台风条件
适用于台风或暴风雨天气

**特点：**
- 温度：26°C
- 湿度：90%
- 东风 (90°)，风速 12.0 m/s
- 低太阳辐射 (DNI: 300 W/m²) - 多云
- 时间：9月15日中午

**适用场景：**
- 极端风载分析
- 强风环境下的行人安全
- 建筑抗风性能评估

## 🚀 使用方法

### 方法 1: 直接使用示例配置

```python
from intelligent_building_agent import IntelligentBuildingAgent
from config import OPENAI_API_KEY

# 使用夏季配置
agent = IntelligentBuildingAgent(
    api_key=OPENAI_API_KEY,
    config_file="config_examples/summer_afternoon.json"
)

result = agent.analyze(
    query="Analyze thermal comfort",
    stl_directory="/path/to/stl"
)
```

### 方法 2: 复制并修改

```bash
# 复制示例配置为主配置
cp config_examples/summer_afternoon.json solver_parameters.json

# 编辑参数
nano solver_parameters.json
```

### 方法 3: 批量分析多个场景

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

## 📊 参数对比

| 参数 | 夏季午后 | 冬季上午 | 台风 |
|------|----------|----------|------|
| 温度 (°C) | 33.0 | 24.0 | 26.0 |
| 湿度 (%) | 75 | 65 | 90 |
| 风速 (m/s) | 1.5 | 2.5 | 12.0 |
| 风向 (°) | 135 (SE) | 0 (N) | 90 (E) |
| DNI (W/m²) | 850 | 650 | 300 |
| DHI (W/m²) | 200 | 160 | 150 |

## ✏️ 自定义配置

基于这些示例创建自己的配置：

```bash
# 1. 复制示例
cp config_examples/summer_afternoon.json config_examples/my_custom.json

# 2. 编辑参数
nano config_examples/my_custom.json

# 3. 使用
python your_analysis_script.py --config config_examples/my_custom.json
```

## 🌍 不同地区适配

如果您在其他地区使用，需要修改以下参数：

### 北京 (中国)

```json
{
  "solar": {
    "latitude": 39.9,
    "longitude": 116.4,
    "elevation": 43.0
  }
}
```

### 纽约 (美国)

```json
{
  "solar": {
    "latitude": 40.7,
    "longitude": -74.0,
    "elevation": 10.0
  }
}
```

### 伦敦 (英国)

```json
{
  "solar": {
    "latitude": 51.5,
    "longitude": -0.1,
    "elevation": 11.0
  }
}
```

## 💡 提示

1. **时区设置**：确保时间字符串包含正确的时区偏移，如 `+08:00` (新加坡/北京)
2. **风向约定**：0° = 北，90° = 东，180° = 南，270° = 西
3. **辐射值**：DNI (直射) + DHI (散射) ≈ GHI (总水平辐射)
4. **验证配置**：使用 `verify_config.py` 验证修改后的配置文件

## 📚 参考资料

- [Solar parameters documentation](../solver_parameters_README.md)
- [Main configuration guide](../USAGE_JSON_CONFIG.md)
- [Intelligent Building Agent](../intelligent_building_agent.py)

---

**更新日期**: 2025-11-03


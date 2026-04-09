# Solver Parameters Configuration

## 概述

从JSON配置文件读取CFD和Solar solver的参数，避免在代码中硬编码参数。

## 配置文件

### 文件位置
`solver_parameters.json`

### 配置结构

```json
{
  "cfd": {
    "wind_speed": 2.0,           // 风速 (m/s)
    "wind_direction": 45.0,       // 风向 (度，0=北，90=东)
    "height": 2.0,                // 分析高度 (m)
    "temperature": 28.0,          // 环境温度 (°C)
    "humidity": 70.0,             // 相对湿度 (%)
    "voxel_pitch": 1.0,           // 体素尺寸 (m)
    "buffer_ratio": 1.5,          // 缓冲区比例
    "alpha_t": 0.1,               // 温度扩散系数
    "alpha_rh": 0.1,              // 湿度扩散系数
    "building_radius": 500.0      // 建筑影响半径 (m)
  },
  "solar": {
    "time": "2025-10-04 14:00:00+08:00",  // 分析时间 (ISO格式+时区)
    "latitude": 1.379,                     // 纬度 (°)
    "longitude": 103.893,                  // 经度 (°)
    "elevation": 14.0,                     // 海拔 (m)
    "DNI": 800.0,                          // 直射辐射 (W/m²)
    "DHI": 180.0,                          // 散射辐射 (W/m²)
    "rays_per_receiver": 64,               // 每个接收点的光线数
    "ground_radius": 25.0,                 // 地面半径 (m)
    "shading_threshold": 0.1,              // 遮阳阈值
    "grid_resolution": 32                  // 网格分辨率
  }
}
```

## 使用方法

### 1. 在 `intelligent_building_agent.py` 中使用

```python
from intelligent_building_agent import IntelligentBuildingAgent

# 创建agent时指定配置文件路径
agent = IntelligentBuildingAgent(
    api_key=OPENAI_API_KEY,
    config_file="/path/to/solver_parameters.json"
)

# 运行分析 - 将使用JSON配置中的参数
result = agent.analyze(
    query="Analyze wind flow around the building",
    stl_directory="/path/to/stl/files"
)
```

### 2. 在 `full_analysis_with_recording_en.py` 中使用

配置文件已经集成，只需运行：

```bash
python full_analysis_with_recording_en.py
```

默认使用 `/scratch/Urban/intelligent_agent_package/solver_parameters.json`

### 3. 参数优先级

系统使用三层参数优先级（从低到高）：

1. **JSON配置文件** - 基础默认值
2. **LLM分析结果** - AI根据查询推荐的参数
3. **用户直接提供** - 最高优先级

示例：

```python
# 使用JSON配置 + 用户覆盖部分参数
result = agent.analyze(
    query="Analyze wind flow",
    stl_directory="/path/to/stl",
    user_parameters={
        "cfd": {
            "wind_speed": 3.0,  # 覆盖JSON中的wind_speed
            # 其他参数仍使用JSON配置
        }
    }
)
```

## 修改配置

### 方法1: 直接编辑JSON文件

```bash
nano solver_parameters.json
```

### 方法2: 创建多个配置文件

为不同的场景创建不同的配置文件：

```
solver_parameters_summer.json
solver_parameters_winter.json
solver_parameters_typhoon.json
```

然后在代码中指定：

```python
agent = IntelligentBuildingAgent(
    api_key=OPENAI_API_KEY,
    config_file="solver_parameters_summer.json"
)
```

## 参数说明

### CFD参数

| 参数 | 类型 | 默认值 | 说明 |
|------|------|--------|------|
| wind_speed | float | 2.0 | 入流风速 (m/s) |
| wind_direction | float | 45.0 | 风向角度 (度，0=北，90=东) |
| height | float | 2.0 | 人行高度分析层 (m) |
| temperature | float | 28.0 | 环境温度 (°C) |
| humidity | float | 70.0 | 相对湿度 (%) |
| voxel_pitch | float | 1.0 | CFD网格体素尺寸 (m) |
| buffer_ratio | float | 1.5 | 计算域缓冲区比例 |
| alpha_t | float | 0.1 | 温度扩散系数 |
| alpha_rh | float | 0.1 | 湿度扩散系数 |
| building_radius | float | 500.0 | 建筑影响半径 (m) |

### Solar参数

| 参数 | 类型 | 默认值 | 说明 |
|------|------|--------|------|
| time | string | "2025-10-04 14:00:00+08:00" | 分析时间 (ISO格式+时区) |
| latitude | float | 1.379 | 纬度 (°N) |
| longitude | float | 103.893 | 经度 (°E) |
| elevation | float | 14.0 | 海拔高度 (m) |
| DNI | float | 800.0 | 直射辐射强度 (W/m²) |
| DHI | float | 180.0 | 散射辐射强度 (W/m²) |
| rays_per_receiver | int | 64 | 光线追踪密度 |
| ground_radius | float | 25.0 | 地面反射半径 (m) |
| shading_threshold | float | 0.1 | 遮阳判定阈值 (0-1) |
| grid_resolution | int | 32 | 网格分辨率 |

## 常见场景配置示例

### 夏季午后场景（新加坡）

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

### 冬季场景（北半球）

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

### 台风场景

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

## 调试

如果配置文件加载失败，系统会输出警告信息：

```
⚠️  Configuration file not found: /path/to/config.json
⚠️  Invalid JSON in configuration file: ...
```

系统会继续运行，使用代码中的默认值或LLM推荐的参数。

## 相关文件

- `solver_parameters.json` - 默认配置文件
- `intelligent_building_agent.py` - Agent主文件，包含配置加载逻辑
- `full_analysis_with_recording_en.py` - 完整分析脚本，已集成JSON配置
- `wrapper/cfd_solver.py` - CFD参数包装器
- `wrapper/solar_solver.py` - Solar参数包装器


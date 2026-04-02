# `.nea` 跑道端点距离计算项目

本项目用于处理 GNSS `.nea` 原始数据文件，并按照文件名中的 `1/2` 端点语义计算跑道长度。当前约定是：

- `1` 表示起点端点文件
- `2` 表示终点端点文件
- `gps / bd / double` 表示三种测量方式

当前最终算法参考 `2026GNSS-本科学生版.pdf` 中关于静态定位的处理思路，使用 `GGA` 观测点做质量筛选和静态统计，再计算起终点间的大地距离。

## 文件结构

```text
gps,bd,double result/
├─ data/
│  └─ nea/                         # 原始 .nea 数据目录，18 个端点文件都放在这里
├─ custom/
│  ├─ nea_length/                  # 长度计算代码和结果输出目录
│  │  ├─ nea_tools.py              # 核心算法：GGA 提取、质量筛选、均值/标准差、距离公式
│  │  ├─ calculate_runway_distance.py # 批处理入口：扫描数据、配对 1/2、导出 CSV
│  │  ├─ endpoint_representatives.csv # 端点统计结果，不是最终长度，而是端点质量摘要
│  │  ├─ runway_pair_results.csv   # 当前最终跑道长度结果
│  │  └─ runway_distance_results.csv # 旧算法中间结果，仅保留对照
│  └─ notes/                       # 版本记录和思路档案
│     ├─ v1.0-nea-runway-distance.md
│     ├─ v1.1-nea-runway-distance-window-filter.md
│     ├─ v1.2-nea-endpoint-pairing.md
│     ├─ v1.3-project-manual.md
│     ├─ v1.4-pdf-guided-static-gga.md
│     └─ v1.5-structure-readme-refresh.md
└─ README.md                       # 当前项目入口说明
```

## 核心文件与算法

### `data/nea/`

这个文件夹只负责存放原始实验数据，不做人工编辑。文件名本身就是算法输入的一部分，因为程序要通过文件名识别：

- 跑道名称
- 测量方式
- 端点编号 `1/2`

### `custom/nea_length/nea_tools.py`

这个文件是真正的算法核心，主要做四件事。

第一，读取 `GGA` 句型。之所以用 `GGA` 而不是 `RMC`，是因为静态定位分析更依赖：

- `fix quality`
- 卫星数
- `HDOP`

这些质量指标在 `GGA` 中更完整。

第二，只取文件尾部 10 分钟数据，并按质量逐层筛选：

- 先保留当前文件中最高的 `fix quality`
- 再按 `HDOP` 做第二层筛选
- 最后剔除空间离群点

这个过程对应的是“先取更可信的定位解，再在这些定位解里做静态统计”的思路。

第三，用筛选后的静态点构造端点代表点。这里不是取最后一个点，也不是取轨迹首尾，而是对端点静态点做均值统计：

```text
lat_mean = (1/n) * Σ(lat_i)
lon_mean = (1/n) * Σ(lon_i)
```

同时计算标准差来描述端点稳定性：

```text
σ = sqrt((1/n) * Σ(x_i - x_mean)^2)
```

程序会分别得到：

- `std_lat_m`
- `std_lon_m`
- `horizontal_std_m = sqrt(std_lat_m^2 + std_lon_m^2)`

为了把经纬度偏差换成米，程序使用局部近似尺度：

```text
lat_scale ≈ 110540 m/deg
lon_scale ≈ 111320 * cos(latitude) m/deg
```

第四，计算起终点距离。这里使用 Haversine 公式：

```text
Δφ = φ2 - φ1
Δλ = λ2 - λ1
a = sin²(Δφ / 2) + cos(φ1) * cos(φ2) * sin²(Δλ / 2)
d = 2R * asin(sqrt(a))
```

其中 `d` 是最终端点距离，单位是米。

### `custom/nea_length/calculate_runway_distance.py`

这个文件是批处理入口，负责把 `nea_tools.py` 的算法应用到整批数据上。它的工作流程是：

1. 扫描 `data/nea/` 中所有 `.nea` 文件
2. 对每个文件做静态点筛选与均值/标准差统计
3. 按跑道名和测量方式分组
4. 把 `1` 和 `2` 当成起终点配对
5. 用端点代表点计算距离
6. 导出端点统计表和最终长度表

这里最重要的约定是：`1` 和 `2` 不是重复测量，而是起点文件和终点文件。

### `custom/nea_length/endpoint_representatives.csv`

这份表不是最终长度，而是端点文件质量表。它用来回答“这个端点坐标稳不稳”。

重点看这些字段：

- `representative_latitude`
- `representative_longitude`
- `horizontal_std_m`
- `fix_quality`
- `satellite_count_mean`
- `hdop_mean`

如果一个端点的 `horizontal_std_m` 很大，或者 `HDOP` 偏大，那么即使最终距离算出来了，也应该对这组结果保持谨慎。

### `custom/nea_length/runway_pair_results.csv`

这是当前最终结果表。每一行就是一条跑道在某种方法下的端点距离，应该优先以这份表作为结论来源。

### `custom/nea_length/runway_distance_results.csv`

这是旧算法结果，保留它只是为了追溯历史。它使用的是更早期的单文件首尾法，不再作为最终口径。

### `custom/notes/`

这个目录存放版本记录，作用不是重复 README，而是记录算法为什么从旧方案改到新方案。后续继续改算法时，应优先看这里，避免重复走回头路。

## 使用方法

在项目根目录直接运行：

```bash
python custom/nea_length/calculate_runway_distance.py
```

脚本默认输入目录就是：

```text
data/nea
```

如果以后换一批 `.nea` 文件，也可以显式指定目录：

```bash
python custom/nea_length/calculate_runway_distance.py --input-dir data/nea
```

运行后会更新：

- `custom/nea_length/endpoint_representatives.csv`
- `custom/nea_length/runway_pair_results.csv`

## 如何看结果

最终应以 `custom/nea_length/runway_pair_results.csv` 为准，但不要只看距离值本身。更稳妥的做法是把它和 `endpoint_representatives.csv` 一起看：

- 距离值回答“算出来多长”
- 标准差、`fix_quality`、`HDOP` 回答“这个长度靠不靠谱”

一般来说：

- `horizontal_std_m` 越小越稳
- `HDOP` 越小越好
- `fix_quality` 越高越可信
- `point_count` 越多越稳定

## 当前结果

当前 `runway_pair_results.csv` 中的结果为：

- 东操主席台
  - `bd`: `84.515 m`
  - `double`: `83.949 m`
  - `gps`: `95.361 m`

- 东操外侧
  - `bd`: `73.120 m`
  - `double`: `78.872 m`
  - `gps`: `71.539 m`

- 西操
  - `bd`: `91.757 m`
  - `double`: `93.652 m`
  - `gps`: `111.908 m`

## 注意事项

- 当前最终结果看 `runway_pair_results.csv`，不要把 `runway_distance_results.csv` 当成最终结论。
- 当前算法默认 `1` 是起点，`2` 是终点。
- 如果后续还要继续逼近理论 `100m`，优先考虑人工标注更严格的静态区间，或者确认不同设备的 `fix quality` 编码含义。


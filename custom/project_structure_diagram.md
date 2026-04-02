# 项目结构图

本文档用于展示当前仓库的实际目录结构，并在每个关键目录或文件后补充一句简短说明，便于在阅读 README、版本记录或实验报告之前快速建立整体认识。

```text
gps,bd,double result/                    # 项目根目录，包含原始数据、算法代码、结果文件和过程记录
├── data/                                # 原始数据区，只放输入数据
│   └── nea/                             # 18 个 .nea 原始观测文件，文件名同时承载跑道、方法、端点 1/2 信息
│       ├── 东操主席台1bd.nea           # 东操主席台，北斗方式，起点文件
│       ├── 东操主席台1double.nea       # 东操主席台，双模方式，起点文件
│       ├── 东操主席台1gps.nea          # 东操主席台，GPS 方式，起点文件
│       ├── 东操主席台2bd.nea           # 东操主席台，北斗方式，终点文件
│       ├── 东操主席台2double.nea       # 东操主席台，双模方式，终点文件
│       ├── 东操主席台2gps.nea          # 东操主席台，GPS 方式，终点文件
│       ├── 东操外侧1bd.nea             # 东操外侧，北斗方式，起点文件
│       ├── 东操外侧1double.nea         # 东操外侧，双模方式，起点文件
│       ├── 东操外侧1gps.nea            # 东操外侧，GPS 方式，起点文件
│       ├── 东操外侧2bd.nea             # 东操外侧，北斗方式，终点文件
│       ├── 东操外侧2double.nea         # 东操外侧，双模方式，终点文件
│       ├── 东操外侧2gps.nea            # 东操外侧，GPS 方式，终点文件
│       ├── 西操BD1.nea                 # 西操，北斗方式，起点文件
│       ├── 西操bd2.nea                 # 西操，北斗方式，终点文件
│       ├── 西操double1.nea             # 西操，双模方式，起点文件
│       ├── 西操double2.nea             # 西操，双模方式，终点文件
│       ├── 西操GPS1.nea                # 西操，GPS 方式，起点文件
│       └── 西操GPS2.nea                # 西操，GPS 方式，终点文件
├── custom/                              # AI 生成内容集中区，避免污染主目录
│   ├── nea_length/                      # 跑道长度计算模块，代码和结果都放在这里
│   │   ├── nea_tools.py                 # 核心算法库，负责 GGA 解析、质量筛选、均值统计和大地距离计算
│   │   ├── calculate_runway_distance.py # 批处理入口，负责扫描数据、按 1/2 配对并导出结果
│   │   ├── endpoint_representatives.csv # 端点统计结果，记录每个端点的代表坐标和质量指标
│   │   ├── runway_pair_results.csv      # 最终结果表，记录三条跑道三种方法的起终点距离
│   │   ├── runway_distance_results.csv  # 旧算法中间结果，仅保留作历史对照，不再作为最终结论
│   │   └── __pycache__/                 # Python 运行后生成的缓存目录，不属于人工维护内容
│   └── notes/                           # 正式版本记录区，保存每一轮思路、取舍和验证信息
│       ├── v1.0-nea-runway-distance.md
│       ├── v1.1-nea-runway-distance-window-filter.md
│       ├── v1.2-nea-endpoint-pairing.md
│       ├── v1.3-project-manual.md
│       ├── v1.4-pdf-guided-static-gga.md
│       ├── v1.5-structure-readme-refresh.md
│       └── v1.6-project-structure-diagram.md # 本轮记录，说明为什么新增结构图以及它解决了什么问题
├── .gitignore                           # Git 忽略规则，当前主要忽略 Python 缓存文件
├── LICENSE                              # 仓库许可证文件
└── README.md                            # 项目总说明，负责介绍目录、使用方式、算法口径和注意事项
```

## 结构图使用说明

- 如果想先理解“项目有哪些部分”，优先看本文件。
- 如果想知道“项目怎么运行”，看根目录 `README.md`。
- 如果想知道“算法为什么这样设计”，优先看 `custom/notes/v1.4-pdf-guided-static-gga.md`。
- 如果想直接查看最终长度结果，打开 `custom/nea_length/runway_pair_results.csv`。
- 如果想判断某个端点数据稳不稳，打开 `custom/nea_length/endpoint_representatives.csv`。

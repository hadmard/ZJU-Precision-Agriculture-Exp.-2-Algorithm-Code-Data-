"""
文件说明：该文件用于生成项目结构图图片。
功能说明：负责把当前项目的目录结构和中文说明渲染为 PNG 图片，供 README、报告或答辩材料直接引用。

结构概览：
  第一部分：导入依赖与基础常量
  第二部分：结构图文本内容定义
  第三部分：图片尺寸测量与绘制
  第四部分：主流程入口
"""

from pathlib import Path

from PIL import Image, ImageDraw, ImageFont


# ========== 第一部分：导入依赖与基础常量 ==========

ROOT_DIR = Path(__file__).resolve().parents[1]
OUTPUT_PATH = ROOT_DIR / "custom" / "project_structure_diagram.png"
FONT_PATH = Path(r"C:\Windows\Fonts\msyh.ttc")


# ========== 第二部分：结构图文本内容定义 ==========

# 这里直接在 UTF-8 源文件中维护中文内容，而不是走命令行内联字符串。
# 原因是 PowerShell 内联脚本在当前环境里会把中文转坏，最终导致 PNG 中出现问号。
LINES = [
    "项目结构图",
    "",
    "gps,bd,double result/    项目根目录，包含原始数据、算法代码、结果文件和过程记录",
    "├─ data/                  原始数据区，只放输入数据",
    "│  └─ nea/               18 个 .nea 原始观测文件，文件名同时承载跑道、方法、端点 1/2 信息",
    "│     ├─ 东操主席台1bd.nea        东操主席台，北斗方式，起点文件",
    "│     ├─ 东操主席台1double.nea    东操主席台，双模方式，起点文件",
    "│     ├─ 东操主席台1gps.nea       东操主席台，GPS 方式，起点文件",
    "│     ├─ 东操主席台2bd.nea        东操主席台，北斗方式，终点文件",
    "│     ├─ 东操主席台2double.nea    东操主席台，双模方式，终点文件",
    "│     ├─ 东操主席台2gps.nea       东操主席台，GPS 方式，终点文件",
    "│     ├─ 东操外侧1bd.nea          东操外侧，北斗方式，起点文件",
    "│     ├─ 东操外侧1double.nea      东操外侧，双模方式，起点文件",
    "│     ├─ 东操外侧1gps.nea         东操外侧，GPS 方式，起点文件",
    "│     ├─ 东操外侧2bd.nea          东操外侧，北斗方式，终点文件",
    "│     ├─ 东操外侧2double.nea      东操外侧，双模方式，终点文件",
    "│     ├─ 东操外侧2gps.nea         东操外侧，GPS 方式，终点文件",
    "│     ├─ 西操BD1.nea              西操，北斗方式，起点文件",
    "│     ├─ 西操bd2.nea              西操，北斗方式，终点文件",
    "│     ├─ 西操double1.nea          西操，双模方式，起点文件",
    "│     ├─ 西操double2.nea          西操，双模方式，终点文件",
    "│     ├─ 西操GPS1.nea             西操，GPS 方式，起点文件",
    "│     └─ 西操GPS2.nea             西操，GPS 方式，终点文件",
    "├─ custom/                AI 生成内容集中区，避免污染主目录",
    "│  ├─ nea_length/         跑道长度计算模块，代码和结果都放在这里",
    "│  │  ├─ nea_tools.py                 核心算法库，负责 GGA 解析、质量筛选、均值统计和大地距离计算",
    "│  │  ├─ calculate_runway_distance.py 批处理入口，负责扫描数据、按 1/2 配对并导出结果",
    "│  │  ├─ endpoint_representatives.csv 端点统计结果，记录每个端点的代表坐标和质量指标",
    "│  │  ├─ runway_pair_results.csv      最终结果表，记录三条跑道三种方法的起终点距离",
    "│  │  ├─ runway_distance_results.csv  旧算法中间结果，仅保留作历史对照",
    "│  │  └─ __pycache__/                 Python 运行缓存目录",
    "│  └─ notes/              正式版本记录区，保存每一轮思路、取舍和验证信息",
    "│     ├─ v1.0-nea-runway-distance.md",
    "│     ├─ v1.1-nea-runway-distance-window-filter.md",
    "│     ├─ v1.2-nea-endpoint-pairing.md",
    "│     ├─ v1.3-project-manual.md",
    "│     ├─ v1.4-pdf-guided-static-gga.md",
    "│     ├─ v1.5-structure-readme-refresh.md",
    "│     └─ v1.6-project-structure-diagram.md",
    "├─ .gitignore             Git 忽略规则",
    "├─ LICENSE                仓库许可证文件",
    "└─ README.md              项目总说明，介绍目录、使用方式、算法口径和注意事项",
]


# ========== 第三部分：图片尺寸测量与绘制 ==========

def pick_line_color(line: str) -> str:
    """根据目录层级给不同部分上轻量配色，便于阅读。"""
    if line.startswith("├─ data/") or line.startswith("├─ custom/"):
        return "#0b5cad"
    if line.startswith("│  ├─ nea_length/") or line.startswith("│  └─ notes/") or line.startswith("│  └─ nea/"):
        return "#176f5c"
    if line.startswith("├─ .gitignore") or line.startswith("├─ LICENSE") or line.startswith("└─ README.md"):
        return "#7a3e00"
    return "#1b1f24"


def render_structure_image(output_path: Path) -> None:
    if not FONT_PATH.exists():
        raise FileNotFoundError(f"未找到中文字体文件：{FONT_PATH}")

    title_font = ImageFont.truetype(str(FONT_PATH), 34)
    body_font = ImageFont.truetype(str(FONT_PATH), 20)
    small_font = ImageFont.truetype(str(FONT_PATH), 18)

    probe = Image.new("RGB", (10, 10), "white")
    draw = ImageDraw.Draw(probe)

    left = 48
    right = 48
    top = 40
    bottom = 40
    line_gap = 10
    line_heights = []
    max_width = 0

    for index, line in enumerate(LINES):
        font = title_font if index == 0 else body_font
        bbox = draw.textbbox((0, 0), line, font=font)
        width = bbox[2] - bbox[0]
        height = bbox[3] - bbox[1]
        max_width = max(max_width, width)
        line_heights.append(height)

    canvas_width = left + max_width + right
    canvas_height = top + bottom + sum(line_heights) + line_gap * (len(LINES) - 1) + 40

    image = Image.new("RGB", (canvas_width, canvas_height), "#f6f8fb")
    draw = ImageDraw.Draw(image)

    header_height = 74
    draw.rounded_rectangle((24, 20, canvas_width - 24, 20 + header_height), radius=18, fill="#1f4f8c")
    draw.text((left, 34), LINES[0], font=title_font, fill="white")
    draw.text((canvas_width - 360, 40), "GNSS 跑道长度计算项目", font=small_font, fill="#dbe8ff")

    current_y = 20 + header_height + 24
    for index, line in enumerate(LINES[1:], start=1):
        if line == "":
            current_y += 8
            continue
        draw.text((left, current_y), line, font=body_font, fill=pick_line_color(line))
        current_y += line_heights[index] + line_gap

    image.save(output_path)


# ========== 第四部分：主流程入口 ==========

def main() -> None:
    render_structure_image(OUTPUT_PATH)
    print(OUTPUT_PATH)


if __name__ == "__main__":
    main()

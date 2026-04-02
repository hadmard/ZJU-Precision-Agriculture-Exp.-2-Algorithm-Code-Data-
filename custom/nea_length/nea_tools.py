"""
文件说明：该文件提供 `.nea` 文件解析与跑道端点距离计算工具。
功能说明：负责读取 NMEA 文本、提取 GGA 静态定位点、按质量筛选端点样本，并计算端点间距离。

结构概览：
  第一部分：基础数据结构
  第二部分：NMEA 解析基础函数
  第三部分：GGA 观测提取
  第四部分：静态点质量筛选与代表点生成
  第五部分：文件名解析与距离计算
"""

from __future__ import annotations

import math
import re
import statistics
from dataclasses import dataclass
from pathlib import Path
from typing import Iterator


# ========== 第一部分：基础数据结构 ==========


@dataclass(frozen=True)
class GgaPoint:
    """单个有效 GGA 观测点。"""

    timestamp_s: int
    latitude: float
    longitude: float
    fix_quality: int
    satellite_count: int
    hdop: float
    altitude_m: float | None
    sentence_type: str
    line_no: int


@dataclass(frozen=True)
class RepresentativePoint:
    """
    单个端点文件提炼出的静态代表点。

    这里不只保存均值坐标，还保存标准差、点数、平均卫星数、平均 HDOP。
    这样后续在看结果时，不会只拿一个距离值做判断，而是能同时评估端点质量。
    """

    latitude: float
    longitude: float
    std_lat_m: float
    std_lon_m: float
    horizontal_std_m: float
    point_count: int
    fix_quality: int
    satellite_count_mean: float
    hdop_mean: float


# ========== 第二部分：NMEA 解析基础函数 ==========


def _parse_nmea_coordinate(raw_value: str, hemisphere: str) -> float | None:
    """把 NMEA 的 ddmm.mmmm / dddmm.mmmm 形式转换为十进制度。"""

    if not raw_value:
        return None

    try:
        value = float(raw_value)
    except ValueError:
        return None

    degrees = int(value // 100)
    minutes = value - degrees * 100
    decimal = degrees + minutes / 60.0
    if hemisphere in {"S", "W"}:
        decimal = -decimal
    return decimal


def _parse_nmea_time(raw_value: str) -> int | None:
    """把 NMEA 的 `hhmmss.sss` 时间字段转换为从零点开始的秒数。"""

    if not raw_value or len(raw_value) < 6:
        return None

    try:
        hours = int(raw_value[0:2])
        minutes = int(raw_value[2:4])
        seconds = int(raw_value[4:6])
    except ValueError:
        return None

    return hours * 3600 + minutes * 60 + seconds


def haversine_distance_m(start: tuple[float, float], end: tuple[float, float]) -> float:
    """计算两点之间的大地距离，单位为米。"""

    radius_m = 6_371_000.0
    start_lat, start_lon = map(math.radians, start)
    end_lat, end_lon = map(math.radians, end)
    delta_lat = end_lat - start_lat
    delta_lon = end_lon - start_lon
    a = (
        math.sin(delta_lat / 2) ** 2
        + math.cos(start_lat) * math.cos(end_lat) * math.sin(delta_lon / 2) ** 2
    )
    return 2 * radius_m * math.asin(min(1.0, math.sqrt(a)))


def _meters_per_degree(latitude: float) -> tuple[float, float]:
    """估算当前纬度下，经纬度对应的米制尺度。"""

    lat_scale = 110_540.0
    lon_scale = 111_320.0 * math.cos(math.radians(latitude))
    return lat_scale, lon_scale


# ========== 第三部分：GGA 观测提取 ==========


def read_gga_points(file_path: Path) -> list[GgaPoint]:
    """
    从 `.nea` 文件中提取有效 GGA 观测点。

    PDF 明确强调静态定位要利用定位质量、卫星数、HDOP 等指标，
    这些字段在 GGA 里最完整，所以这里以 GGA 为主。

    当前解析逻辑不依赖具体品牌设备，只要句型尾部是 GGA、字段位置符合 NMEA 常见格式，
    就能统一抽成一个结构化观测点。
    """

    points: list[GgaPoint] = []
    text = file_path.read_text(encoding="ascii", errors="ignore")

    for line_no, raw_line in enumerate(text.splitlines(), start=1):
        if not raw_line.startswith("$"):
            continue

        parts = raw_line.split(",")
        sentence_type = parts[0]
        if not sentence_type.endswith("GGA"):
            continue

        if len(parts) < 10:
            continue

        timestamp_s = _parse_nmea_time(parts[1])
        latitude = _parse_nmea_coordinate(parts[2], parts[3])
        longitude = _parse_nmea_coordinate(parts[4], parts[5])

        try:
            fix_quality = int(parts[6]) if parts[6] else 0
            satellite_count = int(parts[7]) if parts[7] else 0
            hdop = float(parts[8]) if parts[8] else float("inf")
            altitude_m = float(parts[9]) if parts[9] else None
        except ValueError:
            continue

        if timestamp_s is None or latitude is None or longitude is None:
            continue
        if fix_quality <= 0:
            continue

        points.append(
            GgaPoint(
                timestamp_s=timestamp_s,
                latitude=latitude,
                longitude=longitude,
                fix_quality=fix_quality,
                satellite_count=satellite_count,
                hdop=hdop,
                altitude_m=altitude_m,
                sentence_type=sentence_type,
                line_no=line_no,
            )
        )

    return points


def trim_last_ten_minutes(points: list[GgaPoint]) -> list[GgaPoint]:
    """
    只保留尾部 10 分钟的观测点。

    这是当前实验口径的一部分。它不是通用 GNSS 规则，而是本项目对原始数据的固定裁剪方式。
    """

    if not points:
        return []

    window_end = points[-1].timestamp_s
    window_start = window_end - 600
    trimmed = [point for point in points if window_start <= point.timestamp_s <= window_end]

    # 同一秒可能出现重复句子，这里只保留质量更高、HDOP 更小的一条。
    # 这样做是为了避免同一时刻多个句子把静态统计中的样本权重放大。
    deduped: dict[int, GgaPoint] = {}
    for point in trimmed:
        current = deduped.get(point.timestamp_s)
        if current is None:
            deduped[point.timestamp_s] = point
            continue
        better = (
            point.fix_quality > current.fix_quality
            or (
                point.fix_quality == current.fix_quality
                and point.hdop < current.hdop
            )
        )
        if better:
            deduped[point.timestamp_s] = point

    return [deduped[key] for key in sorted(deduped)]


# ========== 第四部分：静态点质量筛选与代表点生成 ==========


def _select_best_quality_layer(points: list[GgaPoint]) -> list[GgaPoint]:
    """
    优先保留最佳定位质量层。

    不同设备对 fix quality 的编码不完全一致，所以这里不硬编码只认某个值，
    而是直接取当前文件里最高质量等级。

    这样虽然牺牲了一部分“严格按设备说明书写死”的确定性，但换来了跨不同日志格式时更稳的兼容性。
    """

    if not points:
        return []

    best_fix_quality = max(point.fix_quality for point in points)
    return [point for point in points if point.fix_quality == best_fix_quality]


def _filter_by_hdop(points: list[GgaPoint]) -> list[GgaPoint]:
    """
    利用 HDOP 做第二层质量筛选。

    这里不直接写死一个全局阈值，而是以当前样本中位数为基础做自适应限制。
    原因是不同测量方式和不同设备的 HDOP 基线并不完全一致。
    """

    if len(points) < 5:
        return points

    ordered_hdop = sorted(point.hdop for point in points if math.isfinite(point.hdop))
    if not ordered_hdop:
        return points

    median_hdop = statistics.median(ordered_hdop)
    hdop_limit = max(min(2.5, median_hdop * 1.5), median_hdop)
    filtered = [point for point in points if point.hdop <= hdop_limit]
    return filtered if len(filtered) >= 5 else points


def _filter_spatial_outliers(points: list[GgaPoint]) -> list[GgaPoint]:
    """
    用静态散布的 MAD 规则剔除明显离群点。

    这里把每个点到中位数中心的平面距离转成米，再做鲁棒统计。
    相比直接按经纬度阈值过滤，这样更符合“静态点云散布”的实际形态。
    """

    if len(points) < 5:
        return points

    center_lat = statistics.median(point.latitude for point in points)
    center_lon = statistics.median(point.longitude for point in points)
    lat_scale, lon_scale = _meters_per_degree(center_lat)

    distances = []
    for point in points:
        north_m = (point.latitude - center_lat) * lat_scale
        east_m = (point.longitude - center_lon) * lon_scale
        distances.append(math.hypot(north_m, east_m))

    median_distance = statistics.median(distances)
    mad = statistics.median(abs(distance - median_distance) for distance in distances)
    limit = max(0.5, median_distance + 4.0 * mad)

    filtered = [
        point
        for point, distance in zip(points, distances)
        if distance <= limit
    ]
    return filtered if len(filtered) >= 5 else points


def select_static_points(points: list[GgaPoint]) -> list[GgaPoint]:
    """
    根据 PDF 的静态定位思路选择端点样本。

    处理顺序：
    1. 只看尾部 10 分钟
    2. 选择当前文件内最高 fix quality
    3. 再按 HDOP 做质量筛选
    4. 最后去掉空间离群点

    这个顺序是有意安排的：
    - 先按 fix quality 分层，是为了优先保留更可信的定位解
    - 再按 HDOP 控制几何质量
    - 最后才做空间离群点过滤，避免低质量点把中心位置带偏
    """

    window_points = trim_last_ten_minutes(points)
    quality_points = _select_best_quality_layer(window_points)
    hdop_points = _filter_by_hdop(quality_points)
    return _filter_spatial_outliers(hdop_points)


def build_representative_point(points: list[GgaPoint]) -> RepresentativePoint:
    """
    用静态观测均值生成端点代表点，并输出标准差。

    这一步直接对应 PDF 中“静态定位误差可用平均值与标准差描述”的处理思路。

    这里使用总体标准差 `pstdev`，是因为当前点集被看作“本次端点静态观测样本整体”，
    目标是描述这批点自身的离散程度，而不是去估计更大总体的抽样误差。
    """

    if len(points) < 2:
        raise ValueError("有效静态点少于 2 个，无法生成端点代表点。")

    latitudes = [point.latitude for point in points]
    longitudes = [point.longitude for point in points]
    center_lat = statistics.mean(latitudes)
    center_lon = statistics.mean(longitudes)
    lat_scale, lon_scale = _meters_per_degree(center_lat)

    if len(points) >= 2:
        std_lat_m = statistics.pstdev(latitudes) * lat_scale
        std_lon_m = statistics.pstdev(longitudes) * lon_scale
    else:
        std_lat_m = 0.0
        std_lon_m = 0.0

    return RepresentativePoint(
        latitude=center_lat,
        longitude=center_lon,
        std_lat_m=std_lat_m,
        std_lon_m=std_lon_m,
        horizontal_std_m=math.hypot(std_lat_m, std_lon_m),
        point_count=len(points),
        fix_quality=max(point.fix_quality for point in points),
        satellite_count_mean=statistics.mean(point.satellite_count for point in points),
        hdop_mean=statistics.mean(point.hdop for point in points),
    )


# ========== 第五部分：文件名解析与距离计算 ==========


def parse_file_identity(file_path: Path) -> tuple[str, str, str]:
    """
    从文件名中解析跑道名、测量方式和 1/2 端点编号。

    当前项目同时存在两种命名风格：
    - `东操主席台1gps.nea`
    - `西操GPS1.nea`

    所以这里保留两套正则，而不是为了代码整洁强行重命名原始文件。
    """

    stem = file_path.stem

    east_style = re.match(r"^(?P<runway>.+?)(?P<repeat>\d+)(?P<method>gps|bd|double)$", stem, re.I)
    if east_style:
        return (
            east_style.group("runway"),
            east_style.group("method").lower(),
            east_style.group("repeat"),
        )

    west_style = re.match(r"^(?P<runway>.+?)(?P<method>gps|bd|double)(?P<repeat>\d+)$", stem, re.I)
    if west_style:
        return (
            west_style.group("runway"),
            west_style.group("method").lower(),
            west_style.group("repeat"),
        )

    return stem, "unknown", ""


def iter_nea_files(input_dir: Path) -> Iterator[Path]:
    """按文件名排序遍历目录中的 `.nea` 文件。"""

    yield from sorted(input_dir.glob("*.nea"), key=lambda item: item.name)

"""
文件说明：该文件是 `.nea` 跑道端点配对计算的批量入口。
功能说明：按 PDF 的静态定位思路，读取每个端点文件的 GGA 观测，生成端点均值坐标，再按 `1/2` 配对计算跑道长度。

结构概览：
  第一部分：命令行参数解析
  第二部分：单文件端点统计
  第三部分：跑道配对计算
  第四部分：结果导出
  第五部分：主流程
"""

from __future__ import annotations

import argparse
import csv
from dataclasses import dataclass
from pathlib import Path

from nea_tools import (
    RepresentativePoint,
    build_representative_point,
    haversine_distance_m,
    iter_nea_files,
    parse_file_identity,
    read_gga_points,
    select_static_points,
)


# ========== 第一部分：命令行参数解析 ==========


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="按端点文件计算 .nea 跑道长度")
    parser.add_argument(
        "--input-dir",
        default="data/nea",
        help="包含 .nea 文件的目录，默认 data/nea",
    )
    parser.add_argument(
        "--endpoint-csv",
        default="custom/nea_length/endpoint_representatives.csv",
        help="每个端点文件的统计结果输出路径",
    )
    parser.add_argument(
        "--pair-csv",
        default="custom/nea_length/runway_pair_results.csv",
        help="跑道 1/2 配对后的距离输出路径",
    )
    return parser


# ========== 第二部分：单文件端点统计 ==========#


@dataclass(frozen=True)
class EndpointResult:
    """
    单个端点文件的静态统计结果。

    这一层是“端点文件级”的摘要，目的是让结果 CSV 本身就能解释：
    当前端点是怎么统计出来的、稳定性如何、质量指标大概是什么水平。
    """

    file_name: str
    runway_name: str
    method_name: str
    repeat_id: str
    point_count: int
    representative_latitude: float
    representative_longitude: float
    std_lat_m: float
    std_lon_m: float
    horizontal_std_m: float
    fix_quality: int
    satellite_count_mean: float
    hdop_mean: float


def process_file(file_path: Path) -> tuple[EndpointResult, RepresentativePoint]:
    """
    处理单个端点文件。

    算法顺序与 `nea_tools.py` 保持一致：
    1. 读取 GGA
    2. 选尾部 10 分钟
    3. 选最高质量层
    4. 按 HDOP 和空间散布过滤
    5. 用均值和标准差生成端点代表点
    """

    runway_name, method_name, repeat_id = parse_file_identity(file_path)
    raw_points = read_gga_points(file_path)
    static_points = select_static_points(raw_points)
    representative = build_representative_point(static_points)

    row = EndpointResult(
        file_name=file_path.name,
        runway_name=runway_name,
        method_name=method_name,
        repeat_id=repeat_id,
        point_count=representative.point_count,
        representative_latitude=representative.latitude,
        representative_longitude=representative.longitude,
        std_lat_m=representative.std_lat_m,
        std_lon_m=representative.std_lon_m,
        horizontal_std_m=representative.horizontal_std_m,
        fix_quality=representative.fix_quality,
        satellite_count_mean=representative.satellite_count_mean,
        hdop_mean=representative.hdop_mean,
    )
    return row, representative


# ========== 第三部分：跑道配对计算 ==========#


@dataclass(frozen=True)
class PairResult:
    """同一路径 1/2 文件配对后的长度结果。"""

    runway_name: str
    method_name: str
    start_file: str
    end_file: str
    start_latitude: float
    start_longitude: float
    end_latitude: float
    end_longitude: float
    distance_m: float


def build_pair_results(
    endpoint_rows: list[EndpointResult],
    endpoint_points: dict[str, RepresentativePoint],
) -> list[PairResult]:
    """
    按跑道和方法把 1/2 端点配对。

    这里默认遵守当前项目约定：
    - `1` 是起点
    - `2` 是终点

    不再把 `1/2` 当成重复测量，也不做跨文件平均。
    """

    grouped: dict[tuple[str, str], dict[str, EndpointResult]] = {}
    for row in endpoint_rows:
        grouped.setdefault((row.runway_name, row.method_name), {})[row.repeat_id] = row

    pair_results: list[PairResult] = []
    for (runway_name, method_name), repeats in sorted(grouped.items()):
        if "1" not in repeats or "2" not in repeats:
            continue

        start_row = repeats["1"]
        end_row = repeats["2"]
        start_point = endpoint_points[start_row.file_name]
        end_point = endpoint_points[end_row.file_name]
        distance_m = haversine_distance_m(
            (start_point.latitude, start_point.longitude),
            (end_point.latitude, end_point.longitude),
        )

        pair_results.append(
            PairResult(
                runway_name=runway_name,
                method_name=method_name,
                start_file=start_row.file_name,
                end_file=end_row.file_name,
                start_latitude=start_point.latitude,
                start_longitude=start_point.longitude,
                end_latitude=end_point.latitude,
                end_longitude=end_point.longitude,
                distance_m=distance_m,
            )
        )

    return pair_results


# ========== 第四部分：结果导出 ==========#


def write_endpoint_csv(output_path: Path, rows: list[EndpointResult]) -> None:
    """导出端点统计结果，供质量复核和报告引用。"""

    output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open("w", newline="", encoding="utf-8-sig") as fh:
        writer = csv.writer(fh)
        writer.writerow(
            [
                "file_name",
                "runway_name",
                "method_name",
                "repeat_id",
                "point_count",
                "representative_latitude",
                "representative_longitude",
                "std_lat_m",
                "std_lon_m",
                "horizontal_std_m",
                "fix_quality",
                "satellite_count_mean",
                "hdop_mean",
            ]
        )
        for row in rows:
            writer.writerow(
                [
                    row.file_name,
                    row.runway_name,
                    row.method_name,
                    row.repeat_id,
                    row.point_count,
                    f"{row.representative_latitude:.8f}",
                    f"{row.representative_longitude:.8f}",
                    f"{row.std_lat_m:.3f}",
                    f"{row.std_lon_m:.3f}",
                    f"{row.horizontal_std_m:.3f}",
                    row.fix_quality,
                    f"{row.satellite_count_mean:.2f}",
                    f"{row.hdop_mean:.3f}",
                ]
            )


def write_pair_csv(output_path: Path, rows: list[PairResult]) -> None:
    """导出最终跑道配对结果。"""

    output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open("w", newline="", encoding="utf-8-sig") as fh:
        writer = csv.writer(fh)
        writer.writerow(
            [
                "runway_name",
                "method_name",
                "start_file",
                "end_file",
                "start_latitude",
                "start_longitude",
                "end_latitude",
                "end_longitude",
                "distance_m",
            ]
        )
        for row in rows:
            writer.writerow(
                [
                    row.runway_name,
                    row.method_name,
                    row.start_file,
                    row.end_file,
                    f"{row.start_latitude:.8f}",
                    f"{row.start_longitude:.8f}",
                    f"{row.end_latitude:.8f}",
                    f"{row.end_longitude:.8f}",
                    f"{row.distance_m:.3f}",
                ]
            )


def print_summary(rows: list[PairResult]) -> None:
    """在终端打印简化后的最终结果。"""

    print("=== 跑道配对结果 ===")
    for row in rows:
        print(
            f"{row.runway_name}\t{row.method_name}\t"
            f"{row.start_file} -> {row.end_file}\t"
            f"distance_m={row.distance_m:.3f}"
        )


# ========== 第五部分：主流程 ==========#


def main() -> int:
    """
    主流程说明：

    - 先逐个端点文件做静态统计
    - 再按跑道名和测量方式分组
    - 最后把 `1/2` 文件配成一条跑道长度结果
    """

    args = build_arg_parser().parse_args()
    input_dir = Path(args.input_dir)
    endpoint_csv = Path(args.endpoint_csv)
    pair_csv = Path(args.pair_csv)

    endpoint_rows: list[EndpointResult] = []
    endpoint_points: dict[str, RepresentativePoint] = {}

    for file_path in iter_nea_files(input_dir):
        try:
            row, representative = process_file(file_path)
        except Exception as exc:  # noqa: BLE001 - 单文件失败需要显式提示
            print(f"[跳过] {file_path.name}: {exc}")
            continue
        endpoint_rows.append(row)
        endpoint_points[row.file_name] = representative

    if not endpoint_rows:
        print("未找到可用的 .nea 文件或没有成功解析的文件。")
        return 1

    pair_rows = build_pair_results(endpoint_rows, endpoint_points)
    if not pair_rows:
        print("没有找到完整的 1/2 配对文件。")
        return 1

    write_endpoint_csv(endpoint_csv, endpoint_rows)
    write_pair_csv(pair_csv, pair_rows)
    print_summary(pair_rows)
    print()
    print(f"端点统计结果已写入: {endpoint_csv}")
    print(f"跑道配对结果已写入: {pair_csv}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

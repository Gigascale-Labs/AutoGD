"""Run both Figure 6 parameter cases for the static scarcity-of-labor model."""

from __future__ import annotations

import json
import math
import sys
import struct
import zlib
from pathlib import Path

from model import automation_threshold, evaluate_model


ROOT = Path(__file__).resolve().parent
OUTPUTS = ROOT / "outputs"
GRID_SIZE = 101
ACCOUNTING_TOLERANCE = 1e-10


def phi_grid() -> list[float]:
    return [index / (GRID_SIZE - 1) for index in range(GRID_SIZE)]


def evaluate_case(case_name: str, parameters: dict[str, float]) -> dict:
    results = [evaluate_model(phi, parameters) for phi in phi_grid()]
    failures = [result for result in results if not math.isclose(
        result["Y"],
        result["wage_bill"] + result["capital_income"],
        rel_tol=ACCOUNTING_TOLERANCE,
        abs_tol=ACCOUNTING_TOLERANCE,
    )]
    if failures:
        raise ArithmeticError(
            f"Accounting identity failed for {case_name} at Phi={failures[0]['phi']}."
        )
    return {
        "case": case_name,
        "parameters": parameters,
        "threshold": automation_threshold(parameters["K"], parameters["L"]),
        "results": results,
    }


def save_json(path: Path, result: dict) -> None:
    with path.open("w", encoding="utf-8") as output_file:
        json.dump(result, output_file, indent=2, allow_nan=False)
        output_file.write("\n")


def set_pixel(image: bytearray, width: int, height: int, x: int, y: int, color: tuple[int, int, int]) -> None:
    if 0 <= x < width and 0 <= y < height:
        offset = (y * width + x) * 3
        image[offset:offset + 3] = bytes(color)


def draw_line(image: bytearray, width: int, height: int, start: tuple[int, int], end: tuple[int, int], color: tuple[int, int, int]) -> None:
    x0, y0 = start
    x1, y1 = end
    steps = max(abs(x1 - x0), abs(y1 - y0), 1)
    for step in range(steps + 1):
        x = round(x0 + (x1 - x0) * step / steps)
        y = round(y0 + (y1 - y0) * step / steps)
        set_pixel(image, width, height, x, y, color)


FONT = {
    "A": ("01110", "10001", "10001", "11111", "10001", "10001", "10001"),
    "B": ("11110", "10001", "10001", "11110", "10001", "10001", "11110"),
    "E": ("11111", "10000", "10000", "11110", "10000", "10000", "11111"),
    "F": ("11111", "10000", "10000", "11110", "10000", "10000", "10000"),
    "G": ("01110", "10000", "10000", "10111", "10001", "10001", "01110"),
    "H": ("10001", "10001", "10001", "11111", "10001", "10001", "10001"),
    "I": ("11111", "00100", "00100", "00100", "00100", "00100", "11111"),
    "K": ("10001", "10010", "10100", "11000", "10100", "10010", "10001"),
    "L": ("10000", "10000", "10000", "10000", "10000", "10000", "11111"),
    "P": ("11110", "10001", "10001", "11110", "10000", "10000", "10000"),
    "R": ("11110", "10001", "10001", "11110", "10100", "10010", "10001"),
    "T": ("11111", "00100", "00100", "00100", "00100", "00100", "00100"),
    "W": ("10001", "10001", "10001", "10101", "10101", "10101", "01010"),
    "Y": ("10001", "10001", "01010", "00100", "00100", "00100", "00100"),
    ":": ("00000", "00100", "00100", "00000", "00100", "00100", "00000"),
    " ": ("000", "000", "000", "000", "000", "000", "000"),
}


def draw_text(image: bytearray, width: int, height: int, x: int, y: int, text: str, color: tuple[int, int, int], scale: int = 2) -> None:
    cursor = x
    for character in text:
        glyph = FONT[character]
        for row, pixels in enumerate(glyph):
            for column, pixel in enumerate(pixels):
                if pixel == "1":
                    for dx in range(scale):
                        for dy in range(scale):
                            set_pixel(image, width, height, cursor + column * scale + dx, y + row * scale + dy, color)
        cursor += (len(glyph[0]) + 1) * scale


def write_png(path: Path, image: bytearray, width: int, height: int) -> None:
    raw_rows = b"".join(b"\x00" + bytes(image[row * width * 3:(row + 1) * width * 3]) for row in range(height))

    def chunk(kind: bytes, payload: bytes) -> bytes:
        return struct.pack(">I", len(payload)) + kind + payload + struct.pack(">I", zlib.crc32(kind + payload) & 0xFFFFFFFF)

    png = b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", struct.pack(">IIBBBBB", width, height, 8, 2, 0, 0, 0))
    png += chunk(b"IDAT", zlib.compress(raw_rows, level=9)) + chunk(b"IEND", b"")
    path.write_bytes(png)


def create_plot(case_results: dict[str, dict]) -> None:
    width, height = 1200, 600
    image = bytearray([255, 255, 255]) * (width * height)
    colors = {"Y": (31, 119, 180), "wage_bill": (44, 160, 44), "capital_income": (214, 39, 40)}
    for index, data in enumerate(case_results.values()):
        left = 80 + index * 600
        right, top, bottom = left + 500, 70, 520
        results = data["results"]
        maximum = max(item[key] for item in results for key in colors) * 1.05
        draw_line(image, width, height, (left, bottom), (right, bottom), (0, 0, 0))
        draw_line(image, width, height, (left, top), (left, bottom), (0, 0, 0))
        threshold_x = round(left + (right - left) * data["threshold"])
        for y in range(top, bottom, 8):
            draw_line(image, width, height, (threshold_x, y), (threshold_x, min(y + 3, bottom)), (80, 80, 80))
        for key, color in colors.items():
            points = [
                (round(left + (right - left) * item["phi"]), round(bottom - (bottom - top) * item[key] / maximum))
                for item in results
            ]
            for start, end in zip(points, points[1:]):
                draw_line(image, width, height, start, end, color)
        label = "LEFT" if index == 0 else "RIGHT"
        draw_text(image, width, height, left, 20, label, (0, 0, 0))
        draw_text(image, width, height, left, 545, "PHI", (0, 0, 0))
        draw_text(image, width, height, left + 120, 20, "Y", colors["Y"])
        draw_text(image, width, height, left + 150, 20, "WL", colors["wage_bill"])
        draw_text(image, width, height, left + 200, 20, "RK", colors["capital_income"])
    write_png(OUTPUTS / "figure6.png", image, width, height)


def main() -> int:
    with (ROOT / "parameters.json").open(encoding="utf-8") as parameter_file:
        cases = json.load(parameter_file)

    OUTPUTS.mkdir(exist_ok=True)
    case_results = {
        case_name: evaluate_case(case_name, parameters)
        for case_name, parameters in cases.items()
    }
    save_json(OUTPUTS / "left_results.json", case_results["left"])
    save_json(OUTPUTS / "right_results.json", case_results["right"])
    create_plot(case_results)
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except ArithmeticError as error:
        print(error, file=sys.stderr)
        raise SystemExit(1)

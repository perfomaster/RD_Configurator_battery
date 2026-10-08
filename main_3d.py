from __future__ import annotations

import csv
import io
import json
import math
import re
import signal
import sys
import threading
from dataclasses import dataclass
from functools import lru_cache
from itertools import permutations
from pathlib import Path
from typing import Optional

try:
    import customtkinter as ctk
except ImportError:
    print("Установите зависимости: pip install customtkinter openpyxl Pillow cairosvg matplotlib")
    raise

import tkinter as tk
from tkinter import filedialog, messagebox

try:
    from PIL import Image, ImageDraw, ImageFont, ImageTk
except ImportError:
    Image = None
    ImageDraw = None
    ImageFont = None
    ImageTk = None

try:
    from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
    from matplotlib.figure import Figure
    from mpl_toolkits.mplot3d.art3d import Poly3DCollection
    MATPLOTLIB_AVAILABLE = True
except ImportError:
    Figure = None
    FigureCanvasTkAgg = None
    Poly3DCollection = None
    MATPLOTLIB_AVAILABLE = False


ROOT = Path(__file__).resolve().parent
DB_PATH = ROOT / "cells_db.txt"
ONLINE_DB_PATH = ROOT / "cell_online.txt"
STATE_PATH = ROOT / "main_state.json"
LOGO_PATHS = [ROOT / "logo_RD.png", ROOT / "logo.png", ROOT / "logo_RD.svg", ROOT / "logo.svg"]
ICO_PATHS = [ROOT / "logo_RD_ico.ico", ROOT / "logo_RD.ico", ROOT / "logo.ico"]
ICON_PATHS = [*ICO_PATHS, ROOT / "logo_RD_ico.png", ROOT / "logo_RD.png"]
HEADER = [
    "наименование", "бренд", "тип_химии", "тип_формы", "длина_мм", "ширина_мм",
    "высота_мм", "емкость_Ач", "напряжение_ном_В", "напряжение_мин_В",
    "напряжение_макс_В", "макс_ток_разряда_А", "макс_ток_заряда_А",
    "мин_темп_разряда", "макс_темп_разряда", "масса_г",
    "внутр_сопротивление_мОм", "циклов", "емкость_после_1000_циклов_%",
]
BG = "#fdf6f4"
FIELD_BG = "#f6dcd6"
BUTTON = "#c9c9c9"
BUTTON_HOVER = "#b5b5b5"
ERROR = "#b00020"
OK = "#1b7a1b"
CONFIRMED_BG = "#dff3df"
ONLINE_BG = "#fff4c7"
FONT = ("GOST type A", 14)


@dataclass
class Cell:
    name: str
    brand: str
    chemistry: str
    shape: str
    length: float
    width: float
    height: float
    capacity: float
    voltage_nom: float
    voltage_min: Optional[float]
    voltage_max: Optional[float]
    max_discharge: float
    max_charge: Optional[float]
    temp_min: Optional[float]
    temp_max: Optional[float]
    mass: Optional[float]
    resistance: Optional[float]
    cycles: Optional[float]
    capacity_1000: Optional[float]
    source: str = "manual"


@dataclass
class Pack:
    s: int
    p: int
    n: int
    dims: tuple[float, float, float]
    grid: tuple[int, int, int]
    orientation: tuple[str, str, str]
    energy: float
    capacity: float
    voltage: float
    max_current: float
    runtime: float
    volume: float
    ok_time: bool
    ok_dims: bool
    warning: str
    cell: Cell
    marks: str = ""


def ensure_db(path: Path = DB_PATH) -> None:
    if not path.exists() or path.stat().st_size == 0:
        path.write_text(";".join(HEADER) + "\n", encoding="utf-8")


def to_float(value: str) -> Optional[float]:
    value = value.strip().replace(",", ".")
    if not value:
        return None
    return float(value)


def must_float(row: dict[str, str], key: str) -> float:
    value = to_float(row.get(key, ""))
    if value is None:
        raise ValueError(key)
    return value


def load_one_db(path: Path, source: str) -> tuple[list[Cell], int]:
    ensure_db(path)
    cells: list[Cell] = []
    skipped = 0
    with path.open("r", encoding="utf-8", newline="") as fh:
        reader = csv.reader(fh, delimiter=";")
        try:
            header = next(reader)
        except StopIteration:
            return [], 0
        if header != HEADER:
            print("Предупреждение: заголовок базы отличается от ожидаемого.")
        for line_no, parts in enumerate(reader, start=2):
            if not parts or all(not p.strip() for p in parts):
                continue
            if len(parts) != len(HEADER):
                skipped += 1
                print(f"Пропуск строки {line_no}: ожидалось {len(HEADER)} полей, получено {len(parts)}")
                continue
            row = {key: value.strip() for key, value in zip(HEADER, parts)}
            try:
                shape = row["тип_формы"].upper()
                if shape not in {"C", "P"}:
                    raise ValueError("тип_формы")
                cells.append(Cell(
                    row["наименование"], row["бренд"], row["тип_химии"], shape,
                    must_float(row, "длина_мм"), must_float(row, "ширина_мм"), must_float(row, "высота_мм"),
                    must_float(row, "емкость_Ач"), must_float(row, "напряжение_ном_В"),
                    to_float(row["напряжение_мин_В"]), to_float(row["напряжение_макс_В"]),
                    must_float(row, "макс_ток_разряда_А"), to_float(row["макс_ток_заряда_А"]),
                    to_float(row["мин_темп_разряда"]), to_float(row["макс_темп_разряда"]),
                    to_float(row["масса_г"]), to_float(row["внутр_сопротивление_мОм"]),
                    to_float(row["циклов"]), to_float(row["емкость_после_1000_циклов_%"]), source,
                ))
            except Exception as exc:
                skipped += 1
                print(f"Пропуск строки {line_no}: {exc}")
    print(f"База: {path}")
    print(f"Загружено ячеек ({source}): {len(cells)}")
    print(f"Пропущено строк: {skipped}")
    return cells, skipped


def load_db() -> tuple[list[Cell], int]:
    manual, skipped_manual = load_one_db(DB_PATH, "manual")
    # Онлайн-база временно отключена от расчётов, код загрузки оставлен для будущего возврата.
    return manual, skipped_manual


def generated_rd_logo(size: int):
    if Image is None or ImageDraw is None:
        return None
    image = Image.new("RGBA", (size, size), (253, 246, 244, 255))
    draw = ImageDraw.Draw(image)
    draw.rounded_rectangle((1, 1, size - 2, size - 2), radius=max(4, size // 5), fill="#f6dcd6", outline="#1a1a1a", width=2)
    try:
        font = ImageFont.truetype("arialbd.ttf", max(14, int(size * 0.42))) if ImageFont else None
    except Exception:
        font = None
    text = "RD"
    box = draw.textbbox((0, 0), text, font=font)
    x = (size - (box[2] - box[0])) / 2
    y = (size - (box[3] - box[1])) / 2 - 1
    draw.text((x, y), text, fill="#1a1a1a", font=font)
    return ctk.CTkImage(light_image=image, dark_image=image, size=(size, size))


def add_black_background(image: Image.Image) -> Image.Image:
    image = image.convert("RGBA")
    bg = Image.new("RGBA", image.size, (0, 0, 0, 255))
    bg.alpha_composite(image)
    return bg


def svg_dimensions(path: Path) -> tuple[int, int]:
    text = path.read_text(encoding="utf-8", errors="ignore")[:1000]
    width = re.search(r'width="(\d+(?:\.\d+)?)px"', text)
    height = re.search(r'height="(\d+(?:\.\d+)?)px"', text)
    if width and height:
        return int(float(width.group(1))), int(float(height.group(1)))
    viewbox = re.search(r'viewBox="[^"]*?(\d+(?:\.\d+)?)\s+(\d+(?:\.\d+)?)"', text)
    if viewbox:
        return int(float(viewbox.group(1))), int(float(viewbox.group(2)))
    return 1, 1


def load_logo(size: int):
    if Image is None:
        print("Pillow не установлен, логотип отключен.")
        return None
    for path in LOGO_PATHS:
        if not path.exists():
            continue
        try:
            if path.suffix.lower() == ".svg":
                try:
                    import cairosvg
                    svg_w, svg_h = svg_dimensions(path)
                    out_w = max(size, min(180, int(size * svg_w / max(svg_h, 1))))
                    png = cairosvg.svg2png(url=str(path), output_width=out_w, output_height=size)
                    image = Image.open(io.BytesIO(png)).convert("RGBA")
                except Exception as exc:
                    print(f"Не удалось прочитать SVG {path.name}: {exc}")
                    continue
            else:
                source = Image.open(path).convert("RGBA")
                out_w = max(size, min(180, int(size * source.width / max(source.height, 1))))
                image = source.resize((out_w, size))
            image = add_black_background(image)
            return ctk.CTkImage(light_image=image, dark_image=image, size=image.size)
        except Exception as exc:
            print(f"Логотип {path.name} не загружен: {exc}")
    print("Логотип не найден или не прочитан, используется встроенный знак RD.")
    return generated_rd_logo(size)


def load_window_icon(master: tk.Misc, size: int) -> Optional[ImageTk.PhotoImage]:
    if Image is None or ImageTk is None:
        return None
    for path in ICON_PATHS:
        if not path.exists():
            continue
        try:
            source = Image.open(path).convert("RGBA")
            scale = min(size / max(source.width, 1), size / max(source.height, 1))
            logo = source.resize((max(1, int(source.width * scale)), max(1, int(source.height * scale))))
            image = Image.new("RGBA", (size, size), (0, 0, 0, 255))
            image.alpha_composite(logo, ((size - logo.width) // 2, (size - logo.height) // 2))
            return ImageTk.PhotoImage(image, master=master)
        except Exception as exc:
            print(f"Иконка {path.name} не загружена: {exc}")
    fallback = generated_rd_logo(size)
    if fallback is None:
        return None
    image = fallback.cget("light_image")
    return ImageTk.PhotoImage(image, master=master)


def fmt(value: Optional[float], unit: str = "", digits: int = 2) -> str:
    if value is None:
        return "—"
    text = f"{value:.{digits}f}".rstrip("0").rstrip(".")
    return f"{text} {unit}".strip()


def fmt_runtime(hours: float) -> str:
    total_minutes = max(0, int(round(hours * 60)))
    h, minutes = divmod(total_minutes, 60)
    if h and minutes:
        return f"{h} ч {minutes} мин"
    if h:
        return f"{h} ч"
    return f"{minutes} мин"


def shape_name(shape: str) -> str:
    return "цилиндрическая" if shape.upper() == "C" else "призматическая"


def rounded_dims(dims: tuple[float, float, float]) -> tuple[float, float, float]:
    return tuple(round(x, 1) for x in dims)  # type: ignore[return-value]


def row_size(count: int, size: float, gap: float) -> float:
    return count * size + max(0, count - 1) * gap


MAX_CELL_COUNTS = 5
MAX_VARIANTS_PER_CELL_COUNT = 5
MAX_SCHEMES_PER_CELL_COUNT = 6
MAX_RESULT_PACKS = MAX_CELL_COUNTS * MAX_VARIANTS_PER_CELL_COUNT
MAX_LAYOUTS_PER_SCHEME = 5
MAX_DIM_LAYOUTS_PER_SCHEME = 5


def effective_target_dims(target: tuple[float, float, float], cut: float, wall: float) -> tuple[float, float, float]:
    return tuple(max(1.0, d * (1 + cut / 100.0) - 2 * wall) for d in target)  # type: ignore[return-value]


def fill_stats(dims: tuple[float, float, float], effective: tuple[float, float, float]) -> tuple[float, float, float]:
    target_volume = max(1.0, effective[0] * effective[1] * effective[2])
    filled_volume = math.prod(min(dims[i], effective[i]) for i in range(3))
    empty_ratio = sum(max(0.0, effective[i] - dims[i]) / effective[i] for i in range(3))
    overflow_ratio = sum(max(0.0, dims[i] - effective[i]) / effective[i] for i in range(3))
    return filled_volume / target_volume, empty_ratio, overflow_ratio


def pack_fill_key(pack: Pack, effective: tuple[float, float, float]) -> tuple[object, ...]:
    fill_ratio, empty_ratio, overflow_ratio = fill_stats(pack.dims, effective)
    return (not pack.ok_time, -fill_ratio, empty_ratio, overflow_ratio, -pack.n, -pack.runtime, pack.s, pack.p, pack.grid)


def layout_signature(pack: Pack) -> tuple[tuple[int, int], int]:
    return tuple(sorted((pack.grid[0], pack.grid[1]))), pack.grid[2]


def pack_layout_preference(pack: Pack) -> tuple[object, ...]:
    footprint = pack.dims[0] * pack.dims[1]
    return (not pack.ok_dims, pack.grid[2] != 1, footprint, pack.dims[2], pack.volume)


def layout_item_signature(item: tuple[float, tuple[float, float, float], tuple[int, int, int], tuple[str, str, str], bool, list[float]]) -> tuple[tuple[int, int], int]:
    return tuple(sorted((item[2][0], item[2][1]))), item[2][2]


def layout_item_footprint_key(item: tuple[float, tuple[float, float, float], tuple[int, int, int], tuple[str, str, str], bool, list[float]]) -> tuple[object, ...]:
    _volume, dims, grid, orient, _ok, _overflow = item
    footprint = dims[0] * dims[1]
    return (grid[2] != 1, footprint, dims[2], max(grid[0], grid[1]), sum(grid), orient)


def target_cell_counts(cell: Cell, load_w: float, required_h: float) -> list[int]:
    required_energy = load_w * required_h
    e_cell = max(0.001, cell.voltage_nom * cell.capacity)
    ratios = (0.70, 0.85, 1.00, 1.15, 1.30)
    counts: list[int] = []
    for ratio in ratios:
        count = max(1, min(400, math.ceil(required_energy * ratio / e_cell)))
        if count not in counts:
            counts.append(count)
    center = max(1, min(400, math.ceil(required_energy / e_cell)))
    step = 1
    while len(counts) < MAX_CELL_COUNTS and step < 400:
        for count in (center - step, center + step):
            if 1 <= count <= 400 and count not in counts:
                counts.append(count)
                if len(counts) >= MAX_CELL_COUNTS:
                    break
        step += 1
    return sorted(counts[:MAX_CELL_COUNTS])


def scheme_candidates(n: int) -> list[tuple[int, int]]:
    schemes = [(s, n // s) for s in range(1, min(100, n) + 1) if n % s == 0 and n // s <= 100]
    if not schemes:
        return []
    picked: list[tuple[int, int]] = []
    selectors = (
        min(schemes, key=lambda item: item[0]),
        max(schemes, key=lambda item: item[0]),
        min(schemes, key=lambda item: abs(item[0] - item[1])),
    )
    for scheme in selectors:
        if scheme not in picked:
            picked.append(scheme)
    for scheme in sorted(schemes, key=lambda item: (abs(item[0] - item[1]), item[0])):
        if scheme not in picked:
            picked.append(scheme)
        if len(picked) >= MAX_SCHEMES_PER_CELL_COUNT:
            break
    return picked


def select_count_variants(candidates: list[Pack], limit: int = MAX_VARIANTS_PER_CELL_COUNT) -> list[Pack]:
    groups: dict[tuple[tuple[int, int], int], list[Pack]] = {}
    signatures: list[tuple[tuple[int, int], int]] = []
    for pack in candidates:
        signature = layout_signature(pack)
        if signature not in groups:
            groups[signature] = []
            signatures.append(signature)
        groups[signature].append(pack)
    unique: list[Pack] = []
    scheme_usage: dict[tuple[int, int], int] = {}
    for signature in signatures:
        group = groups[signature]
        pack = min(group, key=lambda item: (*pack_layout_preference(item), scheme_usage.get((item.s, item.p), 0), item.s, item.p))
        unique.append(pack)
        scheme = (pack.s, pack.p)
        scheme_usage[scheme] = scheme_usage.get(scheme, 0) + 1
    return unique[:limit]


def limit_pack_variants(packs: list[Pack], max_total: int = MAX_RESULT_PACKS) -> list[Pack]:
    result: list[Pack] = []
    counts_seen: set[int] = set()
    per_count: dict[int, int] = {}
    signatures_by_n: dict[int, set[tuple[tuple[int, int], int]]] = {}
    for pack in packs:
        if pack.n not in counts_seen and len(counts_seen) >= MAX_CELL_COUNTS:
            continue
        if per_count.get(pack.n, 0) >= MAX_VARIANTS_PER_CELL_COUNT:
            continue
        signatures = signatures_by_n.setdefault(pack.n, set())
        signature = layout_signature(pack)
        if signature in signatures:
            continue
        counts_seen.add(pack.n)
        signatures.add(signature)
        per_count[pack.n] = per_count.get(pack.n, 0) + 1
        result.append(pack)
        if len(result) >= max_total:
            return result
    return result


@lru_cache(maxsize=None)
def grid_candidates(n: int) -> list[tuple[int, int, int]]:
    triples = []
    for c in range(1, n + 1):
        max_a = math.ceil(n / c)
        for a in range(1, max_a + 1):
            b = math.ceil(n / (a * c))
            if a * b * c >= n:
                triples.append((a, b, c))
    empty_limit = max(12, math.ceil(n * 0.12))
    filtered = [t for t in triples if t[0] * t[1] * t[2] - n <= empty_limit]
    return sorted(set(filtered), key=lambda t: (t[0] * t[1] * t[2] - n, max(t), sum(t)))[:180]


def layout_candidates(
    cell: Cell,
    n: int,
    consider_dims: bool,
    target: tuple[float, float, float],
    gap: float,
    wall: float,
    bms: float,
    bms_side: str,
    cut: float,
    limit: int = 1,
) -> list[tuple[tuple[float, float, float], tuple[int, int, int], tuple[str, str, str], bool, str]]:
    base_axes = {"L": cell.length, "W": cell.width, "H": cell.height}
    effective = effective_target_dims(target, cut, wall)
    all_items = []
    variants = []
    near = None
    for grid in grid_candidates(n):
        for orient in set(permutations(("L", "W", "H"))):
            sizes = [base_axes[axis] for axis in orient]
            dims = (
                row_size(grid[0], sizes[0], gap),
                row_size(grid[1], sizes[1], gap),
                row_size(grid[2], sizes[2], gap),
            )
            axis = {"front": 0, "side": 1, "top": 2}.get(bms_side, 0)
            dims_with_bms = list(dims)
            dims_with_bms[axis] += bms
            rdims = rounded_dims(tuple(dims_with_bms))
            overflow = [max(0.0, rdims[i] - effective[i]) for i in range(3)]
            if consider_dims and any(overflow[i] / effective[i] > 0.5 for i in range(3)):
                continue
            volume = rdims[0] * rdims[1] * rdims[2]
            ok = not consider_dims or all(v <= 1e-9 for v in overflow)
            item = (volume, rdims, grid, orient, ok, overflow)
            all_items.append(item)
            if ok:
                variants.append(item)
            if near is None or sum(overflow) < sum(near[-1]):
                near = item
    sources = all_items if consider_dims else (variants if variants else ([near] if near is not None else []))
    if not sources:
        return []
    if consider_dims:
        sources = sorted(
            sources,
            key=lambda item: (
                -fill_stats(item[1], effective)[0],
                fill_stats(item[1], effective)[1],
                fill_stats(item[1], effective)[2],
                item[3][2] == "L",
                item[1][2],
                tuple(sorted(item[2])),
            ),
        )
    else:
        sources = sorted(sources, key=layout_item_footprint_key)
    picked = []
    picked_signatures: set[tuple[tuple[int, int], int]] = set()
    if not consider_dims and len(sources) > 1:
        selectors = (
            min(sources, key=layout_item_footprint_key),
            min(sources, key=lambda item: (item[2][2] != 1, abs(item[2][0] - item[2][1]), item[1][0] * item[1][1])),
            min(sources, key=lambda item: (item[2][2] != 1, max(item[2][0], item[2][1]), item[1][0] * item[1][1])),
            min(sources, key=lambda item: (item[2][2] == 1, item[1][0] * item[1][1], item[1][2])),
            max(sources, key=lambda item: sum(1 for count in item[2] if count > 1)),
        )
        for item in selectors:
            signature = layout_item_signature(item)
            if item not in picked and signature not in picked_signatures:
                picked.append(item)
                picked_signatures.add(signature)
    for item in sources:
        signature = layout_item_signature(item)
        if item not in picked and signature not in picked_signatures:
            picked.append(item)
            picked_signatures.add(signature)
        if len(picked) >= limit:
            break
    result = []
    for _volume, dims, grid, orient, ok, overflow in picked[:limit]:
        warning = ""
        if consider_dims and not ok:
            axes = ["глубине", "ширине", "высоте"]
            idx = max(range(3), key=lambda i: overflow[i])
            percent = overflow[idx] / max(effective[idx], 1.0) * 100.0
            warning = f"⚠ превышение по {axes[idx]} на {overflow[idx]:.1f} мм ({percent:.1f}%)"
        result.append((dims, grid, orient, ok, warning))
    return result


def best_layout(
    cell: Cell,
    n: int,
    consider_dims: bool,
    target: tuple[float, float, float],
    gap: float,
    wall: float,
    bms: float,
    bms_side: str,
    cut: float,
) -> tuple[tuple[float, float, float], tuple[int, int, int], tuple[str, str, str], bool, str]:
    return layout_candidates(cell, n, consider_dims, target, gap, wall, bms, bms_side, cut, 1)[0]


def calculate(
    cell: Cell,
    load_w: float,
    required_h: float,
    consider_dims: bool,
    target: tuple[float, float, float],
    cut: float,
    wall: float,
    gap: float,
    bms: float,
    bms_side: str,
) -> list[Pack]:
    packs: list[Pack] = []
    e_cell = cell.voltage_nom * cell.capacity
    for n in target_cell_counts(cell, load_w, required_h):
        count_packs: list[Pack] = []
        energy = e_cell * n
        runtime = energy / load_w
        ok_time = runtime >= required_h
        layout_limit = MAX_DIM_LAYOUTS_PER_SCHEME if consider_dims else MAX_LAYOUTS_PER_SCHEME
        for s, p in scheme_candidates(n):
            energy = e_cell * n
            for dims, grid, orient, ok_dims, warning in layout_candidates(cell, n, consider_dims, target, gap, wall, bms, bms_side, cut, layout_limit):
                pack = Pack(
                    s, p, n, dims, grid, orient, energy, cell.capacity * p, cell.voltage_nom * s,
                    cell.max_discharge * p, runtime, dims[0] * dims[1] * dims[2], ok_time, ok_dims,
                    "" if ok_time and ok_dims else (warning or f"⚠ время меньше требуемого на {fmt_runtime(required_h - runtime)}"),
                    cell,
                )
                count_packs.append(pack)
        if consider_dims:
            effective = effective_target_dims(target, cut, wall)
            count_packs.sort(key=lambda x: pack_fill_key(x, effective))
        else:
            count_packs.sort(key=pack_layout_preference)
        packs.extend(select_count_variants(count_packs))
    final = sorted(packs, key=lambda x: x.n)[:MAX_RESULT_PACKS]
    if final:
        max_s = max(final, key=lambda x: x.s)
        max_p = max(final, key=lambda x: x.p)
        balanced = min(final, key=lambda x: abs(x.s - x.p))
        for pack, mark in ((max_s, "S"), (max_p, "P"), (balanced, "B")):
            pack.marks = "".join(sorted(set(pack.marks + mark)))
    return final


class MainApp(ctk.CTk):
    def __init__(self) -> None:
        super().__init__()
        ctk.set_appearance_mode("light")
        self.title("RD конфигуратор АКБ 3D")
        self.configure(fg_color=BG)
        self.minsize(1000, 700)
        self._center(0.7, 0.7)
        self.logo = load_logo(40)
        self.window_icon = load_window_icon(self, 32)
        for ico_path in ICO_PATHS:
            if ico_path.exists():
                try:
                    self.iconbitmap(str(ico_path))
                except Exception as exc:
                    print(f"Не удалось установить iconbitmap {ico_path.name}: {exc}")
                break
        if self.window_icon:
            self.iconphoto(True, self.window_icon)
        self.cells, _skipped = load_db()
        if not self.cells:
            messagebox.showerror("База пуста", "cells_db.txt отсутствует или не содержит корректных ячеек.")
            self.after(100, self.destroy)
            return
        self.cell_by_label = {self.cell_label(c): c for c in self.cells}
        self.chemistries = sorted({cell.chemistry for cell in self.cells if cell.chemistry})
        self.last_cell_label = next(iter(self.cell_by_label))
        self.last_chemistry = self.chemistries[0] if self.chemistries else ""
        self.entries: dict[str, ctk.CTkEntry] = {}
        self.errors: dict[str, ctk.CTkLabel] = {}
        self.field_widgets: dict[str, tuple[ctk.CTkLabel, ctk.CTkEntry, ctk.CTkLabel]] = {}
        self.dim_extra_widgets: list[ctk.CTkBaseClass] = []
        self.packs: list[Pack] = []
        self.selected: Optional[Pack] = None
        self.calc_running = False
        self.calc_anim_job: Optional[str] = None
        self.calc_anim_step = 0
        self.fullscreen_model_window: Optional[tk.Toplevel] = None
        self.fullscreen_model_fig = None
        self.fullscreen_model_ax = None
        self.fullscreen_model_canvas = None
        self._build()
        self.restore_state()
        self.on_calc_mode_change()
        self.protocol("WM_DELETE_WINDOW", self.on_close)
        signal.signal(signal.SIGINT, lambda _sig, _frame: self.after(0, self.on_close))
        self.after(100, self.keep_signal_handling_alive)

    def _center(self, wf: float, hf: float) -> None:
        sw, sh = self.winfo_screenwidth(), self.winfo_screenheight()
        w, h = int(sw * wf), int(sh * hf)
        self.geometry(f"{w}x{h}+{(sw - w) // 2}+{(sh - h) // 2}")

    def cell_label(self, cell: Cell) -> str:
        prefix = "✓ База" if cell.source == "manual" else "○ Онлайн"
        return f"{prefix}: {cell.name} — {cell.brand} — {fmt(cell.capacity, 'А·ч')} — Uном {fmt(cell.voltage_nom, 'В')}"

    def _build(self) -> None:
        self.page = ctk.CTkScrollableFrame(self, fg_color=BG)
        self.page.pack(fill="both", expand=True)

        header = ctk.CTkFrame(self.page, fg_color=BG)
        header.pack(fill="x", padx=16, pady=(14, 6))
        if self.logo:
            ctk.CTkLabel(header, image=self.logo, text="").pack(side="left")
        ctk.CTkLabel(header, text="RD конфигуратор АКБ 3D", font=("GOST type A", 26, "bold")).pack(side="left", padx=12)

        top = ctk.CTkFrame(self.page, fg_color=BG)
        top.pack(fill="x", padx=16, pady=8)
        top.grid_columnconfigure(0, weight=1)
        top.grid_columnconfigure(1, weight=1)

        inputs = ctk.CTkFrame(top, fg_color=BG)
        inputs.grid(row=0, column=0, sticky="nsew", padx=(0, 12))
        self.calc_mode_var = tk.StringVar(value="cell")
        mode_row = ctk.CTkFrame(inputs, fg_color=BG)
        mode_row.pack(fill="x", pady=(0, 6))
        ctk.CTkRadioButton(mode_row, text="По ячейке", value="cell", variable=self.calc_mode_var, command=self.on_calc_mode_change, font=("GOST type A", 13)).pack(side="left", padx=(0, 12))
        ctk.CTkRadioButton(mode_row, text="По химии", value="chemistry", variable=self.calc_mode_var, command=self.on_calc_mode_change, font=("GOST type A", 13)).pack(side="left")
        self.cell_combo = ctk.CTkOptionMenu(inputs, values=list(self.cell_by_label), command=self.on_selector_change, fg_color=FIELD_BG, button_color=BUTTON, text_color="#111", font=FONT)
        self.cell_combo.pack(fill="x", pady=(0, 8))
        fields = [
            ("load", "Нагрузка, Вт", ""),
            ("time", "Требуемое время работы, ч", ""),
            ("depth", "Длина сборки, мм", ""),
            ("width", "Ширина сборки, мм", ""),
            ("height", "Высота сборки, мм", ""),
            ("wall", "Толщина стенки корпуса, мм", "0"),
            ("gap", "Зазор между ячейками, мм", "2"),
            ("bms", "Место под BMS, мм", "0"),
        ]
        self.consider_var = tk.BooleanVar(value=False)
        self.consider_box = ctk.CTkCheckBox(inputs, text="Учитывать габариты", variable=self.consider_var, command=self.on_consider_toggle, font=FONT)
        self.consider_box.pack(anchor="w", pady=(0, 6))
        self.dim_group = ctk.CTkFrame(inputs, fg_color="#fff4d8")
        ctk.CTkLabel(self.dim_group, text="Габариты и зазоры", anchor="w", font=("GOST type A", 15, "bold")).pack(fill="x", padx=10, pady=(8, 4))
        self.bms_group = ctk.CTkFrame(inputs, fg_color="#eaf2ff")
        ctk.CTkLabel(self.bms_group, text="Место под BMS", anchor="w", font=("GOST type A", 15, "bold")).pack(fill="x", padx=10, pady=(8, 4))
        for key, label, default in fields:
            if key in {"depth", "width", "height", "wall", "gap"}:
                parent = self.dim_group
                padx = 10
            elif key == "bms":
                parent = self.bms_group
                padx = 10
            else:
                parent = inputs
                padx = 0
            label_widget = ctk.CTkLabel(parent, text=label, anchor="w", font=FONT)
            label_widget.pack(fill="x", padx=padx)
            entry = ctk.CTkEntry(parent, width=230, fg_color=FIELD_BG, border_width=0, font=FONT)
            entry.insert(0, default)
            entry.pack(anchor="w", padx=padx)
            err = ctk.CTkLabel(parent, text="", text_color=ERROR, anchor="w", height=15, font=("GOST type A", 11))
            err.pack(fill="x", padx=padx)
            self.entries[key] = entry
            self.errors[key] = err
            self.field_widgets[key] = (label_widget, entry, err)
            if key == "bms":
                self.bms_side_label = ctk.CTkLabel(self.bms_group, text="Сторона BMS", anchor="w", font=FONT)
                self.bms_side_label.pack(fill="x", padx=10)
                self.bms_side_menu = ctk.CTkOptionMenu(
                    self.bms_group,
                    width=230,
                    values=["спереди", "сбоку", "сверху"],
                    fg_color=FIELD_BG,
                    button_color=BUTTON,
                    button_hover_color=BUTTON_HOVER,
                    text_color="#111111",
                    font=FONT,
                    command=lambda _value: self.save_state(),
                )
                self.bms_side_menu.set("спереди")
                self.bms_side_menu.pack(anchor="w", padx=10, pady=(0, 10))
                self.dim_extra_widgets.extend([self.bms_side_label, self.bms_side_menu])

        self.mirror = ctk.CTkFrame(top, fg_color="#ffffff", border_width=1, border_color="#d0d0d0")
        self.mirror.grid(row=0, column=1, sticky="nsew")

        self.calc_button = ctk.CTkButton(self.page, text="Рассчитать сборку", height=48, fg_color=BUTTON, hover_color=BUTTON_HOVER, text_color="#111", font=("GOST type A", 20, "bold"), command=self.run_calc)
        self.calc_button.pack(fill="x", padx=16, pady=8)

        self.output = ctk.CTkFrame(self.page, height=96, fg_color="#ffffff", border_width=1, border_color="#c8c8c8")
        self.output.pack(fill="x", padx=16, pady=(0, 16))
        self.output.pack_propagate(False)
        self.summary_row = ctk.CTkFrame(self.output, height=130, fg_color="#ffffff")
        self.summary_row.grid_columnconfigure(0, weight=2)
        self.summary_row.grid_columnconfigure(1, weight=1)
        self.summary_row.grid_rowconfigure(0, weight=1)
        self.variant_bar = ctk.CTkFrame(self.summary_row, fg_color="#ffffff")
        self.variant_bar.grid(row=0, column=0, sticky="nsew", padx=(8, 6), pady=8)
        self.description = ctk.CTkLabel(
            self.summary_row,
            text="",
            fg_color="#ffffff",
            text_color="#111111",
            anchor="nw",
            justify="left",
            font=("GOST type A", 20, "bold"),
            wraplength=360,
            height=104,
        )
        self.description.grid(row=0, column=1, sticky="nsew", padx=(6, 8), pady=8)
        self.runtime_label = ctk.CTkLabel(
            self.summary_row,
            text="",
            fg_color="#ffffff",
            text_color="#111111",
            anchor="w",
            justify="left",
            font=("GOST type A", 22, "bold"),
            height=30,
        )
        self.runtime_label.grid(row=1, column=1, sticky="ew", padx=(6, 8), pady=(0, 8))

        self.empty_output_label = ctk.CTkLabel(
            self.output,
            text="Вывод появится здесь после расчёта сборки.",
            fg_color="#ffffff",
            text_color="#777777",
            font=("GOST type A", 20),
            height=28,
        )

        self.detail = ctk.CTkFrame(self.output, height=880, fg_color="#ffffff")
        self.detail.pack_propagate(False)
        self.detail.grid_columnconfigure(0, weight=1)
        self.detail.grid_rowconfigure(0, weight=1)
        model_area = ctk.CTkFrame(self.detail, fg_color="#eef3f6")
        model_area.grid(row=0, column=0, sticky="nsew", pady=(0, 8))
        model_area.grid_rowconfigure(0, weight=1)
        model_area.grid_columnconfigure(0, weight=1)

        model_panel = ctk.CTkFrame(model_area, fg_color="#eef3f6")
        model_panel.grid(row=0, column=0, sticky="nsew", padx=10, pady=10)
        model_panel.grid_rowconfigure(3, weight=1)
        model_panel.grid_columnconfigure(0, weight=1)
        model_head = ctk.CTkFrame(model_panel, fg_color="#eef3f6")
        model_head.grid(row=0, column=0, sticky="ew", pady=(0, 4))
        model_head.grid_columnconfigure(0, weight=1)
        ctk.CTkLabel(model_head, text="3D-модель", anchor="w", font=("GOST type A", 18, "bold")).grid(row=0, column=0, sticky="ew")
        ctk.CTkButton(model_head, text="На весь экран", width=132, fg_color=BUTTON, hover_color=BUTTON_HOVER, text_color="#111", command=self.open_fullscreen_model).grid(row=0, column=1, sticky="e")
        model_controls = ctk.CTkFrame(model_panel, fg_color="#eef3f6")
        model_controls.grid(row=1, column=0, sticky="ew", pady=(0, 4))
        self.show_3d_bms_var = tk.BooleanVar(value=True)
        self.show_3d_target_var = tk.BooleanVar(value=True)
        self.show_3d_result_var = tk.BooleanVar(value=True)
        for text, var in (
            ("BMS", self.show_3d_bms_var),
            ("Требуемые размеры", self.show_3d_target_var),
            ("Получившаяся сборка", self.show_3d_result_var),
        ):
            ctk.CTkCheckBox(model_controls, text=text, variable=var, command=self.redraw_selected_pack, font=("GOST type A", 13)).pack(side="left", padx=(0, 14))
        self.model_zoom = 1.0
        self.model_yaw = 35.0
        self.model_pitch = 20.0
        self.model_drag_start: Optional[tuple[int, int]] = None
        self.model_drag_angles: tuple[float, float] = (self.model_yaw, self.model_pitch)
        sliders = ctk.CTkFrame(model_panel, fg_color="#eef3f6")
        sliders.grid(row=2, column=0, sticky="ew", pady=(0, 4))
        sliders.grid_columnconfigure(1, weight=1)
        sliders.grid_columnconfigure(3, weight=1)
        sliders.grid_columnconfigure(5, weight=1)
        ctk.CTkLabel(sliders, text="Масштаб", font=("GOST type A", 12)).grid(row=0, column=0, padx=(0, 6))
        zoom_slider = ctk.CTkSlider(sliders, from_=0.4, to=4.0, command=self.set_model_zoom)
        zoom_slider.set(self.model_zoom)
        zoom_slider.grid(row=0, column=1, sticky="ew", padx=(0, 12))
        ctk.CTkLabel(sliders, text="Поворот", font=("GOST type A", 12)).grid(row=0, column=2, padx=(0, 6))
        yaw_slider = ctk.CTkSlider(sliders, from_=0, to=360, command=self.set_model_yaw)
        yaw_slider.set(self.model_yaw)
        yaw_slider.grid(row=0, column=3, sticky="ew", padx=(0, 12))
        ctk.CTkLabel(sliders, text="Наклон", font=("GOST type A", 12)).grid(row=0, column=4, padx=(0, 6))
        pitch_slider = ctk.CTkSlider(sliders, from_=-45, to=55, command=self.set_model_pitch)
        pitch_slider.set(self.model_pitch)
        pitch_slider.grid(row=0, column=5, sticky="ew")
        if MATPLOTLIB_AVAILABLE:
            self.model_fig = Figure(figsize=(10, 7), dpi=100, facecolor="#eef3f6")
            self.model_ax = self.model_fig.add_subplot(111, projection="3d")
            self.model_canvas = FigureCanvasTkAgg(self.model_fig, master=model_panel)
            self.model_canvas.get_tk_widget().grid(row=3, column=0, sticky="nsew")
        else:
            self.model_fig = None
            self.model_ax = None
            self.model_canvas = tk.Canvas(model_panel, bg="white", highlightthickness=1, highlightbackground="#e0e0e0")
            self.model_canvas.grid(row=3, column=0, sticky="nsew")

        self.model_legend = ctk.CTkFrame(self.detail, fg_color="#f7f3e8")
        self.model_legend.grid_columnconfigure(0, weight=1)
        self.model_variant_bar = ctk.CTkFrame(self.model_legend, fg_color="#f7f3e8")
        self.model_runtime_label = ctk.CTkLabel(self.model_legend, text="", anchor="w", justify="left", fg_color="#f7f3e8", font=("GOST type A", 20, "bold"))
        self.model_info_label = ctk.CTkLabel(self.model_legend, text="", anchor="nw", justify="left", fg_color="#f7f3e8", font=("GOST type A", 13), wraplength=260)

        self.export_button = ctk.CTkButton(
            self.output,
            text="Экспорт в Excel",
            height=54,
            fg_color="#1b7a1b",
            hover_color="#146414",
            text_color="#ffffff",
            font=("GOST type A", 20, "bold"),
            command=self.export_excel,
        )
        self.toggle_cut()
        self.show_empty_output()
        self.bind_all("<Return>", self.on_calc_hotkey)
        self.bind_all("<F5>", self.on_calc_hotkey)

    def toggle_cut(self) -> None:
        dim_keys = {"depth", "width", "height", "wall", "gap"}
        if self.consider_var.get():
            if not self.dim_group.winfo_ismapped():
                self.dim_group.pack(fill="x", pady=(4, 8), padx=0, after=self.consider_box)
            if not self.bms_group.winfo_ismapped():
                self.bms_group.pack(fill="x", pady=(0, 8), padx=0, after=self.dim_group)
        else:
            for key in dim_keys:
                self.errors[key].configure(text="")
            self.dim_group.pack_forget()
            if not self.bms_group.winfo_ismapped():
                self.bms_group.pack(fill="x", pady=(4, 8), padx=0, after=self.consider_box)

    def on_consider_toggle(self) -> None:
        self.toggle_cut()
        self.save_state()

    def restore_state(self) -> None:
        if not STATE_PATH.exists():
            return
        try:
            state = json.loads(STATE_PATH.read_text(encoding="utf-8"))
        except Exception as exc:
            print(f"Не удалось прочитать настройки {STATE_PATH.name}: {exc}")
            return
        cell_label = state.get("cell")
        if isinstance(cell_label, str) and cell_label in self.cell_by_label:
            self.last_cell_label = cell_label
        mode = state.get("calc_mode")
        if mode in {"cell", "chemistry"}:
            self.calc_mode_var.set(mode)
        chemistry = state.get("chemistry")
        if isinstance(chemistry, str) and chemistry in self.chemistries:
            self.last_chemistry = chemistry
        self.consider_var.set(bool(state.get("consider_dims", False)))
        fields = state.get("fields", {})
        if isinstance(fields, dict):
            for key, value in fields.items():
                if key in self.entries:
                    self.entries[key].delete(0, "end")
                    self.entries[key].insert(0, str(value))
        bms_side = state.get("bms_side")
        if isinstance(bms_side, str) and bms_side in {"спереди", "сбоку", "сверху"}:
            self.bms_side_menu.set(bms_side)
        self.toggle_cut()

    def save_state(self) -> None:
        if not self.entries:
            return
        state = {
            "calc_mode": self.calc_mode_var.get(),
            "cell": self.last_cell_label,
            "chemistry": self.last_chemistry,
            "consider_dims": bool(self.consider_var.get()),
            "bms_side": self.bms_side_menu.get(),
            "fields": {key: entry.get() for key, entry in self.entries.items()},
        }
        try:
            STATE_PATH.write_text(json.dumps(state, ensure_ascii=False, indent=2), encoding="utf-8")
        except Exception as exc:
            print(f"Не удалось сохранить настройки {STATE_PATH.name}: {exc}")

    def on_close(self) -> None:
        self.save_state()
        self.destroy()

    def keep_signal_handling_alive(self) -> None:
        self.after(100, self.keep_signal_handling_alive)

    def on_calc_hotkey(self, _event: tk.Event) -> str:
        self.run_calc()
        return "break"

    def show_empty_output(self) -> None:
        self.output.configure(height=96)
        self.summary_row.pack_forget()
        self.detail.pack_forget()
        self.export_button.pack_forget()
        self.empty_output_label.pack(fill="both", expand=True, padx=8, pady=8)
        self.description.configure(text="")
        self.runtime_label.configure(text="")
        self.model_info_label.configure(text="")
        self.model_runtime_label.configure(text="")
        for widget in self.model_variant_bar.winfo_children():
            widget.destroy()
        self.clear_3d_model()

    def show_detail_output(self) -> None:
        self.output.configure(height=1180)
        self.empty_output_label.pack_forget()
        if not self.summary_row.winfo_ismapped():
            self.summary_row.pack(fill="x", padx=8, pady=(8, 4))
        if not self.detail.winfo_ismapped():
            self.detail.pack(fill="both", expand=True, padx=8, pady=8)
        if not self.export_button.winfo_ismapped():
            self.export_button.pack(fill="x", padx=8, pady=(0, 10))

    def scroll_to_output(self) -> None:
        canvas = getattr(self.page, "_parent_canvas", None)
        if canvas is not None:
            canvas.yview_moveto(0.55)

    def on_calc_mode_change(self) -> None:
        if self.calc_mode_var.get() == "chemistry":
            self.last_cell_label = self.cell_combo.get() if self.cell_combo.get() in self.cell_by_label else self.last_cell_label
            self.cell_combo.configure(values=self.chemistries, command=self.on_selector_change)
            if self.last_chemistry not in self.chemistries and self.chemistries:
                self.last_chemistry = self.chemistries[0]
            self.cell_combo.set(self.last_chemistry)
            self.on_chemistry_change(self.last_chemistry)
        else:
            self.last_chemistry = self.cell_combo.get() if self.cell_combo.get() in self.chemistries else self.last_chemistry
            self.cell_combo.configure(values=list(self.cell_by_label), command=self.on_selector_change)
            if self.last_cell_label not in self.cell_by_label:
                self.last_cell_label = next(iter(self.cell_by_label))
            self.cell_combo.set(self.last_cell_label)
            self.on_cell_change(self.last_cell_label)
        self.save_state()

    def on_selector_change(self, value: str) -> None:
        if self.calc_mode_var.get() == "chemistry":
            self.on_chemistry_change(value)
        else:
            self.on_cell_change(value)

    def on_chemistry_change(self, _value: str) -> None:
        self.last_chemistry = self.cell_combo.get()
        self.save_state()
        for widget in self.mirror.winfo_children():
            widget.destroy()
        cells = self.selected_cells()
        rows = [
            ("Режим", "расчёт по типу химии"),
            ("Тип химии", self.cell_combo.get()),
            ("Ячеек в расчёте", str(len(cells))),
        ]
        brands = sorted({cell.brand for cell in cells if cell.brand})
        if brands:
            rows.append(("Бренды", ", ".join(brands[:6]) + ("..." if len(brands) > 6 else "")))
        for key, value in rows:
            line = ctk.CTkFrame(self.mirror, fg_color="#ffffff")
            line.pack(fill="x", padx=10, pady=2)
            ctk.CTkLabel(line, text=f"{key} →", width=180, anchor="w", font=FONT).pack(side="left")
            ctk.CTkLabel(line, text=value, anchor="w", font=FONT).pack(side="left", fill="x", expand=True)

    def on_cell_change(self, _value: str) -> None:
        self.last_cell_label = self.cell_combo.get()
        self.save_state()
        cell = self.current_cell()
        for widget in self.mirror.winfo_children():
            widget.destroy()
        rows = [
            ("Наименование", cell.name), ("Бренд", cell.brand), ("Тип химии", cell.chemistry),
            ("Тип формы", cell.shape), ("Габариты Д×Ш×В, мм", f"{cell.length:g}×{cell.width:g}×{cell.height:g}"),
            ("Ёмкость", fmt(cell.capacity, "А·ч")), ("Напряжение ном.", fmt(cell.voltage_nom, "В")),
            ("Напряжение мин./макс.", f"{fmt(cell.voltage_min, 'В')} / {fmt(cell.voltage_max, 'В')}"),
            ("Макс. ток разряда", fmt(cell.max_discharge, "А")), ("Макс. ток заряда", fmt(cell.max_charge, "А")),
            ("Мин./Макс. темп.", f"{fmt(cell.temp_min, '°C')} / {fmt(cell.temp_max, '°C')}"),
            ("Масса", fmt(cell.mass, "г")), ("Внутр. сопротивление", fmt(cell.resistance, "мОм")),
            ("Циклов", fmt(cell.cycles, "")), ("После 1000 циклов", fmt(cell.capacity_1000, "%")),
        ]
        for key, value in rows:
            line = ctk.CTkFrame(self.mirror, fg_color="#ffffff")
            line.pack(fill="x", padx=10, pady=2)
            ctk.CTkLabel(line, text=f"{key} →", width=180, anchor="w", font=FONT).pack(side="left")
            ctk.CTkLabel(line, text=value, anchor="w", font=FONT).pack(side="left", fill="x", expand=True)

    def current_cell(self) -> Cell:
        return self.cell_by_label[self.cell_combo.get()]

    def selected_cells(self) -> list[Cell]:
        if self.calc_mode_var.get() == "chemistry":
            chemistry = self.cell_combo.get()
            return [cell for cell in self.cells if cell.chemistry == chemistry]
        return [self.current_cell()]

    def parse_input(self, key: str, required: bool = True) -> Optional[float]:
        self.errors[key].configure(text="")
        text = self.entries[key].get().strip().replace(",", ".")
        if not text and required:
            self.errors[key].configure(text="поле обязательно")
            return None
        if not text:
            return 0.0
        try:
            return float(text)
        except ValueError:
            self.errors[key].configure(text="должно быть число")
            return None

    def start_calc_animation(self) -> None:
        self.calc_running = True
        self.calc_anim_step = 0
        self.calc_button.configure(text="Идёт расчёт  [■□□□□]", command=lambda: None)
        self.update_idletasks()
        self.animate_calc_button()

    def animate_calc_button(self) -> None:
        if not self.calc_running:
            return
        blocks = ("[■□□□□]", "[■■□□□]", "[■■■□□]", "[■■■■□]", "[■■■■■]")
        self.calc_button.configure(text=f"Идёт расчёт  {blocks[self.calc_anim_step % len(blocks)]}")
        self.calc_anim_step += 1
        self.calc_anim_job = self.after(180, self.animate_calc_button)

    def stop_calc_animation(self) -> None:
        self.calc_running = False
        if self.calc_anim_job is not None:
            try:
                self.after_cancel(self.calc_anim_job)
            except tk.TclError:
                pass
            self.calc_anim_job = None
        self.calc_button.configure(text="Рассчитать сборку", command=self.run_calc)

    def run_calc(self, keep_selection: bool = False) -> None:
        if self.calc_running:
            return
        self.save_state()
        values = {k: self.parse_input(k, k in {"load", "time"} or self.consider_var.get() and k in {"depth", "width", "height"}) for k in self.entries}
        if any(v is None for v in values.values()):
            return
        if values["load"] <= 0 or values["time"] <= 0:
            self.errors["load"].configure(text="нагрузка и время должны быть больше 0")
            return
        selected_cells = self.selected_cells()
        if not selected_cells:
            self.description.configure(text="Для выбранного типа химии не найдено ячеек.")
            self.show_empty_output()
            return
        consider_dims = bool(self.consider_var.get())
        bms_side = {"спереди": "front", "сбоку": "side", "сверху": "top"}.get(self.bms_side_menu.get(), "front")
        previous = self.selected if keep_selection else None
        self.start_calc_animation()
        threading.Thread(target=self._calc_worker, args=(selected_cells, values, consider_dims, bms_side, previous), daemon=True).start()

    def _calc_worker(
        self,
        selected_cells: list[Cell],
        values: dict[str, float],
        consider_dims: bool,
        bms_side: str,
        previous: Optional[Pack],
    ) -> None:
        try:
            packs = self.build_packs_for_cells(selected_cells, values, consider_dims, bms_side)
            error = ""
        except Exception as exc:
            packs = []
            error = str(exc)
        try:
            self.after(0, lambda: self.finish_calc(packs, previous, error))
        except RuntimeError:
            pass

    def build_packs_for_cells(self, selected_cells: list[Cell], values: dict[str, float], consider_dims: bool, bms_side: str) -> list[Pack]:
        all_packs: list[Pack] = []
        for cell in selected_cells:
            all_packs.extend(calculate(
                cell, values["load"], values["time"], consider_dims,
                (values["depth"], values["width"], values["height"]),
                values.get("cut", 0.0),
                values["wall"],
                values["gap"],
                values["bms"],
                bms_side,
            ))
        if len(selected_cells) == 1:
            packs = all_packs[:MAX_RESULT_PACKS]
        else:
            if consider_dims:
                effective = effective_target_dims((values["depth"], values["width"], values["height"]), values.get("cut", 0.0), values["wall"])
                all_packs.sort(key=lambda pack: (pack.n, pack_fill_key(pack, effective)))
            else:
                all_packs.sort(key=lambda pack: (pack.n, abs(pack.runtime - values["time"]), pack.volume, pack.s, pack.p))
            packs = limit_pack_variants(all_packs)
        if packs:
            max_s = max(packs, key=lambda x: x.s)
            max_p = max(packs, key=lambda x: x.p)
            balanced = min(packs, key=lambda x: abs(x.s - x.p))
            for pack, mark in ((max_s, "S"), (max_p, "P"), (balanced, "B")):
                pack.marks = "".join(sorted(set(pack.marks + mark)))
        return packs

    def finish_calc(self, packs: list[Pack], previous: Optional[Pack], error: str) -> None:
        self.stop_calc_animation()
        if error:
            self.description.configure(text=f"Ошибка расчёта: {error}")
            self.show_empty_output()
            return
        self.packs = packs
        if self.consider_var.get() and self.packs and not any(p.ok_dims for p in self.packs):
            self.description.configure(text="Ни одна сборка не влезает в заданные габариты.\nПоказаны ближайшие варианты.")
        self.draw_variant_buttons()
        if self.packs:
            selected = previous if previous in self.packs else self.packs[0]
            self.select_pack(selected)
            self.after(120, self.scroll_to_output)
        else:
            self.show_empty_output()

    def draw_variant_buttons(self) -> None:
        for widget in self.variant_bar.winfo_children():
            widget.destroy()
        colors = self.variant_colors()
        for col in range(5):
            self.variant_bar.grid_columnconfigure(col, weight=1)
        for index, (pack, color) in enumerate(zip(self.packs, colors)):
            layout = f"{pack.grid[0]}×{pack.grid[1]}×{pack.grid[2]}"
            label = f"{pack.s}S{pack.p}P\n{layout}"
            if self.calc_mode_var.get() == "chemistry":
                name = pack.cell.name[:18] + ("..." if len(pack.cell.name) > 18 else "")
                label = f"{name}\n{label}"
            hover = self.darken_color(color)
            ctk.CTkButton(self.variant_bar, text=label, width=95, height=58, fg_color=color, hover_color=hover, text_color="#111", command=lambda p=pack: self.select_pack(p)).grid(row=index // 5, column=index % 5, padx=4, pady=4, sticky="ew")
        if hasattr(self, "fullscreen_variant_bar") and self.fullscreen_variant_bar.winfo_exists():
            self.populate_fullscreen_variants()

    def variant_colors(self) -> list[str]:
        return [self.pack_color(pack) for pack in self.packs]

    def reserve_color(self, reserve_ratio: float) -> str:
        # 0% запаса - желтый, 50% и больше - уверенно зеленый.
        if reserve_ratio < 0:
            ratio = max(0.0, min(1.0, (reserve_ratio + 0.3) / 0.3))
            start = (217, 83, 79)
            end = (242, 201, 76)
        else:
            ratio = max(0.0, min(1.0, reserve_ratio / 0.3))
            start = (242, 201, 76)
            end = (49, 158, 80)
        rgb = tuple(round(start[i] + (end[i] - start[i]) * ratio) for i in range(3))
        return "#{:02x}{:02x}{:02x}".format(*rgb)

    def pack_color(self, pack: Pack) -> str:
        required = self.parse_input("time", False) or 0.0
        if required <= 0:
            return "#f2c94c"
        reserve_ratio = (pack.runtime - required) / required
        return self.reserve_color(reserve_ratio)

    def darken_color(self, color: str) -> str:
        color = color.lstrip("#")
        rgb = [int(color[i:i + 2], 16) for i in (0, 2, 4)]
        dark = [max(0, int(v * 0.82)) for v in rgb]
        return "#{:02x}{:02x}{:02x}".format(*dark)

    def cell_shade(self, index: int, total: int) -> str:
        ratio = 0.0 if total <= 1 else index / max(1, total - 1)
        start = (217, 238, 218)
        end = (67, 160, 71)
        rgb = tuple(round(start[i] + (end[i] - start[i]) * ratio) for i in range(3))
        return "#{:02x}{:02x}{:02x}".format(*rgb)

    def select_pack(self, pack: Pack) -> None:
        self.show_detail_output()
        self.selected = pack
        cell = pack.cell
        selected_color = self.pack_color(pack)
        orient = "стоит" if pack.orientation[2] == "L" else "лежит"
        text = [
            f"{cell.name}",
            f"Тип химии: {cell.chemistry}",
            f"Форма ячейки: {shape_name(cell.shape)}, ориентация {orient} ({''.join(pack.orientation)})",
            f"{pack.s}S × {pack.p}P",
            f"ЧИСЛО ИСПОЛЬЗУЕМЫХ ЯЧЕЕК = {pack.n}",
            f"Общая ёмкость: {fmt(pack.capacity, 'А·ч')}",
            f"Номинальное напряжение сборки: {fmt(pack.voltage, 'В')}",
            f"Общая энергия: {fmt(pack.energy, 'Вт·ч')}",
            f"Макс ток разряда сборки: {fmt(pack.max_current, 'А')}",
            f"Температура: {fmt(cell.temp_min, '°C')} / {fmt(cell.temp_max, '°C')}",
            f"Ёмкость после 1000 циклов: {fmt(cell.capacity_1000, '%')}",
            f"Габариты Д×Ш×В: {pack.dims[0]:.1f}×{pack.dims[1]:.1f}×{pack.dims[2]:.1f} мм",
        ]
        if pack.warning:
            text.append(pack.warning)
        self.description.configure(text="\n".join(text))
        runtime_text = fmt_runtime(pack.runtime)
        self.runtime_label.configure(text=f"Расчётное время: {runtime_text}", text_color=selected_color)
        self.model_runtime_label.configure(text=f"Время: {runtime_text}", text_color=selected_color)
        self.model_info_label.configure(text="\n".join(text))
        if hasattr(self, "fullscreen_info_label") and self.fullscreen_info_label.winfo_exists():
            self.fullscreen_runtime_label.configure(text=f"Время: {runtime_text}", text_color=selected_color)
            self.fullscreen_info_label.configure(text="\n".join(text))
        self.update_idletasks()
        self.draw_pack(pack)
        self.after(80, lambda p=pack: self.draw_pack(p) if self.selected is p else None)

    def draw_pack(self, pack: Pack) -> None:
        self.draw_3d_model(pack)

    def redraw_selected_pack(self) -> None:
        if self.selected:
            self.draw_pack(self.selected)

    def set_model_zoom(self, value: float) -> None:
        self.model_zoom = float(value)
        self.redraw_selected_pack()

    def set_model_yaw(self, value: float) -> None:
        self.model_yaw = float(value)
        self.redraw_selected_pack()

    def set_model_pitch(self, value: float) -> None:
        self.model_pitch = float(value)
        self.redraw_selected_pack()

    def start_model_drag(self, event: tk.Event) -> None:
        self.model_drag_start = (event.x, event.y)
        self.model_drag_angles = (self.model_yaw, self.model_pitch)

    def drag_model(self, event: tk.Event) -> None:
        if not self.model_drag_start:
            return
        sx, sy = self.model_drag_start
        start_yaw, start_pitch = self.model_drag_angles
        self.model_yaw = (start_yaw + (event.x - sx) * 0.6) % 360
        self.model_pitch = max(-45.0, min(55.0, start_pitch - (event.y - sy) * 0.4))
        self.redraw_selected_pack()

    def draw_3d_model(self, pack: Pack) -> None:
        if not MATPLOTLIB_AVAILABLE:
            self.clear_3d_model()
            return
        self.render_3d_model(self.model_ax, self.model_fig, self.model_canvas, pack)
        if self.fullscreen_model_window is not None and self.fullscreen_model_window.winfo_exists():
            self.render_3d_model(self.fullscreen_model_ax, self.fullscreen_model_fig, self.fullscreen_model_canvas, pack)

    def render_3d_model(self, ax, fig, canvas, pack: Pack) -> None:
        if ax is None or fig is None or canvas is None:
            return
        ax.clear()
        d, wid, hei = pack.dims
        target = tuple(self.parse_input(k, False) or 0.0 for k in ("depth", "width", "height"))
        max_dims = [d, wid, hei]
        if self.show_3d_result_var.get():
            self.draw_cells_3d(ax, pack)
        if self.show_3d_target_var.get() and self.consider_var.get() and all(v > 0 for v in target):
            self.draw_wire_box_3d(ax, (0, 0, 0), target, "#159947", linewidth=2.4, linestyle="--")
            max_dims = [max(max_dims[i], target[i]) for i in range(3)]
        if self.show_3d_bms_var.get():
            self.draw_bms_3d(ax, pack)

        spans = [max(value, 1.0) * 1.12 for value in max_dims]
        zoom = max(0.25, self.model_zoom)
        centers = [max_dims[0] / 2, max_dims[1] / 2, max_dims[2] / 2]
        limits = []
        for center, span in zip(centers, spans):
            half = span / (2 * zoom)
            limits.append((center - half, center + half))
        ax.set_xlim(*limits[0])
        ax.set_ylim(*limits[1])
        ax.set_zlim(*limits[2])
        ax.set_box_aspect((max(max_dims[0], 1), max(max_dims[1], 1), max(max_dims[2], 1)))
        ax.view_init(elev=self.model_pitch, azim=self.model_yaw)
        try:
            ax.dist = max(3, 8 / zoom)
        except Exception:
            pass
        ax.set_xlabel("Длина, мм")
        ax.set_ylabel("Ширина, мм")
        ax.set_zlabel("Высота, мм")
        ax.grid(True, alpha=0.25)
        fig.tight_layout()
        canvas.draw_idle()

    def clear_3d_model(self) -> None:
        if MATPLOTLIB_AVAILABLE and self.model_ax is not None:
            self.model_ax.clear()
            self.model_ax.text2D(0.5, 0.5, "3D-модель появится после расчёта", transform=self.model_ax.transAxes, ha="center", va="center")
            self.model_canvas.draw_idle()
        else:
            self.model_canvas.delete("all")
            self.model_canvas.create_text(
                220,
                80,
                text="Для 3D установите библиотеку:\npip install matplotlib",
                fill="#777777",
                font=("GOST type A", 16),
                justify="center",
            )

    def open_fullscreen_model(self) -> None:
        if not MATPLOTLIB_AVAILABLE:
            messagebox.showinfo("3D", "Для 3D установите библиотеку:\npip install matplotlib")
            return
        if self.fullscreen_model_window is not None and self.fullscreen_model_window.winfo_exists():
            self.fullscreen_model_window.lift()
            self.fullscreen_model_window.focus_force()
            return
        window = tk.Toplevel(self)
        window.title("RD конфигуратор АКБ 3D")
        window.configure(bg="#eef3f6")
        try:
            window.state("zoomed")
        except tk.TclError:
            window.attributes("-fullscreen", True)
        window.bind("<Escape>", lambda _event: self.close_fullscreen_model())
        window.protocol("WM_DELETE_WINDOW", self.close_fullscreen_model)

        shell = ctk.CTkFrame(window, fg_color="#eef3f6")
        shell.pack(fill="both", expand=True)
        shell.grid_columnconfigure(0, weight=4)
        shell.grid_columnconfigure(1, weight=1)
        shell.grid_rowconfigure(0, weight=1)

        model_frame = ctk.CTkFrame(shell, fg_color="#eef3f6")
        model_frame.grid(row=0, column=0, sticky="nsew", padx=(14, 8), pady=14)
        model_frame.grid_rowconfigure(0, weight=1)
        model_frame.grid_columnconfigure(0, weight=1)

        legend = ctk.CTkFrame(shell, fg_color="#f7f3e8")
        legend.grid(row=0, column=1, sticky="nsew", padx=(8, 14), pady=14)
        legend.grid_columnconfigure(0, weight=1)
        legend.grid_rowconfigure(2, weight=1)
        legend.grid_rowconfigure(4, weight=2)
        ctk.CTkLabel(legend, text="Сборка", anchor="w", font=("GOST type A", 22, "bold"), fg_color="#f7f3e8").grid(row=0, column=0, sticky="ew", padx=12, pady=(12, 6))
        self.fullscreen_runtime_label = ctk.CTkLabel(legend, text="", anchor="w", justify="left", fg_color="#f7f3e8", font=("GOST type A", 24, "bold"))
        self.fullscreen_runtime_label.grid(row=1, column=0, sticky="ew", padx=12, pady=(0, 8))
        self.fullscreen_info_label = ctk.CTkLabel(legend, text="", anchor="nw", justify="left", fg_color="#f7f3e8", font=("GOST type A", 15), wraplength=320)
        self.fullscreen_info_label.grid(row=2, column=0, sticky="nsew", padx=12, pady=(0, 12))
        ctk.CTkLabel(legend, text="Варианты", anchor="w", font=("GOST type A", 20, "bold"), fg_color="#f7f3e8").grid(row=3, column=0, sticky="ew", padx=12, pady=(4, 6))
        self.fullscreen_variant_bar = ctk.CTkScrollableFrame(legend, fg_color="#f7f3e8", height=280)
        self.fullscreen_variant_bar.grid(row=4, column=0, sticky="nsew", padx=10, pady=(0, 10))
        ctk.CTkButton(legend, text="Закрыть", height=42, fg_color=BUTTON, hover_color=BUTTON_HOVER, text_color="#111", command=self.close_fullscreen_model).grid(row=5, column=0, sticky="ew", padx=12, pady=(0, 12))

        self.fullscreen_model_window = window
        self.fullscreen_model_fig = Figure(figsize=(13, 9), dpi=100, facecolor="#eef3f6")
        self.fullscreen_model_ax = self.fullscreen_model_fig.add_subplot(111, projection="3d")
        self.fullscreen_model_canvas = FigureCanvasTkAgg(self.fullscreen_model_fig, master=model_frame)
        self.fullscreen_model_canvas.get_tk_widget().grid(row=0, column=0, sticky="nsew")
        self.populate_fullscreen_variants()
        if self.selected:
            self.select_pack(self.selected)

    def close_fullscreen_model(self) -> None:
        if self.fullscreen_model_window is not None and self.fullscreen_model_window.winfo_exists():
            self.fullscreen_model_window.destroy()
        self.fullscreen_model_window = None
        self.fullscreen_model_fig = None
        self.fullscreen_model_ax = None
        self.fullscreen_model_canvas = None

    def populate_fullscreen_variants(self) -> None:
        if not hasattr(self, "fullscreen_variant_bar") or not self.fullscreen_variant_bar.winfo_exists():
            return
        for widget in self.fullscreen_variant_bar.winfo_children():
            widget.destroy()
        for col in range(2):
            self.fullscreen_variant_bar.grid_columnconfigure(col, weight=1)
        for index, (pack, color) in enumerate(zip(self.packs, self.variant_colors())):
            layout = f"{pack.grid[0]}×{pack.grid[1]}×{pack.grid[2]}"
            label = f"{pack.s}S{pack.p}P\n{layout}"
            if self.calc_mode_var.get() == "chemistry":
                name = pack.cell.name[:20] + ("..." if len(pack.cell.name) > 20 else "")
                label = f"{name}\n{label}"
            hover = self.darken_color(color)
            ctk.CTkButton(
                self.fullscreen_variant_bar,
                text=label,
                width=96,
                height=58,
                fg_color=color,
                hover_color=hover,
                text_color="#111",
                command=lambda p=pack: self.select_pack(p),
            ).grid(row=index // 2, column=index % 2, padx=4, pady=4, sticky="ew")

    def cuboid_faces(self, origin: tuple[float, float, float], dims: tuple[float, float, float]) -> list[list[tuple[float, float, float]]]:
        x, y, z = origin
        dx, dy, dz = dims
        p = [
            (x, y, z), (x + dx, y, z), (x + dx, y + dy, z), (x, y + dy, z),
            (x, y, z + dz), (x + dx, y, z + dz), (x + dx, y + dy, z + dz), (x, y + dy, z + dz),
        ]
        return [
            [p[0], p[1], p[2], p[3]],
            [p[4], p[5], p[6], p[7]],
            [p[0], p[1], p[5], p[4]],
            [p[1], p[2], p[6], p[5]],
            [p[2], p[3], p[7], p[6]],
            [p[3], p[0], p[4], p[7]],
        ]

    def add_cuboid_3d(self, ax, origin: tuple[float, float, float], dims: tuple[float, float, float], face: str, edge: str, alpha: float = 0.35) -> None:
        collection = Poly3DCollection(self.cuboid_faces(origin, dims), facecolors=face, edgecolors=edge, linewidths=0.7, alpha=alpha)
        ax.add_collection3d(collection)

    def draw_cells_3d(self, ax, pack: Pack) -> None:
        cell = pack.cell
        base_axes = {"L": cell.length, "W": cell.width, "H": cell.height}
        sx, sy, sz = [base_axes[axis] for axis in pack.orientation]
        gap = self.parse_input("gap", False) or 0.0
        gx, gy, gz = pack.grid
        used = 0
        bms = self.parse_input("bms", False) or 0.0
        offset = [0.0, 0.0, 0.0]
        if self.bms_side_menu.get() == "спереди":
            offset[0] = 0.0
        elif self.bms_side_menu.get() == "сбоку":
            offset[1] = 0.0
        elif self.bms_side_menu.get() == "сверху":
            offset[2] = 0.0
        for z in range(gz):
            for y in range(gy):
                for x in range(gx):
                    if used >= pack.n:
                        return
                    origin = (offset[0] + x * (sx + gap), offset[1] + y * (sy + gap), offset[2] + z * (sz + gap))
                    self.add_cuboid_3d(ax, origin, (sx, sy, sz), self.cell_shade(used, pack.n), "#4d6b4f", alpha=0.48)
                    used += 1

    def draw_wire_box_3d(self, ax, origin: tuple[float, float, float], dims: tuple[float, float, float], color: str, linewidth: float = 2.0, linestyle: str = "-") -> None:
        x, y, z = origin
        dx, dy, dz = dims
        pts = [
            (x, y, z), (x + dx, y, z), (x + dx, y + dy, z), (x, y + dy, z),
            (x, y, z + dz), (x + dx, y, z + dz), (x + dx, y + dy, z + dz), (x, y + dy, z + dz),
        ]
        edges = [(0, 1), (1, 2), (2, 3), (3, 0), (4, 5), (5, 6), (6, 7), (7, 4), (0, 4), (1, 5), (2, 6), (3, 7)]
        for a, b in edges:
            ax.plot([pts[a][0], pts[b][0]], [pts[a][1], pts[b][1]], [pts[a][2], pts[b][2]], color=color, linewidth=linewidth, linestyle=linestyle)

    def draw_bms_3d(self, ax, pack: Pack) -> None:
        bms = self.parse_input("bms", False) or 0.0
        if bms <= 0:
            return
        d, w, h = pack.dims
        if self.consider_var.get():
            target = tuple(self.parse_input(k, False) or 0.0 for k in ("depth", "width", "height"))
            if all(v > 0 for v in target):
                d, w, h = target
        side = self.bms_side_menu.get()
        if side == "спереди":
            origin, dims = (max(0.0, d - bms), 0, 0), (min(bms, d), w, h)
        elif side == "сбоку":
            origin, dims = (0, max(0.0, w - bms), 0), (d, min(bms, w), h)
        else:
            origin, dims = (0, 0, max(0.0, h - bms)), (d, w, min(bms, h))
        self.add_cuboid_3d(ax, origin, dims, "#9bd69b", "#cc0000", alpha=0.38)
        cx = origin[0] + dims[0] / 2
        cy = origin[1] + dims[1] / 2
        cz = origin[2] + dims[2] / 2
        ax.text(cx, cy, cz, "BMS", color="#111111", ha="center", va="center", fontsize=10, weight="bold")

    def iso_project(self, x: float, y: float, z: float, origin: tuple[float, float], scale: float) -> tuple[float, float]:
        ox, oy = origin
        cx, cy, cz = getattr(self, "model_center", (0.0, 0.0, 0.0))
        x, y, z = x - cx, y - cy, z - cz
        yaw = math.radians(self.model_yaw)
        pitch = math.radians(self.model_pitch)
        x1 = x * math.cos(yaw) - y * math.sin(yaw)
        y1 = x * math.sin(yaw) + y * math.cos(yaw)
        z1 = z
        y2 = y1 * math.cos(pitch) - z1 * math.sin(pitch)
        z2 = y1 * math.sin(pitch) + z1 * math.cos(pitch)
        return (ox + x1 * scale, oy + y2 * scale - z2 * scale * 0.72)

    def draw_iso_box(
        self,
        canvas: tk.Canvas,
        origin: tuple[float, float],
        dims: tuple[float, float, float],
        scale: float,
        outline: str,
        fill: str,
        dash: bool = False,
    ) -> None:
        d, w, h = dims
        pts = {
            "000": self.iso_project(0, 0, 0, origin, scale),
            "100": self.iso_project(d, 0, 0, origin, scale),
            "010": self.iso_project(0, w, 0, origin, scale),
            "110": self.iso_project(d, w, 0, origin, scale),
            "001": self.iso_project(0, 0, h, origin, scale),
            "101": self.iso_project(d, 0, h, origin, scale),
            "011": self.iso_project(0, w, h, origin, scale),
            "111": self.iso_project(d, w, h, origin, scale),
        }
        line_dash = (7, 4) if dash else None
        if fill:
            canvas.create_polygon(*pts["001"], *pts["101"], *pts["111"], *pts["011"], fill=fill, outline=outline, width=2)
            canvas.create_polygon(*pts["100"], *pts["110"], *pts["111"], *pts["101"], fill="#eeeeee", outline=outline, width=2)
            canvas.create_polygon(*pts["010"], *pts["110"], *pts["111"], *pts["011"], fill="#e3e3e3", outline=outline, width=2)
        edges = [
            ("000", "100"), ("000", "010"), ("100", "110"), ("010", "110"),
            ("001", "101"), ("001", "011"), ("101", "111"), ("011", "111"),
            ("000", "001"), ("100", "101"), ("010", "011"), ("110", "111"),
        ]
        for a, b in edges:
            canvas.create_line(*pts[a], *pts[b], fill=outline, width=3 if not dash else 2, dash=line_dash)

    def draw_iso_bms(
        self,
        canvas: tk.Canvas,
        origin: tuple[float, float],
        dims: tuple[float, float, float],
        scale: float,
        bms: float,
        side: str,
    ) -> None:
        d, w, h = dims
        if side == "спереди":
            x0, x1 = max(0.0, d - bms), d
            corners = [(x0, 0, 0), (x1, 0, 0), (x1, 0, h), (x0, 0, h)]
        elif side == "сбоку":
            y0, y1 = max(0.0, w - bms), w
            corners = [(0, y0, 0), (d, y0, 0), (d, y1, h), (0, y1, h)]
        else:
            z0, z1 = max(0.0, h - bms), h
            corners = [(0, 0, z0), (d, 0, z0), (d, w, z1), (0, w, z1)]
        pts = [self.iso_project(*p, origin, scale) for p in corners]
        canvas.create_polygon(*[coord for point in pts for coord in point], fill="#e9f5ea", outline="#555555", width=2)
        cx = sum(p[0] for p in pts) / len(pts)
        cy = sum(p[1] for p in pts) / len(pts)
        canvas.create_rectangle(cx - 28, cy - 13, cx + 28, cy + 13, fill="#ffffff", outline="#ffffff")
        canvas.create_text(cx, cy, text="BMS", fill="#111111", font=("GOST type A", 14, "bold"))

    def _draw_canvas(self, canvas: tk.Canvas, pack: Pack, front: bool) -> None:
        canvas.delete("all")
        canvas.update_idletasks()
        w, h = max(240, canvas.winfo_width()), max(180, canvas.winfo_height())
        d, wid, hei = pack.dims
        view_w, view_h = (wid, hei) if front else (d, hei)
        target = (0.0, 0.0, 0.0)
        cut = 0.0
        target_view_w, target_view_h = 0.0, 0.0
        cut_view_w, cut_view_h = 0.0, 0.0
        if self.consider_var.get():
            target = tuple(self.parse_input(k, False) or 0.0 for k in ("depth", "width", "height"))
            target_view_w, target_view_h = (target[1], target[2]) if front else (target[0], target[2])
        scale_w = max(view_w, target_view_w, cut_view_w, 1)
        scale_h = max(view_h, target_view_h, cut_view_h, 1)
        left_pad = max(24, min(48, int(w * 0.05)))
        top_pad = max(20, min(38, int(h * 0.07)))
        right_pad = max(54, min(82, int(w * 0.10)))
        bottom_pad = max(44, min(70, int(h * 0.14)))
        scale = min((w - left_pad - right_pad) / scale_w, (h - top_pad - bottom_pad) / scale_h)
        ox, oy = left_pad, top_pad
        rw, rh = view_w * scale, view_h * scale
        canvas.create_rectangle(ox, oy, ox + rw, oy + rh, outline="#cc0000", width=3)
        bms = self.parse_input("bms", False) or 0.0
        bms_side = self.bms_side_menu.get()
        cell_view_w, cell_view_h = view_w, view_h
        bms_rect = None
        if self.consider_var.get() and bms > 0:
            bms_area_w = target_view_w if target_view_w > 0 else view_w
            bms_area_h = target_view_h if target_view_h > 0 else view_h
            bms_area_px = bms_area_w * scale
            bms_area_py = bms_area_h * scale
            bms_px = min(bms_area_px, bms * scale)
            bms_py = min(bms_area_py, bms * scale)
            if bms_side == "спереди" and not front:
                cell_view_w = max(0.0, view_w - bms)
                bms_rect = (ox + bms_area_px - bms_px, oy, ox + bms_area_px, oy + bms_area_py)
            elif bms_side == "сбоку" and front:
                cell_view_w = max(0.0, view_w - bms)
                bms_rect = (ox + bms_area_px - bms_px, oy, ox + bms_area_px, oy + bms_area_py)
            elif bms_side == "сверху":
                cell_view_h = max(0.0, view_h - bms)
                bms_rect = (ox, oy, ox + bms_area_px, oy + bms_py)
        cell_rw, cell_rh = cell_view_w * scale, cell_view_h * scale
        gx, gy, gz = pack.grid
        cols, rows = (gy, gz) if front else (gx, gz)
        cell_origin_y = oy + (rh - cell_rh if bms_rect and bms_side == "сверху" else 0)
        cell_w, cell_h = cell_rw / max(cols, 1), cell_rh / max(rows, 1)
        for y in range(rows):
            for x in range(cols):
                shade_index = y * cols + x
                fill = self.cell_shade(shade_index, max(1, cols * rows))
                x0 = ox + x * cell_w + 2
                y0 = cell_origin_y + y * cell_h + 2
                x1 = ox + (x + 1) * cell_w - 2
                y1 = cell_origin_y + (y + 1) * cell_h - 2
                if pack.cell.shape == "C" and front and pack.orientation[2] == "L":
                    canvas.create_oval(x0, y0, x1, y1, fill=fill, outline="#4d6b4f", width=3)
                else:
                    canvas.create_rectangle(x0, y0, x1, y1, fill=fill, outline="#4d6b4f", width=3)
        if bms_rect:
            self.draw_hatched_rect(canvas, bms_rect)
            self.draw_bms_label(canvas, bms_rect)
        if self.consider_var.get():
            if cut > 0:
                canvas.create_rectangle(
                    ox,
                    oy,
                    ox + cut_view_w * scale,
                    oy + cut_view_h * scale,
                    outline="#d6a400",
                    width=4,
                    dash=(10, 5),
                )
            canvas.create_rectangle(
                ox,
                oy,
                ox + target_view_w * scale,
                oy + target_view_h * scale,
                outline="#159947",
                width=6,
            )
            if target_view_w > 0 and target_view_h > 0:
                self.draw_dimension_labels(
                    canvas,
                    ox,
                    oy,
                    target_view_w * scale,
                    target_view_h * scale,
                    target_view_w,
                    target_view_h,
                    "#159947",
                    outside=False,
                )
        self.draw_dimension_labels(canvas, ox, oy, rw, rh, view_w, view_h, "#ffffff", outside=True)

    def dimension_font_size(self, side_px: float, text: str, limit: int) -> int:
        by_side = int(side_px / max(len(text) * 0.62, 1))
        return max(9, min(limit, by_side))

    def draw_dimension_labels(
        self,
        canvas: tk.Canvas,
        x: float,
        y: float,
        rect_w: float,
        rect_h: float,
        value_w: float,
        value_h: float,
        color: str,
        outside: bool,
    ) -> None:
        text_w = f"{value_w:.1f} мм"
        text_h = f"{value_h:.1f} мм"
        font_w = self.dimension_font_size(rect_w, text_w, 36 if outside else 28)
        font_h = self.dimension_font_size(rect_h, text_h, 36 if outside else 28)
        bg = "#6a6a6a"
        if outside:
            gap = 12
            self.draw_label_box(canvas, x + rect_w / 2, y + rect_h + gap + font_w * 0.45, text_w, font_w, color, bg, angle=0)
            self.draw_label_box(canvas, x + rect_w + gap + font_h * 0.45, y + rect_h / 2, text_h, font_h, color, bg, angle=90)
        else:
            gap = 12
            self.draw_label_box(canvas, x + rect_w / 2, y + gap + font_w * 0.45, text_w, font_w, color, bg, angle=0)
            self.draw_label_box(canvas, x + rect_w - gap - font_h * 0.45, y + rect_h / 2, text_h, font_h, color, bg, angle=90)

    def draw_label_box(
        self,
        canvas: tk.Canvas,
        cx: float,
        cy: float,
        text: str,
        font_size: int,
        color: str,
        bg: str,
        angle: int,
    ) -> None:
        color = self.contrast_text_color(bg)
        pad_x = max(10, int(font_size * 0.45))
        pad_y = max(6, int(font_size * 0.28))
        text_w = max(28, len(text) * font_size * 0.55)
        text_h = font_size * 1.1
        text_w *= 1.15
        if angle == 90:
            box_w, box_h = text_h + pad_y * 2, text_w + pad_x * 2
        else:
            box_w, box_h = text_w + pad_x * 2, text_h + pad_y * 2
        canvas.create_rectangle(cx - box_w / 2, cy - box_h / 2, cx + box_w / 2, cy + box_h / 2, fill=bg, outline=bg)
        canvas.create_text(cx, cy, text=text, fill=color, font=("GOST type A", font_size), angle=angle, anchor="center")

    def contrast_text_color(self, bg: str) -> str:
        bg = bg.lstrip("#")
        r, g, b = (int(bg[i:i + 2], 16) for i in (0, 2, 4))
        luminance = 0.2126 * r + 0.7152 * g + 0.0722 * b
        return "#ffffff" if luminance < 150 else "#111111"

    def draw_hatched_rect(self, canvas: tk.Canvas, rect: tuple[float, float, float, float]) -> None:
        x0, y0, x1, y1 = rect
        canvas.create_rectangle(x0, y0, x1, y1, outline="#555555", fill="#e9f5ea", width=2)
        step = 12
        height = y1 - y0
        pos = x0 - height
        while pos < x1:
            raw_a = (pos, y1)
            raw_b = (pos + height, y0)
            clipped = self.clip_line_to_rect(raw_a, raw_b, rect)
            if clipped:
                (xa, ya), (xb, yb) = clipped
                canvas.create_line(xa, ya, xb, yb, fill="#cc0000", width=2)
            pos += step
        canvas.create_rectangle(x0, y0, x1, y1, outline="#555555", width=2)

    def draw_bms_label(self, canvas: tk.Canvas, rect: tuple[float, float, float, float]) -> None:
        x0, y0, x1, y1 = rect
        width, height = x1 - x0, y1 - y0
        cx, cy = (x0 + x1) / 2, (y0 + y1) / 2
        angle = 90 if height > width * 1.4 else 0
        text = "BMS"
        pad_x, pad_y = 8, 5
        if angle == 90:
            max_font_by_width = int((width - pad_x * 2) / 1.25)
            max_font_by_height = int((height - pad_y * 2) / (len(text) * 0.72))
        else:
            max_font_by_width = int((width - pad_x * 2) / (len(text) * 0.72))
            max_font_by_height = int((height - pad_y * 2) / 1.25)
        font_size = max(8, min(28, max_font_by_width, max_font_by_height))
        text_w = max(20, len(text) * font_size * 0.72)
        text_h = font_size * 1.25
        if angle == 90:
            box_w = min(width - 4, text_h + pad_y * 2)
            box_h = min(height - 4, text_w + pad_x * 2)
        else:
            box_w = min(width - 4, text_w + pad_x * 2)
            box_h = min(height - 4, text_h + pad_y * 2)
        canvas.create_rectangle(
            cx - box_w / 2,
            cy - box_h / 2,
            cx + box_w / 2,
            cy + box_h / 2,
            fill="#ffffff",
            outline="#ffffff",
        )
        canvas.create_text(cx, cy, text=text, angle=angle, fill="#111111", font=("GOST type A", font_size, "bold"), anchor="center")

    def clip_line_to_rect(
        self,
        p0: tuple[float, float],
        p1: tuple[float, float],
        rect: tuple[float, float, float, float],
    ) -> Optional[tuple[tuple[float, float], tuple[float, float]]]:
        x0, y0 = p0
        x1, y1 = p1
        xmin, ymin, xmax, ymax = rect
        dx, dy = x1 - x0, y1 - y0
        t0, t1 = 0.0, 1.0
        for p, q in ((-dx, x0 - xmin), (dx, xmax - x0), (-dy, y0 - ymin), (dy, ymax - y0)):
            if p == 0:
                if q < 0:
                    return None
                continue
            r = q / p
            if p < 0:
                if r > t1:
                    return None
                t0 = max(t0, r)
            else:
                if r < t0:
                    return None
                t1 = min(t1, r)
        return ((x0 + t0 * dx, y0 + t0 * dy), (x0 + t1 * dx, y0 + t1 * dy))

    def export_excel(self) -> None:
        if not self.packs:
            return
        try:
            from openpyxl import Workbook
            from openpyxl.styles import Alignment, Font, PatternFill
        except ImportError:
            messagebox.showerror("Нет openpyxl", "Установите зависимость: pip install openpyxl")
            return
        path = filedialog.asksaveasfilename(defaultextension=".xlsx", filetypes=[("Excel", "*.xlsx")], initialfile="rd_pack_variants.xlsx")
        if not path:
            return
        wb = Workbook()
        wb.remove(wb.active)
        inputs = {key: self.entries[key].get() for key in self.entries}

        title_fill = PatternFill("solid", fgColor="1B7A1B")
        section_fill = PatternFill("solid", fgColor="D9EAD3")
        warning_fill = PatternFill("solid", fgColor="F4CCCC")
        title_font = Font(bold=True, color="FFFFFF", size=14)
        section_font = Font(bold=True)

        for index, pack in enumerate(self.packs, start=1):
            cell = pack.cell
            sheet_name = f"{pack.s}S{pack.p}P"
            if sheet_name in wb.sheetnames:
                sheet_name = f"{sheet_name}_{index}"
            ws = wb.create_sheet(sheet_name[:31])
            ws.column_dimensions["A"].width = 34
            ws.column_dimensions["B"].width = 42
            ws.column_dimensions["C"].width = 18

            def section(title: str) -> None:
                row = ws.max_row + 1
                ws.cell(row, 1, title)
                ws.merge_cells(start_row=row, start_column=1, end_row=row, end_column=3)
                ws.cell(row, 1).font = section_font
                ws.cell(row, 1).fill = section_fill

            def item(key: str, value: object, unit: str = "") -> None:
                row = ws.max_row + 1
                ws.cell(row, 1, key)
                ws.cell(row, 2, value)
                ws.cell(row, 3, unit)

            ws.append([f"RD конфигуратор АКБ - сборка {pack.s}S{pack.p}P"])
            ws.merge_cells(start_row=1, start_column=1, end_row=1, end_column=3)
            ws["A1"].font = title_font
            ws["A1"].fill = title_fill
            ws["A1"].alignment = Alignment(horizontal="center")

            section("Исходная ячейка")
            item("Наименование", cell.name)
            item("Бренд", cell.brand)
            item("Тип химии", cell.chemistry)
            item("Тип формы", cell.shape)
            item("Габариты ячейки Д×Ш×В", f"{cell.length:g}×{cell.width:g}×{cell.height:g}", "мм")
            item("Ёмкость ячейки", round(cell.capacity, 3), "А·ч")
            item("Номинальное напряжение ячейки", round(cell.voltage_nom, 3), "В")
            item("Мин./макс. напряжение ячейки", f"{fmt(cell.voltage_min, 'В')} / {fmt(cell.voltage_max, 'В')}")
            item("Макс. ток разряда ячейки", round(cell.max_discharge, 3), "А")
            item("Макс. ток заряда ячейки", "" if cell.max_charge is None else round(cell.max_charge, 3), "А")
            item("Рабочая температура", f"{fmt(cell.temp_min, '°C')} / {fmt(cell.temp_max, '°C')}")
            item("Масса", "" if cell.mass is None else round(cell.mass, 3), "г")
            item("Внутр. сопротивление", "" if cell.resistance is None else round(cell.resistance, 3), "мОм")
            item("Циклов", "" if cell.cycles is None else round(cell.cycles, 0))
            item("Ёмкость после 1000 циклов", "" if cell.capacity_1000 is None else round(cell.capacity_1000, 2), "%")

            section("Конфигурация сборки")
            item("Схема", f"{pack.s}S × {pack.p}P")
            item("Число используемых ячеек", pack.n, "шт")
            item("3D-укладка a×b×c", f"{pack.grid[0]}×{pack.grid[1]}×{pack.grid[2]}")
            item("Ориентация осей", " → ".join(pack.orientation))
            item("Характерная метка", pack.marks or "обычный вариант")

            section("Электрические параметры")
            item("Общая ёмкость", round(pack.capacity, 3), "А·ч")
            item("Номинальное напряжение", round(pack.voltage, 3), "В")
            item("Общая энергия", round(pack.energy, 3), "Вт·ч")
            item("Макс. ток разряда сборки", round(pack.max_current, 3), "А")
            item("Расчётное время работы", fmt_runtime(pack.runtime))
            item("Заданная нагрузка", inputs.get("load", ""), "Вт")
            item("Требуемое время", inputs.get("time", ""), "ч")

            section("Габариты и ограничения")
            item("Габариты сборки Д×Ш×В", f"{pack.dims[0]:.1f}×{pack.dims[1]:.1f}×{pack.dims[2]:.1f}", "мм")
            item("Объём сборки", round(pack.volume, 1), "мм³")
            item("Учитывать габариты", "да" if self.consider_var.get() else "нет")
            item("Целевые габариты Д×Ш×В", f"{inputs.get('depth', '')}×{inputs.get('width', '')}×{inputs.get('height', '')}", "мм")
            item("Толщина стенки корпуса", inputs.get("wall", ""), "мм")
            item("Зазор между ячейками", inputs.get("gap", ""), "мм")
            item("Место под BMS", inputs.get("bms", ""), "мм")
            item("Сторона установки BMS", self.bms_side_menu.get())

            section("Статус")
            status = "проходит" if pack.ok_time and pack.ok_dims else pack.warning
            item("Итог", status)
            if pack.warning:
                ws.cell(ws.max_row, 2).fill = warning_fill

            for row in ws.iter_rows():
                for cell_obj in row:
                    cell_obj.alignment = Alignment(vertical="top", wrap_text=True)
        wb.save(path)


if __name__ == "__main__":
    try:
        MainApp().mainloop()
    except KeyboardInterrupt:
        sys.exit(0)

from __future__ import annotations

import csv
import io
import math
import sys
from dataclasses import dataclass
from itertools import permutations
from pathlib import Path
from typing import Optional

try:
    import customtkinter as ctk
except ImportError:
    print("Установите зависимости: pip install customtkinter openpyxl Pillow cairosvg")
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


ROOT = Path(__file__).resolve().parent
DB_PATH = ROOT / "cells_db.txt"
LOGO_PATHS = [ROOT / "logo.svg", ROOT / "logo_RD.svg", ROOT / "logo.png"]
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
    marks: str = ""


def ensure_db() -> None:
    if not DB_PATH.exists() or DB_PATH.stat().st_size == 0:
        DB_PATH.write_text(";".join(HEADER) + "\n", encoding="utf-8")


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


def load_db() -> tuple[list[Cell], int]:
    ensure_db()
    cells: list[Cell] = []
    skipped = 0
    with DB_PATH.open("r", encoding="utf-8", newline="") as fh:
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
                    to_float(row["циклов"]), to_float(row["емкость_после_1000_циклов_%"]),
                ))
            except Exception as exc:
                skipped += 1
                print(f"Пропуск строки {line_no}: {exc}")
    print(f"База: {DB_PATH}")
    print(f"Загружено ячеек: {len(cells)}")
    print(f"Пропущено строк: {skipped}")
    return cells, skipped


def generated_rd_logo(master: tk.Misc, size: int) -> Optional[ImageTk.PhotoImage]:
    if Image is None or ImageDraw is None or ImageTk is None:
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
    return ImageTk.PhotoImage(image, master=master)


def load_logo(master: tk.Misc, size: int) -> Optional[ImageTk.PhotoImage]:
    if Image is None or ImageTk is None:
        print("Pillow не установлен, логотип отключен.")
        return None
    for path in LOGO_PATHS:
        if not path.exists():
            continue
        try:
            if path.suffix.lower() == ".svg":
                try:
                    import cairosvg
                    png = cairosvg.svg2png(url=str(path), output_width=size, output_height=size)
                    image = Image.open(io.BytesIO(png)).convert("RGBA")
                except Exception as exc:
                    print(f"Не удалось прочитать SVG {path.name}: {exc}")
                    continue
            else:
                image = Image.open(path).convert("RGBA").resize((size, size))
            return ImageTk.PhotoImage(image, master=master)
        except Exception as exc:
            print(f"Логотип {path.name} не загружен: {exc}")
    print("Логотип не найден или не прочитан, используется встроенный знак RD.")
    return generated_rd_logo(master, size)


def fmt(value: Optional[float], unit: str = "", digits: int = 2) -> str:
    if value is None:
        return "—"
    text = f"{value:.{digits}f}".rstrip("0").rstrip(".")
    return f"{text} {unit}".strip()


def rounded_dims(dims: tuple[float, float, float]) -> tuple[float, float, float]:
    return tuple(round(x, 1) for x in dims)  # type: ignore[return-value]


def row_size(count: int, size: float, gap: float) -> float:
    return count * size + max(0, count - 1) * gap


def grid_candidates(n: int) -> list[tuple[int, int, int]]:
    triples = []
    for c in range(1, 4):
        for a in range(1, n + 1):
            b = math.ceil(n / (a * c))
            if a * b * c >= n:
                triples.append((a, b, c))
    min_empty = min(a * b * c - n for a, b, c in triples)
    filtered = [t for t in triples if t[0] * t[1] * t[2] - n == min_empty]
    return sorted(set(filtered), key=lambda t: (t[0] * t[1] * t[2], max(t), sum(t)))[:80]


def bms_axis(pack_dims: tuple[float, float, float], target: tuple[float, float, float], bms: float) -> int:
    if bms <= 0:
        return 0
    margins = [target[i] - pack_dims[i] - bms for i in range(3)]
    return max(range(3), key=lambda i: margins[i])


def best_layout(
    cell: Cell,
    n: int,
    consider_dims: bool,
    target: tuple[float, float, float],
    gap: float,
    wall: float,
    bms: float,
    cut: float,
) -> tuple[tuple[float, float, float], tuple[int, int, int], tuple[str, str, str], bool, str]:
    base_axes = {"L": cell.length, "W": cell.width, "H": cell.height}
    effective = tuple(max(0.0, d * (1 + cut / 100.0) - 2 * wall) for d in target)
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
            axis = bms_axis(dims, effective, bms)
            dims_with_bms = list(dims)
            dims_with_bms[axis] += bms
            rdims = rounded_dims(tuple(dims_with_bms))
            overflow = [max(0.0, rdims[i] - effective[i]) for i in range(3)]
            volume = rdims[0] * rdims[1] * rdims[2]
            ok = not consider_dims or all(v <= 1e-9 for v in overflow)
            item = (volume, rdims, grid, orient, ok, overflow)
            if ok:
                variants.append(item)
            if near is None or sum(overflow) < sum(near[-1]):
                near = item
    source = variants[0] if variants else near
    assert source is not None
    _volume, dims, grid, orient, ok, overflow = source
    warning = ""
    if consider_dims and not ok:
        axes = ["глубине", "ширине", "высоте"]
        idx = max(range(3), key=lambda i: overflow[i])
        warning = f"⚠ превышение по {axes[idx]} на {overflow[idx]:.1f} мм"
    return dims, grid, orient, ok, warning


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
) -> list[Pack]:
    packs: list[Pack] = []
    rejected_time: list[Pack] = []
    rejected_dims: list[Pack] = []
    e_cell = cell.voltage_nom * cell.capacity
    for s in range(1, 101):
        for p in range(1, 101):
            n = s * p
            if n > 400:
                continue
            energy = e_cell * n
            runtime = energy / load_w
            ok_time = runtime >= required_h
            dims, grid, orient, ok_dims, warning = best_layout(cell, n, consider_dims, target, gap, wall, bms, cut)
            pack = Pack(
                s, p, n, dims, grid, orient, energy, cell.capacity * p, cell.voltage_nom * s,
                cell.max_discharge * p, runtime, dims[0] * dims[1] * dims[2], ok_time, ok_dims,
                "" if ok_time and ok_dims else (warning or f"⚠ время меньше требуемого на {required_h - runtime:.2f} ч"),
            )
            if ok_time and ok_dims:
                packs.append(pack)
            elif ok_time:
                rejected_dims.append(pack)
            else:
                rejected_time.append(pack)
    packs.sort(key=lambda x: (x.n, x.volume, x.s))
    final = packs[:10]
    if len(final) < 3:
        rejected_time.sort(key=lambda x: abs(required_h - x.runtime))
        rejected_dims.sort(key=lambda x: x.volume)
        final.extend(rejected_time[: max(0, 3 - len(final))])
        final.extend(rejected_dims[: max(0, 3 - len(final))])
    if not final and rejected_time:
        final = sorted(rejected_time, key=lambda x: abs(required_h - x.runtime))[:1]
    final = sorted(final[:10], key=lambda x: (x.n, x.volume, x.s))
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
        self.title("RD конфигуратор АКБ")
        self.configure(fg_color=BG)
        self.minsize(1000, 700)
        self._center(0.7, 0.7)
        self.logo = load_logo(self, 40)
        if self.logo:
            self.iconphoto(True, self.logo)
        self.cells, _skipped = load_db()
        if not self.cells:
            messagebox.showerror("База пуста", "cells_db.txt отсутствует или не содержит корректных ячеек.")
            self.after(100, self.destroy)
            return
        self.cell_by_label = {self.cell_label(c): c for c in self.cells}
        self.entries: dict[str, ctk.CTkEntry] = {}
        self.errors: dict[str, ctk.CTkLabel] = {}
        self.packs: list[Pack] = []
        self.selected: Optional[Pack] = None
        self._build()
        self.on_cell_change(self.cell_combo.get())

    def _center(self, wf: float, hf: float) -> None:
        sw, sh = self.winfo_screenwidth(), self.winfo_screenheight()
        w, h = int(sw * wf), int(sh * hf)
        self.geometry(f"{w}x{h}+{(sw - w) // 2}+{(sh - h) // 2}")

    def cell_label(self, cell: Cell) -> str:
        return f"{cell.name} — {cell.brand} — {fmt(cell.capacity, 'А·ч')} — Uном {fmt(cell.voltage_nom, 'В')}"

    def _build(self) -> None:
        header = ctk.CTkFrame(self, fg_color=BG)
        header.pack(fill="x", padx=16, pady=(14, 6))
        if self.logo:
            ctk.CTkLabel(header, image=self.logo, text="").pack(side="left")
        ctk.CTkLabel(header, text="RD конфигуратор АКБ", font=("GOST type A", 26, "bold")).pack(side="left", padx=12)

        top = ctk.CTkFrame(self, fg_color=BG)
        top.pack(fill="x", padx=16, pady=8)
        top.grid_columnconfigure(0, weight=1)
        top.grid_columnconfigure(1, weight=1)

        inputs = ctk.CTkFrame(top, fg_color=BG)
        inputs.grid(row=0, column=0, sticky="nsew", padx=(0, 12))
        self.cell_combo = ctk.CTkOptionMenu(inputs, values=list(self.cell_by_label), command=self.on_cell_change, fg_color=FIELD_BG, button_color=BUTTON, text_color="#111", font=FONT)
        self.cell_combo.pack(fill="x", pady=(0, 8))
        fields = [
            ("load", "Нагрузка, Вт", ""),
            ("time", "Требуемое время работы, ч", ""),
            ("depth", "Глубина сборки, мм", ""),
            ("width", "Ширина сборки, мм", ""),
            ("height", "Высота сборки, мм", ""),
            ("cut", "Допуск вырезания, %", "0"),
            ("wall", "Толщина стенки корпуса, мм", "0"),
            ("gap", "Зазор между ячейками, мм", "2"),
            ("bms", "Место под BMS, мм", "0"),
        ]
        self.consider_var = tk.BooleanVar(value=False)
        self.consider_box = ctk.CTkCheckBox(inputs, text="Учитывать габариты", variable=self.consider_var, command=self.toggle_cut, font=FONT)
        self.consider_box.pack(anchor="w", pady=(0, 6))
        for key, label, default in fields:
            ctk.CTkLabel(inputs, text=label, anchor="w", font=FONT).pack(fill="x")
            entry = ctk.CTkEntry(inputs, fg_color=FIELD_BG, border_width=0, font=FONT)
            entry.insert(0, default)
            entry.pack(fill="x")
            err = ctk.CTkLabel(inputs, text="", text_color=ERROR, anchor="w", height=15, font=("GOST type A", 11))
            err.pack(fill="x")
            self.entries[key] = entry
            self.errors[key] = err

        self.mirror = ctk.CTkFrame(top, fg_color="#ffffff", border_width=1, border_color="#d0d0d0")
        self.mirror.grid(row=0, column=1, sticky="nsew")

        self.calc_button = ctk.CTkButton(self, text="Рассчитать сборку", height=48, fg_color=BUTTON, hover_color=BUTTON_HOVER, text_color="#111", font=("GOST type A", 20, "bold"), command=self.run_calc)
        self.calc_button.pack(fill="x", padx=16, pady=8)

        output = ctk.CTkFrame(self, fg_color="#ffffff", border_width=1, border_color="#c8c8c8")
        output.pack(fill="both", expand=True, padx=16, pady=(0, 16))
        self.variant_bar = ctk.CTkScrollableFrame(output, height=58, orientation="horizontal", fg_color="#ffffff")
        self.variant_bar.pack(fill="x", padx=8, pady=8)
        tools = ctk.CTkFrame(output, fg_color="#ffffff")
        tools.pack(fill="x", padx=8)
        self.gap_slider = ctk.CTkSlider(tools, from_=0, to=10, command=lambda v: self.sync_slider("gap", v))
        self.gap_slider.set(2)
        self.gap_slider.pack(side="left", fill="x", expand=True, padx=6)
        self.bms_slider = ctk.CTkSlider(tools, from_=0, to=50, command=lambda v: self.sync_slider("bms", v))
        self.bms_slider.set(0)
        self.bms_slider.pack(side="left", fill="x", expand=True, padx=6)
        ctk.CTkButton(tools, text="Экспорт в Excel", fg_color=BUTTON, hover_color=BUTTON_HOVER, text_color="#111", command=self.export_excel).pack(side="left", padx=6)

        detail = ctk.CTkFrame(output, fg_color="#ffffff")
        detail.pack(fill="both", expand=True, padx=8, pady=8)
        detail.grid_columnconfigure(0, weight=1)
        detail.grid_columnconfigure(1, weight=1)
        detail.grid_rowconfigure(0, weight=1)
        detail.grid_rowconfigure(1, weight=1)
        self.description = ctk.CTkTextbox(detail, fg_color="#ffffff", border_width=1, border_color="#e0e0e0", font=FONT)
        self.description.grid(row=0, column=0, sticky="nsew", padx=(0, 6), pady=(0, 6))
        self.front_canvas = tk.Canvas(detail, bg="white", highlightthickness=1, highlightbackground="#e0e0e0")
        self.front_canvas.grid(row=0, column=1, sticky="nsew", pady=(0, 6))
        self.side_canvas = tk.Canvas(detail, bg="white", highlightthickness=1, highlightbackground="#e0e0e0")
        self.side_canvas.grid(row=1, column=0, columnspan=2, sticky="nsew")
        self.toggle_cut()

    def toggle_cut(self) -> None:
        state = "normal" if self.consider_var.get() else "disabled"
        self.entries["cut"].configure(state=state)

    def sync_slider(self, key: str, value: float) -> None:
        entry = self.entries[key]
        entry.delete(0, "end")
        entry.insert(0, f"{value:.1f}")
        if self.selected:
            self.run_calc(keep_selection=True)

    def on_cell_change(self, _value: str) -> None:
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

    def run_calc(self, keep_selection: bool = False) -> None:
        values = {k: self.parse_input(k, k in {"load", "time"} or self.consider_var.get() and k in {"depth", "width", "height"}) for k in self.entries}
        if any(v is None for v in values.values()):
            return
        if values["load"] <= 0 or values["time"] <= 0:
            self.errors["load"].configure(text="нагрузка и время должны быть больше 0")
            return
        self.packs = calculate(
            self.current_cell(), values["load"], values["time"], self.consider_var.get(),
            (values["depth"], values["width"], values["height"]), values["cut"], values["wall"], values["gap"], values["bms"],
        )
        if self.consider_var.get() and self.packs and not any(p.ok_dims for p in self.packs):
            self.description.delete("1.0", "end")
            self.description.insert("end", "Ни одна сборка не влезает в заданные габариты.\nПоказаны ближайшие варианты.\n")
        self.draw_variant_buttons()
        if self.packs:
            self.select_pack(self.selected if keep_selection and self.selected in self.packs else self.packs[0])

    def draw_variant_buttons(self) -> None:
        for widget in self.variant_bar.winfo_children():
            widget.destroy()
        for pack in self.packs:
            label = f"{pack.s}S{pack.p}P {pack.marks}".strip()
            color = "#d9d9d9" if pack.ok_time and pack.ok_dims else "#ead0d0"
            ctk.CTkButton(self.variant_bar, text=label, width=95, fg_color=color, hover_color=BUTTON_HOVER, text_color="#111", command=lambda p=pack: self.select_pack(p)).pack(side="left", padx=4, pady=4)

    def select_pack(self, pack: Pack) -> None:
        self.selected = pack
        cell = self.current_cell()
        self.description.delete("1.0", "end")
        orient = "стоит" if pack.orientation[2] == "L" else "лежит"
        text = [
            f"{cell.name}, форма {cell.shape}, ориентация {orient} ({''.join(pack.orientation)})",
            f"{pack.s}S × {pack.p}P",
            f"ЧИСЛО ИСПОЛЬЗУЕМЫХ ЯЧЕЕК = {pack.n}",
            f"Общая ёмкость: {fmt(pack.capacity, 'А·ч')}",
            f"Номинальное напряжение сборки: {fmt(pack.voltage, 'В')}",
            f"Общая энергия: {fmt(pack.energy, 'Вт·ч')}",
            f"Макс ток разряда сборки: {fmt(pack.max_current, 'А')}",
            f"Температура: {fmt(cell.temp_min, '°C')} / {fmt(cell.temp_max, '°C')}",
            f"Ёмкость после 1000 циклов: {fmt(cell.capacity_1000, '%')}",
            f"Расчётное время: {fmt(pack.runtime, 'ч')}",
            f"Габариты Д×Ш×В: {pack.dims[0]:.1f}×{pack.dims[1]:.1f}×{pack.dims[2]:.1f} мм",
        ]
        if pack.warning:
            text.append(pack.warning)
        self.description.insert("end", "\n".join(text))
        self.draw_pack(pack)

    def draw_pack(self, pack: Pack) -> None:
        self._draw_canvas(self.front_canvas, pack, front=True)
        self._draw_canvas(self.side_canvas, pack, front=False)

    def _draw_canvas(self, canvas: tk.Canvas, pack: Pack, front: bool) -> None:
        canvas.delete("all")
        canvas.update_idletasks()
        w, h = max(240, canvas.winfo_width()), max(180, canvas.winfo_height())
        d, wid, hei = pack.dims
        view_w, view_h = (wid, hei) if front else (d, hei)
        scale = min((w - 80) / max(view_w, 1), (h - 60) / max(view_h, 1))
        ox, oy = 40, 25
        rw, rh = view_w * scale, view_h * scale
        canvas.create_rectangle(ox, oy, ox + rw, oy + rh, outline="#cc0000", width=3)
        canvas.create_text(ox + rw / 2, oy + rh + 18, text=f"{view_w:.1f} мм", fill="#111")
        canvas.create_text(ox + rw + 30, oy + rh / 2, text=f"{view_h:.1f} мм", angle=90, fill="#111")
        gx, gy, gz = pack.grid
        cols, rows = (gy, gz) if front else (gx, gz)
        cell_w, cell_h = rw / max(cols, 1), rh / max(rows, 1)
        for y in range(rows):
            for x in range(cols):
                x0 = ox + x * cell_w + 2
                y0 = oy + y * cell_h + 2
                x1 = ox + (x + 1) * cell_w - 2
                y1 = oy + (y + 1) * cell_h - 2
                if self.current_cell().shape == "C" and front and pack.orientation[2] == "L":
                    canvas.create_oval(x0, y0, x1, y1, outline="#777777", width=3)
                else:
                    canvas.create_rectangle(x0, y0, x1, y1, outline="#777777", width=3)
        if self.consider_var.get():
            target = tuple(self.parse_input(k, False) or 0.0 for k in ("depth", "width", "height"))
            tw, th = (target[1], target[2]) if front else (target[0], target[2])
            canvas.create_rectangle(ox, oy, ox + tw * scale, oy + th * scale, outline="#159947", width=2, dash=(6, 4))
            bms = self.parse_input("bms", False) or 0.0
            if bms > 0:
                canvas.create_rectangle(ox + rw - min(rw, bms * scale), oy, ox + rw, oy + rh, outline="#159947", fill="#e9f5ea", stipple="gray25")

    def export_excel(self) -> None:
        if not self.packs:
            return
        try:
            from openpyxl import Workbook
        except ImportError:
            messagebox.showerror("Нет openpyxl", "Установите зависимость: pip install openpyxl")
            return
        path = filedialog.asksaveasfilename(defaultextension=".xlsx", filetypes=[("Excel", "*.xlsx")], initialfile="rd_pack_variants.xlsx")
        if not path:
            return
        wb = Workbook()
        ws = wb.active
        ws.title = "Варианты"
        ws.append(["S", "P", "число ячеек", "габариты Д×Ш×В мм", "энергия Вт·ч", "ёмкость А·ч", "напряжение В", "макс ток А", "время ч", "ориентация", "форма", "пометка"])
        shape = self.current_cell().shape
        for p in self.packs:
            ws.append([p.s, p.p, p.n, f"{p.dims[0]:.1f}×{p.dims[1]:.1f}×{p.dims[2]:.1f}", round(p.energy, 2), round(p.capacity, 2), round(p.voltage, 2), round(p.max_current, 2), round(p.runtime, 2), "".join(p.orientation), shape, "проходит" if p.ok_time and p.ok_dims else p.warning])
        wb.save(path)


if __name__ == "__main__":
    try:
        MainApp().mainloop()
    except KeyboardInterrupt:
        sys.exit(0)

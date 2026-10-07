from __future__ import annotations

import csv
import io
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

try:
    import customtkinter as ctk
except ImportError:
    print("Установите зависимости: pip install customtkinter Pillow cairosvg")
    raise

import tkinter as tk
from tkinter import ttk

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
class DbResult:
    rows: list[dict[str, str]]
    skipped: int


FORM_FIELDS = [
    ("наименование", "Наименование*", True, False),
    ("бренд", "Бренд*", True, False),
    ("тип_химии", "Тип химии*", True, False),
    ("тип_формы", "Тип формы* (C/P)", True, False),
    ("длина_мм", "Длина мм*", True, True),
    ("ширина_мм", "Ширина мм*", True, True),
    ("высота_мм", "Высота мм*", True, True),
    ("емкость_Ач", "Ёмкость А·ч*", True, True),
    ("напряжение_ном_В", "Напряжение ном. В*", True, True),
    ("напряжение_мин_В", "Напряжение мин. В", False, True),
    ("напряжение_макс_В", "Напряжение макс. В", False, True),
    ("макс_ток_разряда_А", "Макс. ток разряда А*", True, True),
    ("макс_ток_заряда_А", "Макс. ток заряда А", False, True),
    ("мин_темп_разряда", "Мин. темп. °C", False, True),
    ("макс_темп_разряда", "Макс. темп. °C", False, True),
    ("масса_г", "Масса г", False, True),
    ("внутр_сопротивление_мОм", "Внутр. сопротивление мОм", False, True),
    ("циклов", "Ресурс циклов", False, True),
    ("емкость_после_1000_циклов_%", "Ёмкость после 1000 циклов %", False, True),
]


def ensure_db() -> None:
    if not DB_PATH.exists() or DB_PATH.stat().st_size == 0:
        DB_PATH.write_text(";".join(HEADER) + "\n", encoding="utf-8")


def load_db() -> DbResult:
    ensure_db()
    rows: list[dict[str, str]] = []
    skipped = 0
    with DB_PATH.open("r", encoding="utf-8", newline="") as fh:
        reader = csv.reader(fh, delimiter=";")
        try:
            header = next(reader)
        except StopIteration:
            ensure_db()
            return DbResult([], 0)
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
            if row["тип_формы"].upper() not in {"C", "P"}:
                skipped += 1
                print(f"Пропуск строки {line_no}: тип формы должен быть C или P")
                continue
            rows.append(row)
    print(f"База: {DB_PATH}")
    print(f"Загружено ячеек: {len(rows)}")
    print(f"Пропущено строк: {skipped}")
    return DbResult(rows, skipped)


def parse_number(text: str) -> str:
    text = text.strip().replace(",", ".")
    if not text:
        return ""
    number = float(text)
    return f"{number:g}"


def generated_rd_logo(master: tk.Misc, size: int) -> Optional[ImageTk.PhotoImage]:
    if Image is None or ImageDraw is None or ImageTk is None:
        return None
    image = Image.new("RGBA", (size, size), (253, 246, 244, 255))
    draw = ImageDraw.Draw(image)
    draw.rounded_rectangle((1, 1, size - 2, size - 2), radius=max(4, size // 5), fill="#f6dcd6", outline="#1a1a1a", width=2)
    try:
        font = ImageFont.truetype("arialbd.ttf", max(12, int(size * 0.42))) if ImageFont else None
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


class AddCellApp(ctk.CTk):
    def __init__(self) -> None:
        super().__init__()
        ctk.set_appearance_mode("light")
        self.title("RD — добавление ячейки")
        self.configure(fg_color=BG)
        self.minsize(900, 600)
        self._center(0.7, 0.7)
        self.logo = load_logo(self, 32)
        if self.logo:
            self.iconphoto(True, self.logo)
        self.entries: dict[str, ctk.CTkEntry] = {}
        self.errors: dict[str, ctk.CTkLabel] = {}
        self.rows: list[dict[str, str]] = []
        self._build()
        self.refresh()

    def _center(self, wf: float, hf: float) -> None:
        sw, sh = self.winfo_screenwidth(), self.winfo_screenheight()
        w, h = int(sw * wf), int(sh * hf)
        self.geometry(f"{w}x{h}+{(sw - w) // 2}+{(sh - h) // 2}")

    def _build(self) -> None:
        header = ctk.CTkFrame(self, fg_color=BG)
        header.pack(fill="x", padx=16, pady=(14, 6))
        if self.logo:
            ctk.CTkLabel(header, image=self.logo, text="").pack(side="left")
        ctk.CTkLabel(header, text="Добавление ячейки", font=("GOST type A", 24, "bold"), text_color="#1a1a1a").pack(side="left", padx=12)

        body = ctk.CTkFrame(self, fg_color=BG)
        body.pack(fill="both", expand=True, padx=16, pady=8)
        body.grid_columnconfigure(1, weight=1)
        body.grid_rowconfigure(0, weight=1)

        form = ctk.CTkScrollableFrame(body, width=380, fg_color=BG)
        form.grid(row=0, column=0, sticky="nsw", padx=(0, 12))
        for key, label, _required, _numeric in FORM_FIELDS:
            ctk.CTkLabel(form, text=label, anchor="w", font=FONT).pack(fill="x", pady=(4, 0))
            entry = ctk.CTkEntry(form, fg_color=FIELD_BG, border_width=0, font=FONT)
            entry.pack(fill="x")
            err = ctk.CTkLabel(form, text="", text_color=ERROR, anchor="w", height=16, font=("GOST type A", 11))
            err.pack(fill="x")
            self.entries[key] = entry
            self.errors[key] = err

        buttons = ctk.CTkFrame(form, fg_color=BG)
        buttons.pack(fill="x", pady=8)
        ctk.CTkButton(buttons, text="Обновить базу", fg_color=BUTTON, hover_color=BUTTON_HOVER, text_color="#111", command=self.refresh).pack(fill="x", pady=4)
        ctk.CTkButton(buttons, text="Добавить в базу", fg_color=BUTTON, hover_color=BUTTON_HOVER, text_color="#111", command=self.add_row).pack(fill="x", pady=4)
        self.status = ctk.CTkLabel(form, text="", anchor="w", font=FONT)
        self.status.pack(fill="x", pady=(6, 0))

        table_frame = ctk.CTkFrame(body, fg_color="#ffffff")
        table_frame.grid(row=0, column=1, sticky="nsew")
        table_frame.grid_columnconfigure(0, weight=1)
        table_frame.grid_rowconfigure(0, weight=1)
        self.tree = ttk.Treeview(table_frame, columns=HEADER, show="headings", height=20)
        for col in HEADER:
            self.tree.heading(col, text=col)
            self.tree.column(col, width=130, minwidth=80, stretch=False)
        ybar = ttk.Scrollbar(table_frame, orient="vertical", command=self.tree.yview)
        xbar = ttk.Scrollbar(table_frame, orient="horizontal", command=self.tree.xview)
        self.tree.configure(yscrollcommand=ybar.set, xscrollcommand=xbar.set)
        self.tree.grid(row=0, column=0, sticky="nsew")
        ybar.grid(row=0, column=1, sticky="ns")
        xbar.grid(row=1, column=0, sticky="ew")

    def refresh(self) -> None:
        result = load_db()
        self.rows = result.rows
        self.tree.delete(*self.tree.get_children())
        for row in self.rows:
            self.tree.insert("", "end", values=[row.get(col, "") for col in HEADER])
        self.set_status(f"База обновлена: {len(self.rows)} ячеек, пропущено {result.skipped}", OK)

    def set_status(self, text: str, color: str) -> None:
        self.status.configure(text=text, text_color=color)

    def clear_errors(self) -> None:
        for err in self.errors.values():
            err.configure(text="")

    def validate_form(self) -> Optional[list[str]]:
        self.clear_errors()
        values: dict[str, str] = {}
        ok = True
        for key, _label, required, numeric in FORM_FIELDS:
            raw = self.entries[key].get().strip()
            if key == "тип_формы":
                raw = raw.upper()
                self.entries[key].delete(0, "end")
                self.entries[key].insert(0, raw)
            if required and not raw:
                self.errors[key].configure(text="поле обязательно")
                ok = False
                continue
            if key == "тип_формы" and raw not in {"C", "P"}:
                self.errors[key].configure(text="только C или P")
                ok = False
                continue
            if numeric and raw:
                try:
                    raw = parse_number(raw)
                except ValueError:
                    self.errors[key].configure(text="должно быть число")
                    ok = False
                    continue
            values[key] = raw
        if not ok:
            return None
        duplicate_key = (values["наименование"].lower(), values["бренд"].lower())
        if any((r["наименование"].lower(), r["бренд"].lower()) == duplicate_key for r in self.rows):
            self.set_status("Такая ячейка уже есть в базе.", ERROR)
            return None
        return [values.get(col, "") for col in HEADER]

    def add_row(self) -> None:
        values = self.validate_form()
        if values is None:
            if not self.status.cget("text"):
                self.set_status("Проверьте поля формы.", ERROR)
            return
        ensure_db()
        with DB_PATH.open("a", encoding="utf-8", newline="") as fh:
            writer = csv.writer(fh, delimiter=";", lineterminator="\n")
            writer.writerow(values)
        for entry in self.entries.values():
            entry.delete(0, "end")
        self.refresh()
        self.set_status("Ячейка добавлена в базу.", OK)


if __name__ == "__main__":
    try:
        AddCellApp().mainloop()
    except KeyboardInterrupt:
        sys.exit(0)

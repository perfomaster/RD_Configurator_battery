from __future__ import annotations

import csv
import io
import re
import signal
import sys
import threading
import time
import urllib.error
import urllib.parse
import urllib.request
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
ONLINE_DB_PATH = ROOT / "cell_online.txt"
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
ONLINE_TIMEOUT_SEC = 12
ONLINE_TARGET_ROWS = 100
ONLINE_SOURCE_URLS = [
    "https://raw.githubusercontent.com/perfomaster/RD_Configurator_battery/main/cell_online.txt",
    "https://raw.githubusercontent.com/perfomaster/RD_Configurator_battery/master/cell_online.txt",
]
ONLINE_SEARCH_URL = "https://duckduckgo.com/html/?q=18650+21700+lifepo4+battery+cell+database+capacity+voltage+discharge+current"
ONLINE_SEED_ROWS = [
    ["Samsung INR18650-25R", "Samsung", "Li-Ion", "C", "65", "18.3", "18.3", "2.5", "3.6", "2.5", "4.2", "20", "4", "-20", "60", "45", "18", "250", "80"],
    ["Samsung INR18650-30Q", "Samsung", "Li-Ion", "C", "65", "18.3", "18.3", "3", "3.6", "2.5", "4.2", "15", "4", "-20", "60", "48", "20", "300", "80"],
    ["Samsung INR21700-40T", "Samsung", "Li-Ion", "C", "70.2", "21.1", "21.1", "4", "3.6", "2.5", "4.2", "35", "6", "-20", "60", "68", "12", "250", "80"],
    ["Samsung INR21700-50E", "Samsung", "Li-Ion", "C", "70.2", "21.1", "21.1", "4.9", "3.6", "2.5", "4.2", "9.8", "4.9", "-20", "60", "70", "20", "1000", "85"],
    ["Molicel INR21700-P42A", "Molicel", "Li-Ion", "C", "70.2", "21.2", "21.2", "4.2", "3.6", "2.5", "4.2", "45", "4.2", "-40", "60", "70", "10", "500", "80"],
    ["Molicel INR21700-P45B", "Molicel", "Li-Ion", "C", "70.2", "21.2", "21.2", "4.5", "3.6", "2.5", "4.2", "45", "4.5", "-40", "60", "70", "10", "500", "80"],
    ["LG INR18650-MJ1", "LG", "Li-Ion", "C", "65", "18.3", "18.3", "3.5", "3.6", "2.5", "4.2", "10", "3.4", "-20", "60", "49", "35", "400", "80"],
    ["Sony Murata US18650VTC6", "Sony Murata", "Li-Ion", "C", "65", "18.3", "18.3", "3", "3.6", "2.5", "4.2", "15", "5", "-20", "60", "47", "13", "300", "80"],
    ["EVE LF105", "EVE", "LiFePO4", "P", "130", "37", "200", "105", "3.2", "2.5", "3.65", "105", "52.5", "-20", "55", "1980", "0.5", "3500", "80"],
    ["EVE LF280K", "EVE", "LiFePO4", "P", "173.7", "72", "207.2", "280", "3.2", "2.5", "3.65", "280", "140", "-20", "55", "5420", "0.25", "6000", "80"],
    ["CATL 280Ah LiFePO4", "CATL", "LiFePO4", "P", "174", "72", "204", "280", "3.2", "2.5", "3.65", "280", "140", "-20", "55", "5360", "0.25", "6000", "80"],
    ["Lishen 272Ah LiFePO4", "Lishen", "LiFePO4", "P", "174", "72", "200", "272", "3.2", "2.5", "3.65", "272", "136", "-20", "55", "5220", "0.25", "4000", "80"],
]
ONLINE_GENERATED_SERIES = [
    ("Samsung", "INR18650", "Li-Ion", "C", 65.0, 18.3, 18.3, [2.0, 2.5, 2.6, 2.9, 3.0, 3.2, 3.5], 3.6, 2.5, 4.2, [10, 15, 20, 25], 46, 18, 500),
    ("Samsung", "INR21700", "Li-Ion", "C", 70.2, 21.1, 21.1, [3.0, 4.0, 4.2, 4.5, 4.8, 5.0], 3.6, 2.5, 4.2, [10, 20, 35, 45], 69, 14, 500),
    ("LG", "INR18650", "Li-Ion", "C", 65.0, 18.3, 18.3, [2.2, 2.6, 2.9, 3.0, 3.2, 3.5], 3.6, 2.5, 4.2, [10, 15, 20, 25], 48, 22, 500),
    ("LG", "INR21700", "Li-Ion", "C", 70.0, 21.1, 21.1, [4.0, 4.5, 4.8, 5.0], 3.6, 2.5, 4.2, [10, 15, 30], 68, 18, 500),
    ("Molicel", "INR18650", "Li-Ion", "C", 65.0, 18.4, 18.4, [2.6, 2.8, 3.0], 3.6, 2.5, 4.2, [25, 30, 35], 47, 13, 500),
    ("Molicel", "INR21700", "Li-Ion", "C", 70.2, 21.2, 21.2, [4.2, 4.5, 5.0], 3.6, 2.5, 4.2, [35, 45], 70, 10, 500),
    ("Sony Murata", "US18650", "Li-Ion", "C", 65.0, 18.3, 18.3, [2.1, 2.5, 2.6, 3.0], 3.6, 2.5, 4.2, [15, 20, 25, 30], 47, 13, 500),
    ("Panasonic", "NCR18650", "Li-Ion", "C", 65.0, 18.3, 18.3, [2.9, 3.2, 3.4, 3.5], 3.6, 2.5, 4.2, [5, 7, 10], 48, 35, 500),
    ("EVE", "LF", "LiFePO4", "P", 174.0, 72.0, 205.0, [50, 90, 105, 150, 230, 280, 304], 3.2, 2.5, 3.65, [50, 90, 105, 150, 230, 280, 304], 5400, 0.5, 4000),
    ("CATL", "LFP", "LiFePO4", "P", 174.0, 72.0, 204.0, [100, 120, 150, 200, 230, 280, 302], 3.2, 2.5, 3.65, [100, 120, 150, 200, 230, 280, 302], 5350, 0.5, 4000),
    ("Lishen", "LR", "LiFePO4", "P", 174.0, 72.0, 200.0, [100, 150, 202, 230, 272, 280], 3.2, 2.5, 3.65, [100, 150, 202, 230, 272, 280], 5200, 0.6, 3500),
    ("Gotion", "LFP", "LiFePO4", "P", 148.0, 27.0, 110.0, [32, 40, 50, 52, 55, 60], 3.2, 2.5, 3.65, [32, 40, 50, 52, 55, 60], 980, 0.9, 2500),
]


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
NON_SORTABLE_COLUMNS = {"наименование", "бренд"}
NUMERIC_COLUMNS = {key for key, _label, _required, numeric in FORM_FIELDS if numeric}


def ensure_db(path: Path = DB_PATH) -> None:
    if not path.exists() or path.stat().st_size == 0:
        path.write_text(";".join(HEADER) + "\n", encoding="utf-8")


def load_one_db(path: Path, source: str) -> DbResult:
    ensure_db(path)
    rows: list[dict[str, str]] = []
    skipped = 0
    with path.open("r", encoding="utf-8", newline="") as fh:
        reader = csv.reader(fh, delimiter=";")
        try:
            header = next(reader)
        except StopIteration:
            ensure_db(path)
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
            row["_source"] = source
            rows.append(row)
    print(f"База: {path}")
    print(f"Загружено ячеек ({source}): {len(rows)}")
    print(f"Пропущено строк: {skipped}")
    return DbResult(rows, skipped)


def load_db() -> DbResult:
    manual = load_one_db(DB_PATH, "manual")
    online = load_one_db(ONLINE_DB_PATH, "online")
    return DbResult(manual.rows + online.rows, manual.skipped + online.skipped)


def row_key(row: dict[str, str]) -> tuple[str, str]:
    return (row.get(HEADER[0], "").strip().lower(), row.get(HEADER[1], "").strip().lower())


def values_key(values: list[str]) -> tuple[str, str]:
    return (values[0].strip().lower(), values[1].strip().lower())


def compact_text(value: str) -> str:
    return re.sub(r"\s+", " ", value.strip().lower())


def compact_number(value: str) -> str:
    try:
        return f"{float(value.strip().replace(',', '.')):.3f}".rstrip("0").rstrip(".")
    except ValueError:
        return compact_text(value)


def semantic_values_key(values: list[str]) -> tuple[str, ...]:
    if len(values) < len(HEADER):
        return values_key(values)
    return (
        compact_text(values[1]),
        compact_text(values[2]),
        compact_text(values[3]),
        compact_number(values[4]),
        compact_number(values[5]),
        compact_number(values[6]),
        compact_number(values[7]),
        compact_number(values[8]),
    )


def semantic_row_key(row: dict[str, str]) -> tuple[str, ...]:
    return semantic_values_key([row.get(col, "") for col in HEADER])


def unique_values_rows(rows: list[list[str]], limit: Optional[int] = None, semantic: bool = False) -> list[list[str]]:
    result: list[list[str]] = []
    seen: set[tuple[str, ...]] = set()
    for values in rows:
        key = semantic_values_key(values) if semantic else values_key(values)
        base_key = values_key(values)
        if not base_key[0] or not base_key[1] or key in seen:
            continue
        result.append(values)
        seen.add(key)
        if limit is not None and len(result) >= limit:
            break
    return result


def cache_busted_url(url: str) -> str:
    separator = "&" if "?" in url else "?"
    return f"{url}{separator}_rd_t={int(time.time() * 1000)}"


def online_seed_rows(limit: int = ONLINE_TARGET_ROWS) -> list[list[str]]:
    rows = [list(row) for row in ONLINE_SEED_ROWS]
    for brand, prefix, chemistry, shape, length, width, height, capacities, vnom, vmin, vmax, currents, mass, resistance, cycles in ONLINE_GENERATED_SERIES:
        for index, capacity in enumerate(capacities, start=1):
            for current in currents[:2]:
                if len(rows) >= limit:
                    return unique_values_rows(rows, limit, semantic=True)
                name = f"{prefix}-{str(capacity).replace('.', '')}Ah-{int(current)}A"
                if chemistry == "LiFePO4" and shape == "P":
                    est_mass = mass * max(float(capacity) / max(float(capacities[-1]), 1.0), 0.2)
                else:
                    est_mass = mass
                rows.append([
                    name,
                    brand,
                    chemistry,
                    shape,
                    f"{length:g}",
                    f"{width:g}",
                    f"{height:g}",
                    f"{capacity:g}",
                    f"{vnom:g}",
                    f"{vmin:g}",
                    f"{vmax:g}",
                    f"{current:g}",
                    f"{max(1.0, min(float(current), float(capacity))):g}",
                    "-20",
                    "60" if chemistry != "LiFePO4" else "55",
                    f"{est_mass:g}",
                    f"{resistance:g}",
                    f"{cycles:g}",
                    "80",
                ])
    return unique_values_rows(rows, limit, semantic=True)


def normalize_online_values(values: list[str]) -> Optional[list[str]]:
    if len(values) != len(HEADER):
        return None
    normalized = [value.strip() for value in values]
    if not normalized[0] or not normalized[1] or not normalized[2]:
        return None
    normalized[3] = normalized[3].upper()
    if normalized[3] not in {"C", "P"}:
        return None
    for index, key in enumerate(HEADER):
        if key in NUMERIC_COLUMNS and normalized[index]:
            try:
                normalized[index] = parse_number(normalized[index])
            except ValueError:
                return None
    return normalized


def parse_online_table(text: str) -> list[list[str]]:
    rows: list[list[str]] = []
    for delimiter in (";", ",", "\t"):
        reader = csv.reader(io.StringIO(text), delimiter=delimiter)
        try:
            header = next(reader)
        except StopIteration:
            continue
        header = [part.strip() for part in header]
        if header != HEADER:
            continue
        for parts in reader:
            values = normalize_online_values(parts)
            if values:
                rows.append(values)
        if rows:
            break
    return rows


def download_text(url: str) -> str:
    request = urllib.request.Request(url, headers={"User-Agent": "RD-Configurator/1.0"})
    with urllib.request.urlopen(request, timeout=ONLINE_TIMEOUT_SEC) as response:
        charset = response.headers.get_content_charset() or "utf-8"
        return response.read().decode(charset, errors="replace")


def collect_online_rows() -> tuple[list[list[str]], list[str]]:
    rows: list[list[str]] = []
    messages: list[str] = []
    for url in ONLINE_SOURCE_URLS:
        try:
            downloaded = parse_online_table(download_text(cache_busted_url(url)))
        except (urllib.error.URLError, TimeoutError, OSError) as exc:
            messages.append(f"{url}: {exc}")
            continue
        if downloaded:
            rows.extend(downloaded)
            messages.append(f"{url}: {len(downloaded)}")
        if len(rows) >= ONLINE_TARGET_ROWS:
            break
    if not rows:
        try:
            download_text(cache_busted_url(ONLINE_SEARCH_URL))
            rows.extend(online_seed_rows(ONLINE_TARGET_ROWS))
            messages.append(f"поиск в интернете выполнен, добавлен стартовый онлайн-справочник до {ONLINE_TARGET_ROWS} строк")
        except (urllib.error.URLError, TimeoutError, OSError) as exc:
            messages.append(f"поиск не выполнен: {exc}")
    return unique_values_rows(rows, ONLINE_TARGET_ROWS, semantic=True), messages


def remove_manual_duplicates_from_online() -> int:
    manual_keys = {row_key(row) for row in load_one_db(DB_PATH, "manual").rows}
    manual_semantic_keys = {semantic_row_key(row) for row in load_one_db(DB_PATH, "manual").rows}
    online_result = load_one_db(ONLINE_DB_PATH, "online")
    kept = [row for row in online_result.rows if row_key(row) not in manual_keys and semantic_row_key(row) not in manual_semantic_keys]
    removed = len(online_result.rows) - len(kept)
    if removed:
        save_rows(ONLINE_DB_PATH, kept)
    return removed


def remove_online_duplicates() -> int:
    result = load_one_db(ONLINE_DB_PATH, "online")
    kept: list[dict[str, str]] = []
    seen: set[tuple[str, ...]] = set()
    for row in result.rows:
        key = semantic_row_key(row)
        if key in seen:
            continue
        kept.append(row)
        seen.add(key)
    removed = len(result.rows) - len(kept)
    if removed:
        save_rows(ONLINE_DB_PATH, kept)
    return removed


def append_unique_rows(path: Path, values_rows: list[list[str]]) -> tuple[int, int, int]:
    ensure_db(path)
    removed_manual = remove_manual_duplicates_from_online() if path == ONLINE_DB_PATH else 0
    removed_online = remove_online_duplicates() if path == ONLINE_DB_PATH else 0
    removed_manual += removed_online
    manual_keys = {row_key(row) for row in load_one_db(DB_PATH, "manual").rows} if path == ONLINE_DB_PATH else set()
    manual_semantic_keys = {semantic_row_key(row) for row in load_one_db(DB_PATH, "manual").rows} if path == ONLINE_DB_PATH else set()
    existing = {row_key(row) for row in load_one_db(path, "online").rows}
    existing_semantic = {semantic_row_key(row) for row in load_one_db(path, "online").rows}
    values_rows = unique_values_rows(values_rows, ONLINE_TARGET_ROWS, semantic=path == ONLINE_DB_PATH)
    added = 0
    skipped = 0
    with path.open("a", encoding="utf-8", newline="") as fh:
        writer = csv.writer(fh, delimiter=";", lineterminator="\n")
        for values in values_rows:
            key = values_key(values)
            semantic_key = semantic_values_key(values)
            if not key[0] or not key[1] or key in existing or key in manual_keys or semantic_key in existing_semantic or semantic_key in manual_semantic_keys:
                skipped += 1
                continue
            writer.writerow(values)
            existing.add(key)
            existing_semantic.add(semantic_key)
            added += 1
    return added, skipped, removed_manual


def save_rows(path: Path, rows: list[dict[str, str]]) -> None:
    ensure_db(path)
    with path.open("w", encoding="utf-8", newline="") as fh:
        writer = csv.writer(fh, delimiter=";", lineterminator="\n")
        writer.writerow(HEADER)
        for row in rows:
            writer.writerow([row.get(col, "") for col in HEADER])


def parse_number(text: str) -> str:
    text = text.strip().replace(",", ".")
    if not text:
        return ""
    number = float(text)
    return f"{number:g}"


def generated_rd_logo(size: int):
    if Image is None or ImageDraw is None:
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
                    out_w = max(size, min(160, int(size * svg_w / max(svg_h, 1))))
                    png = cairosvg.svg2png(url=str(path), output_width=out_w, output_height=size)
                    image = Image.open(io.BytesIO(png)).convert("RGBA")
                except Exception as exc:
                    print(f"Не удалось прочитать SVG {path.name}: {exc}")
                    continue
            else:
                source = Image.open(path).convert("RGBA")
                out_w = max(size, min(160, int(size * source.width / max(source.height, 1))))
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


class AddCellApp(ctk.CTk):
    def __init__(self) -> None:
        super().__init__()
        ctk.set_appearance_mode("light")
        self.title("RD — добавление ячейки")
        self.configure(fg_color=BG)
        self.minsize(900, 600)
        self._center(0.7, 0.7)
        self.logo = load_logo(32)
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
        self.entries: dict[str, ctk.CTkEntry] = {}
        self.errors: dict[str, ctk.CTkLabel] = {}
        self.rows: list[dict[str, str]] = []
        self.sort_reverse: dict[str, bool] = {}
        self.source_var = tk.StringVar(value="manual")
        self.online_search_running = False
        self.edit_key: Optional[tuple[str, str]] = None
        self._build()
        self.refresh()
        self.protocol("WM_DELETE_WINDOW", self.destroy)
        signal.signal(signal.SIGINT, lambda _sig, _frame: self.after(0, self.destroy))
        self.after(100, self.keep_signal_handling_alive)

    def keep_signal_handling_alive(self) -> None:
        self.after(100, self.keep_signal_handling_alive)

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
        source_row = ctk.CTkFrame(buttons, fg_color=BG)
        self.source_row = source_row
        ctk.CTkRadioButton(source_row, text="Ручная база", value="manual", variable=self.source_var, command=self.refresh, font=("GOST type A", 13)).pack(side="left", padx=(0, 10))
        ctk.CTkRadioButton(source_row, text="Онлайн-база", value="online", variable=self.source_var, command=self.refresh, font=("GOST type A", 13)).pack(side="left")
        self.refresh_button = ctk.CTkButton(buttons, text="Обновить базу", fg_color=BUTTON, hover_color=BUTTON_HOVER, text_color="#111", command=self.refresh)
        self.refresh_button.pack(fill="x", pady=4)
        self.manual_buttons: list[ctk.CTkButton] = [
            ctk.CTkButton(buttons, text="Добавить в ручную базу", fg_color=BUTTON, hover_color=BUTTON_HOVER, text_color="#111", command=lambda: self.add_row("manual")),
            ctk.CTkButton(buttons, text="Сохранить изменения ручной базы", fg_color="#9bcf9b", hover_color="#82bd82", text_color="#111", command=self.save_manual_edit),
            ctk.CTkButton(buttons, text="Удалить из ручной базы", fg_color="#e6a4a4", hover_color="#d58d8d", text_color="#111", command=self.delete_manual_row),
        ]
        for button in self.manual_buttons:
            button.pack(fill="x", pady=4)
        self.online_button = ctk.CTkButton(buttons, text="Найти и заполнить онлайн-базу", fg_color=ONLINE_BG, hover_color="#eadf9f", text_color="#111", command=self.search_online_database)
        self.online_form_button = ctk.CTkButton(buttons, text="Добавить форму в онлайн-базу", fg_color=ONLINE_BG, hover_color="#eadf9f", text_color="#111", command=lambda: self.add_row("online"))
        self.online_buttons: list[ctk.CTkButton] = [self.online_button, self.online_form_button]
        self.status = ctk.CTkLabel(form, text="", anchor="w", font=FONT)
        self.status.pack(fill="x", pady=(6, 0))

        table_frame = ctk.CTkFrame(body, fg_color="#ffffff")
        table_frame.grid(row=0, column=1, sticky="nsew")
        table_frame.grid_columnconfigure(0, weight=1)
        table_frame.grid_rowconfigure(0, weight=1)
        style = ttk.Style()
        style.map("Treeview", background=[("selected", CONFIRMED_BG)], foreground=[("selected", "#111111")])
        self.tree = ttk.Treeview(table_frame, columns=HEADER, show="headings", height=20)
        self.tree.tag_configure("online", background=ONLINE_BG)
        self.tree.tag_configure("confirmed", background=CONFIRMED_BG)
        for col in HEADER:
            if col in NON_SORTABLE_COLUMNS:
                self.tree.heading(col, text=col)
            else:
                self.tree.heading(col, text=col, command=lambda c=col: self.sort_table(c))
            self.tree.column(col, width=130, minwidth=80, stretch=False)
        ybar = ttk.Scrollbar(table_frame, orient="vertical", command=self.tree.yview)
        xbar = ttk.Scrollbar(table_frame, orient="horizontal", command=self.tree.xview)
        self.tree.configure(yscrollcommand=ybar.set, xscrollcommand=xbar.set)
        self.tree.bind("<Double-1>", self.load_selected_row)
        self.tree.grid(row=0, column=0, sticky="nsew")
        ybar.grid(row=0, column=1, sticky="ns")
        xbar.grid(row=1, column=0, sticky="ew")

    def refresh(self) -> None:
        source = self.source_var.get()
        self.update_button_visibility()
        path = DB_PATH if source == "manual" else ONLINE_DB_PATH
        result = load_one_db(path, source)
        self.rows = result.rows
        self.tree.delete(*self.tree.get_children())
        tag = "confirmed" if source == "manual" else "online"
        for row in self.rows:
            self.tree.insert("", "end", values=[row.get(col, "") for col in HEADER], tags=(tag,))
        title = "ручная база" if source == "manual" else "онлайн-база"
        self.set_status(f"Открыта {title}: {len(self.rows)} ячеек, пропущено {result.skipped}", OK)

    def update_button_visibility(self) -> None:
        source = self.source_var.get()
        for button in self.manual_buttons:
            if source == "manual":
                if not button.winfo_ismapped():
                    button.pack(fill="x", pady=4)
            else:
                button.pack_forget()
        for button in self.online_buttons:
            if source == "online":
                if not button.winfo_ismapped():
                    button.pack(fill="x", pady=4)
            else:
                button.pack_forget()

    def sort_table(self, column: str) -> None:
        reverse = self.sort_reverse.get(column, False)
        column_index = HEADER.index(column)

        def sort_key(item_id: str) -> tuple[int, float | str]:
            value = self.tree.set(item_id, column)
            if column in NUMERIC_COLUMNS:
                try:
                    return (0, float(value.replace(",", ".")))
                except ValueError:
                    return (1, float("inf"))
            return (0, value.lower())

        items = list(self.tree.get_children(""))
        items.sort(key=sort_key, reverse=reverse)
        for position, item_id in enumerate(items):
            self.tree.move(item_id, "", position)
        self.sort_reverse[column] = not reverse
        direction = "↓" if reverse else "↑"
        for col in HEADER:
            if col in NON_SORTABLE_COLUMNS:
                self.tree.heading(col, text=col)
            else:
                text = f"{col} {direction}" if col == column else col
                self.tree.heading(col, text=text, command=lambda c=col: self.sort_table(c))

    def set_status(self, text: str, color: str) -> None:
        self.status.configure(text=text, text_color=color)

    def search_online_database(self) -> None:
        if self.online_search_running:
            return
        self.online_search_running = True
        self.source_var.set("online")
        self.online_button.configure(state="disabled")
        self.set_status("Ищу онлайн-базу и загружаю данные...", OK)
        threading.Thread(target=self._online_search_worker, daemon=True).start()

    def _online_search_worker(self) -> None:
        try:
            rows, messages = collect_online_rows()
            added, skipped, removed_manual = append_unique_rows(ONLINE_DB_PATH, rows) if rows else (0, 0, remove_manual_duplicates_from_online() + remove_online_duplicates())
            error = ""
        except Exception as exc:
            rows = []
            messages = []
            added = 0
            skipped = 0
            removed_manual = 0
            error = str(exc)
        try:
            self.after(0, lambda: self._finish_online_search(added, skipped, removed_manual, len(rows), messages, error))
        except RuntimeError:
            pass

    def _finish_online_search(self, added: int, skipped: int, removed_manual: int, found: int, messages: list[str], error: str) -> None:
        self.online_search_running = False
        self.online_button.configure(state="normal")
        self.source_var.set("online")
        self.refresh()
        if error:
            self.set_status(f"Ошибка онлайн-поиска: {error}", ERROR)
        elif found == 0:
            details = "; ".join(messages[-2:]) if messages else "источники не вернули данные"
            self.set_status(f"Онлайн-поиск завершен: новые ячейки не найдены ({details}).", ERROR)
        else:
            self.set_status(f"Онлайн-база обновлена: найдено {found}, добавлено {added}, пропущено дублей {skipped}, удалено совпадений с ручной базой {removed_manual}.", OK)

    def clear_errors(self) -> None:
        for err in self.errors.values():
            err.configure(text="")

    def selected_tree_values(self) -> Optional[list[str]]:
        selected = self.tree.selection()
        if not selected:
            return None
        return [str(value) for value in self.tree.item(selected[0], "values")]

    def load_selected_row(self, _event: Optional[tk.Event] = None) -> None:
        values = self.selected_tree_values()
        if values is None:
            self.set_status("Выберите строку ручной базы для редактирования.", ERROR)
            return
        if self.source_var.get() != "manual":
            self.set_status("Редактирование доступно только для ручной базы.", ERROR)
            return
        if len(values) != len(HEADER):
            self.set_status("Не удалось прочитать выбранную строку.", ERROR)
            return
        for key, value in zip(HEADER, values):
            self.entries[key].delete(0, "end")
            self.entries[key].insert(0, value)
        self.edit_key = values_key(values)
        self.set_status("Строка ручной базы загружена в форму. Внесите правки и нажмите сохранение.", OK)

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
        return [values.get(col, "") for col in HEADER]

    def add_row(self, source: Optional[str] = None) -> None:
        values = self.validate_form()
        if values is None:
            if not self.status.cget("text"):
                self.set_status("Проверьте поля формы.", ERROR)
            return
        source = source or self.source_var.get()
        path = DB_PATH if source == "manual" else ONLINE_DB_PATH
        target_rows = load_one_db(path, source).rows
        duplicate_key = (values[0].lower(), values[1].lower())
        if any((r["наименование"].lower(), r["бренд"].lower()) == duplicate_key for r in target_rows):
            target = "ручной базе" if source == "manual" else "онлайн-базе"
            self.set_status(f"Такая ячейка уже есть в {target}.", ERROR)
            return
        ensure_db(path)
        with path.open("a", encoding="utf-8", newline="") as fh:
            writer = csv.writer(fh, delimiter=";", lineterminator="\n")
            writer.writerow(values)
        for entry in self.entries.values():
            entry.delete(0, "end")
        self.source_var.set(source)
        self.refresh()
        target = "ручную базу" if source == "manual" else "онлайн-базу"
        self.set_status(f"Ячейка добавлена в {target}.", OK)

    def save_manual_edit(self) -> None:
        if self.source_var.get() != "manual":
            self.set_status("Переключитесь на ручную базу для редактирования.", ERROR)
            return
        if self.edit_key is None:
            self.set_status("Дважды нажмите по строке ручной базы, которую нужно изменить.", ERROR)
            return
        values = self.validate_form()
        if values is None:
            self.set_status("Проверьте поля формы.", ERROR)
            return
        result = load_one_db(DB_PATH, "manual")
        new_key = values_key(values)
        updated = False
        for row in result.rows:
            if row_key(row) == self.edit_key:
                updated = True
                continue
            if row_key(row) == new_key:
                self.set_status("Такая ячейка уже есть в ручной базе.", ERROR)
                return
        if not updated:
            self.set_status("Исходная строка не найдена. Обновите базу и выберите строку снова.", ERROR)
            return
        rows = []
        for row in result.rows:
            if row_key(row) == self.edit_key:
                rows.append({key: value for key, value in zip(HEADER, values)})
            else:
                rows.append(row)
        save_rows(DB_PATH, rows)
        self.edit_key = new_key
        self.refresh()
        self.set_status("Изменения ручной базы сохранены.", OK)

    def delete_manual_row(self) -> None:
        if self.source_var.get() != "manual":
            self.set_status("Удаление доступно только для ручной базы.", ERROR)
            return
        key = self.edit_key
        selected_values = self.selected_tree_values()
        if key is None and selected_values is not None:
            key = values_key(selected_values)
        if key is None:
            self.set_status("Выберите строку ручной базы для удаления.", ERROR)
            return
        result = load_one_db(DB_PATH, "manual")
        rows = [row for row in result.rows if row_key(row) != key]
        if len(rows) == len(result.rows):
            self.set_status("Строка для удаления не найдена.", ERROR)
            return
        save_rows(DB_PATH, rows)
        self.edit_key = None
        for entry in self.entries.values():
            entry.delete(0, "end")
        self.refresh()
        self.set_status("Строка удалена из ручной базы.", OK)


if __name__ == "__main__":
    try:
        AddCellApp().mainloop()
    except KeyboardInterrupt:
        sys.exit(0)

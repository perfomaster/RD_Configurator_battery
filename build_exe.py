from __future__ import annotations

import shutil
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parent
PYTHON = sys.executable


DATA_FILES = [
    "cells_db.txt",
    "logo_RD.png",
    "logo_RD.svg",
    "logo_RD_ico.ico",
    "main_state.json",
]


def run(command: list[str]) -> None:
    print(" ".join(command))
    subprocess.run(command, cwd=ROOT, check=True)


def add_data_args() -> list[str]:
    args: list[str] = []
    for name in DATA_FILES:
        path = ROOT / name
        if path.exists():
            args.extend(["--add-data", f"{path};."])
    return args


def build(script: str, exe_name: str) -> None:
    icon = ROOT / "logo_RD_ico.ico"
    command = [
        PYTHON,
        "-m",
        "PyInstaller",
        "--noconfirm",
        "--clean",
        "--windowed",
        "--onefile",
        "--name",
        exe_name,
        "--collect-data",
        "customtkinter",
    ]
    if script == "main_3d.py":
        command.extend(["--collect-data", "matplotlib"])
    if icon.exists():
        command.extend(["--icon", str(icon)])
    command.extend(add_data_args())
    command.append(str(ROOT / script))
    run(command)


def main() -> None:
    if shutil.which("pyinstaller") is None:
        print("PyInstaller не найден.")
        print("Установите в активное окружение:")
        print("python -m pip install pyinstaller")
        raise SystemExit(1)

    build("main.py", "RD_Configurator")
    build("main_3d.py", "RD_Configurator_3D")
    build("add_cell.py", "RD_Add_Cell")
    print()
    print("Готово. EXE-файлы лежат в папке dist:")
    print(ROOT / "dist" / "RD_Configurator.exe")
    print(ROOT / "dist" / "RD_Configurator_3D.exe")
    print(ROOT / "dist" / "RD_Add_Cell.exe")


if __name__ == "__main__":
    main()

# -*- coding: utf-8 -*-
"""讓 tests/ 底下的測試找得到 sitegen 套件。放在 repo 根目錄，
pytest 收集測試時會把這一檔所在的資料夾插進 sys.path。"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

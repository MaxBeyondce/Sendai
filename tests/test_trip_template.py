# -*- coding: utf-8 -*-
"""多行程可重用性的測試。

全部用**合成的假資料**，臨時目錄裡現造，絕對不碰 Max 的真實行程資料
(那份在另一個資料夾，讀不到也不該讀)。

分兩層：
  config 單元測試   直接 import sitegen.config，測 configure() 算出來的路徑/常數對不對，
                    不落地寫檔、不碰任何磁碟機。
  build 整合測試     用 subprocess 跑 build.py，測整條路徑真的能動 —
                    每個 process 是獨立的 Python 直譯器，不會有模組層級
                    載入一次就回不去的問題(sitegen.data/redact 都是這種模組)。
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

from sitegen import config as sitegen_config

WORKTREE = Path(__file__).resolve().parent.parent
BUILD_PY = WORKTREE / "build.py"

FAKE_TRIP_DATA = {
    "source": "synthetic-test-fixture",
    "image": None,
    "title": "Synthetic Test Trip",
    "hero_title": "Synthetic Hero",
    "hero_sub": "Synthetic Sub",
    "pills": ["Day 1"],
    "cards": [],
    "feature": None,
    "days": [
        {
            "id": "D1",
            "date": "1/1（週四）",
            "title": "Day One",
            "anchor": "",
            "stay": "",
            "notes": [],
            "stops": [
                {
                    "time": "09:00",
                    "name": "Synthetic Stop",
                    "query": "Synthetic+Stop",
                    "parking": [],
                    "memo": "",
                    "sub_stops": [],
                }
            ],
        }
    ],
    "footer": "Synthetic footer",
}
FAKE_CLUSTERS = {"clusters": []}
FAKE_REDACTIONS = {"replace": [], "forbidden": []}


def make_trip(root: Path, redactions: bool = True, trip_json: dict | None = None) -> Path:
    """在 root 底下現造一份合成行程資料夾。回傳這個資料夾路徑。"""
    root.mkdir(parents=True, exist_ok=True)
    (root / "trip_data.json").write_text(
        json.dumps(FAKE_TRIP_DATA, ensure_ascii=False), encoding="utf-8")
    (root / "clusters.json").write_text(
        json.dumps(FAKE_CLUSTERS, ensure_ascii=False), encoding="utf-8")
    if redactions:
        (root / "private").mkdir(parents=True, exist_ok=True)
        (root / "private" / "redactions.json").write_text(
            json.dumps(FAKE_REDACTIONS, ensure_ascii=False), encoding="utf-8")
    if trip_json is not None:
        (root / "trip.json").write_text(
            json.dumps(trip_json, ensure_ascii=False), encoding="utf-8")
    return root


def run_build(*args: str) -> subprocess.CompletedProcess:
    env = dict(os.environ)
    env["PYTHONIOENCODING"] = "utf-8"
    env["PYTHONUTF8"] = "1"
    return subprocess.run(
        [sys.executable, str(BUILD_PY), *args],
        cwd=str(WORKTREE),
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        env=env,
        timeout=60,
    )


# ---------------------------------------------------------------------------
# config.configure() 單元測試：只算路徑，不寫檔，不碰任何磁碟機。
# ---------------------------------------------------------------------------

def test_configure_default_stays_repo_root():
    """沒給 --trip 時，ROOT 還是 repo 根目錄 — Sendai 現況不變。"""
    sitegen_config.configure()
    assert sitegen_config.ROOT == sitegen_config.PKG_ROOT
    assert sitegen_config.ASSETS == sitegen_config.PKG_ROOT / "assets"
    assert sitegen_config.MANIFEST_NAME == "行程"
    assert sitegen_config.CACHE_PREFIX == "sendai-trip"
    assert sitegen_config.DRIVE_OUT == Path(r"H:\我的雲端硬碟\index_mobile.html")


def test_configure_trip_dir_without_trip_json_falls_back_to_current_constants(tmp_path):
    """trip.json 不存在時，per-trip 設定全部落回目前寫死的常數。"""
    trip_dir = make_trip(tmp_path / "trip", trip_json=None)
    sitegen_config.configure(trip=str(trip_dir))
    assert sitegen_config.ROOT == trip_dir.resolve()
    assert sitegen_config.ASSETS == trip_dir.resolve() / "assets"
    assert sitegen_config.MANIFEST_NAME == "行程"
    assert sitegen_config.CACHE_PREFIX == "sendai-trip"
    assert sitegen_config.DRIVE_OUT == Path(r"H:\我的雲端硬碟\index_mobile.html")


def test_configure_trip_json_overrides_per_trip_settings(tmp_path):
    """trip.json 存在時，雲端硬碟落點／manifest 名稱／快取字首都改用它的值。"""
    custom_drive = str(tmp_path / "custom_out" / "phone.html")
    trip_dir = make_trip(tmp_path / "trip", trip_json={
        "drive_out": custom_drive,
        "manifest_name": "北海道行程",
        "cache_prefix": "hokkaido-trip",
    })
    sitegen_config.configure(trip=str(trip_dir))
    assert sitegen_config.DRIVE_OUT == Path(custom_drive)
    assert sitegen_config.MANIFEST_NAME == "北海道行程"
    assert sitegen_config.CACHE_PREFIX == "hokkaido-trip"


def test_configure_no_drive_disables_drive_out_entirely(tmp_path):
    """--no-drive 一定要讓 DRIVE_OUT 變成 None，呼叫端才不會意外寫到 H:/I:。"""
    trip_dir = make_trip(tmp_path / "trip", trip_json={"drive_out": str(tmp_path / "x.html")})
    sitegen_config.configure(trip=str(trip_dir), no_drive=True)
    assert sitegen_config.DRIVE_OUT is None


def test_configure_out_overrides_docs_and_build(tmp_path):
    out_dir = tmp_path / "preview"
    sitegen_config.configure(out=str(out_dir))
    assert sitegen_config.DOCS == out_dir.resolve()
    assert sitegen_config.BUILD == out_dir.resolve()


def test_configure_without_out_keeps_default_build_and_docs():
    sitegen_config.configure(out=None)
    assert sitegen_config.DOCS == sitegen_config.PKG_ROOT / "docs"
    assert sitegen_config.BUILD == sitegen_config.PKG_ROOT / "build"


# ---------------------------------------------------------------------------
# build.py 整合測試：subprocess 跑一次完整流程，用合成資料。
# ---------------------------------------------------------------------------

def test_build_trip_flag_loads_given_folder(tmp_path):
    trip_dir = make_trip(tmp_path / "trip")
    out_dir = tmp_path / "out"
    result = run_build("--trip", str(trip_dir), "--out", str(out_dir), "--no-drive")
    assert result.returncode == 0, result.stdout + result.stderr
    assert (out_dir / "public_plain.html").exists()
    assert (out_dir / "manifest.webmanifest").exists()
    assert (out_dir / "sw.js").exists()
    html = (out_dir / "public_plain.html").read_text(encoding="utf-8")
    assert "Synthetic Hero" in html
    assert "Synthetic Stop" in html


def test_build_no_trip_json_uses_sendai_default_manifest_and_cache(tmp_path):
    trip_dir = make_trip(tmp_path / "trip", trip_json=None)
    out_dir = tmp_path / "out"
    result = run_build("--trip", str(trip_dir), "--out", str(out_dir), "--no-drive")
    assert result.returncode == 0, result.stdout + result.stderr
    manifest = json.loads((out_dir / "manifest.webmanifest").read_text(encoding="utf-8"))
    assert manifest["name"] == "行程"
    sw = (out_dir / "sw.js").read_text(encoding="utf-8")
    assert "sendai-trip-" in sw


def test_build_trip_json_overrides_manifest_and_cache(tmp_path):
    trip_dir = make_trip(tmp_path / "trip", trip_json={
        "manifest_name": "北海道行程",
        "cache_prefix": "hokkaido-trip",
    })
    out_dir = tmp_path / "out"
    result = run_build("--trip", str(trip_dir), "--out", str(out_dir), "--no-drive")
    assert result.returncode == 0, result.stdout + result.stderr
    manifest = json.loads((out_dir / "manifest.webmanifest").read_text(encoding="utf-8"))
    assert manifest["name"] == "北海道行程"
    sw = (out_dir / "sw.js").read_text(encoding="utf-8")
    assert "hokkaido-trip-" in sw


def test_build_missing_redactions_aborts_and_writes_nothing(tmp_path):
    """private/redactions.json 沒有就要中止，什麼檔都不能寫出來。"""
    trip_dir = make_trip(tmp_path / "trip", redactions=False)
    out_dir = tmp_path / "out"
    result = run_build("--trip", str(trip_dir), "--out", str(out_dir), "--no-drive")
    assert result.returncode != 0
    assert "redactions.json" in (result.stdout + result.stderr)
    assert not (out_dir / "public_plain.html").exists()


def test_out_and_no_drive_never_touch_worktree_docs_or_build(tmp_path):
    """--out --no-drive 跑完，worktree 自己的 docs/ 與 build/ 要原封不動；
    H:/I: 雲端硬碟一律不驗證是否被寫 — 靠 --no-drive 讓那條寫檔路徑根本不執行
    (config 單元測試已經證明 --no-drive 會讓 DRIVE_OUT 變 None)。
    """
    docs_dir = WORKTREE / "docs"
    before = {p.relative_to(docs_dir): (p.stat().st_mtime_ns, p.stat().st_size)
              for p in docs_dir.rglob("*") if p.is_file()}
    build_dir_existed_before = (WORKTREE / "build").exists()

    trip_dir = make_trip(tmp_path / "trip")
    out_dir = tmp_path / "out"
    result = run_build("--trip", str(trip_dir), "--out", str(out_dir), "--no-drive")
    assert result.returncode == 0, result.stdout + result.stderr

    after = {p.relative_to(docs_dir): (p.stat().st_mtime_ns, p.stat().st_size)
             for p in docs_dir.rglob("*") if p.is_file()}
    assert before == after, "worktree 的 docs/ 被動到了"
    assert (WORKTREE / "build").exists() == build_dir_existed_before, "worktree 的 build/ 被動到了"


# ---------------------------------------------------------------------------
# new_trip.py：骨架長出來的形狀要能直接餵給 build.py --trip。
# ---------------------------------------------------------------------------

def test_new_trip_scaffold_is_buildable(tmp_path, monkeypatch):
    import new_trip

    trips_root = tmp_path / "trips"
    monkeypatch.setattr(new_trip, "TRIPS", trips_root)
    trip_dir = new_trip.scaffold("demo-trip", force=False)

    assert trip_dir == trips_root / "demo-trip"
    for name in ("trip_data.json", "clusters.json", "places.json", "guide.json",
                 "guide_overrides.json", "shopping.json", "shopping_overrides.json",
                 "trip.json", "private/redactions.json"):
        assert (trip_dir / name).exists(), f"缺少 {name}"
    assert (trip_dir / "assets").is_dir()

    # 骨架沒有真實資料，但形狀要對 — build.py 應該能直接吃(空行程也是行程)。
    out_dir = tmp_path / "out"
    result = run_build("--trip", str(trip_dir), "--out", str(out_dir), "--no-drive")
    assert result.returncode == 0, result.stdout + result.stderr
    assert (out_dir / "public_plain.html").exists()


def test_new_trip_refuses_nonempty_existing_folder_without_force(tmp_path, monkeypatch):
    import new_trip

    trips_root = tmp_path / "trips"
    monkeypatch.setattr(new_trip, "TRIPS", trips_root)
    new_trip.scaffold("demo-trip", force=False)

    with pytest.raises(SystemExit):
        new_trip.scaffold("demo-trip", force=False)

    # --force 要能覆蓋，不能因為已存在就跟著拋錯
    new_trip.scaffold("demo-trip", force=True)

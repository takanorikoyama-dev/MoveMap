"""ブートストラップ(DB 自動初期化)の単体テスト.

参照: app/shared/bootstrap.py
背景: Streamlit Cloud の ephemeral 環境で data/movemap.duckdb が無い場合に
seeds/movemap_sample.duckdb から自動 copy する仕組み(DEC-016 / T6).
"""

from __future__ import annotations

import shutil
from pathlib import Path

import pytest

import app.shared.bootstrap as bootstrap_mod
import app.shared.config as config_mod


@pytest.fixture()
def isolated_data_dir(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):  # type: ignore[no-untyped-def]
    """テスト用に Config の db_path を tmp_path に差し替え."""
    db_path = tmp_path / "data" / "test.duckdb"
    fake = config_mod.Config(
        db_path=db_path,
        seeds_dir=tmp_path / "seeds",
        log_level="INFO",
        estat_app_id=None,
    )
    monkeypatch.setattr(config_mod, "load_config", lambda: fake)
    monkeypatch.setattr(bootstrap_mod, "load_config", lambda: fake)
    return fake


def test_ensure_db_initialized_noop_when_db_exists(isolated_data_dir, monkeypatch: pytest.MonkeyPatch) -> None:  # type: ignore[no-untyped-def]
    """既に DB が存在する場合は何もしない."""
    isolated_data_dir.db_path.parent.mkdir(parents=True, exist_ok=True)
    isolated_data_dir.db_path.write_bytes(b"existing_db_content_dummy")
    before_mtime = isolated_data_dir.db_path.stat().st_mtime

    # copy / seed が走らないことを確認するためカウンタを差し込む
    copy_called = {"n": 0}

    def fake_copy(src, dst):  # type: ignore[no-untyped-def]
        copy_called["n"] += 1
        return shutil.copy2(src, dst)

    monkeypatch.setattr(bootstrap_mod.shutil, "copy2", fake_copy)

    bootstrap_mod.ensure_db_initialized()
    assert copy_called["n"] == 0
    assert isolated_data_dir.db_path.stat().st_mtime == before_mtime


def test_ensure_db_initialized_copies_sample_when_missing(isolated_data_dir, monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:  # type: ignore[no-untyped-def]
    """DB が無く、サンプル DB があれば copy する."""
    # サンプル DB を tmp_path に作成して bootstrap の参照先を差し替え
    sample = tmp_path / "movemap_sample.duckdb"
    sample.write_bytes(b"sample_db_content_for_copy_test" * 100)
    monkeypatch.setattr(bootstrap_mod, "SAMPLE_DB_PATH", sample)

    assert not isolated_data_dir.db_path.exists()

    bootstrap_mod.ensure_db_initialized()

    assert isolated_data_dir.db_path.exists()
    assert isolated_data_dir.db_path.read_bytes() == sample.read_bytes()


def test_ensure_db_initialized_swallows_exceptions(isolated_data_dir, monkeypatch: pytest.MonkeyPatch) -> None:  # type: ignore[no-untyped-def]
    """サンプルも seed も失敗しても例外を投げない(UI を止めない)."""
    # サンプル DB の参照先を存在しないパスに
    monkeypatch.setattr(
        bootstrap_mod,
        "SAMPLE_DB_PATH",
        bootstrap_mod.PROJECT_ROOT / "nonexistent_sample.duckdb",
    )

    # seed.py の main を例外を投げるよう差し替え
    def fake_seed_main(argv):  # type: ignore[no-untyped-def]
        raise RuntimeError("simulated seed failure")

    from scripts import seed as seed_module

    monkeypatch.setattr(seed_module, "main", fake_seed_main)

    # 例外が伝播しないことを検証(UI 起動を止めないため)
    bootstrap_mod.ensure_db_initialized()

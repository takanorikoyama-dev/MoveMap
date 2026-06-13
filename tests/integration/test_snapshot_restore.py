"""scripts/snapshot.py + scripts/restore.py の統合テスト(INFRA-P6-01).

一時的に DB パスを差し替えて、snapshot → restore のラウンドトリップを検証する.
"""

from __future__ import annotations

from pathlib import Path

import duckdb
import pytest

import app.shared.config as config_mod
from app.shared.db import initialize_schema
from scripts import restore as restore_mod
from scripts import snapshot as snapshot_mod


@pytest.fixture()
def isolated_db(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):  # type: ignore[no-untyped-def]
    """テスト用 DB パスに差し替えた Config を提供."""
    db_path = tmp_path / "movemap.duckdb"
    seeds_dir = tmp_path / "seeds"
    seeds_dir.mkdir()

    fake_config = config_mod.Config(
        db_path=db_path,
        seeds_dir=seeds_dir,
        log_level="INFO",
        estat_app_id=None,
    )
    monkeypatch.setattr(config_mod, "load_config", lambda: fake_config)
    monkeypatch.setattr(snapshot_mod, "load_config", lambda: fake_config)
    monkeypatch.setattr(restore_mod, "load_config", lambda: fake_config)

    # スキーマ初期化 + データ 1 行
    con = duckdb.connect(str(db_path))
    initialize_schema(con)
    con.execute("""
        INSERT INTO data_sources (id, name, url, license, update_frequency)
        VALUES ('estat', 'e-Stat', 'https://example.test', 'MIT', 'monthly')
    """)
    con.close()

    return fake_config


def test_take_snapshot_creates_file(isolated_db) -> None:  # type: ignore[no-untyped-def]
    target = snapshot_mod.take_snapshot(tag="202605")
    assert target.exists()
    assert target.name == "movemap.duckdb"
    assert target.parent.name == "202605"


def test_take_snapshot_default_uses_yyyymm(isolated_db) -> None:  # type: ignore[no-untyped-def]
    from datetime import datetime

    target = snapshot_mod.take_snapshot()
    expected_label = datetime.now().strftime("%Y%m")
    assert target.parent.name == expected_label


def test_take_snapshot_enforces_retention(isolated_db) -> None:  # type: ignore[no-untyped-def]
    """retention=2 で 3 世代目を作ると最古が削除される."""
    snapshot_mod.take_snapshot(tag="202601", retention=2)
    snapshot_mod.take_snapshot(tag="202602", retention=2)
    snapshot_mod.take_snapshot(tag="202603", retention=2)

    snapshot_root = isolated_db.db_path.parent / "snapshots"
    remaining = sorted(d.name for d in snapshot_root.iterdir() if d.is_dir())
    assert remaining == ["202602", "202603"]


def test_list_snapshots_returns_sorted(isolated_db) -> None:  # type: ignore[no-untyped-def]
    snapshot_mod.take_snapshot(tag="202603")
    snapshot_mod.take_snapshot(tag="202601")
    snapshot_mod.take_snapshot(tag="202602")

    snapshots = restore_mod.list_snapshots()
    assert [s.name for s in snapshots] == ["202601", "202602", "202603"]


def test_restore_latest_overwrites_db(isolated_db) -> None:  # type: ignore[no-untyped-def]
    # 1 つ目 snapshot を取った後、DB を改変
    snapshot_mod.take_snapshot(tag="202601")

    con = duckdb.connect(str(isolated_db.db_path))
    con.execute("""
        INSERT INTO data_sources (id, name, url, license, update_frequency)
        VALUES ('modified', 'Modified', 'https://x', 'MIT', 'monthly')
    """)
    con.close()

    # snapshot から復元
    restore_mod.restore_snapshot()

    con = duckdb.connect(str(isolated_db.db_path))
    (count,) = con.execute("SELECT COUNT(*) FROM data_sources WHERE id = 'modified'").fetchone()
    con.close()
    assert count == 0, "復元後 'modified' は消えているはず"


def test_restore_creates_pre_restore_backup(isolated_db) -> None:  # type: ignore[no-untyped-def]
    snapshot_mod.take_snapshot(tag="202601")
    restore_mod.restore_snapshot()

    parent = isolated_db.db_path.parent
    backups = list(parent.glob("movemap.pre_restore_*.duckdb"))
    assert len(backups) == 1


def test_restore_specific_tag(isolated_db) -> None:  # type: ignore[no-untyped-def]
    """--tag 指定で特定 snapshot を復元."""
    snapshot_mod.take_snapshot(tag="202601")
    # 改変
    con = duckdb.connect(str(isolated_db.db_path))
    con.execute("DELETE FROM data_sources WHERE id = 'estat'")
    con.close()
    snapshot_mod.take_snapshot(tag="202602")  # estat 削除済み状態

    # 202601 から復元 → estat が戻る
    restore_mod.restore_snapshot(tag="202601")
    con = duckdb.connect(str(isolated_db.db_path))
    (count,) = con.execute("SELECT COUNT(*) FROM data_sources WHERE id = 'estat'").fetchone()
    con.close()
    assert count == 1


def test_restore_missing_tag_raises(isolated_db) -> None:  # type: ignore[no-untyped-def]
    snapshot_mod.take_snapshot(tag="202601")
    with pytest.raises(FileNotFoundError):
        restore_mod.restore_snapshot(tag="999999")


def test_snapshot_when_db_missing_raises(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    fake_config = config_mod.Config(
        db_path=tmp_path / "missing.duckdb",
        seeds_dir=tmp_path,
        log_level="INFO",
        estat_app_id=None,
    )
    monkeypatch.setattr(snapshot_mod, "load_config", lambda: fake_config)
    with pytest.raises(FileNotFoundError):
        snapshot_mod.take_snapshot()


def test_main_list_returns_zero(isolated_db, capsys: pytest.CaptureFixture[str]) -> None:  # type: ignore[no-untyped-def]
    snapshot_mod.take_snapshot(tag="202601")
    rc = restore_mod.main(["--list"])
    assert rc == 0

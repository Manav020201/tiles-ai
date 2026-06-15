"""Seeding a starter board into a directory (`tiles init` / first `tiles up`)."""

from pathlib import Path

import pytest

from tiles_ai.bootstrap import BoardExistsError, has_board, init_board

# A minimal "starter" source the tests copy from — stands in for the bundled
# board so these tests don't depend on the release-time generated dir.


def _fake_starter(root: Path) -> Path:
    src = root / "starter_board"
    (src / "tiles" / "ask").mkdir(parents=True)
    (src / "tiles" / "ask" / "manifest.yaml").write_text("id: ask\n")
    (src / "connectors" / "gmail").mkdir(parents=True)
    (src / "connectors" / "gmail" / "manifest.yaml").write_text("id: gmail\n")
    (src / "examples").mkdir()
    (src / "examples" / "server.py").write_text("# example\n")
    (src / "sample_docs").mkdir()
    (src / "sample_docs" / "note.txt").write_text("hello\n")
    # build/secret noise that must NOT be copied
    (src / "tiles" / "ask" / "__pycache__").mkdir()
    (src / "tiles" / "ask" / "__pycache__" / "x.pyc").write_text("junk")
    (src / "connectors" / "gmail" / "oauth.local.yaml").write_text("token: secret")
    return src


def test_init_copies_the_board(tmp_path):
    src = _fake_starter(tmp_path)
    dest = tmp_path / "board"

    created = init_board(dest, source=src)

    assert sorted(created) == ["connectors", "examples", "sample_docs", "tiles"]
    assert (dest / "tiles" / "ask" / "manifest.yaml").read_text() == "id: ask\n"
    assert (dest / "connectors" / "gmail" / "manifest.yaml").is_file()
    assert (dest / "examples" / "server.py").is_file()
    assert (dest / "sample_docs" / "note.txt").is_file()


def test_init_skips_pycache_and_local_secrets(tmp_path):
    src = _fake_starter(tmp_path)
    dest = tmp_path / "board"

    init_board(dest, source=src)

    assert not (dest / "tiles" / "ask" / "__pycache__").exists()
    assert not (dest / "connectors" / "gmail" / "oauth.local.yaml").exists()


def test_init_refuses_when_board_exists(tmp_path):
    src = _fake_starter(tmp_path)
    dest = tmp_path / "board"
    (dest / "tiles").mkdir(parents=True)  # pre-existing board

    assert has_board(dest)
    with pytest.raises(BoardExistsError):
        init_board(dest, source=src)


def test_init_force_overwrites(tmp_path):
    src = _fake_starter(tmp_path)
    dest = tmp_path / "board"
    (dest / "tiles").mkdir(parents=True)

    created = init_board(dest, source=src, force=True)

    assert "tiles" in created
    assert (dest / "tiles" / "ask" / "manifest.yaml").is_file()


def test_init_without_a_bundled_board_raises(tmp_path, monkeypatch):
    # No source given and no bundled board available -> clear error.
    monkeypatch.setattr("tiles_ai.bootstrap.bundled_board", lambda: None)
    with pytest.raises(FileNotFoundError):
        init_board(tmp_path / "board")


def test_has_board_detects_either_dir(tmp_path):
    assert not has_board(tmp_path)
    (tmp_path / "connectors").mkdir()
    assert has_board(tmp_path)

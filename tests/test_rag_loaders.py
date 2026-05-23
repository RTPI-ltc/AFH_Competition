from __future__ import annotations

import json
from pathlib import Path

import pytest

from agent.rag import loaders


def test_load_text_file_utf8(tmp_path: Path) -> None:
    path = tmp_path / "note.txt"
    path.write_text("中文内容\nsecond line", encoding="utf-8")
    text = loaders.load_file(path)
    assert "中文内容" in text
    assert "second line" in text


def test_load_text_file_gbk(tmp_path: Path) -> None:
    path = tmp_path / "gbk.txt"
    path.write_bytes("中文 GBK 编码".encode("gbk"))
    text = loaders.load_file(path)
    assert "中文" in text


def test_load_bytes_unsupported_extension_raises() -> None:
    with pytest.raises(ValueError):
        loaders.load_bytes("image.png", b"\x89PNG")


def test_load_json_pretty_prints(tmp_path: Path) -> None:
    payload = {"中文": [1, 2], "英文": "value"}
    path = tmp_path / "data.json"
    path.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
    rendered = loaders.load_file(path)
    assert "中文" in rendered
    assert rendered.count("\n") >= 2


def test_load_pdf_bytes_without_pypdf(monkeypatch: pytest.MonkeyPatch) -> None:
    import sys

    monkeypatch.setitem(sys.modules, "pypdf", None)
    with pytest.raises(RuntimeError):
        loaders.load_bytes("a.pdf", b"%PDF-1.4")


def test_iter_files_finds_supported(tmp_path: Path) -> None:
    (tmp_path / "a.txt").write_text("a", encoding="utf-8")
    (tmp_path / "ignore.png").write_bytes(b"binary")
    nested = tmp_path / "nested"
    nested.mkdir()
    (nested / "b.md").write_text("b", encoding="utf-8")
    paths = loaders.iter_files(tmp_path)
    names = {p.name for p in paths}
    assert names == {"a.txt", "b.md"}

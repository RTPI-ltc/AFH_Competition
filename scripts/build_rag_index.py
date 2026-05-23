from __future__ import annotations

"""CLI for building/maintaining personal knowledge-base indexes.

Usage examples:
    python scripts/build_rag_index.py --input D:/docs/618 --name "618规则库" --create
    python scripts/build_rag_index.py --input ./README.md --kb-id kb_xxx
    python scripts/build_rag_index.py --input D:/docs/618.pdf --kb-id kb_xxx --replace
    python scripts/build_rag_index.py --list
    python scripts/build_rag_index.py --kb-id kb_xxx --delete
    python scripts/build_rag_index.py --rebuild-all   # rebuild every KB from raw/
"""

import argparse
import json
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from agent import database  # noqa: E402
from agent.rag import build_or_update_index, kb_store  # noqa: E402
from agent.rag.indexer import index_uploaded_bytes  # noqa: E402


def _print_kbs() -> int:
    items = database.list_knowledge_bases()
    if not items:
        print("(暂无知识库)")
        return 0
    for item in items:
        print(
            f"- {item['id']} | {item['name']} | type={item['type']} | "
            f"files={item.get('file_count', 0)} chunks={item.get('chunk_count', 0)} | "
            f"backend={item.get('embedding_backend') or '?'} | updated={item.get('updated_at')}"
        )
    return 0


def _delete_kb(kb_id: str) -> int:
    record = database.get_knowledge_base(kb_id)
    if not record:
        print(f"知识库 {kb_id} 不存在")
        return 1
    try:
        kb_store(kb_id).destroy()
    except Exception as exc:  # pragma: no cover - best effort
        print(f"清理磁盘失败：{exc}")
    database.delete_knowledge_base(kb_id)
    print(f"已删除知识库 {kb_id}")
    return 0


def _rebuild_all() -> int:
    items = database.list_knowledge_bases()
    if not items:
        print("(没有知识库可重建)")
        return 0
    total_ok = 0
    total_failed = 0
    for item in items:
        kb_id = item["id"]
        store = kb_store(kb_id)
        raw_dir = store.raw_dir
        if not raw_dir.exists():
            print(f"[skip] {kb_id} {item['name']}: 无原始文件目录")
            continue
        files: list[tuple[str, bytes]] = []
        for path in sorted(raw_dir.iterdir()):
            if path.is_file():
                try:
                    files.append((path.name, path.read_bytes()))
                except Exception as exc:
                    print(f"[warn] {kb_id} 读取 {path.name} 失败: {exc}")
        if not files:
            print(f"[skip] {kb_id} {item['name']}: raw/ 为空")
            continue
        # Wipe chunks + manifest so we re-chunk with the new config and rebuild
        # both FAISS and BM25 from scratch.
        store.save_chunks([])
        store.save_manifest([])
        store.clear_bm25()
        if store.faiss_path.exists():
            store.faiss_path.unlink()
        json_idx = store.faiss_path.with_suffix(".json")
        if json_idx.exists():
            json_idx.unlink()
        result = index_uploaded_bytes(kb_id, files, replace_same_name=True)
        database.update_knowledge_base_stats(
            kb_id,
            file_count=result.files_indexed,
            chunk_count=result.chunks_total,
            embedding_backend=result.embedding_backend,
        )
        print(
            f"[ok] {kb_id} {item['name']}: files={result.files_indexed} "
            f"chunks={result.chunks_total} backend={result.embedding_backend}"
        )
        if result.errors:
            for err in result.errors:
                print(f"     warn: {err}")
            total_failed += 1
        else:
            total_ok += 1
    print(f"\n重建完成：成功 {total_ok}，有警告 {total_failed}")
    return 0


def _resolve_paths(inputs: list[str]) -> list[Path]:
    resolved: list[Path] = []
    for raw in inputs:
        path = Path(raw).expanduser()
        if not path.exists():
            print(f"忽略不存在路径: {path}")
            continue
        resolved.append(path)
    return resolved


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="AFH 个人知识库索引 CLI")
    parser.add_argument("--input", action="append", default=[], help="输入文件或目录，可多次指定")
    parser.add_argument("--name", default="", help="新建知识库时的名称")
    parser.add_argument("--description", default="", help="新建时的描述")
    parser.add_argument("--kb-id", dest="kb_id", default="", help="已有知识库 id")
    parser.add_argument("--create", action="store_true", help="新建知识库并索引")
    parser.add_argument("--replace", action="store_true", help="同名文件覆盖重建")
    parser.add_argument("--list", action="store_true", help="列出所有知识库")
    parser.add_argument("--delete", action="store_true", help="删除指定知识库")
    parser.add_argument("--rebuild-all", action="store_true", help="重建所有知识库索引（从 raw/ 重新切片+嵌入+BM25）")
    args = parser.parse_args(argv)

    if args.list:
        return _print_kbs()

    if args.rebuild_all:
        return _rebuild_all()

    if args.delete:
        if not args.kb_id:
            parser.error("--delete 必须配合 --kb-id 使用")
        return _delete_kb(args.kb_id)

    if not args.input:
        parser.error("缺少 --input 参数")

    paths = _resolve_paths(args.input)
    if not paths:
        return 1

    if args.create:
        kb_id = database.create_knowledge_base(
            name=args.name or "未命名知识库",
            description=args.description,
            kb_type="personal",
        )
        store = kb_store(kb_id)
        database.update_knowledge_base_stats(kb_id, index_path=str(store.directory))
        print(f"已创建知识库 {kb_id}")
    else:
        if not args.kb_id:
            parser.error("追加索引必须提供 --kb-id 或加 --create")
        record = database.get_knowledge_base(args.kb_id)
        if not record:
            print(f"知识库 {args.kb_id} 不存在")
            return 1
        kb_id = args.kb_id

    result = build_or_update_index(kb_id, paths, replace_same_name=args.replace)
    database.update_knowledge_base_stats(
        kb_id,
        file_count=database.get_knowledge_base(kb_id).get("file_count", 0) + result.files_indexed
        if not args.create else result.files_indexed,
        chunk_count=result.chunks_total,
        embedding_backend=result.embedding_backend,
    )
    print(json.dumps(result.to_dict(), ensure_ascii=False, indent=2))
    return 0 if not result.errors else 0


if __name__ == "__main__":
    raise SystemExit(main())

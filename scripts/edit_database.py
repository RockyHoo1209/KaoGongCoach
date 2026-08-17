import re
import sys

DB = "D:/work/exam-mistake-manager/scripts/database.py"

with open(DB, "r", encoding="utf-8-sig") as f:
    lines = f.read().split("\n")

print(f"Read {len(lines)} lines")

# 1. Add "import re" after line 23 (from typing import ...)
lines.insert(24, "import re")
print("Added import re")

# 2. After "return "\u9519\u9898-001"" (line 357), insert helper functions
helper_funcs = [
    "",
    '# ---------------------------------------------------------------------------',
    '# 从索引文件导入（index-*.md / index.md V3）',
    '# ---------------------------------------------------------------------------',
    "",
    "_INDEX_TABLE_ROW_RE = re.compile(",
    '    r"^\\|\\s*([^|]+)\\s*\\|\\s*([^|]+)\\s*\\|\\s*([^|]+)\\s*\\|\\s*([^|]+)\\s*\\|"',
    '    r"\\s*([^|]+)\\s*\\|\\s*([^|]+)\\s*\\|\\s*([^|]+)\\s*\\|\\s*([^|]+)\\s*\\|$"',
    ")",
    "",
    "",
    "def _parse_index_table_row(line: str):",
    '    """Parse index table row, return dict or None."""',
    "    m = _INDEX_TABLE_ROW_RE.match(line.strip())",
    "    if not m:",
    "        return None",
    "    cells = [c.strip() for c in m.groups()]",
    '    if all(set(c) <= set("-: ") for c in cells):',
    "        return None",
    '    if cells[0] == "ID":',
    "        return None",
    "    return {",
    '        "id": cells[0],',
    '        "knowledge_point": cells[1],',
    '        "error_reason": cells[2],',
    '        "correct_answer": cells[3],',
    '        "source": cells[4],',
    '        "stage_str": cells[5],',
    '        "next_review": cells[6],',
    '        "status": cells[7],',
    "    }",
    "",
    "",
    "def _parse_index_stage(stage_str: str) -> int:",
    '    if "/" in stage_str:',
    "        try:",
    '            return int(stage_str.split("/")[0])',
    "        except ValueError:",
    "            return 0",
    "    try:",
    "        return int(stage_str)",
    "    except ValueError:",
    "        return 0",
    "",
    "",
    'def _parse_index_status(status_str: str) -> str:',
    '    if "\u5df2\u638c\u63e1" in status_str:',
    '        return "mastered"',
    '    return "pending"',
    "",
    "",
    'def db_row_to_entry(row: dict) -> "IndexEntry":',
    "    from models import IndexEntry",
    "    return IndexEntry(",
    '        id=row["id"],',
    '        knowledge_point=row.get("knowledge_point", ""),',
    '        error_reason=row.get("error_reason", ""),',
    '        correct_answer=row.get("correct_answer", ""),',
    '        source=row.get("source", ""),',
    '        review_stage=row.get("ebbinghaus_value", 0),',
    '        next_review=row.get("next_review", ""),',
    '        status=row.get("status", "pending"),',
    '        question_type=row.get("question_type", ""),',
    '        tags=row.get("tags", \'{"tag":[]}\'),',
    "    )",
    "",
    "",
    "def get_due_entries_db_as_entries(today: str) -> list:",
    "    rows = get_due_entries_db(today)",
    "    return [db_row_to_entry(r) for r in rows]",
]

# Insert after the blank line after return "\u9519\u9898-001" (line 357)
lines[357:357] = helper_funcs
print(f"Inserted helper functions after line 357 (now {len(lines)} lines)")

# 3. Insert import_from_index_files function before the tags section
import_func = [
    "",
    "",
    "def import_from_index_files(",
    "    mistake_root=None,",
    "    dry_run=False,",
    "):",
    '    """从 index-*.md 索引文件扫描并导入错题到 SQLite。"""',
    "    if mistake_root is None:",
    "        import config as _cfg",
    "        mistake_root = _cfg.MISTAKE_ROOT",
    "    mistake_root = Path(mistake_root)",
    "    if not mistake_root.exists():",
    '        raise ValueError(f"错题库目录不存在: {mistake_root}")',
    "",
    "    import config as _cfg",
    "    imported = 0",
    "    skipped = 0",
    "    errors = 0",
    "    items = []",
    "    seen_ids = set()",
    "",
    '    for index_file in sorted(mistake_root.glob("index-*.md")):',
    "        stem = index_file.stem",
    '        if not stem.startswith("index-"):',
    "            skipped += 1",
    "            continue",
    "        qtype = stem[6:]",
    "        if qtype not in _cfg.ALL_TYPES:",
    "            skipped += 1",
    "            continue",
    "",
    '        text = index_file.read_text(encoding="utf-8")',
    "        for line in text.splitlines():",
    "            row_data = _parse_index_table_row(line)",
    "            if not row_data:",
    "                continue",
    '            rid = row_data["id"]',
    "            if rid in seen_ids:",
    "                continue",
    "            seen_ids.add(rid)",
    "",
    "            try:",
    '                stage = _parse_index_stage(row_data["stage_str"])',
    '                status = _parse_index_status(row_data["status"])',
    '                img_rel = f"{qtype}/screenshots/{rid}.png"',
    '                full_img = mistake_root / qtype / "screenshots" / f"{rid}.png"',
    "                if not full_img.exists():",
    '                    img_rel = ""',
    "",
    "                from models import MistakeCard",
    "                card = MistakeCard(",
    "                    id=rid,",
    '                    date="",',
    "                    question_type=qtype,",
    '                    knowledge_point=row_data["knowledge_point"],',
    '                    error_reason=row_data["error_reason"],',
    '                    correct_answer=row_data["correct_answer"],',
    '                    source=row_data["source"],',
    "                    review_stage=stage,",
    '                    next_review=row_data["next_review"],',
    "                    review_history=[],",
    "                    status=status,",
    "                    screenshot=img_rel,",
    "                    tags='{\"tag\":[]}',",
    "                    image_path=img_rel,",
    "                )",
    "                if not dry_run:",
    "                    init_db()",
    "                    insert_mistake(card)",
    "",
    "                imported += 1",
    "                items.append({",
    '                    "id": rid,',
    '                    "question_type": qtype,',
    '                    "knowledge_point": row_data["knowledge_point"],',
    '                    "status": status,',
    "                })",
    "            except Exception as e:",
    '                errors += 1',
    '                items.append({"id": rid, "error": str(e)})',
    "",
    "    return {",
    '        "total": imported + skipped + errors,',
    '        "imported": imported,',
    '        "skipped": skipped,',
    '        "errors": errors,',
    '        "items": items,',
    "    }",
]

# Find tags section marker
for i, line in enumerate(lines):
    stripped = line.strip()
    if stripped.startswith("# \u6807\u7b7e\u64cd\u4f5c"):
        lines[i:i] = import_func
        print(f"Inserted import_from_index_files at line {i}")
        break

# 4. Insert search_mistakes after get_all_tags
for i, line in enumerate(lines):
    if "def get_all_tags" in line:
        insert_at = i + 1
        while insert_at < len(lines) and lines[insert_at].strip():
            insert_at += 1
        while insert_at < len(lines) and not lines[insert_at].strip():
            insert_at += 1
        break

search_code = [
    "",
    '# ---------------------------------------------------------------------------',
    '# 组合搜索',
    '# ---------------------------------------------------------------------------',
    "",
    "",
    "def search_mistakes(",
    "    question_type=None,",
    "    tag=None,",
    "    keyword=None,",
    "    limit=100,",
    "):",
    '    """组合搜索：可按题型、标签、关键词同时过滤。"""',
    "    conditions = []",
    "    params = []",
    "",
    "    if question_type:",
    '        conditions.append("question_type = ?")',
    "        params.append(question_type)",
    "",
    "    if tag:",
    "        conditions.append(",
    '            "EXISTS (SELECT 1 FROM json_each(tags, \'$.tag\') WHERE value = ?)"',
    "        )",
    "        params.append(tag)",
    "",
    "    if keyword:",
    '        kw = f"%{keyword}%"',
    "        conditions.append(",
    '            "(id LIKE ? OR question_type LIKE ? OR knowledge_point LIKE ? "',
    '            "OR error_reason LIKE ? OR source LIKE ?)"',
    "        )",
    "        params.extend([kw, kw, kw, kw, kw])",
    "",
    '    where_clause = ""',
    "    if conditions:",
    '        where_clause = "WHERE " + " AND ".join(conditions)',
    "",
    "    with get_conn() as conn:",
    "        rows = conn.execute(",
    '            f"SELECT * FROM mistakes {where_clause} ORDER BY id LIMIT ?",',
    "            params + [limit],",
    "        ).fetchall()",
    "    return rows",
    "",
    "",
]

lines[insert_at:insert_at] = search_code
print(f"Inserted search_mistakes at line {insert_at}")

with open(DB, "w", encoding="utf-8-sig") as f:
    f.write("\n".join(lines))

print(f"Done! {len(lines)} lines written.")

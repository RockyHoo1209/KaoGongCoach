"""SQLite 数据库层 — 错题持久化存储。

使用 SQLite 替代 markdown 文件系统作为错题主存储。
支持 JSON1 标签检索、艾宾浩斯遗忘曲线调度、批量导入/导出。

迁移说明：
  原系统使用 markdown 文件 + index.md 分索引存储错题。
  V3 引入 SQLite 作为主存储，markdown 文件保留作 Obsidian 兼容。

数据库路径：
  默认：{OBSIDIAN_ROOT}/mistakes.db
  环境变量覆盖：EXAM_MISTAKES_DB
"""
from __future__ import annotations

import json
import os
import re
import sqlite3
import shutil
from contextlib import contextmanager
from datetime import date, datetime
from pathlib import Path
from typing import Any, Dict, Iterator, List, Optional, Tuple
import re

import config
import scheduler
from models import MistakeCard


# ---------------------------------------------------------------------------
# 数据库路径
# ---------------------------------------------------------------------------

def get_db_path() -> Path:
    """获取 SQLite 数据库文件路径。

    优先级：环境变量 EXAM_MISTAKES_DB > 默认路径。
    """
    env = os.environ.get("EXAM_MISTAKES_DB")
    if env:
        return Path(env)
    return config.MISTAKE_ROOT / "mistakes.db"


_DB_PATH = get_db_path()


# ---------------------------------------------------------------------------
# 连接管理
# ---------------------------------------------------------------------------

def _dict_factory(cursor: sqlite3.Cursor, row: Tuple) -> Dict[str, Any]:
    return {col[0]: row[i] for i, col in enumerate(cursor.description)}


@contextmanager
def get_conn() -> Iterator[sqlite3.Connection]:
    conn = sqlite3.connect(str(_DB_PATH))
    conn.row_factory = _dict_factory
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


# ---------------------------------------------------------------------------
# 建表
# ---------------------------------------------------------------------------

SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS mistakes (
    id              TEXT PRIMARY KEY,
    question_type   TEXT NOT NULL,
    tags            TEXT NOT NULL DEFAULT '{"tag":[]}',
    ebbinghaus_value INTEGER NOT NULL DEFAULT 0,
    image_path      TEXT,
    -- 以下为原有字段，保留兼容
    knowledge_point TEXT NOT NULL DEFAULT '',
    error_reason    TEXT NOT NULL DEFAULT '',
    correct_answer  TEXT NOT NULL DEFAULT '',
    source          TEXT NOT NULL DEFAULT '',
    next_review     TEXT NOT NULL DEFAULT '',
    status          TEXT NOT NULL DEFAULT 'pending',
    review_history  TEXT NOT NULL DEFAULT '[]',
    created_at      TEXT NOT NULL DEFAULT (date('now'))
);

CREATE INDEX IF NOT EXISTS idx_mistakes_type ON mistakes(question_type);
CREATE INDEX IF NOT EXISTS idx_mistakes_status ON mistakes(status);
CREATE INDEX IF NOT EXISTS idx_mistakes_next_review ON mistakes(next_review);
"""


def init_db(force: bool = False) -> None:
    _DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(_DB_PATH))
    try:
        if force:
            conn.execute("DROP TABLE IF EXISTS mistakes")
        conn.executescript(SCHEMA_SQL)
        conn.commit()
    finally:
        conn.close()


# ---------------------------------------------------------------------------
# CRUD 核心操作
# ---------------------------------------------------------------------------

def insert_mistake(card: MistakeCard) -> str:
    tags_json = card.tags if card.tags else json.dumps({"tag": []}, ensure_ascii=False)
    rh_json = json.dumps(card.review_history, ensure_ascii=False)

    with get_conn() as conn:
        conn.execute(
            """INSERT OR REPLACE INTO mistakes
               (id, question_type, tags, ebbinghaus_value, image_path,
                knowledge_point, error_reason, correct_answer, source,
                next_review, status, review_history, created_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                card.id,
                card.question_type,
                tags_json,
                card.review_stage,
                card.screenshot or "",
                card.knowledge_point,
                card.error_reason,
                card.correct_answer,
                card.source,
                card.next_review,
                card.status,
                rh_json,
                card.date or date.today().isoformat(),
            ),
        )
    return card.id


def get_mistake(mistake_id: str) -> Optional[Dict[str, Any]]:
    with get_conn() as conn:
        row = conn.execute(
            "SELECT * FROM mistakes WHERE id = ?", (mistake_id,)
        ).fetchone()
    return row


def _row_to_card(row: Dict[str, Any]) -> MistakeCard:
    rh = []
    try:
        rh = json.loads(row.get("review_history", "[]"))
    except (json.JSONDecodeError, TypeError):
        rh = []

    return MistakeCard(
        id=row["id"],
        date=row.get("created_at", ""),
        question_type=row["question_type"],
        knowledge_point=row.get("knowledge_point", ""),
        error_reason=row.get("error_reason", ""),
        correct_answer=row.get("correct_answer", ""),
        source=row.get("source", ""),
        review_stage=row.get("ebbinghaus_value", 0),
        next_review=row.get("next_review", ""),
        review_history=rh,
        status=row.get("status", "pending"),
        screenshot=row.get("image_path", ""),
    )


def search_by_type(question_type: str) -> List[Dict[str, Any]]:
    with get_conn() as conn:
        rows = conn.execute(
            "SELECT * FROM mistakes WHERE question_type = ? ORDER BY id",
            (question_type,),
        ).fetchall()
    return rows


def search_by_tag(tag_value: str) -> List[Dict[str, Any]]:
    """利用 SQLite JSON1 的 json_each 实现标签精确匹配。"""
    with get_conn() as conn:
        rows = conn.execute(
            """SELECT * FROM mistakes
               WHERE json_extract(tags, '$.tag') IS NOT NULL
               AND EXISTS (
                   SELECT 1 FROM json_each(tags, '$.tag')
                   WHERE value = ?
               )
               ORDER BY id""",
            (tag_value,),
        ).fetchall()
    return rows


def search_by_keyword(keyword: str) -> List[Dict[str, Any]]:
    pattern = f"%{keyword}%"
    with get_conn() as conn:
        rows = conn.execute(
            """SELECT * FROM mistakes
               WHERE id LIKE ?
                  OR question_type LIKE ?
                  OR knowledge_point LIKE ?
                  OR error_reason LIKE ?
                  OR source LIKE ?
               ORDER BY id""",
            (pattern, pattern, pattern, pattern, pattern),
        ).fetchall()
    return rows


def update_mistake_field(mistake_id: str, field: str, value: Any) -> bool:
    field_map = {
        "knowledge_point": "knowledge_point",
        "error_reason": "error_reason",
        "correct_answer": "correct_answer",
        "source": "source",
        "question_type": "question_type",
        "tags": "tags",
        "image_path": "image_path",
        "ebbinghaus_value": "ebbinghaus_value",
    }
    db_field = field_map.get(field)
    if not db_field:
        raise ValueError(f"不支持的修改字段: {field}")

    with get_conn() as conn:
        cur = conn.execute(
            f"UPDATE mistakes SET {db_field} = ? WHERE id = ?",
            (value, mistake_id),
        )
        return cur.rowcount > 0


def delete_mistake_db(mistake_id: str) -> bool:
    with get_conn() as conn:
        cur = conn.execute("DELETE FROM mistakes WHERE id = ?", (mistake_id,))
        return cur.rowcount > 0


# ---------------------------------------------------------------------------
# 艾宾浩斯遗忘曲线相关
# ---------------------------------------------------------------------------

def update_review_state_db(
    mistake_id: str,
    ebbinghaus_value: int,
    next_review: str,
    status: str,
    passed: bool,
    review_date: str,
    old_stage: int,
) -> bool:
    with get_conn() as conn:
        row = conn.execute(
            "SELECT review_history FROM mistakes WHERE id = ?",
            (mistake_id,),
        ).fetchone()
        if not row:
            return False

        rh = []
        try:
            rh = json.loads(row["review_history"])
        except (json.JSONDecodeError, TypeError):
            rh = []

        rh.append({
            "date": review_date,
            "result": "pass" if passed else "fail",
            "stage": old_stage,
            "next_review": next_review,
        })

        conn.execute(
            """UPDATE mistakes
               SET ebbinghaus_value = ?, next_review = ?, status = ?,
                   review_history = ?
               WHERE id = ?""",
            (
                ebbinghaus_value,
                next_review,
                status,
                json.dumps(rh, ensure_ascii=False),
                mistake_id,
            ),
        )
        return True


def get_due_entries_db(today: str) -> List[Dict[str, Any]]:
    with get_conn() as conn:
        rows = conn.execute(
            """SELECT * FROM mistakes
               WHERE status != 'mastered'
                 AND next_review <= ?
                 AND knowledge_point NOT IN ('', '待补充')
                 AND error_reason NOT IN ('', '待补充')
               ORDER BY next_review ASC, ebbinghaus_value ASC, id""",
            (today,),
        ).fetchall()
    return rows


def get_stats_db() -> Dict[str, Any]:
    with get_conn() as conn:
        total = conn.execute("SELECT COUNT(*) as c FROM mistakes").fetchone()["c"]
        pending = conn.execute(
            "SELECT COUNT(*) as c FROM mistakes WHERE status = 'pending'"
        ).fetchone()["c"]
        mastered = conn.execute(
            "SELECT COUNT(*) as c FROM mistakes WHERE status = 'mastered'"
        ).fetchone()["c"]

        by_type = conn.execute(
            """SELECT question_type, COUNT(*) as total,
                      SUM(CASE WHEN status='pending' THEN 1 ELSE 0 END) as pending,
                      SUM(CASE WHEN status='mastered' THEN 1 ELSE 0 END) as mastered
               FROM mistakes
               GROUP BY question_type
               ORDER BY question_type"""
        ).fetchall()

    type_stats = {}
    for row in by_type:
        type_stats[row["question_type"]] = {
            "total": row["total"],
            "pending": row["pending"],
            "mastered": row["mastered"],
        }

    return {
        "total": total,
        "pending": pending,
        "mastered": mastered,
        "by_type": type_stats,
    }


def get_next_id_db() -> str:
    with get_conn() as conn:
        row = conn.execute(
            """SELECT id FROM mistakes
               ORDER BY CAST(SUBSTR(id, 4) AS INTEGER) DESC
               LIMIT 1"""
        ).fetchone()
    if row:
        last_num = int(row["id"].replace("错题-", ""))
        return f"错题-{last_num + 1:03d}"


    return "错题-001"
# ---------------------------------------------------------------------------
# 从索引文件导入（index-*.md / index.md V3）
# ---------------------------------------------------------------------------

_INDEX_TABLE_ROW_RE = re.compile(
    r"^\|\s*([^|]+)\s*\|\s*([^|]+)\s*\|\s*([^|]+)\s*\|\s*([^|]+)\s*\|"
    r"\s*([^|]+)\s*\|\s*([^|]+)\s*\|\s*([^|]+)\s*\|\s*([^|]+)\s*\|$"
)



# ---------------------------------------------------------------------------
# 从 index-*.md / index.md 导入（扫描索引文件 + 寻找对应图片）
# ---------------------------------------------------------------------------

def _parse_index_table_row(line: str):
    """Parse index table row, return dict or None.

    Handles multiple table formats found in Obsidian markdown:
      - Normal: | ID | 考点 | 错因 | 答案 | 来源 | 阶段 | 下次复习 | 状态 |
      - Double-pipe wrapped: || ID | 考点 | ... | 状态 ||
      - No leading pipe: ID | 考点 | ...
    """
    line = line.strip()
    if not line:
        return None
    # Skip frontmatter / separator lines / non-table content
    if line.startswith("---") or line.startswith("|--") or line.startswith("|---"):
        return None
    # Strip all leading/trailing pipes, then split by |
    stem = line.strip("|")
    cells = [c.strip() for c in stem.split("|")]
    # Expect exactly 8 data cells
    if len(cells) != 8:
        return None
    # Skip header row
    if cells[0] == "ID":
        return None
    # Skip separator row
    if all(set(c) <= set("-: ") | {""} for c in cells):
        return None
    return {
        "id": cells[0],
        "knowledge_point": cells[1],
        "error_reason": cells[2],
        "correct_answer": cells[3],
        "source": cells[4],
        "stage_str": cells[5],
        "next_review": cells[6],
        "status": cells[7],
    }


def _parse_index_stage(stage_str: str) -> int:
    if "/" in stage_str:
        try:
            return int(stage_str.split("/")[0])
        except ValueError:
            return 0
    try:
        return int(stage_str)
    except ValueError:
        return 0


def _parse_index_status(status_str: str) -> str:
    if "已掌握" in status_str:
        return "mastered"
    return "pending"


def _parse_index_md_sections(content: str):
    """Parse composite index.md with ## section headers + table rows.

    Structure:
        ## 判断推理
        | ID | 考点 | 错因 | 答案 | 来源 | 阶段 | 下次复习 | 状态 |
        |----|------|------|------|------|------|----------|------|
        | 错题-050 | 逻辑判断 | 待补充 | ... | 判断推理 | 0/6 | ... |

    Returns list of dicts with question_type inferred from ## header.
    """
    entries = []
    current_type = None

    for line in content.splitlines():
        line = line.strip()
        if not line:
            continue

        # Detect section header: ## 题型名
        sec_m = re.match(r"^##\s+(.+)$", line)
        if sec_m:
            candidate = sec_m.group(1).strip()
            if candidate in config.ALL_TYPES:
                current_type = candidate
            else:
                current_type = None
            continue

        # Parse table row within the current section
        row_data = _parse_index_table_row(line)
        if row_data and current_type:
            row_data["question_type"] = current_type
            entries.append(row_data)

    return entries


def import_from_index_files(
    mistake_root=None,
    dry_run=False,
):
    """从 index-*.md / index.md 索引文件扫描并导入错题到 SQLite。

    扫描指定根目录下所有 index-*.md 文件，解析表格行，
    然后在对应题型目录下寻找截图（screenshots/{id}.png / {id}.jpg），
    将图片路径一并入库。
    """
    imported = 0
    skipped = 0
    errors = 0
    items = []
    seen_ids = set()

    target_root = Path(mistake_root) if mistake_root else config.MISTAKE_ROOT
    if not target_root.exists():
        raise ValueError(f"目录不存在: {target_root}")

    # 搜索所有 index-*.md 文件
    index_files = []
    for pattern in ["index-*.md", "错题库/index-*.md", "**/index-*.md"]:
        for f in target_root.glob(pattern):
            index_files.append(f)

    index_files = sorted(set(index_files))

    if not index_files:
        alt_root = config.MISTAKE_ROOT
        if alt_root != target_root:
            index_files = sorted(alt_root.glob("index-*.md"))

    if not index_files:
        return {
            "total": 0,
            "imported": 0,
            "skipped": 0,
            "errors": 0,
            "items": [],
            "message": "未找到 index-*.md 索引文件",
        }

    for idx_path in index_files:
        stem = idx_path.stem
        if not stem.startswith("index-"):
            skipped += 1
            continue

        qtype = stem[6:]
        if qtype not in config.ALL_TYPES:
            skipped += 1
            continue

        text = idx_path.read_text(encoding="utf-8")
        for line in text.splitlines():
            row_data = _parse_index_table_row(line)
            if not row_data:
                continue
            rid = row_data["id"]
            if rid in seen_ids:
                continue
            seen_ids.add(rid)

            try:
                stage = _parse_index_stage(row_data["stage_str"])
                status_val = _parse_index_status(row_data["status"])

                # 寻找图片
                img_path = ""
                for ext in [".png", ".jpg", ".jpeg", ".webp"]:
                    candidate = (
                        target_root / qtype / "screenshots" / f"{rid}{ext}"
                    )
                    if not candidate.exists():
                        candidate = (
                            config.MISTAKE_ROOT / qtype / "screenshots" / f"{rid}{ext}"
                        )
                    if candidate.exists():
                        img_path = str(candidate)
                        break

                card = MistakeCard(
                    id=rid,
                    date="",
                    question_type=qtype,
                    knowledge_point=row_data["knowledge_point"],
                    error_reason=row_data["error_reason"],
                    correct_answer=row_data["correct_answer"],
                    source=row_data["source"],
                    review_stage=stage,
                    next_review=row_data["next_review"],
                    review_history=[],
                    status=status_val,
                    screenshot=img_path,
                    image_path=img_path,
                )

                if not dry_run:
                    insert_mistake(card)

                imported += 1
                items.append({
                    "id": rid,
                    "question_type": qtype,
                    "knowledge_point": row_data["knowledge_point"],
                    "status": status_val,
                    "image_path": img_path if img_path else "(无截图)",
                })
            except Exception as e:
                errors += 1
                items.append({"id": rid, "error": str(e)})

    # -----------------------------------------------------------------------
    # Phase 2: Parse composite index.md (## sections + table rows)
    # -----------------------------------------------------------------------
    index_md_path = target_root / "index.md"
    if index_md_path.exists():
        text = index_md_path.read_text(encoding="utf-8")
        composite_entries = _parse_index_md_sections(text)

        for row_data in composite_entries:
            rid = row_data["id"]
            if rid in seen_ids:
                continue
            seen_ids.add(rid)

            try:
                qtype = row_data["question_type"]
                stage = _parse_index_stage(row_data.get("stage_str", "0"))
                status_val = _parse_index_status(row_data.get("status", "pending"))

                img_path = ""
                for ext in [".png", ".jpg", ".jpeg", ".webp"]:
                    candidate = target_root / qtype / "screenshots" / f"{rid}{ext}"
                    if not candidate.exists():
                        candidate = config.MISTAKE_ROOT / qtype / "screenshots" / f"{rid}{ext}"
                    if candidate.exists():
                        img_path = str(candidate)
                        break

                card = MistakeCard(
                    id=rid,
                    date="",
                    question_type=qtype,
                    knowledge_point=row_data.get("knowledge_point", ""),
                    error_reason=row_data.get("error_reason", ""),
                    correct_answer=row_data.get("correct_answer", ""),
                    source=row_data.get("source", ""),
                    review_stage=stage,
                    next_review=row_data.get("next_review", ""),
                    review_history=[],
                    status=status_val,
                    screenshot=img_path,
                    image_path=img_path,
                )

                if not dry_run:
                    insert_mistake(card)

                imported += 1
                items.append({
                    "id": rid,
                    "question_type": qtype,
                    "knowledge_point": row_data.get("knowledge_point", ""),
                    "status": status_val,
                    "image_path": img_path if img_path else "\u65e0\u622a\u56fe",
                })
            except Exception as e:
                errors += 1
                items.append({"id": rid, "error": str(e)})

    return {
        "total": imported + skipped + errors,
        "imported": imported,
        "skipped": skipped,
        "errors": errors,
        "items": items,
    }


# ---------------------------------------------------------------------------
# 组合搜索（按题型 / 标签 / 关键字同时过滤）
# ---------------------------------------------------------------------------


def search_mistakes(
    question_type=None,
    tag=None,
    keyword=None,
    limit=100,
):
    """组合搜索：可按题型、标签、关键词同时过滤。"""
    conditions = []
    params = []

    if question_type:
        conditions.append("question_type = ?")
        params.append(question_type)

    if tag:
        conditions.append(
            "EXISTS (SELECT 1 FROM json_each(tags, '$.tag') WHERE value = ?)"
        )
        params.append(tag)

    if keyword:
        kw = f"%{keyword}%"
        conditions.append(
            "(id LIKE ? OR question_type LIKE ? OR knowledge_point LIKE ? "
            "OR error_reason LIKE ? OR source LIKE ?)"
        )
        params.extend([kw, kw, kw, kw, kw])

    where_clause = ""
    if conditions:
        where_clause = "WHERE " + " AND ".join(conditions)

    with get_conn() as conn:
        rows = conn.execute(
            f"SELECT * FROM mistakes {where_clause} ORDER BY id LIMIT ?",
            params + [limit],
        ).fetchall()
    return rows



# ---------------------------------------------------------------------------


def add_tag(mistake_id: str, tag: str) -> bool:
    with get_conn() as conn:
        row = conn.execute(
            "SELECT tags FROM mistakes WHERE id = ?", (mistake_id,)
        ).fetchone()
        if not row:
            return False

        try:
            tag_list = json.loads(row["tags"]).get("tag", [])
        except (json.JSONDecodeError, TypeError):
            tag_list = []

        if tag in tag_list:
            return True

        tag_list.append(tag)
        new_tags = json.dumps({"tag": tag_list}, ensure_ascii=False)

        conn.execute(
            "UPDATE mistakes SET tags = ? WHERE id = ?",
            (new_tags, mistake_id),
        )
        return True


def remove_tag(mistake_id: str, tag: str) -> bool:
    with get_conn() as conn:
        row = conn.execute(
            "SELECT tags FROM mistakes WHERE id = ?", (mistake_id,)
        ).fetchone()
        if not row:
            return False

        try:
            tag_list = json.loads(row["tags"]).get("tag", [])
        except (json.JSONDecodeError, TypeError):
            tag_list = []

        if tag not in tag_list:
            return True

        tag_list = [t for t in tag_list if t != tag]
        new_tags = json.dumps({"tag": tag_list}, ensure_ascii=False)

        conn.execute(
            "UPDATE mistakes SET tags = ? WHERE id = ?",
            (new_tags, mistake_id),
        )
        return True


def get_all_tags() -> List[str]:
    with get_conn() as conn:
        rows = conn.execute(
            """SELECT DISTINCT value as tag
               FROM mistakes, json_each(mistakes.tags, '$.tag')
               ORDER BY tag"""
        ).fetchall()
    return [r["tag"] for r in rows]



# ---------------------------------------------------------------------------
# 组合搜索
# ---------------------------------------------------------------------------



# ---------------------------------------------------------------------------
# 批量导入：从原有 markdown 错题库迁移到 SQLite
# ---------------------------------------------------------------------------

def import_from_mistake_root(
    mistake_root: Optional[Path] = None,
    dry_run: bool = False,
) -> Dict[str, Any]:
    if mistake_root is None:
        mistake_root = config.MISTAKE_ROOT

    mistake_root = Path(mistake_root)
    if not mistake_root.exists():
        raise ValueError(f"错题库目录不存在: {mistake_root}")

    imported = 0
    skipped = 0
    errors = 0
    items: List[Dict[str, Any]] = []

    for qtype_dir in sorted(mistake_root.iterdir()):
        if not qtype_dir.is_dir():
            continue
        if qtype_dir.name in ("screenshots", ".git") or qtype_dir.name.startswith("."):
            continue
        if qtype_dir.name.startswith("index"):
            continue

        qtype = qtype_dir.name
        for md_file in sorted(qtype_dir.glob("错题-*.md")):
            try:
                text = md_file.read_text(encoding="utf-8")
                meta = _parse_md_frontmatter(text)
                if not meta or "id" not in meta:
                    skipped += 1
                    continue

                card = MistakeCard(
                    id=meta["id"],
                    date=meta.get("date", ""),
                    question_type=meta.get("题型", qtype),
                    knowledge_point=meta.get("考点", ""),
                    error_reason=meta.get("错误原因", ""),
                    correct_answer=meta.get("正确答案", ""),
                    source=meta.get("来源", ""),
                    review_stage=meta.get("review_stage", 0),
                    next_review=meta.get("next_review", ""),
                    review_history=meta.get("review_history", []),
                    status=meta.get("status", "pending"),
                    screenshot=f"screenshots/{meta['id']}.png",
                )

                if not dry_run:
                    insert_mistake(card)

                imported += 1
                items.append({
                    "id": card.id,
                    "question_type": card.question_type,
                    "knowledge_point": card.knowledge_point,
                    "status": card.status,
                })
            except Exception as e:
                errors += 1
                items.append({
                    "id": md_file.stem,
                    "error": str(e),
                })

    return {
        "total": imported + skipped + errors,
        "imported": imported,
        "skipped": skipped,
        "errors": errors,
        "items": items,
    }


def _parse_md_frontmatter(text: str) -> dict:
    m = re.match(r"^---\s*\n(.*?)\n---\s*\n", text, re.DOTALL)
    if not m:
        return {}
    result = {}
    for line in m.group(1).splitlines():
        if ":" in line:
            k, v = line.split(":", 1)
            k = k.strip()
            v = v.strip()
            if k == "review_history":
                try:
                    result[k] = json.loads(v)
                except (json.JSONDecodeError, ValueError):
                    result[k] = []
            elif k in ("review_stage",):
                try:
                    result[k] = int(v)
                except ValueError:
                    result[k] = 0
            else:
                result[k] = v
    return result


def build_import_report(stats: Dict[str, Any]) -> str:
    lines = [
        "## ✅ 迁移到 SQLite 完成",
        "",
        "### 📊 导入统计",
        "",
        "| 指标 | 数值 |",
        "|------|------|",
        f"| 总数 | {stats['total']} |",
        f"| 成功导入 | {stats['imported']} |",
        f"| 跳过 | {stats['skipped']} |",
        f"| 错误 | {stats['errors']} |",
    ]

    if stats["items"]:
        lines.extend(["", "### 📋 导入明细（前 20 条）", ""])
        lines.append("| ID | 题型 | 考点 | 状态 |")
        lines.append("|----|------|------|------|")
        for item in stats["items"][:20]:
            if "error" in item:
                lines.append(f"| {item['id']} | — | — | ❌ {item['error']} |")
            else:
                status_emoji = "✅" if item.get("status") == "mastered" else "⏳"
                lines.append(
                    f"| {item['id']} | {item.get('question_type', '')} | "
                    f"{item.get('knowledge_point', '')} | {status_emoji} |"
                )
    return "\n".join(lines)


def db_exists() -> bool:
    if not _DB_PATH.exists():
        return False
    try:
        with get_conn() as conn:
            count = conn.execute(
                "SELECT COUNT(*) as c FROM mistakes"
            ).fetchone()["c"]
            return count > 0
    except Exception:
        return False

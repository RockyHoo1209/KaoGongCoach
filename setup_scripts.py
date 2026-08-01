#!/usr/bin/env python3
"""一次性创建/恢复 scripts/ 下的所有 Phase 1 模块。"""
from pathlib import Path

ROOT = Path(__file__).resolve().parent
SCRIPTS = ROOT / "scripts"
SCRIPTS.mkdir(exist_ok=True)

FILES = {
    "index_manager.py": r'''"""index.md 读写管理器。

index.md 是复习系统的单一数据源，包含：
- YAML frontmatter: last_id, total, pending, mastered, updated
- 各题型章节的 markdown 表格

本模块负责解析和重建 index.md，保证数据一致性。
"""
from __future__ import annotations

import re
from datetime import date
from pathlib import Path
from typing import List, Optional

import config
from models import IndexData, IndexEntry, MistakeCard


_FRONTMATTER_RE = re.compile(r"^---\s*\n(.*?)\n---\s*\n", re.DOTALL)


def _parse_frontmatter(text: str) -> dict:
    """解析 YAML frontmatter（仅支持简单的 key: value）。"""
    m = _FRONTMATTER_RE.match(text)
    if not m:
        return {}
    result = {}
    for line in m.group(1).splitlines():
        if ":" in line:
            k, v = line.split(":", 1)
            k = k.strip()
            v = v.strip()
            try:
                result[k] = int(v)
            except ValueError:
                result[k] = v
    return result


def _dump_frontmatter(meta: dict) -> str:
    lines = ["---"]
    for k, v in meta.items():
        lines.append(f"{k}: {v}")
    lines.append("---")
    lines.append("")
    return "\n".join(lines)


_TABLE_ROW_RE = re.compile(
    r"^\|\s*([^|]+)\s*\|\s*([^|]+)\s*\|\s*([^|]+)\s*\|\s*([^|]+)\s*\|"
    r"\s*([^|]+)\s*\|\s*([^|]+)\s*\|\s*([^|]+)\s*\|\s*([^|]+)\s*\|$"
)


def _parse_table_row(line: str) -> Optional[dict]:
    m = _TABLE_ROW_RE.match(line.strip())
    if not m:
        return None
    cells = [c.strip() for c in m.groups()]
    if all(set(c) <= set("-: ") for c in cells):
        return None
    if cells[0] == "ID":
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


def _row_to_entry(row: dict, question_type: str) -> IndexEntry:
    stage_str = row["stage_str"]
    stage = 0
    if "/" in stage_str:
        stage = int(stage_str.split("/")[0])
    else:
        try:
            stage = int(stage_str)
        except ValueError:
            stage = 0
    status = "mastered" if "已掌握" in row["status"] else "pending"
    return IndexEntry(
        id=row["id"],
        knowledge_point=row["knowledge_point"],
        error_reason=row["error_reason"],
        correct_answer=row["correct_answer"],
        source=row["source"],
        review_stage=stage,
        next_review=row["next_review"],
        status=status,
        question_type=question_type,
    )


def load_index(index_path: Path | None = None) -> IndexData:
    """读取 index.md，返回结构化 IndexData。"""
    if index_path is None:
        index_path = config.INDEX_FILE
    if not index_path.exists():
        config.ensure_dirs()
    text = index_path.read_text(encoding="utf-8")
    meta = _parse_frontmatter(text)
    data = IndexData(
        last_id=meta.get("last_id", 0),
        total=meta.get("total", 0),
        pending=meta.get("pending", 0),
        mastered=meta.get("mastered", 0),
        updated=meta.get("updated", ""),
    )
    current_type = ""
    for line in text.splitlines():
        h2 = re.match(r"^##\s+(.+)$", line)
        if h2:
            current_type = h2.group(1).strip()
            continue
        if line.strip().startswith("|"):
            row = _parse_table_row(line)
            if row:
                data.entries.append(_row_to_entry(row, current_type))
    return data


def _entry_to_row(e: IndexEntry) -> str:
    stage_str = f"{e.review_stage}/6"
    status_str = "✅已掌握" if e.status == "mastered" else "⏳待复习"
    return (
        f"| {e.id} | {e.knowledge_point} | {e.error_reason} | "
        f"{e.correct_answer} | {e.source} | {stage_str} | "
        f"{e.next_review} | {status_str} |"
    )


def save_index(data: IndexData, index_path: Path | None = None) -> None:
    if index_path is None:
        index_path = config.INDEX_FILE
    data.total = len(data.entries)
    data.pending = sum(1 for e in data.entries if e.status == "pending")
    data.mastered = sum(1 for e in data.entries if e.status == "mastered")
    data.updated = date.today().isoformat()
    meta = {
        "last_id": data.last_id,
        "total": data.total,
        "pending": data.pending,
        "mastered": data.mastered,
        "updated": data.updated,
    }
    lines = [_dump_frontmatter(meta)]
    lines.append("# 错题库索引")
    lines.append("")
    lines.append(
        f"> 共 {data.total} 题 | ⏳待复习 {data.pending} 题 | "
        f"✅已掌握 {data.mastered} 题 | 最近更新：{data.updated}"
    )
    lines.append("")
    grouped = data.entries_by_type()
    for qtype in config.ALL_TYPES:
        entries = grouped.get(qtype, [])
        if not entries:
            continue
        lines.append(f"## {qtype}")
        lines.append("")
        lines.append(
            "| ID | 考点 | 错误原因 | 答案 | 来源 | 阶段 | 下次复习 | 状态 |"
        )
        lines.append(
            "|----|------|----------|------|------|------|----------|------|"
        )
        for e in entries:
            lines.append(_entry_to_row(e))
        lines.append("")
    index_path.write_text("\n".join(lines), encoding="utf-8")


def next_id(index_path: Path | None = None) -> str:
    data = load_index(index_path)
    return f"错题-{data.last_id + 1:03d}"


def add_entry(card: MistakeCard, index_path: Path | None = None) -> None:
    data = load_index(index_path)
    data.last_id += 1
    entry = IndexEntry(
        id=card.id,
        knowledge_point=card.knowledge_point,
        error_reason=card.error_reason,
        correct_answer=card.correct_answer,
        source=card.source,
        review_stage=card.review_stage,
        next_review=card.next_review,
        status=card.status,
        question_type=card.question_type,
    )
    data.entries.append(entry)
    save_index(data, index_path)


def update_entry(
    mistake_id: str,
    review_stage: int,
    next_review: str,
    status: str,
    index_path: Path | None = None,
) -> None:
    data = load_index(index_path)
    for e in data.entries:
        if e.id == mistake_id:
            e.review_stage = review_stage
            e.next_review = next_review
            e.status = status
            break
    save_index(data, index_path)


def find_entry(mistake_id: str, index_path: Path | None = None) -> Optional[IndexEntry]:
    data = load_index(index_path)
    for e in data.entries:
        if e.id == mistake_id:
            return e
    return None


def delete_entry(mistake_id: str, index_path: Path | None = None) -> bool:
    data = load_index(index_path)
    before = len(data.entries)
    data.entries = [e for e in data.entries if e.id != mistake_id]
    if len(data.entries) < before:
        save_index(data, index_path)
        return True
    return False


def get_due_entries(today: str, index_path: Path | None = None) -> List[IndexEntry]:
    data = load_index(index_path)
    due = [
        e for e in data.entries
        if e.status != "mastered" and e.next_review <= today
    ]
    return due
''',
    "mistake_manager.py": r'''"""错题 CRUD 管理器。"""
from __future__ import annotations

import json
import shutil
from pathlib import Path
from typing import List, Optional

import config
import index_manager
import scheduler
from models import MistakeCard, review_history_to_table


_FRONTMATTER_RE = re.compile(r"^---\s*\n(.*?)\n---\s*\n", re.DOTALL)


def _parse_md_frontmatter(text: str) -> dict:
    m = _FRONTMATTER_RE.match(text)
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


def load_card(mistake_id: str, question_type: str) -> Optional[MistakeCard]:
    md_path = config.MISTAKE_ROOT / question_type / f"{mistake_id}.md"
    if not md_path.exists():
        return None
    text = md_path.read_text(encoding="utf-8")
    meta = _parse_md_frontmatter(text)
    return MistakeCard(
        id=meta["id"],
        date=meta["date"],
        question_type=meta["题型"],
        knowledge_point=meta["考点"],
        error_reason=meta["错误原因"],
        correct_answer=meta["正确答案"],
        source=meta["来源"],
        review_stage=meta.get("review_stage", 0),
        next_review=meta.get("next_review", ""),
        review_history=meta.get("review_history", []),
        status=meta.get("status", "pending"),
        screenshot=f"screenshots/{mistake_id}.png",
    )


def create_mistake(
    question_type: str,
    knowledge_point: str,
    error_reason: str,
    correct_answer: str,
    source: str,
    screenshot_src: Optional[Path] = None,
    ocr_text: Optional[str] = None,
) -> MistakeCard:
    if question_type not in config.ALL_TYPES:
        raise ValueError(f"题型 {question_type} 不在支持列表中: {config.ALL_TYPES}")
    config.ensure_dirs()
    new_id = index_manager.next_id()
    today = scheduler.today_str()
    type_dir = config.MISTAKE_ROOT / question_type
    screenshot_dir = type_dir / "screenshots"
    type_dir.mkdir(parents=True, exist_ok=True)
    screenshot_dir.mkdir(parents=True, exist_ok=True)
    screenshot_rel = f"screenshots/{new_id}.png"
    screenshot_dst = screenshot_dir / f"{new_id}.png"
    if screenshot_src and Path(screenshot_src).exists():
        shutil.copy2(screenshot_src, screenshot_dst)
    card = MistakeCard(
        id=new_id,
        date=today,
        question_type=question_type,
        knowledge_point=knowledge_point,
        error_reason=error_reason,
        correct_answer=correct_answer,
        source=source,
        review_stage=0,
        next_review=today,
        review_history=[],
        status="pending",
        screenshot=screenshot_rel,
        ocr_text=ocr_text,
    )
    md_path = type_dir / f"{new_id}.md"
    md_path.write_text(_card_to_md(card), encoding="utf-8")
    index_manager.add_entry(card)
    return card


def _card_to_md(card: MistakeCard) -> str:
    history_str = json.dumps(card.review_history, ensure_ascii=False)
    history_table = review_history_to_table(card.review_history)
    ocr_section = ""
    if card.ocr_text:
        ocr_section = f"""## OCR 文本
```
{card.ocr_text}
```
"""
    screenshot_ref = f"![[{card.screenshot}]]" if card.screenshot else ""
    return f"""---
id: {card.id}
date: {card.date}
题型: {card.question_type}
考点: {card.knowledge_point}
错误原因: {card.error_reason}
正确答案: {card.correct_answer}
来源: {card.source}
review_stage: {card.review_stage}
next_review: {card.next_review}
review_history: {history_str}
status: {card.status}
---

{ocr_section}
{screenshot_ref}

## 标签
- **题型**：{card.question_type}
- **考点**：{card.knowledge_point}
- **错误原因**：{card.error_reason}
- **正确答案**：{card.correct_answer}
- **来源**：{card.source}

## 复习记录
| 日期 | 结果 | 阶段 | 下次复习 |
|------|------|------|----------|
{history_table}
"""


def update_review_state(
    mistake_id: str,
    question_type: str,
    passed: bool,
    review_stage: int,
    next_review: str,
    status: str,
    review_date: str,
    old_stage: int,
) -> None:
    md_path = config.MISTAKE_ROOT / question_type / f"{mistake_id}.md"
    if not md_path.exists():
        return
    card = load_card(mistake_id, question_type)
    if card is None:
        return
    card.review_stage = review_stage
    card.next_review = next_review
    card.status = status
    card.review_history.append(
        {
            "date": review_date,
            "result": "pass" if passed else "fail",
            "stage": old_stage,
            "next_review": next_review,
        }
    )
    md_path.write_text(_card_to_md(card), encoding="utf-8")
    index_manager.update_entry(mistake_id, review_stage, next_review, status)


def delete_mistake(mistake_id: str, question_type: str) -> bool:
    md_path = config.MISTAKE_ROOT / question_type / f"{mistake_id}.md"
    png_path = config.MISTAKE_ROOT / question_type / "screenshots" / f"{mistake_id}.png"
    deleted = False
    if md_path.exists():
        md_path.unlink()
        deleted = True
    if png_path.exists():
        png_path.unlink()
    index_manager.delete_entry(mistake_id)
    return deleted


def modify_mistake(
    mistake_id: str,
    question_type: str,
    field: str,
    value: str,
) -> Optional[MistakeCard]:
    card = load_card(mistake_id, question_type)
    if card is None:
        return None
    field_map = {
        "knowledge_point": "knowledge_point",
        "error_reason": "error_reason",
        "correct_answer": "correct_answer",
        "source": "source",
        "question_type": "question_type",
    }
    if field not in field_map:
        raise ValueError(f"不支持的修改字段: {field}")
    attr = field_map[field]
    old_type = card.question_type
    setattr(card, attr, value)
    if attr == "question_type" and value != old_type:
        old_md = config.MISTAKE_ROOT / old_type / f"{mistake_id}.md"
        old_png = config.MISTAKE_ROOT / old_type / "screenshots" / f"{mistake_id}.png"
        new_md = config.MISTAKE_ROOT / value / f"{mistake_id}.md"
        new_png = config.MISTAKE_ROOT / value / "screenshots" / f"{mistake_id}.png"
        new_md.parent.mkdir(parents=True, exist_ok=True)
        new_png.parent.mkdir(parents=True, exist_ok=True)
        if old_md.exists():
            shutil.move(str(old_md), str(new_md))
        if old_png.exists():
            shutil.move(str(old_png), str(new_png))
        card.screenshot = f"screenshots/{mistake_id}.png"
        index_manager.delete_entry(mistake_id)
        index_manager.add_entry(card)
    else:
        md_path = config.MISTAKE_ROOT / card.question_type / f"{mistake_id}.md"
        md_path.write_text(_card_to_md(card), encoding="utf-8")
        index_manager.update_entry(
            mistake_id,
            card.review_stage,
            card.next_review,
            card.status,
        )
    return card


def get_screen_path(mistake_id: str, question_type: str) -> Path:
    return config.MISTAKE_ROOT / question_type / "screenshots" / f"{mistake_id}.png"


def list_all_type_dirs() -> List[Path]:
    return [config.MISTAKE_ROOT / t for t in config.ALL_TYPES]
''',
    "review_engine.py": r'''"""错题复习引擎。

把 SKILL.md Workflow 2（复习模式）脚本化：
- 扫描到期题目
- 按规则排序并分批
- 判题（描述性回答 = 通过）
- 调用 scheduler 与 mistake_manager 更新状态
"""
from __future__ import annotations

import random
from dataclasses import dataclass
from datetime import date
from typing import List, Tuple

import config
import index_manager
import mistake_manager
import scheduler
from models import IndexEntry, ReviewResult


@dataclass
class ReviewSessionItem:
    entry: IndexEntry
    screenshot_path: str


def _parse_answers(text: str) -> dict:
    """解析用户回复，如 '1.B 2.C 3.不会 4.a 5.不记得'。

    返回 {题序号: 原始字符串}
    """
    answers = {}
    if not text:
        return answers
    parts = text.split()
    for part in parts:
        part = part.strip()
        if not part:
            continue
        # 支持 1.B / 1、B / 1,B 等分隔符
        for sep in ".．，,、":
            if sep in part and not part.startswith(sep):
                left, right = part.split(sep, 1)
                try:
                    idx = int(left)
                    answers[idx] = right.strip()
                except ValueError:
                    pass
                break
    return answers


def _is_forget(answer: str) -> bool:
    """判断是否表示不记得/不会/跳过。"""
    if not answer:
        return True
    forget_keywords = ["不记得", "忘了", "不会", "跳过", "不知道", "没印象"]
    a = answer.strip().lower()
    for kw in forget_keywords:
        if kw in a:
            return True
    if len(a) <= 1:
        # 单个字母可能是误触，但也可能是选项；按描述性判题原则，单个字母=没实质内容
        return True
    return False


def select_due_items(
    today: str,
) -> List[IndexEntry]:
    """获取今天到期待复习题目，并按优先级排序。"""
    due = index_manager.get_due_entries(today)
    # 排序：next_review 越早越前；相同则 stage 越小越前；相同则随机
    due.sort(key=lambda e: (e.next_review, e.review_stage, random.random()))
    return due


def take_batch(
    due: List[IndexEntry],
    batch_size: int | None = None,
) -> List[ReviewSessionItem]:
    if batch_size is None:
        batch_size = config.REVIEW_BATCH_SIZE
    selected = due[:batch_size]
    items = []
    for e in selected:
        scr = config.MISTAKE_ROOT / e.question_type / f"screenshots/{e.id}.png"
        items.append(
            ReviewSessionItem(
                entry=e,
                screenshot_path=str(scr),
            )
        )
    return items


def review_batch(
    items: List[ReviewSessionItem],
    answers_text: str,
    review_date: str | None = None,
) -> Tuple[List[ReviewResult], str]:
    """判定一组题目，返回结果列表和总结的 markdown 文本。

    Args:
        items: 本次复习的题目
        answers_text: 用户回复，如 '1.B 2.C ...'
        review_date: 复习日期，默认今天

    Returns:
        (results, summary_markdown)
    """
    if review_date is None:
        review_date = scheduler.today_str()

    answers = _parse_answers(answers_text)
    results: List[ReviewResult] = []
    summary_lines = []
    summary_lines.append("## 📊 本次复习结果")
    summary_lines.append("")

    for idx, item in enumerate(items, start=1):
        entry = item.entry
        answer = answers.get(idx, "")
        passed = not _is_forget(answer)

        old_stage = entry.review_stage
        if passed:
            new_stage, next_review, mastered = scheduler.pass_review(
                old_stage, date.fromisoformat(review_date)
            )
            new_status = "mastered" if mastered else "pending"
        else:
            new_stage, next_review = scheduler.fail_review(
                date.fromisoformat(review_date)
            )
            new_status = "pending"
            mastered = False

        # 更新文件
        mistake_manager.update_review_state(
            entry.id,
            entry.question_type,
            passed,
            new_stage,
            next_review,
            new_status,
            review_date,
            old_stage,
        )

        result = ReviewResult(
            mistake_id=entry.id,
            passed=passed,
            old_stage=old_stage,
            new_stage=new_stage,
            next_review=next_review,
            mastered=mastered,
        )
        results.append(result)

        icon = "✅" if passed else "❌"
        if mastered:
            detail = f"{icon} 题{idx} {entry.id} → 🎉已掌握"
        elif passed:
            detail = f"{icon} 题{idx} {entry.id} → 阶段 {old_stage}→{new_stage}，下次复习 {next_review}"
        else:
            detail = f"{icon} 题{idx} {entry.id} → 错误，重置，明天再复习"
        summary_lines.append(detail)

    total = len(results)
    passed_count = sum(1 for r in results if r.passed)
    summary_lines.append("")
    summary_lines.append(f"**通过率**：{passed_count}/{total} ({passed_count/total*100:.0f}%)")
    return results, "\n".join(summary_lines)


def format_review_prompt(items: List[ReviewSessionItem], group_no: int = 1) -> str:
    """生成复习提示文本。"""
    lines = [f"📝 错题复习 · 第 {group_no} 组", ""]
    for idx, item in enumerate(items, start=1):
        e = item.entry
        lines.append(f"【题{idx}】{e.knowledge_point} · {e.source}")
        lines.append(f"截图：{item.screenshot_path}")
        lines.append("你的答案/思路？（不记得就说「不记得」）")
        lines.append("")
    lines.append("请用格式回复：1.B 2.C 3.A ... 或写思路描述")
    return "\n".join(lines)
''',
}

for filename, content in FILES.items():
    path = SCRIPTS / filename
    path.write_text(content, encoding="utf-8")
    print(f"created {path}")

print("setup done")

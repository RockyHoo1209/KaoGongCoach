"""错题 CRUD 管理器（V3：SQLite 为主存储）。

核心原则：
1. ID 生成、卡片读写、复习状态更新均优先使用 SQLite
2. .md 文件保留为 Obsidian 兼容，双向同步
3. index-*.md 索引文件保留为兼容层
"""
from __future__ import annotations

import json
import re
import shutil
from pathlib import Path
from typing import List, Optional

import config
import index_manager
import scheduler
from models import MistakeCard, review_history_to_table
from database import (
    get_next_id_db,
    get_mistake as db_get_mistake,
    insert_mistake as db_insert_mistake,
    update_review_state_db as db_update_review_state,
    delete_mistake_db as db_delete_mistake,
    update_mistake_field as db_update_field,
    init_db as db_init_db,
)


_FRONTMATTER_RE = re.compile(r"^---\s*\n(.*?)\n---\s*\n", re.DOTALL)


def _parse_md_frontmatter(text: str) -> dict:
    """解析 .md 文件 frontmatter（兼容保留）。"""
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
            elif k == "tags":
                try:
                    json.loads(v)
                    result[k] = v
                except (json.JSONDecodeError, ValueError):
                    result[k] = '{"tag":[]}'
            else:
                result[k] = v
    return result


def load_card(mistake_id: str, question_type: str) -> Optional[MistakeCard]:
    """V3：优先从 SQLite 读取，降级到 .md 文件。"""
    # 1) SQLite 优先
    row = db_get_mistake(mistake_id)
    if row:
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
            review_history=json.loads(row.get("review_history", "[]")),
            status=row.get("status", "pending"),
            screenshot=row.get("image_path", ""),
            image_path=row.get("image_path", ""),
            tags=row.get("tags", '{"tag":[]}'),
        )
    # 2) 降级到 .md 文件
    md_path = config.MISTAKE_ROOT / question_type / f"{mistake_id}.md"
    if not md_path.exists():
        return None
    text = md_path.read_text(encoding="utf-8")
    meta = _parse_md_frontmatter(text)
    card = MistakeCard(
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
        tags=meta.get("tags", '{"tag":[]}'),
        image_path=meta.get("image_path", f"screenshots/{mistake_id}.png"),
    )
    # 自动同步回 SQLite
    db_init_db()
    db_insert_mistake(card)
    return card


def create_mistake(
    question_type: str,
    knowledge_point: str,
    error_reason: str,
    correct_answer: str,
    source: str,
    screenshot_src: Optional[Path] = None,
    ocr_text: Optional[str] = None,
    tags: str = '{"tag":[]}',
) -> MistakeCard:
    if question_type not in config.ALL_TYPES:
        raise ValueError(f"题型 {question_type} 不在支持列表中: {config.ALL_TYPES}")
    config.ensure_dirs()
    # V3: SQLite 为主 ID 生成源
    new_id = get_next_id_db()
    today = scheduler.today_str()
    type_dir = config.MISTAKE_ROOT / question_type
    screenshot_dir = type_dir / "screenshots"
    type_dir.mkdir(parents=True, exist_ok=True)
    screenshot_dir.mkdir(parents=True, exist_ok=True)
    screenshot_rel = f"screenshots/{new_id}.png"
    screenshot_dst = screenshot_dir / f"{new_id}.png"
    if screenshot_src and Path(screenshot_src).exists():
        shutil.copy2(screenshot_src, screenshot_dst)
    # 如果提供了绝对路径的截图，直接使用原路径
    image_path = str(screenshot_src) if screenshot_src and Path(screenshot_src).exists() else screenshot_rel
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
        screenshot=image_path,
        ocr_text=ocr_text,
        tags=tags,
        image_path=image_path,
    )
    # V3: SQLite 优先写入
    db_init_db()
    db_insert_mistake(card)
    # 保留 .md 和索引更新用于 Obsidian 兼容
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
`
{card.ocr_text}
`
"""
    screenshot_ref = f"![[{card.image_path}]]" if card.image_path else ""
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
tags: {card.tags}
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
    # V3: SQLite 优先更新
    db_update_review_state(
        mistake_id, review_stage, next_review, status,
        passed, review_date, old_stage,
    )
    # 保留 .md 和索引更新用于 Obsidian 兼容
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
    md_path = config.MISTAKE_ROOT / question_type / f"{mistake_id}.md"
    md_path.write_text(_card_to_md(card), encoding="utf-8")
    index_manager.update_entry(mistake_id, review_stage, next_review, status, qtype=question_type)


def delete_mistake(mistake_id: str, question_type: str) -> bool:
    # V3: SQLite 优先删除
    db_delete_mistake(mistake_id)
    # 保留文件删除用于 Obsidian 兼容
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
        # 同步更新索引中的可变字段，保证 index.md 与 .md 一致
        index_manager.delete_entry(mistake_id)
        index_manager.add_entry(card)
    # V3: SQLite 更新
    db_update_field(mistake_id, field, value)
    return card


def get_screen_path(mistake_id: str, question_type: str) -> Path:
    return config.MISTAKE_ROOT / question_type / "screenshots" / f"{mistake_id}.png"


def list_all_type_dirs() -> List[Path]:
    return [config.MISTAKE_ROOT / t for t in config.ALL_TYPES]

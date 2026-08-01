"""数据模型：错题、知识点、索引等数据类。

统一用 dataclass 表示，各管理器模块读写时通过这些类序列化/反序列化。
"""
from __future__ import annotations

from dataclasses import dataclass, field, asdict
from datetime import date, datetime
from typing import List, Optional


@dataclass
class MistakeCard:
    """错题卡片（对应一个 .md 文件）。"""

    id: str  # 错题-001
    date: str  # 入库日期 YYYY-MM-DD
    question_type: str  # 题型，如 言语理解
    knowledge_point: str  # 考点
    error_reason: str  # 错误原因
    correct_answer: str  # 正确答案
    source: str  # 来源
    review_stage: int = 0
    next_review: str = ""  # YYYY-MM-DD
    review_history: list = field(default_factory=list)
    status: str = "pending"  # pending / mastered
    screenshot: Optional[str] = None  # 截图相对路径 screenshots/错题-XXX.png
    ocr_text: Optional[str] = None  # OCR 提取的题干文本（批量导入时填）
    tags: str = '{"tag":[]}'  # V3: 用户自定义标签 JSON 格式
    image_path: str = ""  # V3: 错题图片路径（同 screenshot，冗余兼容）

    @property
    def md_filename(self) -> str:
        return f"{self.id}.md"

    @property
    def md_path(self) -> str:
        return f"{self.question_type}/{self.id}.md"

    @property
    def screenshot_path(self) -> str:
        return f"{self.question_type}/screenshots/{self.id}.png"


@dataclass
class KnowledgeCard:
    """知识点卡片。"""

    id: str  # 知识-001
    date: str
    card_type: str  # 公式 / 考法 / 总结
    question_type: str  # 所属题型
    knowledge_point: str  # 考点
    front: str  # 正面内容（题目/公式名）
    back: str  # 反面内容（答案/推导/适用条件）
    source: str = ""
    review_stage: int = 0
    next_review: str = ""
    review_history: list = field(default_factory=list)
    status: str = "pending"


@dataclass
class IndexEntry:
    """index.md 表格中的一行。"""

    id: str
    knowledge_point: str
    error_reason: str
    correct_answer: str
    source: str
    review_stage: int
    next_review: str
    status: str
    question_type: str = ""  # 由所在章节推断
    tags: str = '{"tag":[]}'  # V3: 标签 JSON

    @property
    def stage_str(self) -> str:
        return f"{self.review_stage}/6"

    @property
    def status_emoji(self) -> str:
        if self.status == "mastered":
            return "✅已掌握"
        return "⏳待复习"


@dataclass
class IndexData:
    """整个 index.md 的结构化表示。"""

    last_id: int = 0
    total: int = 0
    pending: int = 0
    mastered: int = 0
    updated: str = ""
    entries: List[IndexEntry] = field(default_factory=list)

    def entries_by_type(self) -> dict:
        """按题型分组返回条目。"""
        grouped: dict = {}
        for e in self.entries:
            grouped.setdefault(e.question_type, []).append(e)
        return grouped


@dataclass
class ReviewResult:
    """一次复习判题的结果。"""

    mistake_id: str
    passed: bool
    old_stage: int
    new_stage: int
    next_review: str
    mastered: bool = False


# ---------------------------------------------------------------------------
# 序列化辅助
# ---------------------------------------------------------------------------


def mistake_to_frontmatter(m: MistakeCard) -> str:
    """把 MistakeCard 序列化为 markdown frontmatter + 正文。"""
    import json

    history_str = json.dumps(m.review_history, ensure_ascii=False)
    return f"""---
id: {m.id}
date: {m.date}
题型: {m.question_type}
考点: {m.knowledge_point}
错误原因: {m.error_reason}
正确答案: {m.correct_answer}
来源: {m.source}
review_stage: {m.review_stage}
next_review: {m.next_review}
review_history: {history_str}
status: {m.status}
---

![[{m.screenshot}]]

## 标签
- **题型**：{m.question_type}
- **考点**：{m.knowledge_point}
- **错误原因**：{m.error_reason}
- **正确答案**：{m.correct_answer}
- **来源**：{m.source}

## 复习记录
| 日期 | 结果 | 阶段 | 下次复习 |
|------|------|------|----------|
（暂无）
"""


def review_history_to_table(history: list) -> str:
    """把 review_history 列表渲染成 markdown 表格行。"""
    if not history:
        return "（暂无）"
    lines = []
    for h in history:
        result = "✅通过" if h.get("result") == "pass" else "❌失败"
        lines.append(
            f"| {h.get('date', '')} | {result} | {h.get('stage', '')} | {h.get('next_review', '')} |"
        )
    return "\n".join(lines)

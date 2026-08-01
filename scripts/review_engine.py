"""错题复习引擎。

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

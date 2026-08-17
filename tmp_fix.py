"""错题复习引擎（V3：SQLite 为主存储）。

把 SKILL.md Workflow 2（复习模式）脚本化：
- 从 SQLite 查询到期题目
- 按规则排序并分批
- 判题（描述性回答 = 通过）
- 调用 scheduler 与数据库更新状态
"""
from __future__ import annotations

import random
from dataclasses import dataclass
from datetime import date
from pathlib import Path
from typing import Any, Dict, List, Tuple

import config
import database as db
import mistake_manager
import scheduler


@dataclass
class ReviewSessionItem:
    """复习会话中的一道题。"""
    mistake_id: str
    question_type: str
    ebbinghaus_value: int
    next_review: str
    image_path: str
    knowledge_point: str


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
        return True
    return False


def _row_to_item(row: Dict[str, Any]) -> ReviewSessionItem:
   """将 SQLite 行转换为 ReviewSessionItem。"""
    img = row.get("image_path", "")
    if img and not os.path.isabs(img):
        base = config.MISTAKE_ROOT / row.get("question_type", "")
        img = str(base / img)
    return ReviewSessionItem(
       mistake_id=row["id"],
       question_type=row.get("question_type", ""),
       ebbinghaus_value=row.get("ebbinghaus_value", 0),
       next_review=row.get("next_review", ""),
       image_path=row.get("image_path", ""),
       knowledge_point=row.get("knowledge_point", ""),
   )


def select_due_items(
    today: str,
) -> List[ReviewSessionItem]:
    """获取今天到期待复习题目，并按优先级排序。"""
    rows = db.get_due_entries_db(today)
    # 排序：next_review 越早越前；相同则 stage 越小越前；相同则随机
    rows.sort(key=lambda r: (r["next_review"], r["ebbinghaus_value"], random.random()))
    return [_row_to_item(r) for r in rows]


def take_batch(
    due: List[ReviewSessionItem],
    batch_size: int | None = None,
) -> List[ReviewSessionItem]:
    if batch_size is None:
        batch_size = config.REVIEW_BATCH_SIZE
    selected = due[:batch_size]
    return selected


def format_review_prompt(items: List[ReviewSessionItem], group_no: int = 1) -> str:
    """生成复习提示文本（V3版：输出题号列表+直接嵌入图片内容）。

    V3遵循用户要求：出题时只需要给出题号列表和对应图片路径的图片。
    文字描述由用户从截图中自行阅读，不需要额外输出考点/来源等信息。
    图片通过Markdown语法嵌入，便于在对话中直接显现
    """
    lines = [f"📝 错题复习 · 第 {group_no} 组", ""]
    for idx, item in enumerate(items, start=1):
        lines.append(f"【题{idx}】{item.mistake_id}")
        img_tag = f"![{item.mistake_id}]({item.image_path})" if item.image_path else "(无截图)"
        lines.append(img_tag)
        lines.append("")
        lines.append("你的答案/思路？（不记得就说「不记得」）")
        lines.append("")
    lines.append("请回忆答案并用格式回复：1.B 2.C 3.A ...（或写思路描述，不记得就说「不记得」）")
    return "\n".join(lines)


def review_batch(
    items: List[ReviewSessionItem],
    answers_text: str,
    review_date: str | None = None,
) -> Tuple[List[Dict[str, Any]], str]:
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
    results: List[Dict[str, Any]] = []
    summary_lines = []
    summary_lines.append("## 📊 本次复习结果")
    summary_lines.append("")

    for idx, item in enumerate(items, start=1):
        answer = answers.get(idx, "")
        passed = not _is_forget(answer)

        old_stage = item.ebbinghaus_value
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

        # V3: SQLite 直接更新
        db.update_review_state_db(
            item.mistake_id, new_stage, next_review, new_status,
            passed, review_date, old_stage,
        )
        # 更新文件用于 Obsidian 兼容
        mistake_manager.update_review_state(
            item.mistake_id, item.question_type,
            passed, new_stage, next_review, new_status,
            review_date, old_stage,
        )

        result = {
            "mistake_id": item.mistake_id,
            "passed": passed,
            "old_stage": old_stage,
            "new_stage": new_stage,
            "next_review": next_review,
            "mastered": mastered,
        }
        results.append(result)

        icon = "✅" if passed else "❌"
        if mastered:
            detail = f"{icon} 题{idx} {item.mistake_id} → 🎉已掌握"
        elif passed:
            detail = f"{icon} 题{idx} {item.mistake_id} → 阶段 {old_stage}→{new_stage}，下次复习 {next_review}"
        else:
            detail = f"{icon} 题{idx} {item.mistake_id} → 错误，重置，明天再复习"
        summary_lines.append(detail)

    total = len(results)
    passed_count = sum(1 for r in results if r["passed"])
    summary_lines.append("")
    summary_lines.append(f"**通过率**：{passed_count}/{total} ({passed_count/total*100:.0f}%)")
    return results, "\n".join(summary_lines)

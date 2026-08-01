"""艾宾浩斯遗忘曲线间隔计算。

间隔表与 SKILL.md 完全一致：
    stage 0 → 当天
    stage 1 → +1天
    stage 2 → +2天
    stage 3 → +4天
    stage 4 → +7天
    stage 5 → +15天
    stage 6 → 已掌握

答错 → 重置到 stage 0，明天复习。
"""
from __future__ import annotations

from datetime import date, datetime, timedelta

import config


def today_str() -> str:
    return date.today().isoformat()


def parse_date(s: str) -> date:
    return datetime.strptime(s, "%Y-%m-%d").date()


def compute_next_review(stage: int, base_date: date | None = None) -> str:
    """根据当前 stage 计算通过后的下次复习日期。

    Args:
        stage: 通过前的阶段（0-5）。通过后变为 stage+1。
        base_date: 基准日期，默认今天。

    Returns:
        下次复习日期字符串 YYYY-MM-DD
    """
    if base_date is None:
        base_date = date.today()

    # 通过后进入 stage+1，间隔取新 stage 对应的天数
    new_stage = stage + 1
    if new_stage >= config.MASTERED_STAGE:
        # 已掌握，给一个很远的日期（实际不会被抽到）
        return (base_date + timedelta(days=3650)).isoformat()

    interval = config.EBBINGHAUS_INTERVALS[new_stage]
    return (base_date + timedelta(days=interval)).isoformat()


def pass_review(
    current_stage: int, base_date: date | None = None
) -> tuple[int, str, bool]:
    """通过一次复习。

    Returns:
        (new_stage, next_review_date, is_mastered)
    """
    if base_date is None:
        base_date = date.today()

    new_stage = current_stage + 1
    mastered = new_stage >= config.MASTERED_STAGE
    next_review = compute_next_review(current_stage, base_date)
    return new_stage, next_review, mastered


def fail_review(base_date: date | None = None) -> tuple[int, str]:
    """失败一次复习：重置 stage 0，明天复习。

    Returns:
        (0, next_review_date)
    """
    if base_date is None:
        base_date = date.today()
    return 0, (base_date + timedelta(days=1)).isoformat()


def fuzzy_review(
    current_stage: int, base_date: date | None = None
) -> tuple[int, str]:
    """模糊：stage 不变，缩短下次间隔（取当前 stage 与前一 stage 的中值）。

    Returns:
        (stage, next_review_date)
    """
    if base_date is None:
        base_date = date.today()

    # stage 不变，间隔取当前 stage 与 stage-1 的平均值
    if current_stage <= 1:
        interval = 1
    else:
        interval = (
            config.EBBINGHAUS_INTERVALS[current_stage]
            + config.EBBINGHAUS_INTERVALS[current_stage - 1]
        ) // 2
    return current_stage, (base_date + timedelta(days=interval)).isoformat()
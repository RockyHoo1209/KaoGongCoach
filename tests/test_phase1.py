"""Phase 1 联调测试：不依赖真实 Obsidian 目录，使用临时根目录验证核心流程。"""
from __future__ import annotations

import os
import shutil
import sys
import tempfile
from datetime import date, timedelta
from pathlib import Path

# 保证 import scripts 下模块
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))

import config
import index_manager
import mistake_manager
import review_engine
import scheduler


def _temp_root() -> Path:
    return Path(tempfile.mkdtemp(prefix="exam_skill_test_"))


def _setup_env(temp_root: Path) -> None:
    os.environ["EXAM_OBSIDIAN_ROOT"] = str(temp_root)
    # 避免加载外部配置造成交叉污染
    config.OBSIDIAN_ROOT = temp_root
    config.MISTAKE_ROOT = temp_root / "错题库"
    config.KNOWLEDGE_ROOT = temp_root / "知识点库"
    config.METHOD_ROOT = temp_root / "方法论"
    config.INDEX_FILE = config.MISTAKE_ROOT / "index.md"
    config.KNOWLEDGE_INDEX_FILE = config.KNOWLEDGE_ROOT / "index.md"


def test_create_mistake() -> None:
    temp = _temp_root()
    _setup_env(temp)
    try:
        card = mistake_manager.create_mistake(
            question_type="言语理解",
            knowledge_point="逻辑填空-语境分析",
            error_reason="知识点盲区",
            correct_answer="B",
            source="2025国考行测",
        )
        assert card.id == "错题-001", f"期望 错题-001，得到 {card.id}"
        md_path = config.MISTAKE_ROOT / "言语理解" / "错题-001.md"
        assert md_path.exists(), "错题 markdown 文件未创建"
        data = index_manager.load_index()
        assert data.total == 1, f"期望 total=1，得到 {data.total}"
        assert data.pending == 1
        entry = data.entries[0]
        assert entry.question_type == "言语理解"
        assert entry.status == "pending"
        print("✅ test_create_mistake passed")
    finally:
        shutil.rmtree(temp, ignore_errors=True)


def test_review_lifecycle() -> None:
    temp = _temp_root()
    _setup_env(temp)
    try:
        # 创建 3 道题，复习日期设为当天
        cards = []
        for i in range(3):
            card = mistake_manager.create_mistake(
                question_type="判断推理",
                knowledge_point="加强削弱",
                error_reason="方法不会",
                correct_answer="C",
                source=f"模拟卷-{i+1}",
            )
            cards.append(card)

        today = scheduler.today_str()
        due = review_engine.select_due_items(today)
        assert len(due) == 3, f"期望 3 道到期题，得到 {len(due)}"

        items = review_engine.take_batch(due, batch_size=2)
        assert len(items) == 2, "应取出 2 题"

        answers = "1.外地人作担保无效 2.加强论点 3.不记得"
        results, summary = review_engine.review_batch(items, answers, today)
        assert len(results) == 2
        assert results[0].passed is True
        assert results[0].new_stage == 1
        assert results[1].passed is True
        assert results[2 if False else 1] is not None  # noqa: pointless, 占位提示有 2 个结果
        assert results[1].new_stage == 1

        data = index_manager.load_index()
        pending = sum(1 for e in data.entries if e.status == "pending")
        mastered = sum(1 for e in data.entries if e.status == "mastered")
        assert pending == 3 and mastered == 0, "未到 stage6 不应已掌握"

        print(f"✅ test_review_lifecycle passed\n{summary}")
    finally:
        shutil.rmtree(temp, ignore_errors=True)


def test_mastered_flow() -> None:
    """手动把一道题推进到 stage6，验证 mastered 状态。"""
    temp = _temp_root()
    _setup_env(temp)
    try:
        card = mistake_manager.create_mistake(
            question_type="数量关系",
            knowledge_point="行程问题-相遇追及",
            error_reason="计算失误",
            correct_answer="A",
            source="粉笔模考",
        )
        today = date.today()
        # 连续 6 次通过
        for stage in range(6):
            cur = index_manager.load_index().entries[0]
            assert cur.review_stage == stage
            new_stage, next_review, mastered = scheduler.pass_review(stage, today)
            mistake_manager.update_review_state(
                card.id,
                card.question_type,
                passed=True,
                review_stage=new_stage,
                next_review=next_review,
                status="mastered" if mastered else "pending",
                review_date=today.isoformat(),
                old_stage=stage,
            )
            today += timedelta(days=1)
            if mastered:
                break

        data = index_manager.load_index()
        assert data.mastered == 1, f"期望 mastered=1，得到 {data.mastered}"
        assert data.pending == 0
        due = review_engine.select_due_items(scheduler.today_str())
        assert len(due) == 0, "已掌握不应出现在到期队列"
        print("✅ test_mastered_flow passed")
    finally:
        shutil.rmtree(temp, ignore_errors=True)


def test_fail_reset() -> None:
    """失败后应重置 stage 为 0，明天复习。"""
    temp = _temp_root()
    _setup_env(temp)
    try:
        card = mistake_manager.create_mistake(
            question_type="资料分析",
            knowledge_point="增长率计算",
            error_reason="公式不熟",
            correct_answer="D",
            source="2024省考",
        )
        # 先通过一次到 stage1
        today = date.today()
        mistake_manager.update_review_state(
            card.id,
            card.question_type,
            passed=True,
            review_stage=1,
            next_review=(today + timedelta(days=1)).isoformat(),
            status="pending",
            review_date=today.isoformat(),
            old_stage=0,
        )
        # 然后失败
        tomorrow = today + timedelta(days=1)
        mistake_manager.update_review_state(
            card.id,
            card.question_type,
            passed=False,
            review_stage=0,
            next_review=(tomorrow + timedelta(days=1)).isoformat(),
            status="pending",
            review_date=tomorrow.isoformat(),
            old_stage=1,
        )
        data = index_manager.load_index()
        entry = data.entries[0]
        assert entry.review_stage == 0
        assert entry.next_review == (tomorrow + timedelta(days=1)).isoformat()
        print("✅ test_fail_reset passed")
    finally:
        shutil.rmtree(temp, ignore_errors=True)


def test_modify_and_delete() -> None:
    temp = _temp_root()
    _setup_env(temp)
    try:
        card = mistake_manager.create_mistake(
            question_type="常识判断",
            knowledge_point="宪法",
            error_reason="没记住",
            correct_answer="A",
            source="半月谈",
        )
        updated = mistake_manager.modify_mistake(
            card.id, "常识判断", "knowledge_point", "刑法"
        )
        assert updated is not None
        assert updated.knowledge_point == "刑法"

        entry = index_manager.find_entry(card.id)
        assert entry is not None and entry.knowledge_point == "刑法"

        ok = mistake_manager.delete_mistake(card.id, "常识判断")
        assert ok is True
        entry = index_manager.find_entry(card.id)
        assert entry is None
        data = index_manager.load_index()
        assert data.total == 0
        print("✅ test_modify_and_delete passed")
    finally:
        shutil.rmtree(temp, ignore_errors=True)


if __name__ == "__main__":
    test_create_mistake()
    test_review_lifecycle()
    test_mastered_flow()
    test_fail_reset()
    test_modify_and_delete()
    print("\n🎉 Phase 1 所有联调测试通过")

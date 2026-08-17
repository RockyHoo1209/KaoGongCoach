"""V3 综合集成测试：验证 SQLite 作为主存储的完整功能。

覆盖场景：
- Phase 2: 复合 index.md（## 题型标题 + 表格行）导入
- Phase 1: index-{题型}.md 文件导入
- 混合导入时去重
- 图片路径解析
- 标签 CRUD（JSON1）
- 组合搜索
- 复习全生命周期
- 边缘情况：空库、缺图
"""
from __future__ import annotations

import json
import os
import shutil
import sys
import tempfile
from datetime import date, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))

import config
import database as db
import mistake_manager
import review_engine
import scheduler


def _setup_env(temp_root: Path) -> None:
    """设置临时环境，所有路径指向临时目录。"""
    os.environ["EXAM_OBSIDIAN_ROOT"] = str(temp_root)
    os.environ["EXAM_MISTAKES_DB"] = str(temp_root / "mistakes.db")
    config.OBSIDIAN_ROOT = temp_root
    config.MISTAKE_ROOT = temp_root / "错题库"
    config.KNOWLEDGE_ROOT = temp_root / "知识点库"
    config.METHOD_ROOT = temp_root / "方法论"
    config.INDEX_FILE = config.MISTAKE_ROOT / "index.md"
    config.KNOWLEDGE_INDEX_FILE = config.KNOWLEDGE_ROOT / "index.md"
    config.ensure_dirs()
    db.init_db(force=True)


# =========================================================================
# Test: Phase 2 - Composite index.md with ## headers
# =========================================================================

def test_phase2_composite_index_md_import():
    """从带 ## 题型标题的复合 index.md 导入。"""
    temp = Path(tempfile.mkdtemp(prefix="exam_v3_phase2_"))
    _setup_env(temp)
    try:
        index_md = config.MISTAKE_ROOT / "index.md"
        index_md.write_text("""---
last_id: 5
total: 5
---

# 错题库索引

## 判断推理
| ID | 考点 | 错误原因 | 答案 | 来源 | 阶段 | 下次复习 | 状态 |
|----|------|----------|------|------|------|----------|------|
| 错题-001 | 加强削弱 | 知识点盲区 | B | 2024国考 | 0/6 | 2026-08-16 | ⏳待复习 |
| 错题-002 | 集合推理 | 转换错误 | A | 2024省考 | 1/6 | 2026-08-17 | ⏳待复习 |

## 资料分析
| ID | 考点 | 错误原因 | 答案 | 来源 | 阶段 | 下次复习 | 状态 |
|----|------|----------|------|------|------|----------|------|
| 错题-003 | 增长率计算 | 公式不熟 | C | 2024省考 | 0/6 | 2026-08-16 | ⏳待复习 |
| 错题-004 | 比重计算 | 看错数据 | A | 模考 | 2/6 | 2026-08-20 | ⏳待复习 |

## 数量关系
| ID | 考点 | 错误原因 | 答案 | 来源 | 阶段 | 下次复习 | 状态 |
|----|------|----------|------|------|------|----------|------|
| 错题-005 | 行程问题 | 计算失误 | D | 粉笔模考 | 0/6 | 2026-08-16 | ⏳待复习 |

## 常识判断（不在 ALL_TYPES / EXTRA_TYPES 中，应被忽略）
| ID | 考点 | 错误原因 | 答案 | 来源 | 阶段 | 下次复习 | 状态 |
|----|------|----------|------|------|------|----------|------|
| 错题-999 | 随便 | 随便 | A | 随便 | 0/6 | 2026-08-16 | ⏳待复习 |
""", encoding="utf-8")

        # 创建一些截图文件
        for qtype in ["判断推理", "资料分析", "数量关系"]:
            (config.MISTAKE_ROOT / qtype / "screenshots").mkdir(parents=True, exist_ok=True)
        (config.MISTAKE_ROOT / "判断推理" / "screenshots" / "错题-001.png").write_bytes(b"fake")
        (config.MISTAKE_ROOT / "资料分析" / "screenshots" / "错题-003.png").write_bytes(b"fake")

        result = db.import_from_index_files(
            mistake_root=str(config.MISTAKE_ROOT), dry_run=False
        )

        assert result["imported"] == 5, f"期望导入 5 条，实际 {result['imported']}"
        assert result["errors"] == 0, f"期望 0 错误，实际 {result['errors']}"

        # 验证各条记录正确入库
        for rid, qtype, ebb in [
            ("错题-001", "判断推理", 0),
            ("错题-002", "判断推理", 1),
            ("错题-003", "资料分析", 0),
            ("错题-004", "资料分析", 2),
            ("错题-005", "数量关系", 0),
        ]:
            row = db.get_mistake(rid)
            assert row is not None, f"{rid} 未入库"
            assert row["question_type"] == qtype, f"{rid}: 期望题型 {qtype}，实际 {row['question_type']}"
            assert row["ebbinghaus_value"] == ebb, f"{rid}: 期望阶段 {ebb}，实际 {row['ebbinghaus_value']}"

        # 错题-999 不应入库（题型不在 ALL_TYPES 中）
        assert db.get_mistake("错题-999") is None, "错题-999 不应被导入"

        # 验证图片路径（有截图的）
        row1 = db.get_mistake("错题-001")
        assert row1["image_path"] and "错题-001" in row1["image_path"], \
            f"错题-001 应有图片路径，实际: {row1['image_path']}"

        row3 = db.get_mistake("错题-003")
        assert row3["image_path"] and "错题-003" in row3["image_path"], \
            f"错题-003 应有图片路径，实际: {row3['image_path']}"

        # 验证无截图的
        row5 = db.get_mistake("错题-005")
        assert row5["image_path"] == "", f"错题-005 应无图片路径，实际: {row5['image_path']}"

        print("PASS: test_phase2_composite_index_md_import")
    finally:
        shutil.rmtree(temp, ignore_errors=True)


# =========================================================================
# Test: Phase 1 - index-{题型}.md files import
# =========================================================================

def test_phase1_index_file_import():
    """从 index-{题型}.md 文件导入。"""
    temp = Path(tempfile.mkdtemp(prefix="exam_v3_phase1_"))
    _setup_env(temp)
    try:
        (config.MISTAKE_ROOT / "判断推理" / "screenshots").mkdir(parents=True, exist_ok=True)

        index_path = config.MISTAKE_ROOT / "index-判断推理.md"
        index_path.write_text("""---
last_id: 3
total: 3
---

# 判断推理 · 错题索引

| ID | 考点 | 错误原因 | 答案 | 来源 | 阶段 | 下次复习 | 状态 |
|----|------|----------|------|------|------|----------|------|
| 错题-001 | 加强削弱 | 知识点盲区 | B | 2024国考 | 0/6 | 2026-08-16 | ⏳待复习 |
| 错题-002 | 集合推理 | 转换错误 | A | 2024省考 | 1/6 | 2026-08-17 | ⏳待复习 |
| 错题-003 | 定义判断 | 看漏关键 | C | 模考 | 0/6 | 2026-08-16 | ⏳待复习 |
""", encoding="utf-8")

        (config.MISTAKE_ROOT / "判断推理" / "screenshots" / "错题-001.png").write_bytes(b"fake")

        result = db.import_from_index_files(
            mistake_root=str(config.MISTAKE_ROOT), dry_run=False
        )

        assert result["imported"] == 3, f"期望导入 3 条，实际 {result['imported']}"
        assert result["errors"] == 0, f"期望 0 错误，实际 {result['errors']}"

        row1 = db.get_mistake("错题-001")
        assert row1 is not None
        assert row1["question_type"] == "判断推理"
        assert row1["image_path"] and "错题-001.png" in row1["image_path"]

        stats = db.get_stats_db()
        assert stats["total"] == 3, f"期望 total=3，实际 {stats['total']}"

        print("PASS: test_phase1_index_file_import")
    finally:
        shutil.rmtree(temp, ignore_errors=True)


# =========================================================================
# Test: Mixed import with deduplication
# =========================================================================

def test_mixed_import_dedup():
    """同时存在 index.md 和 index-*.md 时应去重。"""
    temp = Path(tempfile.mkdtemp(prefix="exam_v3_dedup_"))
    _setup_env(temp)
    try:
        for qtype in ["判断推理", "资料分析"]:
            (config.MISTAKE_ROOT / qtype / "screenshots").mkdir(parents=True, exist_ok=True)

        # 1) index-判断推理.md (Phase 1)
        (config.MISTAKE_ROOT / "index-判断推理.md").write_text("""---
| ID | 考点 | 错误原因 | 答案 | 来源 | 阶段 | 下次复习 | 状态 |
|----|------|----------|------|------|------|----------|------|
| 错题-001 | 加强削弱 | 知识点盲区 | B | 国考 | 0/6 | 2026-08-16 | ⏳待复习 |
| 错题-002 | 集合推理 | 转换错误 | A | 省考 | 1/6 | 2026-08-17 | ⏳待复习 |
""", encoding="utf-8")

        # 2) index.md (Phase 2) — 包含判断推理和资料分析
        (config.MISTAKE_ROOT / "index.md").write_text("""## 判断推理
| ID | 考点 | 错误原因 | 答案 | 来源 | 阶段 | 下次复习 | 状态 |
|----|------|----------|------|------|------|----------|------|
| 错题-001 | 加强削弱 | 知识点盲区 | B | 国考 | 0/6 | 2026-08-16 | ⏳待复习 |
| 错题-002 | 集合推理 | 转换错误 | A | 省考 | 1/6 | 2026-08-17 | ⏳待复习 |
| 错题-101 | 定义判断 | 看漏关键 | C | 模考 | 0/6 | 2026-08-16 | ⏳待复习 |

## 资料分析
| ID | 考点 | 错误原因 | 答案 | 来源 | 阶段 | 下次复习 | 状态 |
|----|------|----------|------|------|------|----------|------|
| 错题-201 | 增长率 | 公式不熟 | D | 省考 | 0/6 | 2026-08-16 | ⏳待复习 |
""", encoding="utf-8")

        result = db.import_from_index_files(
            mistake_root=str(config.MISTAKE_ROOT), dry_run=False
        )

        # 应该导入 4 条（Phase 1 的 2 条 + Phase 2 新增的 3 条，去重后不重复计数）
        # 错题-001, 002 被 seen_ids 去重
        assert result["imported"] == 4, f"期望导入 4 条（去重后），实际 {result['imported']}"
        assert result["errors"] == 0

        stats = db.get_stats_db()
        assert stats["total"] == 4, f"期望 total=4，实际 {stats['total']}"

        # 验证新入库的
        for rid in ["错题-101", "错题-201"]:
            row = db.get_mistake(rid)
            assert row is not None, f"{rid} 未入库"

        print("PASS: test_mixed_import_dedup")
    finally:
        shutil.rmtree(temp, ignore_errors=True)


# =========================================================================
# Test: Tags CRUD via JSON1
# =========================================================================

def test_tags_crud():
    """标签完整 CRUD 测试。"""
    temp = Path(tempfile.mkdtemp(prefix="exam_v3_tags_"))
    _setup_env(temp)
    try:
        from models import MistakeCard

        card = MistakeCard(
            id="错题-001", date=date.today().isoformat(),
            question_type="判断推理", knowledge_point="加强削弱",
            error_reason="知识点盲区", correct_answer="B",
            source="2024国考", tags='{"tag":[]}',
        )
        db.insert_mistake(card)

        # 添加标签
        assert db.add_tag("错题-001", "逻辑") is True
        assert db.add_tag("错题-001", "易错") is True
        assert db.add_tag("错题-001", "错题-001不存在") is True  # 先添加

        # 验证标签
        row = db.get_mistake("错题-001")
        tags = json.loads(row["tags"])
        assert "逻辑" in tags["tag"]
        assert "易错" in tags["tag"]

        # 验证新插入的卡片默认标签
        card2 = MistakeCard(
            id="错题-002", date=date.today().isoformat(),
            question_type="资料分析", knowledge_point="增长率",
            error_reason="公式不熟", correct_answer="C",
            source="2024省考",
        )
        db.insert_mistake(card2)
        row2 = db.get_mistake("错题-002")
        tags2 = json.loads(row2["tags"])
        assert tags2 == {"tag": []}, f"默认标签应为空，实际: {tags2}"

        # 获取所有标签
        all_tags = db.get_all_tags()
        assert "逻辑" in all_tags
        assert "易错" in all_tags
        assert len(all_tags) == 3

        # 移除标签
        assert db.remove_tag("错题-001", "逻辑") is True
        all_tags = db.get_all_tags()
        assert "逻辑" not in all_tags
        assert len(all_tags) == 2

        # 按标签搜索
        rows = db.search_by_tag("易错")
        assert len(rows) == 1
        assert rows[0]["id"] == "错题-001"

        rows = db.search_by_tag("不存在的标签")
        assert len(rows) == 0

        print("PASS: test_tags_crud")
    finally:
        shutil.rmtree(temp, ignore_errors=True)


# =========================================================================
# Test: Combined search
# =========================================================================

def test_combined_search():
    """按题型 + 标签 + 关键词组合搜索。"""
    temp = Path(tempfile.mkdtemp(prefix="exam_v3_search_"))
    _setup_env(temp)
    try:
        from models import MistakeCard

        cards = [
            MistakeCard(id="错题-001", date="2026-01-01", question_type="判断推理",
                       knowledge_point="加强削弱", error_reason="知识点盲区",
                       correct_answer="B", source="国考", tags='{"tag":["逻辑","加强"]}'),
            MistakeCard(id="错题-002", date="2026-01-02", question_type="资料分析",
                       knowledge_point="增长率计算", error_reason="公式不熟",
                       correct_answer="C", source="省考", tags='{"tag":["计算"]}'),
            MistakeCard(id="错题-003", date="2026-01-03", question_type="判断推理",
                       knowledge_point="集合推理", error_reason="转换错误",
                       correct_answer="A", source="国考", tags='{"tag":["逻辑","集合"]}'),
            MistakeCard(id="错题-004", date="2026-01-04", question_type="数量关系",
                       knowledge_point="行程问题", error_reason="计算失误",
                       correct_answer="D", source="模考", tags='{"tag":[]}'),
        ]
        for c in cards:
            db.insert_mistake(c)

        # 单一条件
        assert len(db.search_by_type("判断推理")) == 2
        assert len(db.search_by_tag("逻辑")) == 2
        assert len(db.search_by_keyword("计算")) == 2

        # 组合搜索: 题型 + 标签
        r1 = db.search_mistakes(question_type="判断推理", tag="逻辑")
        assert len(r1) == 2

        # 组合搜索: 题型 + 标签 + 关键词
        r2 = db.search_mistakes(question_type="判断推理", tag="逻辑", keyword="加强")
        assert len(r2) == 1
        assert r2[0]["id"] == "错题-001"

        # 组合搜索: 标签 + 关键词 (跨题型)
        r3 = db.search_mistakes(tag="计算", keyword="公式")
        assert len(r3) == 1
        assert r3[0]["id"] == "错题-002"

        # 空结果
        r4 = db.search_mistakes(tag="不存在的")
        assert len(r4) == 0

        # limit 限制
        r5 = db.search_mistakes(limit=2)
        assert len(r5) == 2

        print("PASS: test_combined_search")
    finally:
        shutil.rmtree(temp, ignore_errors=True)


# =========================================================================
# Test: Review lifecycle
# =========================================================================

def test_review_lifecycle():
    """复习全生命周期：创建 → 到期 → 判题 → 复习状态更新。"""
    temp = Path(tempfile.mkdtemp(prefix="exam_v3_review_"))
    _setup_env(temp)
    try:
        today_str = date.today().isoformat()
        tomorrow_str = (date.today() + timedelta(days=1)).isoformat()

        # 创建 3 道题（V3 使用 SQLite）
        for i in range(3):
            mistake_manager.create_mistake(
                question_type="判断推理",
                knowledge_point="加强削弱",
                error_reason="知识点盲区",
                correct_answer="C",
                source=f"模拟卷-{i+1}",
                tags='{"tag":["逻辑"]}',
            )

        # 验证 SQLite 入库
        stats = db.get_stats_db()
        assert stats["total"] == 3
        assert stats["pending"] == 3

        # 获取到期题目
        due = review_engine.select_due_items(today_str)
        assert len(due) == 3, f"期望 3 道到期，实际 {len(due)}"

        # 分批
        batch = review_engine.take_batch(due, batch_size=2)
        assert len(batch) == 2

        # 判题: 全对
        results, summary = review_engine.review_batch(
            batch, "1.搭桥削弱 2.排除他因", review_date=today_str,
        )
        assert len(results) == 2
        assert results[0]["passed"] is True
        assert results[0]["new_stage"] == 1
        assert results[1]["passed"] is True
        assert results[1]["new_stage"] == 1

        # 验证数据库状态已更新
        row = db.get_mistake(results[0]["mistake_id"])
        assert row["ebbinghaus_value"] == 1, f"期望阶段 1，实际 {row['ebbinghaus_value']}"

        # 再获取到期（第3题还在）
        due2 = review_engine.select_due_items(today_str)
        assert len(due2) >= 1

        # 判第3题：失败
        batch2 = review_engine.take_batch(due2, batch_size=1)
        results2, _ = review_engine.review_batch(
            batch2, "1.不记得", review_date=today_str,
        )
        assert results2[0]["passed"] is False
        assert results2[0]["new_stage"] == 0

        # 明天到期检查
        due3 = review_engine.select_due_items(tomorrow_str)
        assert len(due3) >= 1

        print("PASS: test_review_lifecycle")
    finally:
        shutil.rmtree(temp, ignore_errors=True)


# =========================================================================
# Test: Edge cases
# =========================================================================

def test_edge_cases():
    """边缘情况测试。"""
    temp = Path(tempfile.mkdtemp(prefix="exam_v3_edge_"))
    _setup_env(temp)
    try:
        # 1) 空数据库
        stats = db.get_stats_db()
        assert stats["total"] == 0
        assert stats["pending"] == 0
        assert stats["mastered"] == 0

        due = db.get_due_entries_db(date.today().isoformat())
        assert len(due) == 0

        # 2) 不存在的题型导入
        result = db.import_from_index_files(
            mistake_root=str(config.MISTAKE_ROOT), dry_run=False,
        )
        assert result["imported"] == 0

        # 3) 无效的错题库路径
        try:
            db.import_from_index_files(mistake_root="/nonexistent/path")
            assert False, "期望抛出 ValueError"
        except ValueError:
            pass

        # 4) 索引文件不存在
        (config.MISTAKE_ROOT / "index.md").write_text(
            "只有文字\n没有表格\n", encoding="utf-8"
        )
        result = db.import_from_index_files(
            mistake_root=str(config.MISTAKE_ROOT), dry_run=False,
        )
        assert result["imported"] == 0

        # 5) 更新不存在的字段
        try:
            db.update_mistake_field("错题-001", "invalid_field", "value")
            assert False, "期望抛出 ValueError"
        except ValueError:
            pass

        # 6) 删除不存在的记录
        assert db.delete_mistake_db("错题-999") is False

        print("PASS: test_edge_cases")
    finally:
        shutil.rmtree(temp, ignore_errors=True)


# =========================================================================
# Main
# =========================================================================

if __name__ == "__main__":
    test_phase2_composite_index_md_import()
    test_phase1_index_file_import()
    test_mixed_import_dedup()
    test_tags_crud()
    test_combined_search()
    test_review_lifecycle()
    test_edge_cases()
    print()
    print("🎉 V3 所有集成测试通过")


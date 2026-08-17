import sys, os, shutil, tempfile
from pathlib import Path
from datetime import date, timedelta

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / 'scripts'))

import config
import database as db
import mistake_manager
import review_engine
import scheduler


def _setup_sqlite_env(temp_root: Path) -> None:
    os.environ['EXAM_OBSIDIAN_ROOT'] = str(temp_root)
    os.environ['EXAM_MISTAKES_DB'] = str(temp_root / 'mistakes.db')
    config.OBSIDIAN_ROOT = temp_root
    config.MISTAKE_ROOT = temp_root / '错题库'
    config.KNOWLEDGE_ROOT = temp_root / '知识点库'
    config.METHOD_ROOT = temp_root / '方法论'
    config.INDEX_FILE = config.MISTAKE_ROOT / 'index.md'
    config.KNOWLEDGE_INDEX_FILE = config.KNOWLEDGE_ROOT / 'index.md'
    config.ensure_dirs()
    db.init_db(force=True)


def test_sqlite_insert_and_query() -> None:
    temp = Path(tempfile.mkdtemp(prefix='exam_sqlite_test_'))
    _setup_sqlite_env(temp)
    try:
        from models import MistakeCard
        card1 = MistakeCard(
            id='错题-001', date=date.today().isoformat(),
            question_type='判断推理', knowledge_point='加强削弱',
            error_reason='知识点盲区', correct_answer='B',
            source='2024国考', review_stage=0,
            next_review=date.today().isoformat(),
            tags='{"tag":["易错","逻辑"]}',
        )
        card2 = MistakeCard(
            id='错题-002', date=date.today().isoformat(),
            question_type='资料分析', knowledge_point='增长率计算',
            error_reason='公式不熟', correct_answer='C',
            source='2024省考', review_stage=1,
            next_review=date.today().isoformat(),
            tags='{"tag":["计算"]}',
        )
        db.insert_mistake(card1)
        db.insert_mistake(card2)

        stats = db.get_stats_db()
        assert stats['total'] == 2, f"Expected 2, got {stats['total']}"
        assert stats['pending'] == 2
        assert stats['by_type']['判断推理']['total'] == 1
        assert stats['by_type']['资料分析']['total'] == 1

        rows = db.search_by_type('判断推理')
        assert len(rows) == 1
        assert rows[0]['id'] == '错题-001'

        rows = db.search_by_tag('易错')
        assert len(rows) == 1
        assert rows[0]['id'] == '错题-001'

        rows = db.search_by_keyword('增长率')
        assert len(rows) == 1
        assert rows[0]['id'] == '错题-002'

        rows = db.search_mistakes(question_type='判断推理', tag='易错')
        assert len(rows) == 1
        assert rows[0]['id'] == '错题-001'

        print('PASS: test_sqlite_insert_and_query')
    finally:
        shutil.rmtree(temp, ignore_errors=True)


def test_sqlite_tag_operations() -> None:
    temp = Path(tempfile.mkdtemp(prefix='exam_sqlite_tag_'))
    _setup_sqlite_env(temp)
    try:
        from models import MistakeCard
        card = MistakeCard(
            id='错题-001', date=date.today().isoformat(),
            question_type='判断推理', knowledge_point='加强削弱',
            error_reason='知识点盲区', correct_answer='B',
            source='2024国考',
            tags='{"tag":[]}',
        )
        db.insert_mistake(card)

        assert db.add_tag('错题-001', '易错') is True
        assert db.add_tag('错题-001', '逻辑') is True
        assert db.add_tag('错题-001', '类比') is True

        all_tags = db.get_all_tags()
        assert '易错' in all_tags
        assert '逻辑' in all_tags
        assert '类比' in all_tags
        assert len(all_tags) == 3

        assert db.remove_tag('错题-001', '类比') is True
        all_tags = db.get_all_tags()
        assert '类比' not in all_tags
        assert len(all_tags) == 2

        rows = db.search_by_tag('类比')
        assert len(rows) == 0

        print('PASS: test_sqlite_tag_operations')
    finally:
        shutil.rmtree(temp, ignore_errors=True)


def test_sqlite_review_state() -> None:
    temp = Path(tempfile.mkdtemp(prefix='exam_sqlite_review_'))
    _setup_sqlite_env(temp)
    try:
        from models import MistakeCard
        today_str = date.today().isoformat()
        card = MistakeCard(
            id='错题-001', date=today_str,
            question_type='判断推理', knowledge_point='加强削弱',
            error_reason='知识点盲区', correct_answer='B',
            source='2024国考', review_stage=0,
            next_review=today_str,
            tags='{"tag":["逻辑"]}',
        )
        db.insert_mistake(card)

        due = db.get_due_entries_db(today_str)
        assert len(due) == 1, f"Expected 1 due, got {len(due)}"
        assert due[0]['id'] == '错题-001'
        assert due[0]['ebbinghaus_value'] == 0

        tomorrow = (date.today() + timedelta(days=1)).isoformat()
        db.update_review_state_db(
            '错题-001', 1, tomorrow, 'pending',
            True, today_str, 0,
        )

        row = db.get_mistake('错题-001')
        assert row['ebbinghaus_value'] == 1
        assert row['next_review'] == tomorrow

        day_after = (date.today() + timedelta(days=2)).isoformat()
        db.update_review_state_db(
            '错题-001', 0, day_after, 'pending',
            False, tomorrow, 1,
        )

        row = db.get_mistake('错题-001')
        assert row['ebbinghaus_value'] == 0
        assert row['next_review'] == day_after

        print('PASS: test_sqlite_review_state')
    finally:
        shutil.rmtree(temp, ignore_errors=True)


def test_sqlite_import_from_index() -> None:
    temp = Path(tempfile.mkdtemp(prefix='exam_sqlite_import_'))
    _setup_sqlite_env(temp)
    try:
        (temp / '错题库' / '判断推理' / 'screenshots').mkdir(parents=True, exist_ok=True)

        index_content = '''---
last_id: 2
total: 2
pending: 2
mastered: 0
updated: 2026-08-16
qtype: 判断推理
---

# 判断推理 · 错题索引

| ID | 考点 | 错误原因 | 答案 | 来源 | 阶段 | 下次复习 | 状态 |
|----|------|----------|------|------|------|----------|------|
| 错题-001 | 加强削弱 | 知识点盲区 | B | 2024国考 | 0/6 | 2026-08-16 | ⏳待复习 |
| 错题-002 | 集合推理 | 转换错误 | A | 2024省考 | 1/6 | 2026-08-17 | ⏳待复习 |
'''
        (temp / '错题库' / 'index-判断推理.md').write_text(index_content, encoding='utf-8')

        fake_img = temp / '错题库' / '判断推理' / 'screenshots' / '错题-001.png'
        fake_img.write_bytes(b'fake png data')

        result = db.import_from_index_files(mistake_root=temp / '错题库', dry_run=False)
        assert result['imported'] == 2, f"Expected 2 imported, got {result['imported']}"
        assert result['errors'] == 0, f"Expected 0 errors, got {result['errors']}"

        row = db.get_mistake('错题-001')
        assert row is not None
        assert row['question_type'] == '判断推理'
        assert row['knowledge_point'] == '加强削弱'
        assert row['ebbinghaus_value'] == 0
        assert '错题-001.png' in row['image_path']

        row2 = db.get_mistake('错题-002')
        assert row2 is not None
        assert row2['ebbinghaus_value'] == 1

        print('PASS: test_sqlite_import_from_index')
    finally:
        shutil.rmtree(temp, ignore_errors=True)


def test_sqlite_comprehensive_search() -> None:
    temp = Path(tempfile.mkdtemp(prefix='exam_sqlite_search_'))
    _setup_sqlite_env(temp)
    try:
        from models import MistakeCard
        cards = [
            MistakeCard(id='错题-001', date='2026-01-01', question_type='判断推理',
                       knowledge_point='加强削弱', error_reason='知识点盲区',
                       correct_answer='B', source='国考', tags='{"tag":["逻辑","加强"]}'),
            MistakeCard(id='错题-002', date='2026-01-02', question_type='资料分析',
                       knowledge_point='增长率计算', error_reason='公式不熟',
                       correct_answer='C', source='省考', tags='{"tag":["计算"]}'),
            MistakeCard(id='错题-003', date='2026-01-03', question_type='判断推理',
                       knowledge_point='集合推理', error_reason='转换错误',
                       correct_answer='A', source='国考', tags='{"tag":["逻辑","集合"]}'),
            MistakeCard(id='错题-004', date='2026-01-04', question_type='数量关系',
                       knowledge_point='行程问题', error_reason='公式不熟',
                       correct_answer='D', source='模考', tags='{"tag":[]}'),
        ]
        for c in cards:
            db.insert_mistake(c)

        results = db.search_mistakes(question_type='判断推理', tag='逻辑', keyword='加强')
        assert len(results) == 1
        assert results[0]['id'] == '错题-001'

        results = db.search_mistakes(question_type='数量关系')
        assert len(results) == 1
        assert results[0]['id'] == '错题-004'

        results = db.search_mistakes(tag='计算')
        assert len(results) == 1
        assert results[0]['id'] == '错题-002'

        results = db.search_mistakes(keyword='公式不熟')
        assert len(results) == 2

        print('PASS: test_sqlite_comprehensive_search')
    finally:
        shutil.rmtree(temp, ignore_errors=True)


def test_sqlite_review_engine() -> None:
    temp = Path(tempfile.mkdtemp(prefix='exam_sqlite_review_eng_'))
    _setup_sqlite_env(temp)
    try:
        from models import MistakeCard
        today_str = date.today().isoformat()

        for i in range(3):
            mistake_manager.create_mistake(
                question_type='判断推理',
                knowledge_point='加强削弱',
                error_reason='知识点盲区',
                correct_answer='C',
                source=f'模拟卷-{i+1}',
            )

        due = review_engine.select_due_items(today_str)
        assert len(due) == 3, f"Expected 3 due, got {len(due)}"

        items = review_engine.take_batch(due, batch_size=2)
        assert len(items) == 2, f"Expected 2 items, got {len(items)}"

        answers = '1.搭桥加强 2.排除他因'
        results, summary = review_engine.review_batch(items, answers, today_str)
        assert len(results) == 2
        assert results[0]['passed'] is True
        assert results[0]['new_stage'] == 1

        row = db.get_mistake(results[0]['mistake_id'])
        assert row['ebbinghaus_value'] == 1

        print('PASS: test_sqlite_review_engine')
    finally:
        shutil.rmtree(temp, ignore_errors=True)


if __name__ == '__main__':
    test_sqlite_insert_and_query()
    test_sqlite_tag_operations()
    test_sqlite_review_state()
    test_sqlite_import_from_index()
    test_sqlite_comprehensive_search()
    test_sqlite_review_engine()
    print()
    print('All SQLite tests passed')

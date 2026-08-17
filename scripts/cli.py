#!/usr/bin/env python3
"""统一命令行入口（V3：SQLite 为主存储）。

提供以下功能：
- init-db:      初始化 SQLite 数据库，支持从现有错题库导入
- add:          添加错题
- review:       生成今日复习待办（输出题号 + 图片路径）
- judge:        判题（输入答案后更新复习状态）
- import-batch: 从截图目录批量导入
- import-index: 从 index-*.md 索引文件导入
- search:       按题型/标签/ID 搜索错题
- tag:          管理错题标签
- stats:        查看统计
- modify:       修改错题字段
- delete:       删除错题

机器人或定时任务都可以直接调用这个入口。
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional

# 把 scripts/ 加入路径，方便直接运行
_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_ROOT / "scripts"))

import config
import index_manager
import mistake_manager
import review_engine
import scheduler
import database as _db
from batch_importer import build_import_report, import_directory


# ============================================================================
# 辅助函数
# ============================================================================


def _import_from_root(root_path: Path) -> None:
    """从指定根目录导入所有 index-*.md 和 错题-*.md 文件。"""
    print(f"📥 正在导入错题库：{root_path}")
    print()

    # 先尝试从 index-*.md 文件导入
    print("正在扫描 index-*.md 索引文件...")
    result = _db.import_from_index_files(
        mistake_root=str(root_path),
        dry_run=False,
    )
    print(f"   从索引文件导入：{result['imported']} 条成功, {result['skipped']} 条跳过, {result['errors']} 条错误")
    if result.get("message"):
        print(f"   消息：{result['message']}")

    # 再从 .md 文件目录导入
    print("正在扫描 错题-*.md 文件...")
    result2 = _db.import_from_mistake_root(
        mistake_root=root_path,
        dry_run=False,
    )
    print(f"   从 .md 文件导入：{result2['imported']} 条成功, {result2['skipped']} 条跳过, {result2['errors']} 条错误")

    # 去重统计
    final_stats = _db.get_stats_db()
    print()
    print(f"✅ 导入完成！数据库中现有 {final_stats['total']} 条记录")
    if final_stats.get("by_type"):
        print("   按题型分布：")
        for qtype, s in sorted(final_stats["by_type"].items()):
            print(f"     - {qtype}：{s['total']} 题")


def _cmd_init_db(args: argparse.Namespace) -> int:
    _db.init_db(force=args.force)
    print("✅ SQLite 数据库已初始化")
    print(f"   数据库路径：{_db.get_db_path()}")
    print()

    # 检测默认错题库路径
    default_root = config.MISTAKE_ROOT
    has_default = default_root.exists() and (default_root / "index.md").exists()

    if args.from_dir:
        root_path = Path(args.from_dir)
        if not root_path.exists():
            print(f"❌ 错误：目录不存在: {root_path}")
            return 1
        _import_from_root(root_path)
    elif has_default:
        count = len([f for f in default_root.rglob("index*.md") if "index-" in f.stem or f.name == "index.md"])
        print(f"📂 检测到默认错题库路径：{default_root}")
        print(f"   发现 {count} 个索引文件")
        print()
        print("💡 提示：如果要导入现有错题，请运行：")
        print(f'   python cli.py init-db --from-dir "{default_root}"')
        print("   或")
        print(f'   python cli.py import-index "{default_root}"')
        print()
    else:
        print("💡 提示：原有错题库文件未检测到")
        print("   如果已有错题库，请运行：")
        print('   python cli.py init-db --from-dir "你的错题库路径"')
        print()

    # 打印统计
    stats = _db.get_stats_db()
    print(f"📊 数据库统计")
    print(f"   总题数：{stats['total']}")
    print(f"   待复习：{stats['pending']}")
    print(f"   已掌握：{stats['mastered']}")
    if stats.get("by_type"):
        print()
        print("   按题型分布：")
        for qtype, s in sorted(stats["by_type"].items()):
            print(f"     - {qtype}：{s['total']} 题（待复习 {s['pending']}，已掌握 {s['mastered']}）")
    print()
    print("🚀 可用命令：")
    print("   python cli.py add --type ... --point ...  # 添加错题")
    print("   python cli.py review                       # 生成今日复习题")
    print('   python cli.py judge "1.B 2.C"             # 判题')
    print("   python cli.py search --type ... --tag ...  # 搜索错题")
    print("   python cli.py stats                        # 查看统计")
    return 0


def _cmd_add(args: argparse.Namespace) -> int:
    config.ensure_dirs()
    card = mistake_manager.create_mistake(
        question_type=args.type,
        knowledge_point=args.point,
        error_reason=args.reason,
        correct_answer=args.answer,
        source=args.source,
        screenshot_src=Path(args.screenshot) if args.screenshot else None,
    )
    print(f"✅ 已保存 {card.id}")
    print(f"📂 {card.question_type}")
    print(f"📅 已加入复习队列，下次复习 {card.next_review}")
    return 0


def _cmd_review(args: argparse.Namespace) -> int:
    config.ensure_dirs()
    today = args.date or scheduler.today_str()
    due = review_engine.select_due_items(today)
    if not due:
        stats = _db.get_stats_db()
        if stats["total"] > 0:
            with _db.get_conn() as conn:
                row = conn.execute(
                    "SELECT next_review FROM mistakes WHERE status != 'mastered' ORDER BY next_review ASC LIMIT 1"
                ).fetchone()
            future = row["next_review"] if row else "未知"
            print(f"今天没有待复习的错题，下一次复习在 {future}")
        else:
            print("错题库还是空的，先用 add 或 import-batch 添加错题。")
        return 0

    batch_size = args.batch_size or config.REVIEW_BATCH_SIZE
    items = review_engine.take_batch(due, batch_size)
    prompt = review_engine.format_review_prompt(items, group_no=1)
    print(prompt)
    return 0


def _cmd_judge(args: argparse.Namespace) -> int:
    config.ensure_dirs()
    today = args.date or scheduler.today_str()
    due = review_engine.select_due_items(today)
    if not due:
        print("没有到期的错题。")
        return 0
    items = review_engine.take_batch(due, args.batch_size or config.REVIEW_BATCH_SIZE)
    results, summary = review_engine.review_batch(items, args.answers, today)
    print(summary)
    return 0


def _cmd_import_batch(args: argparse.Namespace) -> int:
    config.ensure_dirs()
    report = import_directory(
        source_dir=Path(args.source),
        default_error_reason=args.reason or "待补充",
        default_source=args.source_name or "",
        dry_run=args.dry_run,
    )
    if args.dry_run:
        print("## 👁️ 仅预览（未实际入库）")
    print(build_import_report(report))
    return 0


def _cmd_import_index(args: argparse.Namespace) -> int:
    config.ensure_dirs()
    root_path = Path(args.source) if args.source else config.MISTAKE_ROOT
    if not root_path.exists():
        print(f"❌ 错误：目录不存在: {root_path}")
        return 1
    print(f"正在从 {root_path} 导入索引文件...")
    result = _db.import_from_index_files(
        mistake_root=str(root_path),
        dry_run=args.dry_run,
    )
    if args.dry_run:
        print("## 👁️ 仅预览（未实际入库）")
    print(f"  导入：{result['imported']} 条成功")
    print(f"  跳过：{result['skipped']} 条")
    print(f"  错误：{result['errors']} 条")
    return 0


def _cmd_search(args: argparse.Namespace) -> int:
    config.ensure_dirs()

    if args.id:
        card = _db.get_mistake(args.id)
        if not card:
            print(f"未找到 {args.id}")
            return 1
        print(f"## 错题 {card['id']}")
        print(f"- 题型：{card['question_type']}")
        print(f"- 考点：{card.get('knowledge_point', '')}")
        print(f"- 标签：{card.get('tags', '')}")
        print(f"- 状态：{card.get('status', '')}")
        print(f"- 复习阶段：{card.get('ebbinghaus_value', 0)}")
        print(f"- 下次复习：{card.get('next_review', '')}")
        print(f"- 图片：{card.get('image_path', '')}")
        return 0

    results: List[Dict[str, Any]] = []
    if args.type:
        rows = _db.search_by_type(args.type)
        results.extend(rows)
    if args.tag:
        rows = _db.search_by_tag(args.tag)
        results.extend(rows)
    if not args.type and not args.tag:
        with _db.get_conn() as conn:
            results = conn.execute(
                "SELECT * FROM mistakes ORDER BY id"
            ).fetchall()

    if not results:
        print("没有找到匹配的错题。")
        return 0

    print(f"找到 {len(results)} 条错题：")
    print()
    for r in results:
        tag_str = r.get("tags", "")
        status_icon = "🎉" if r.get("status") == "mastered" else "⏳"
        print(f"  {status_icon} {r['id']} | {r['question_type']} | 阶段{r.get('ebbinghaus_value', 0)} | 下次复习 {r.get('next_review', '')}")
        if tag_str and tag_str != '{"tag":[]}':
            print(f"     标签：{tag_str}")
    return 0


def _cmd_tag(args: argparse.Namespace) -> int:
    config.ensure_dirs()

    if args.action == "list":
        tags = _db.get_all_tags()
        if not tags:
            print("暂无标签。")
            return 0
        print("现有标签：")
        for t in tags:
            print(f"  - {t}")
        return 0

    if not args.id:
        print("❌ 需要指定错题 ID（--id）")
        return 1

    if args.action == "add":
        ok = _db.add_tag(args.id, args.tag)
        if ok:
            print(f"✅ 已为 {args.id} 添加标签：{args.tag}")
        else:
            print(f"标签 {args.tag} 已存在或未找到错题 {args.id}")
    elif args.action == "remove":
        ok = _db.remove_tag(args.id, args.tag)
        if ok:
            print(f"✅ 已从 {args.id} 移除标签：{args.tag}")
        else:
            print(f"标签 {args.tag} 不存在或未找到错题 {args.id}")
    else:
        print(f"❌ 未知操作：{args.action}，支持 add / remove / list")
        return 1
    return 0


def _cmd_stats(args: argparse.Namespace) -> int:
    config.ensure_dirs()
    stats = _db.get_stats_db()
    print("## 📊 复习进度")
    print(f"- 总题数：{stats['total']}")
    print(f"- 待复习：{stats['pending']}")
    print(f"- 已掌握：{stats['mastered']}")
    print("")
    if stats.get("by_type"):
        print("### 题型分布")
        for qtype, s in sorted(stats["by_type"].items()):
            print(f"- {qtype}：{s['total']} 题（待复习 {s['pending']}，已掌握 {s['mastered']}）")
    return 0


def _cmd_modify(args: argparse.Namespace) -> int:
    config.ensure_dirs()
    card = mistake_manager.modify_mistake(
        mistake_id=args.id,
        question_type=args.type,
        field=args.field,
        value=args.value,
    )
    if card is None:
        print(f"未找到 {args.id}")
        return 1
    print(f"✅ 已更新 {card.id} 的 {args.field} 为 {args.value}")
    return 0


def _cmd_delete(args: argparse.Namespace) -> int:
    config.ensure_dirs()
    ok = mistake_manager.delete_mistake(args.id, args.type)
    if ok:
        print(f"✅ 已删除 {args.id}")
        return 0
    print(f"未找到 {args.id}")
    return 1


# ============================================================================
# 参数解析 & 入口
# ============================================================================


def main() -> int:
    parser = argparse.ArgumentParser(
        description="错题管理器 CLI（V3 SQLite 版）",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )

    sub = parser.add_subparsers(dest="command", required=True)

    # init-db
    p_init = sub.add_parser("init-db", help="初始化 SQLite 数据库")
    p_init.add_argument("--force", action="store_true", help="强制重建数据库（清空所有数据）")
    p_init.add_argument("--from-dir", help="从指定错题库根目录导入现有数据")
    p_init.set_defaults(func=_cmd_init_db)

    # add
    p_add = sub.add_parser("add", help="添加一道错题")
    p_add.add_argument("--type", required=True, help="题型（判断推理/资料分析/数量关系/政治理论/常识判断/言语理解）")
    p_add.add_argument("--point", default="", help="考点")
    p_add.add_argument("--reason", default="", help="错误原因")
    p_add.add_argument("--answer", default="", help="正确答案")
    p_add.add_argument("--source", default="", help="题目来源")
    p_add.add_argument("--screenshot", help="截图路径")
    p_add.set_defaults(func=_cmd_add)

    # review
    p_review = sub.add_parser("review", help="生成今日复习题")
    p_review.add_argument("--date", help="指定日期（YYYY-MM-DD），默认今天")
    p_review.add_argument("--batch-size", type=int, help="每组题数，默认 5")
    p_review.set_defaults(func=_cmd_review)

    # judge
    p_judge = sub.add_parser("judge", help="判题并更新复习状态")
    p_judge.add_argument("answers", help="答案字符串，如 '1.B 2.C 3.A'")
    p_judge.add_argument("--date", help="复习日期（YYYY-MM-DD），默认今天")
    p_judge.add_argument("--batch-size", type=int, help="每组题数，默认 5")
    p_judge.set_defaults(func=_cmd_judge)

    # import-batch
    p_ib = sub.add_parser("import-batch", help="从截图目录批量导入")
    p_ib.add_argument("source", help="截图目录路径")
    p_ib.add_argument("--reason", help="默认错误原因")
    p_ib.add_argument("--source-name", help="题目来源")
    p_ib.add_argument("--dry-run", action="store_true", help="仅预览，不实际入库")
    p_ib.set_defaults(func=_cmd_import_batch)

    # import-index
    p_ii = sub.add_parser("import-index", help="从 index-*.md 索引文件导入")
    p_ii.add_argument("source", nargs="?", help="错题库根目录（默认 MISTAKE_ROOT）")
    p_ii.add_argument("--dry-run", action="store_true", help="仅预览，不实际入库")
    p_ii.set_defaults(func=_cmd_import_index)

    # search
    p_search = sub.add_parser("search", help="搜索错题")
    p_search.add_argument("--id", help="按 ID 精确查找")
    p_search.add_argument("--type", help="按题型筛选")
    p_search.add_argument("--tag", help="按标签筛选")
    p_search.set_defaults(func=_cmd_search)

    # tag
    p_tag = sub.add_parser("tag", help="管理错题标签")
    p_tag.add_argument("action", choices=["add", "remove", "list"], help="操作")
    p_tag.add_argument("--id", help="错题 ID（list 操作不需要）")
    p_tag.add_argument("--tag", help="标签名（add/remove 需要）")
    p_tag.set_defaults(func=_cmd_tag)

    # stats
    p_stats = sub.add_parser("stats", help="查看错题统计")
    p_stats.set_defaults(func=_cmd_stats)

    # modify
    p_mod = sub.add_parser("modify", help="修改错题字段")
    p_mod.add_argument("id", help="错题 ID")
    p_mod.add_argument("--type", required=True, help="题型")
    p_mod.add_argument("--field", required=True, help="要修改的字段名")
    p_mod.add_argument("--value", required=True, help="新值")
    p_mod.set_defaults(func=_cmd_modify)

    # delete
    p_del = sub.add_parser("delete", help="删除错题")
    p_del.add_argument("id", help="错题 ID")
    p_del.add_argument("--type", required=True, help="题型")
    p_del.set_defaults(func=_cmd_delete)

    args = parser.parse_args()
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())


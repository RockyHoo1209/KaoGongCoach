#!/usr/bin/env python3
"""统一命令行入口。

把三个 workflow 脚本化为可以独立运行的 CLI：
- add: 添加错题
- review: 复习错题
- import-batch: 批量导入截图目录
- stats: 统计进度
- modify/delete: 管理错题

机器人或定时任务都可以直接调用这个入口。
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

# 把 scripts/ 加入路径，方便直接运行
_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_ROOT / "scripts"))

import config
import index_manager
import mistake_manager
import review_engine
import scheduler
from batch_importer import build_import_report, import_directory


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
    print(f"📂 {card.question_type}/{card.knowledge_point}")
    print(f"📅 已加入复习队列，下次复习 {card.next_review}")
    return 0


def _cmd_review(args: argparse.Namespace) -> int:
    config.ensure_dirs()
    today = args.date or scheduler.today_str()
    due = review_engine.select_due_items(today)
    if not due:
        data = index_manager.load_index()
        if data.entries:
            future = min(e.next_review for e in data.entries if e.status != "mastered")
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
    """对已经从 review 命令生成的一组题进行判题。"""
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


def _cmd_stats(args: argparse.Namespace) -> int:
    config.ensure_dirs()
    data = index_manager.load_index()
    grouped = data.entries_by_type()
    print("## 📊 复习进度")
    print(f"- 总题数：{data.total}")
    print(f"- 待复习：{data.pending}")
    print(f"- 已掌握：{data.mastered}")
    print(f"- 最近更新：{data.updated}")
    print("")
    if grouped:
        print("### 题型分布")
        for qtype, entries in grouped.items():
            pending = sum(1 for e in entries if e.status == "pending")
            mastered = sum(1 for e in entries if e.status == "mastered")
            print(f"- {qtype}：{len(entries)} 题（待复习 {pending}，已掌握 {mastered}）")
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


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="考公错题库命令行入口",
    )
    sub = parser.add_subparsers(dest="command", required=True)

    # add
    add_p = sub.add_parser("add", help="添加一道错题")
    add_p.add_argument("--type", required=True, help="题型")
    add_p.add_argument("--point", required=True, help="考点")
    add_p.add_argument("--reason", required=True, help="错误原因")
    add_p.add_argument("--answer", required=True, help="正确答案")
    add_p.add_argument("--source", required=True, help="来源")
    add_p.add_argument("--screenshot", default=None, help="截图原文件路径")
    add_p.set_defaults(func=_cmd_add)

    # review
    review_p = sub.add_parser("review", help="生成今日复习题")
    review_p.add_argument("--date", default=None, help="日期 YYYY-MM-DD，默认今天")
    review_p.add_argument(
        "--batch-size", type=int, default=None, help="每组题数，默认 5"
    )
    review_p.set_defaults(func=_cmd_review)

    # judge
    judge_p = sub.add_parser("judge", help="判题并更新复习状态")
    judge_p.add_argument("answers", help="用户答案文本，如 '1.B 2.C'")
    judge_p.add_argument("--date", default=None, help="日期 YYYY-MM-DD，默认今天")
    judge_p.add_argument(
        "--batch-size", type=int, default=None, help="每组题数，默认 5"
    )
    judge_p.set_defaults(func=_cmd_judge)

    # import-batch
    import_p = sub.add_parser("import-batch", help="批量导入截图目录")
    import_p.add_argument("source", help="源目录")
    import_p.add_argument("--reason", default="待补充", help="默认错误原因")
    import_p.add_argument("--source-name", default="", help="默认来源")
    import_p.add_argument(
        "--dry-run", action="store_true", help="仅预览，不写入"
    )
    import_p.set_defaults(func=_cmd_import_batch)

    # stats
    stats_p = sub.add_parser("stats", help="查看统计")
    stats_p.set_defaults(func=_cmd_stats)

    # modify
    modify_p = sub.add_parser("modify", help="修改错题字段")
    modify_p.add_argument("id", help="错题 ID")
    modify_p.add_argument("--type", required=True, help="题型")
    modify_p.add_argument(
        "--field",
        required=True,
        choices=["knowledge_point", "error_reason", "correct_answer", "source", "question_type"],
        help="要修改的字段",
    )
    modify_p.add_argument("--value", required=True, help="新值")
    modify_p.set_defaults(func=_cmd_modify)

    # delete
    delete_p = sub.add_parser("delete", help="删除错题")
    delete_p.add_argument("id", help="错题 ID")
    delete_p.add_argument("--type", required=True, help="题型")
    delete_p.set_defaults(func=_cmd_delete)

    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())

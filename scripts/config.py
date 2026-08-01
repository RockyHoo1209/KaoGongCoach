"""全局配置：路径、考试日期、API、艾宾浩斯参数等。

所有模块统一从这里读取配置，便于跨平台（Windows / Linux）部署。
V2：新增按题型拆分的索引文件路径。
V3：新增 SQLite 数据库路径 DATABASE_PATH，新增「政治理论」题型。
"""
from __future__ import annotations

import os
from pathlib import Path
from typing import List


# ---------------------------------------------------------------------------
# 路径配置
# ---------------------------------------------------------------------------

# Obsidian 笔记根目录（考公相关目录都挂在这里）
# SKILL.md 使用 /mnt/e/obsidianNote/考公，对应 Windows 下 E:\\obsidianNote\\考公
OBSIDIAN_ROOT = Path(os.environ.get("EXAM_OBSIDIAN_ROOT", r"E:\\obsidianNote\\考公"))

# 错题库 / 知识点库 / 方法论
MISTAKE_ROOT = OBSIDIAN_ROOT / "错题库"
KNOWLEDGE_ROOT = OBSIDIAN_ROOT / "知识点库"
METHOD_ROOT = OBSIDIAN_ROOT / "方法论"

# ---------------------------------------------------------------------------
# V3：SQLite 数据库路径
# ---------------------------------------------------------------------------

# 数据库文件默认路径（可通过 EXAM_MISTAKES_DB 环境变量覆盖）
DATABASE_PATH = MISTAKE_ROOT / "mistakes.db"

# 主索引（总览摘要，自动从分题型索引生成）
INDEX_FILE = MISTAKE_ROOT / "index.md"
KNOWLEDGE_INDEX_FILE = KNOWLEDGE_ROOT / "index.md"

# ---------------------------------------------------------------------------
# V2：按题型拆分的索引文件（提升查找速度）
# 每个题型一个独立 index-{题型}.md，只含该题型的条目
# 查找/更新时只读写对应题型文件，无需解析整个 index.md
# ---------------------------------------------------------------------------

def category_index_path(qtype: str) -> Path:
    """返回某题型的分索引文件路径。"""
    return MISTAKE_ROOT / f"index-{qtype}.md"


# 所有题型索引文件路径映射（惰性生成）
def all_category_index_paths() -> dict[str, Path]:
    """返回 {题型: Path} 字典。"""
    return {t: category_index_path(t) for t in ALL_TYPES}


# 五大题型子目录
QUESTION_TYPES: List[str] = [
    "言语理解",
    "数量关系",
    "判断推理",
    "资料分析",
    "常识判断",
    "政治理论",
]

# 可扩展科目（公安 / 申论 / 面试 等）
EXTRA_TYPES: List[str] = ["公安专业知识", "申论", "面试"]

ALL_TYPES = QUESTION_TYPES + EXTRA_TYPES


# ---------------------------------------------------------------------------
# 考试配置
# ---------------------------------------------------------------------------

# 用户确认的考试日期：11月1日
EXAM_DATE = os.environ.get("EXAM_EXAM_DATE", "2026-11-01")


# ---------------------------------------------------------------------------
# 艾宾浩斯遗忘曲线间隔表
# ---------------------------------------------------------------------------

# stage -> 距上次复习的天数（与 SKILL.md 间隔表一致）
EBBINGHAUS_INTERVALS: List[int] = [0, 1, 2, 4, 7, 15]
# stage 6 表示已掌握，不再安排复习
MASTERED_STAGE = 6


# ---------------------------------------------------------------------------
# 复习参数
# ---------------------------------------------------------------------------

REVIEW_BATCH_SIZE = 5  # 每组抽题数


# ---------------------------------------------------------------------------
# OCR / 视觉分析配置
# ---------------------------------------------------------------------------

OCR_API_URL = "https://api.siliconflow.cn/v1/chat/completions"
OCR_MODEL = "deepseek-ai/DeepSeek-OCR"
OCR_API_KEY = os.environ.get(
    "EXAM_OCR_API_KEY",
    "sk-cenbimztrqpkfijlcryqzerlnlswxmpvkfuihbjamkfeofwl",
)


# ---------------------------------------------------------------------------
# 飞书机器人（可选，Phase 2 用）
# ---------------------------------------------------------------------------

FEISHU_WEBHOOK_URL = os.environ.get("EXAM_FEISHU_WEBHOOK", "")


# ---------------------------------------------------------------------------
# 关键词→考点 映射表（与 SKILL.md Workflow 3 复用）
# ---------------------------------------------------------------------------

KEYWORD_MAP: List[tuple] = [
    ("回避", "回避制度"),
    ("鉴定", "鉴定程序"),
    ("传唤", "传唤程序"),
    ("证据", "证据规则"),
    ("处罚", "处罚程序"),
    ("强制", "行政强制"),
    ("调解", "治安调解"),
    ("听证", "听证程序"),
    ("扣押", "扣押程序"),
    ("行政复议", "行政复议"),
    ("行政诉讼", "行政诉讼"),
    ("治安管理", "治安管理处罚法"),
    ("程序规定", "办理行政案件程序"),
    # 言语理解
    ("逻辑填空", "逻辑填空-语境分析"),
    ("片段阅读", "片段阅读-主旨概括"),
    ("语句排序", "语句排序"),
    ("语句填空", "语句填空"),
    # 数量关系
    ("行程问题", "行程问题-相遇追及"),
    ("工程问题", "工程问题"),
    ("排列组合", "排列组合"),
    ("概率", "概率问题"),
    ("利润", "利润问题"),
    # 判断推理
    ("图形推理", "图形推理"),
    ("类比推理", "类比推理"),
    ("定义判断", "定义判断"),
    ("逻辑判断", "逻辑判断-加强削弱"),
    ("加强", "加强削弱"),
    ("削弱", "加强削弱"),
    # 资料分析
    ("增长率", "增长率计算"),
    ("增长量", "增长量计算"),
    ("比重", "比重计算"),
    ("平均数", "平均数计算"),
    # 常识判断
    ("宪法", "宪法"),
    ("刑法", "刑法"),
    ("民法", "民法"),
    ("行政法", "行政法"),
]

# 政治理论
("政治", "政治理论"),
("新思想", "政治理论"),


def ensure_dirs() -> None:
    """首次使用时自动创建目录结构和 index.md。"""
    MISTAKE_ROOT.mkdir(parents=True, exist_ok=True)
    KNOWLEDGE_ROOT.mkdir(parents=True, exist_ok=True)
    METHOD_ROOT.mkdir(parents=True, exist_ok=True)

    for t in ALL_TYPES:
        (MISTAKE_ROOT / t / "screenshots").mkdir(parents=True, exist_ok=True)
        (KNOWLEDGE_ROOT / t).mkdir(parents=True, exist_ok=True)

    if not INDEX_FILE.exists():
        INDEX_FILE.write_text(
            _DEFAULT_INDEX_TEMPLATE, encoding="utf-8"
        )

    if not KNOWLEDGE_INDEX_FILE.exists():
        KNOWLEDGE_INDEX_FILE.write_text(
            _DEFAULT_KNOWLEDGE_INDEX_TEMPLATE, encoding="utf-8"
        )

    # V2：确保各题型分索引文件存在
    for qtype in ALL_TYPES:
        cpath = category_index_path(qtype)
        if not cpath.exists():
            cpath.write_text(
                _DEFAULT_CATEGORY_INDEX_TEMPLATE.format(
                    qtype=qtype, updated="2026-01-01"
                ),
                encoding="utf-8",
            )


_DEFAULT_INDEX_TEMPLATE = """---
updated: {updated}
---

# 错题库索引 · 总览

> 最后更新：{updated}
""".format(updated="2026-01-01")


_DEFAULT_KNOWLEDGE_INDEX_TEMPLATE = """---
last_id: 0
total: 0
pending: 0
mastered: 0
updated: 2026-01-01
---

# 知识点库索引

> 共 0 张 | ⏳待复习 0 张 | ✅已掌握 0 张
"""


_DEFAULT_CATEGORY_INDEX_TEMPLATE = """---
last_id: 0
total: 0
pending: 0
mastered: 0
updated: {updated}
qtype: {qtype}
---

# {qtype} · 错题索引

> 共 0 题 | ⏳待复习 0 题 | ✅已掌握 0 题 | 最近更新：{updated}

| ID | 考点 | 错误原因 | 答案 | 来源 | 阶段 | 下次复习 | 状态 |
|----|------|----------|------|------|------|----------|------|

"""

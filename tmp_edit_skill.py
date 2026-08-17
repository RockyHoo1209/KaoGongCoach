import sys
skill_path = r"D:\work\exam-mistake-manager\SKILL.md"
ks_path = r"D:\work\exam-mistake-manager\knowledge_section.md"

with open(ks_path, "r", encoding="utf-8") as f:
    ks = f.read()
print(f"知识库文件: {len(ks)} 字符")

with open(skill_path, "r", encoding="utf-8") as f:
    content = f.read()

# Overview section
overview = (
    "## \U0001f4cb 当前功能总览\n\n"
    "本 Skill 提供以下核心能力（V3 \u2014 SQLite 主存储）：\n\n"
    "### \U0001f5c4 数据库层（SQLite）\n"
    "- `mistakes.db` 为主存储，**不再依赖 .md 文件**作为数据源\n"
    "- 12 个字段：id(PK), question_type, tags(JSON1), ebbinghaus_value, image_path, knowledge_point, error_reason, correct_answer, source, next_review, status, review_history(JSON), created_at\n"
    "- 3 个索引：按题型、状态、下次复习日期快速检索\n"
    "- SQLite JSON1 扩展支持：按标签精确搜索、增删标签、获取所有标签\n\n"
    "### \U0001f527 CLI 命令（`python cli.py <command>`）\n"
    "| 命令 | 功能 |\n"
    "|------|------|\n"
    "| `init-db` | 初始化数据库，支持 `--from-dir` 从现有错题库导入 |\n"
    "| `add` | 添加错题（题型、考点、错因、答案、来源、截图） |\n"
    "| `review` | 今日复习 \u2014 输出题号列表 + 直接展示截图 |\n"
    "| `judge` | 判题（接收用户答案序列，更新艾宾浩斯状态） |\n"
    "| `import-index` | 从 index-*.md 索引文件导入到 SQLite |\n"
    "| `import-batch` | 批量导入截图目录（OCR 自动识别） |\n"
    "| `search` | 组合搜索（题型 / 标签 / 关键词 / ID） |\n"
    "| `tag` | 管理错题标签（增/删/查） |\n"
    "| `stats` | 查看统计（总量、待复习、已掌握、按题型分布） |\n"
    "| `modify` | 修改错题字段（考点/错因/答案/来源/题型/标签/图片路径） |\n"
    "| `delete` | 删除错题 |\n\n"
    "### \U0001f4d0 支持的题型\n"
    "`言语理解` / `数量关系` / `判断推理` / `资料分析` / `常识判断` / `政治理论` / `公安专业知识` / `申论` / `面试`\n\n"
    "### \U0001f504 7 个工作流\n"
    "| 编号 | 名称 | 触发条件 |\n"
    "|:----:|------|---------|\n"
    "| 0 | **初始化数据库** | 首次使用，或从已有错题库导入 |\n"
    "| 1 | **添加错题** | 用户发送截图 + 标签信息 |\n"
    "| 2 | **复习错题** | 用户说\"复习\"/\"抽题\" \u2014 艾宾浩斯到期筛选 + 主动抽题混合复习 |\n"
    "| 3 | **批量导入** | 用户指定截图目录路径 \u2014 OCR 自动识别入库 |\n"
    "| 4 | **知识巩固** | 添加错题后自动触发 \u2014 Wiki MCP 检索 + 历史同类错题对比 |\n"
    "| 5 | **考前速查** | 用户说\"考前速查\" \u2014 薄弱点分析 + Wiki 检索 + 三种输出模式 |\n"
    "| 6 | **批量从对话入库** | 用户在对话中讨论了多道题后说\"入库题目\" |\n"
    "| 7 | **截图抽取模式** | 用户说\"出N题\" \u2014 零文字纯截图展示，用户答完再判 |\n\n"
    "### \u23f0 艾宾浩斯遗忘曲线\n"
    "| 阶段 | 通过后间隔 | 说明 |\n"
    "|:---:|:--------:|------|\n"
    "| 0 | 当天 | 新题 / 答错重置 |\n"
    "| 1 | +1 天 | 第 1 次通过 |\n"
    "| 2 | +2 天 | 第 2 次通过 |\n"
    "| 3 | +4 天 | 第 3 次通过 |\n"
    "| 4 | +7 天 | 第 4 次通过 |\n"
    "| 5 | +15 天 | 第 5 次通过 |\n"
    "| 6 | \u2705 已掌握 | 退出复习队列 |\n\n"
    "### \U0001f3f7 标签系统（SQLite JSON1）\n"
    '- 存储格式：`{"tag": ["易错", "集合推理", "2024国考"]}`\n'
    "- 支持查询：`search --tag 易错` 精确匹配\n"
    "- 支持组合：`search --type 判断推理 --tag 易错 --keyword 集合推理`\n"
    "- 支持管理：`add_tag()` / `remove_tag()` / `get_all_tags()` 通过 SQLite API\n\n"
    "### \U0001f5bc 截图与图片路径\n"
    "- 每个错题关联一张截图（`screenshots/错题-XXX.png` 或绝对路径）\n"
    "- 复习时**直接展示截图**（题号列表 + Markdown 图片语法 `![id](path)`）\n"
    "- 无截图不上（Workflow 7 截图抽取模式严格遵循）\n\n"
    "---\n"
)

# Insert overview after frontmatter (after the ---\r\n\r\n# 考公错题自动化整理)
print(f"正在查找插入点...")
idx = content.find("---\r\n\r\n# 考公错题自动化整理")
print(f"Overview 插入点在位置 {idx}")
content = content[:idx+5] + "\r\n" + overview + content[idx+5:]
print("Overview 插入完成")

# Find Workflow 0 position for knowledge base
wf_idx = content.find("## Workflow 0：初始化数据库")
print(f"Workflow 0 在位置 {wf_idx}")

# Build knowledge base section with proper escaping
kb = (
    "## \U0001f4da 知识库（从参考书籍蒸馏）\n\n"
    "> 以下内容蒸馏自 `E:\\obsidianNote\\考公\\参考书籍` 下的学习资料，使用 cangjie-skill 方法论提取。\n"
    "> 供 AI 在分析错题、出题讲评、考前速查时直接引用，无需外部文件读取。\n\n"
    + ks + "\n"
    "---\n\n"
    "### 标签系统详解（SQLite JSON1）\n\n"
    "SKILL.md 中的 tags 字段使用 SQLite JSON1 扩展实现灵活标签管理。\n\n"
    "**存储格式：**\n"
    '```json\n{"tag": ["易错", "集合推理", "2024国考"]}\n```\n\n'
    "**支持的查询操作（`database.py` 实现）：**\n\n"
    "| 操作 | 函数 | SQL 核心 |\n"
    "|------|------|---------|\n"
    "| 按标签精确搜索 | `search_by_tag(tag)` | `json_each(tags, '$.tag') WHERE value = ?` |\n"
    "| 添加标签 | `add_tag(id, tag)` | 读 JSON \u2192 追加 \u2192 写回 |\n"
    "| 移除标签 | `remove_tag(id, tag)` | 读 JSON \u2192 过滤 \u2192 写回 |\n"
    "| 获取所有标签 | `get_all_tags()` | `SELECT DISTINCT value FROM mistakes, json_each(tags, '$.tag')` |\n"
    "| 组合搜索（题型+标签+关键词） | `search_mistakes(type, tag, keyword)` | `question_type=? AND EXISTS(json_each...) AND (id LIKE ? OR ...)` |\n\n"
    "**对应的 CLI 命令：**\n"
    "```bash\n"
    "# 按标签搜索错题\n"
    "python cli.py search --tag 易错\n"
    "# 组合搜索\n"
    "python cli.py search --type 判断推理 --tag 集合推理\n"
    "# 添加标签\n"
    "python cli.py tag add 错题-001 易错\n"
    "# 移除标签\n"
    "python cli.py tag remove 错题-001 易错\n"
    "```\n\n"
    "---\n\n"
    "### \U0001f5bc 复习输出规范（直接展示截图）\n\n"
    "用户明确要求出题时**直接展示截图**，不发文字重建。\n\n"
    "**V3 截图路径解析逻辑（`review_engine.py`）：**\n"
    "```\n"
    "1. 优先使用 SQLite 中的 image_path（可能是绝对路径或相对路径）\n"
    "2. 若为相对路径 \u2192 拼接 {错题库根目录}/{题型}/{image_path}\n"
    "3. 若找不到 \u2192 依次尝试 screenshots/{id}.png / .jpg / .jpeg / .webp\n"
    "4. 仍找不到 \u2192 标记为无截图\n"
    "```\n\n"
    "**展示格式（`format_review_prompt()`）：**\n"
    "```\n"
    "\U0001f4dd 错题复习 \u00b7 第 N 组\n\n"
    "【题1】错题-{ID}\n"
    "![错题-{ID}]({absolute_image_path})    \u2190 Markdown 语法直接展示截图\n\n"
    "你的答案/思路？（不记得就说\u300c不记得\u300d）\n"
    "```\n\n"
    "**\u26a0\ufe0f 重要规则：**\n"
    "- Workflow 2（复习模式）展示截图时**可以附带题号**，但不写考点/错因/口诀\n"
    "- Workflow 7（截图抽取模式）**严格纯截图、零文字**\u2014\u2014不写编号、不写说明、不判题\n"
    "- 无截图时 Workflow 2 会跳过该题，Workflow 7 会跳过该题\n\n"
    "---\n\n"
)

content = content[:wf_idx] + kb + content[wf_idx:]

with open(skill_path, "w", encoding="utf-8") as f:
    f.write(content)

print(f"\u2705 更新完成！新 SKILL.md 共 {len(content)} 字符")
print(f"   原文件字符数: {len(content) - len(overview) - len(kb)}")
print(f"   Overview: {len(overview)} chars")
print(f"   Knowledge base section: {len(kb)} chars")

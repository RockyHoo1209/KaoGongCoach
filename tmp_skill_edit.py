import sys
skill_path = r"D:\work\exam-mistake-manager\SKILL.md"
ks_path = r"D:\work\exam-mistake-manager\knowledge_section.md"

with open(ks_path, 'r', encoding='utf-8') as f:
    ks_content = f.read()
print(f"知识库文件: {len(ks_content)} 字符, {len(ks_content.splitlines())} 行")

with open(skill_path, 'r', encoding='utf-8') as f:
    content = f.read()

head = """## 📋 当前功能总览

本 Skill 提供以下核心能力（V3 — SQLite 主存储）：

### 🗄 数据库层（SQLite）
- `mistakes.db` 为主存储，**不再依赖 .md 文件**作为数据源
- 12 个字段：id(PK), question_type, tags(JSON1), ebbinghaus_value, image_path, knowledge_point, error_reason, correct_answer, source, next_review, status, review_history(JSON), created_at
- 3 个索引：按题型、状态、下次复习日期快速检索
- SQLite JSON1 扩展支持：按标签精确搜索、增删标签、获取所有标签

### 🔧 CLI 命令（`python cli.py <command>`）
| 命令 | 功能 |
|------|------|
| `init-db` | 初始化数据库，支持 `--from-dir` 从现有错题库导入 |
| `add` | 添加错题（题型、考点、错因、答案、来源、截图） |
| `review` | 今日复习 — 输出题号列表 + 直接展示截图 |
| `judge` | 判题（接收用户答案序列，更新艾宾浩斯状态） |
| `import-index` | 从 index-*.md 索引文件导入到 SQLite |
| `import-batch` | 批量导入截图目录（OCR 自动识别） |
| `search` | 组合搜索（题型 / 标签 / 关键词 / ID） |
| `tag` | 管理错题标签（增/删/查） |
| `stats` | 查看统计（总量、待复习、已掌握、按题型分布） |
| `modify` | 修改错题字段（考点/错因/答案/来源/题型/标签/图片路径） |
| `delete` | 删除错题 |

### 📐 支持的题型
`言语理解` / `数量关系` / `判断推理` / `资料分析` / `常识判断` / `政治理论` / `公安专业知识` / `申论` / `面试`

### 🔄 7 个工作流
| 编号 | 名称 | 触发条件 |
|:----:|------|---------|
| 0 | **初始化数据库** | 首次使用，或从已有错题库导入 |
| 1 | **添加错题** | 用户发送截图 + 标签信息 |
| 2 | **复习错题** | 用户说"复习"/"抽题" — 艾宾浩斯到期筛选 + 主动抽题混合复习 |
| 3 | **批量导入** | 用户指定截图目录路径 — OCR 自动识别入库 |
| 4 | **知识巩固** | 添加错题后自动触发 — Wiki MCP 检索 + 历史同类错题对比 |
| 5 | **考前速查** | 用户说"考前速查" — 薄弱点分析 + Wiki 检索 + 三种输出模式 |
| 6 | **批量从对话入库** | 用户在对话中讨论了多道题后说"入库题目" |
| 7 | **截图抽取模式** | 用户说"出N题" — 零文字纯截图展示，用户答完再判 |

### ⏰ 艾宾浩斯遗忘曲线
| 阶段 | 通过后间隔 | 说明 |
|:---:|:--------:|------|
| 0 | 当天 | 新题 / 答错重置 |
| 1 | +1 天 | 第 1 次通过 |
| 2 | +2 天 | 第 2 次通过 |
| 3 | +4 天 | 第 3 次通过 |
| 4 | +7 天 | 第 4 次通过 |
| 5 | +15 天 | 第 5 次通过 |
| 6 | ✅ 已掌握 | 退出复习队列 |

### 🏷 标签系统（SQLite JSON1）
- 存储格式：`{"tag": ["易错", "集合推理", "2024国考"]}`
- 支持查询：`search --tag 易错` 精确匹配
- 支持组合：`search --type 判断推理 --tag 易错 --keyword 集合推理`
- 支持管理：`add_tag()` / `remove_tag()` / `get_all_tags()` 通过 SQLite API

### 🖼 截图与图片路径
- 每个错题关联一张截图（`screenshots/错题-XXX.png` 或绝对路径）
- 复习时**直接展示截图**（题号列表 + Markdown 图片语法 `![id](path)`）
- 无截图不上（Workflow 7 截图抽取模式严格遵循）

---
"""
# Insert after frontmatter (after the first ---\\n...\\n---\\n\\n# 考公...)
idx = content.find("---\\n\\n# 考公错题自动化整理")
if idx >= 0:
    content = content[:idx+5] + "\\n" + head + content[idx+5:]
    with open(skill_path, 'w', encoding='utf-8') as f:
        f.write(content)
    print(f"✅ 插入成功！新 SKILL.md 字符数: {len(content)}")
else:
    print("❌ 未找到插入点")

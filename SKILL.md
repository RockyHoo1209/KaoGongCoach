---
name: exam-mistake-manager (V3 — SQLite + 知识库集成)
description: "考公错题自动化整理：输入模式（截图+标签→结构化错题入 SQLite）、复习模式（艾宾浩斯遗忘曲线抽题，输出题号列表+直接发送截图）、批量导入模式（目录截图→OCR解析→入库）、知识巩固模式（入题后自动从参考书籍知识库提取相关方法论+历史同类错题对比）、考前速查整理（错题库薄弱点分析+知识库检索+三模式）。"
category: productivity
scripts: ./scripts/
---

# 考公错题自动化整理（V3 — SQLite 主存储 + 知识库集成）

## 功能概述

### 七大核心功能

| 功能 | 说明 |
|------|------|
| **输入模式** | 截图+标签→结构化错题入 SQLite，自动分配题号，复制截图 |
| **复习模式** | 艾宾浩斯遗忘曲线自动抽题，直接发送题号列表+错题截图，用户回忆后判题更新 |
| **纯截图抽取** | 只听用户说出"出N题"，只发截图不发文字，用户答完再判 |
| **批量导入** | 目录截图→DeepSeek-OCR 识别→自动推断题型/考点→入库 |
| **知识巩固** | 入题后自动从知识库匹配陷阱模式，复习时推送相关速查表/口诀 |
| **考前速查** | 从 SQLite 汇总薄弱点，按题型/考点输出速查指南+考场时间分配 |
| **对话批量入库** | 对话中逐一分析了多题→用户说"都入库"→一次脚本批量写入 |

### 用户交互概览

```
你发截图 → 我提取入库
你说"复习" → 我显示题号+艾宾浩斯阶段+截图（直接嵌入图片）
你说"出N题" → 只发截图，零文字
你给答案 → 我判题更新艾宾浩斯阶段
你搜题目 → 我支持按题型/标签/关键词组合搜索
```

---

## 核心数据模型

每条错题在 SQLite mistakes 表中存储的字段如下（**加粗为 V3 必备字段**）：

| 字段 | 类型 | 说明 |
|------|------|------|
| **id** | TEXT PK | **题号**，唯一索引主键，格式 错题-001 |
| **question_type** | TEXT NOT NULL | **题型**，须在 ALL_TYPES 内（判断推理/资料分析/数量关系/政治理论/常识判断/言语理解） |
| **tags** | TEXT | **标签 JSON**，格式 {"tag":[]}，利用 SQLite JSON1 做高效检索 |
| **ebbinghaus_value** | INTEGER DEFAULT 0 | **艾宾浩斯遗忘值**，0-6 阶段，出题时给用户参考 |
| **image_path** | TEXT | **错题图片路径**，截图的绝对路径，复习时直接发送给用户 |
| knowledge_point | TEXT | 考点（兼容保留） |
| error_reason | TEXT | 错误原因（兼容保留） |
| correct_answer | TEXT | 正确答案（兼容保留） |
| source | TEXT | 题目来源（兼容保留） |
| next_review | TEXT | 下次复习日期 YYYY-MM-DD |
| status | TEXT | pending / mastered |
| review_history | TEXT | JSON 复习历史数组 |
| created_at | TEXT | 入库日期 |

### 标签 JSON1 用法

`sql
-- 按标签精确匹配
SELECT * FROM mistakes WHERE EXISTS (
    SELECT 1 FROM json_each(tags, '$.tag') WHERE value = ?
);

-- 列出所有已使用的标签
SELECT DISTINCT value AS tag FROM mistakes, json_each(mistakes.tags, '$.tag') ORDER BY tag;

-- 组合搜索（题型 + 标签 + 关键字）
SELECT * FROM mistakes
WHERE question_type = ?
  AND EXISTS (SELECT 1 FROM json_each(tags, '$.tag') WHERE value = ?)
  AND (id LIKE ? OR knowledge_point LIKE ? OR error_reason LIKE ? OR source LIKE ?);
`

> 标签格式固定为 {"tag":[]}，[] 内为字符串数组。后续用户可根据标签检索对应题目。

---

## 目录结构

`
{MISTAKE_ROOT}/
├── mistakes.db              ← SQLite 数据库（主存储）
│   └── mistakes 表          ← 字段见上方核心数据模型
├── 言语理解/                 ← Obsidian 兼容（.md 文件，复习时不需读写）
├── 数量关系/
├── 判断推理/
├── 资料分析/
├── 常识判断/
├── 政治理论/                 ← V3 新增题型
├── 公安专业知识/
├── 申论/
└── 面试/

{KNOWLEDGE_ROOT}/
├── knowledge.db             ← 知识库 SQLite（来自参考书籍蒸馏）
│   ├── 资料分析_公式          ← 公式卡片（含口诀+适用条件）
│   ├── 资料分析_陷阱          ← 陷阱模式（含防御口诀+历史错题索引）
│   ├── 判断推理_框架          ← 决策框架（图形入口/论证力度比较等）
│   ├── 数量关系_公式          ← 数量关系公式
│   └── 言语理解_方法论        ← 言语理解方法论
├── 资料分析/                 ← 知识点 .md 文件（Obsidian 兼容）
├── 判断推理/
├── 数量关系/
└── ...
`

> 截图文件组织结构：{题型}/screenshots/{错题-ID}.png（或 .jpg/.webp），复习时通过 image_path 字段的**绝对路径**直接发送图片。
>
> index-*.md 和 index.md 索引文件**仅用于首次导入**，导入后所有 CRUD 操作均通过 SQLite 完成。

---

## CLI 快速参考（V3 — SQLite 版）

`bash
# 初始化数据库 + 从现有错题库导入
python scripts/cli.py init-db --from-dir E:\obsidianNote\考公\错题库
python scripts/cli.py init-db --force                          # 强制重建

# 从 index-*.md 索引文件导入到 SQLite（首次迁移用）
python scripts/cli.py import-index E:\obsidianNote\考公\错题库
python scripts/cli.py import-index . --dry-run          # 仅预览

# 添加一道错题
python scripts/cli.py add \
  --type 判断推理 --point 加强削弱 \
  --reason 知识点盲区 --answer B \
  --source 2024国考行测 [--screenshot /path/to/img.png]

# 生成今日复习题（输出题号列表 + 直接展示截图）
python scripts/cli.py review [--date YYYY-MM-DD] [--batch-size 5]

# 判题并更新状态
python scripts/cli.py judge "1.B 2.C 3.A 4.D 5.B" [--date YYYY-MM-DD]

# 组合搜索（按题型 / 标签 / 关键词）
python scripts/cli.py search --type 判断推理 --tag 易错 --keyword 集合推理

# 批量导入截图目录
python scripts/cli.py import-batch /path/to/dir \
  [--reason 待补充] [--source-name 公安题库] [--dry-run]

# 查看统计（从 SQLite 读取）
python scripts/cli.py stats

# 修改错题字段
python scripts/cli.py modify 错题-001 --type 判断推理 \
  --field knowledge_point --value 图形推理

# 删除错题
python scripts/cli.py delete 错题-001 --type 判断推理
`

> ⚠️ Python 版本要求：代码使用了 from __future__ import annotations（Python 3.7+），默认 python 命令为 Anaconda 3.6 无法运行。请使用 C:\Users\Administrator\.local\bin\python3.12.exe 或设置别名。

---

## ✅ 支持的题型（ALL_TYPES）

`
言语理解 / 数量关系 / 判断推理 / 资料分析 / 常识判断 / 政治理论
`

扩展科目：公安专业知识 / 申论 / 面试

> 用户可根据题型搜索题目或聚合查询。传入不在此列表中的题型会抛出 ValueError。

---

## 知识库集成（参考书籍蒸馏 + cangjie-skill）

### 提取方式

使用 cangjie-skill 方法对 `E:\obsidianNote\考公\参考书籍` 下的 8 份核心资料进行蒸馏提取：

1. 对每份资料执行 Adler 整书理解 + RIA 框架提取
2. 将提取的公式/陷阱/方法论按题型分类整理
3. 生成 `knowledge_section.md`（22KB）作为**内联知识库**（已包含在当前 skill 中）
4. 后续维护：参考书籍内容更新时，重新运行 cangjie-skill 提取并更新 knowledge_section.md

### 参考资料列表

| 文件 | 覆盖领域 |
|------|---------|
| 【判断推理讲义（下册）】.md | 判断推理全套方法论 |
| 【判断理论讲义（上册）】.md | 判断推理基础理论 |
| 数量关系总结笔记.md | 数量关系公式与技巧 |
| 资料分析3页纸.md | 资料分析精华 3 页 |
| 资料分析·你的专属易错公式卡.md | 资料分析易错公式卡 |
| 资料分析公式与抄错原因速查.md | 公式+抄错原因速查表 |
| 资料分析公式汇总.md | 资料分析全公式汇总 |
| 资料分析常用公式速查.md | 资料分析常用公式速查表 |

### 知识库用途

知识库为**只读引用**，不随错题 CRUD 修改，通过 cangjie-skill 方法蒸馏后整合到 skill 的 `knowledge_section.md` 中。AI 在分析错题、出题讲评、考前速查时直接从中引用，无需外部读取。

| 场景 | 调用方式 |
|------|---------|
| **入库时自动匹配陷阱模式** | 从知识库检索同类错题，追加到 references/ |
| **复习时推送相关速查** | 判题后从知识库拉取对应考点的速查表/口诀 |
| **考前速查** | 知识库索引→薄弱点分析→按题型输出速查指南 |
| **新增题考点自动分类** | 基于知识库关键词映射表判定考点 |

### 知识库维护

当参考书籍内容更新时，重新使用 cangjie-skill 方法蒸馏：

1. 读取 `E:\obsidianNote\考公\参考书籍` 下的 .md 文件
2. 对每份资料执行 Adler 整书理解 + RIA 框架提取
3. 将提取的公式/陷阱/方法论追加到 `knowledge_section.md`
4. 验证知识点与错题 references/ 的关联一致性

> `knowledge_section.md`（22KB）包含了从 8 份参考资料提取的全部知识体系：
> 花生十三 ABRX 体系、资料分析 14 类公式、判断推理完整框架（图形推理五定性/六提示/四类图/定义判断/类比推理/逻辑论证）、
> 数量关系（工程/行程/排列组合/概率/经济利润/溶液/几何）、政治理论高频考点、常识判断高频考点。

## Workflow 0：初始化数据库（含现有错题库导入）

### 触发条件
- 首次使用本系统
- 用户说"初始化" / "导入错题库" / "开始使用"

### Step 1：询问用户是否有已有错题库

使用自然语言询问用户：
`
请问你是否已有错题库？
- 如果有，请提供错题库根目录路径（如 E:\obsidianNote\考公\错题库），我将自动扫描导入。
- 如果没有或不需要导入，我将直接创建空数据库。
`

如果用户回答"没有"或"不需要"：
→ 直接调用 init_db() 创建空数据库

如果用户提供路径：
→ 验证目录是否存在，进入 Step 2

### Step 2：扫描索引文件 + 错题文件，导入到 SQLite

`python
mistake_root = Path(user_provided_path)

# 1. 建表
_db.init_db(force=False)

# 2. 从 index-*.md / index.md 导入
#    ☆ 扫描 {根目录}/**/index-*.md（支持递归查找）
#      解析每个 index-{题型}.md 的表格行，提取 ID/考点/错因/答案/来源/阶段
#    ☆ 扫描 {根目录}/index.md（复合格式，带 ## 题型标题 + 表格行）
#    ☆ 对每条记录，在对应题型目录的 screenshots/ 下查找匹配的截图文件
#       （支持 .png/.jpg/.jpeg/.webp），找到后将绝对路径存入 image_path
_db.import_from_index_files(mistake_root=str(mistake_root))

# 3. 从 错题-*.md 文件导入（补充导入未被索引覆盖的 .md 文件）
_db.import_from_mistake_root(mistake_root=mistake_root)

# 4. 输出统计
stats = _db.get_stats_db()
`

**图片查找策略**：
`
for each item in index file:
    提取 id = "错题-XXX", 题型 = qtype
    在 {root}/{qtype}/screenshots/ 查找文件（按优先级）：
        screenshots/{id}.png
        screenshots/{id}.jpg
        screenshots/{id}.jpeg
        screenshots/{id}.webp
    如果找到：image_path = 该文件的**绝对路径**（存入 SQLite）
    如果找不到：image_path = ""（后续可手动补充）
`

### Step 3：向用户报告导入结果

报告包含：
- 总题数、待复习/已掌握数量
- 各题型分布
- 成功/跳过/错误数
- 有截图 vs 无截图统计

**导入报告示例**：
```
## ✅ 迁移到 SQLite 完成

### 📊 导入统计

| 指标 | 数值 |
|------|------|
| 总数 | 128 |
| 成功导入 | 126 |
| 跳过 | 2 |
| 错误 | 0 |

### 📋 导入明细（前 10 条）

| ID | 题型 | 考点 | 状态 | 截图 |
|----|------|------|------|------|
| 错题-001 | 判断推理 | 加强削弱 | ⏳待复习 | ✅ 有截图 |
| 错题-002 | 资料分析 | 增长率计算 | ✅已掌握 | ✅ 有截图 |
| 错题-003 | 数量关系 | 行程问题 | ⏳待复习 | ❌ 无截图 |
| ... | ... | ... | ... | ... |
```

**导入报告示例**：
```
## ✅ 迁移到 SQLite 完成

### 📊 导入统计

| 指标 | 数值 |
|------|------|
| 总数 | 128 |
| 成功导入 | 126 |
| 跳过 | 2 |
| 错误 | 0 |

### 📋 导入明细（前 10 条）

| ID | 题型 | 考点 | 状态 | 截图 |
|----|------|------|------|------|
| 错题-001 | 判断推理 | 加强削弱 | ⏳待复习 | ✅ 有截图 |
| 错题-002 | 资料分析 | 增长率计算 | ✅已掌握 | ✅ 有截图 |
| 错题-003 | 数量关系 | 行程问题 | ⏳待复习 | ❌ 无截图 |
| ... | ... | ... | ... | ... |
```

### ⚠️ 注意事项
- **图片路径自动绑定**：导入时会自动扫描 screenshots/ 下的 png/jpg/webp 文件，将**绝对路径**存入 image_path
- **不覆盖已有数据**：init_db(force=True) 仅在使用 --force 标志时重建
- **支持两种目录结构**：可直接指向错题库目录（含 index-*.md），也可指向 Obsidian 根目录（错题库/ 子目录）
- **标签默认空**：导入的条目 tags 默认 {"tag":[]}，用户后续可通过 add_tag / 
emove_tag 操作
- **原有 index-*.md 不受影响**：导入过程只读这些索引文件，不会修改或删除它们

---

## 艾宾浩斯遗忘曲线间隔表

由 scheduler.py 实现，间隔配置在 config.EBBINGHAUS_INTERVALS：

| 阶段（stage） | 状态 | 通过后间隔（天） | 到达方式 |
|:---:|------|:---:|------|
| 0 | 新题 / 答错重置 | 当天 | 新建 或 fail_review() |
| 1 | 第 1 次通过 | +1 | pass_review(stage=0) |
| 2 | 第 2 次通过 | +2 | pass_review(stage=1) |
| 3 | 第 3 次通过 | +4 | pass_review(stage=2) |
| 4 | 第 4 次通过 | +7 | pass_review(stage=3) |
| 5 | 第 5 次通过 | +15 | pass_review(stage=4) |
| 6 | ✅ 已掌握 | — | pass_review(stage=5) → MASTERED_STAGE |

**答错（fail_review()）**：任意阶段答错 → stage=0，
 next_review = 明天。
**模糊记得（fuzzy_review()）**：stage 不变，
 next_review 取相邻两档间隔的中值（供扩展，当前 CLI 未暴露）。
**已掌握**：stage=6 >= MASTERED_STAGE(6) → status="mastered"，退出复习队列，
 next_review 设为 今天+3650天（占位，不会被抽到）。

---

## Workflow 1：添加错题（输入模式）

### 触发条件
- 用户发送截图后，下一条消息包含标签信息
- 用户明确说"添加错题"/"记录错题"

### 必填字段（缺失时追问）

| 字段 | Python 参数 | 说明 |
|------|-------------|------|
| 题型 | question_type | 必须在 ALL_TYPES 内 |
| 考点 | knowledge_point | 具体知识点 |
| 错误原因 | error_reason | 知识点盲区 / 计算失误 / 审题偏差 / 方法不会 / 粗心 / 时间不够 |
| 正确答案 | correct_answer | A/B/C/D 或 √/× |
| 来源 | source | 试卷名称 |
| 标签 | tags | 可选，JSON 格式 {"tag":[]}。用户给出的标签如"易错/高频"等 |

### 执行步骤

`
1. 调用 config.ensure_dirs() 确保目录存在
2. 调用 db.get_next_id_db() 从 SQLite 生成新 ID
   → SELECT MAX(CAST(SUBSTR(id, 4) AS INTEGER)) FROM mistakes
   → MAX+1，格式化为 错题-XXX
3. 调用 mistake_manager.create_mistake(...)
   → 写入 SQLite（主存储）：
      · id, question_type, tags, ebbinghaus_value=0,
        image_path={截图绝对路径}, knowledge_point, error_reason,
        correct_answer, source, next_review=today, status=pending
   → 复制截图到 {题型}/screenshots/{新ID}.png（若提供 screenshot_src）
   → 写入 {题型}/{新ID}.md（Obsidian 兼容）
`

### 回复用户

`
✅ 已保存 错题-XXX
📂 {题型}/{考点}
📅 已加入复习队列，下次复习 {next_review}
🏷️ 标签：{tags}
🖼️ 截图：{image_path}
`

---

## Workflow 2：复习错题 — 输出题号 + 直接发送截图

### 触发条件
- 用户说"复习"/"复习错题"/"来几题"/"抽题"/"继续复习"

### Step 1：扫描到期题目

`python
# 从 SQLite 读取到期题目
# SELECT * FROM mistakes
# WHERE status != 'mastered'
#   AND next_review <= ?
#   AND knowledge_point NOT IN ('', '待补充')
#   AND error_reason NOT IN ('', '待补充')
# ORDER BY next_review ASC, ebbinghaus_value ASC, id
`

**⚠️ 过滤"待补充"条目**：早期入库的很多错题的 knowledge_point 和 error_reason 为"待补充"，没有考点和错因，复习价值极低。到期扫描时必须过滤这两项。

**当到期不足时的补位策略**：
1. 从同题型选取最近的（created_at DESC）且 knowledge_point != "待补充" 的条目补位
2. 它们在艾宾浩斯计划上尚未到期但内容完整，补位复习优于无内容复习
3. 给用户说明：（N 题到期，补 M 题近期入库题凑够一批）

若无到期题目且无可补位：输出"今天没有待复习的错题，下一次复习在 {最近 next_review}"。

### Step 2：取一批（默认 5 题）

`python
# review_engine.take_batch(due, batch_size=config.REVIEW_BATCH_SIZE)
selected = due[:batch_size]
`

### Step 3：展示题目（V3 — 题号 + 直接展示图片）

**V3 展示方法（用户要求：出题时只需要给出题号列表和发送对应图片路径的图片）：**

`
📝 错题复习 · 第 N 组（复习模式）

【题1】错题-{ID}  |  {题型}  |  {考点}  |  艾宾浩斯 {stage}/6
![错题-{ID}]({image_path_abs})

【题2】错题-{ID}  |  {题型}  |  {考点}  |  艾宾浩斯 {stage}/6
![错题-{ID}]({image_path_abs})
...

请回忆答案并用格式回复：1.B 2.C 3.A ...（或写思路描述，不记得就说「不记得」）
`

**图片发送策略（复习时**必须**遵守）**：

1. 从 SQLite mistakes 表读取 image_path 字段（绝对路径）
2. 如果 image_path 为空 → 降级查找 {题型}/screenshots/{id}.png/.jpg/.webp
3. 如果找到 → 用 Markdown 图片语法 ![{id}]({绝对路径}) 嵌入回复作为**可直接看到的图片**
4. 如果没有找到任何截图 → **跳过该题**（不展示无图题目）
5. **每条题目都附带题号和艾宾浩斯阶段值**，方便用户定位和评估难度

> ⚠️ **不要**使用 MEDIA: 标记或不明确的路径引用——用户需要直接在回复中看到截图。
> **必须** 在回复中用 ![错题-XXX](绝对路径) 嵌入图片，让图片直接显示在对话中。
> **review 时不仅输题号列表和路径，也直接将对应图片发送给用户。**

### Step 4：解析答案并判题

答案解析由 review_engine._parse_answers() 处理，支持分隔符：. ． ， , 、

**判题规则（_is_forget(answer)）：**
- 为空 → ❌ 失败
- 包含关键词「不记得 / 忘了 / 不会 / 跳过 / 不知道 / 没印象」→ ❌ 失败
- 字符长度 ≤ 1（含单个字母）→ ❌ 失败（单字母视为没有实质内容）
- 其他任何描述性回答 → ✅ 通过

> ⚠️ **注意**：当前判题不核对正确答案字母，能描述思路即为通过。

### Step 5：更新状态

`python
# ⚠️ pass_review(stage, today) → (new_stage, next_review, is_mastered)  # 3 值
# ⚠️ fail_review(today)       → (stage, next_review)                   # 2 值

if passed:
    new_stage, next_review, is_mastered = scheduler.pass_review(old_stage, today)
else:
    new_stage, next_review = scheduler.fail_review(today)

mistake_manager.update_review_state(
    mistake_id=eid, question_type=qt, passed=passed,
    review_stage=new_stage, next_review=next_review,
    status="learning", review_date=today.isoformat(),
    old_stage=old_stage,
)
`

> 🐛 **常见坑**：pass_review 返回 3 个值而 fail_review 只返回 2 个。如果用相同变量数解包会触发 ValueError: too many values to unpack。

---

## Workflow 7：纯截图抽取（只发图，零文字）

### 触发条件
- 用户说"出N题"/"再出N题"/"抽题"/"抽几道题"

### 核心规则（2026-07-23 用户明确纠正，不可违反）

1. **只发原图，零文字** — 不发考点说明、不发题目重建文字、不发错因分析、不发口诀、不发任何解释性文字
2. **截图文件存在时直接展示** — 用 ![错题-{ID}]({绝对路径}) 直接嵌入
3. **无截图不上** — 若截图文件不存在，直接跳过该题，不文字重建、不替代展示
4. **不发汇总表** — 不发 ID/考点/答案对照表、不发陷阱分析、不判题、不更新复习状态
5. **等用户答完再响应** — 用户把答案发回来后，才做判题+讲评+状态更新

**一句话记忆：** 「题图直出→用户自己做→用户发答案→我再判」。不发考点/错因/口诀/汇总表。

### 与 Workflow 2 的区别

| 维度 | Workflow 2（复习模式） | Workflow 7（纯截图抽取） |
|------|----------------------|--------------------------|
| 触发 | 说"复习"/"判题" | 说"出N题"/"再出N题"/"抽题" |
| 输出方式 | 文字+截图混合 | **纯截图，零文字** |
| 判题时机 | 用户答完即判 | 等用户主动发答案再判 |

---

## Workflow 3：批量导入截图目录

### 触发条件
- 用户说"批量导入"/"导入错题截图"/"import batch"

### 流程

`python
# 1. 扫描源目录下常见图片格式（png/jpg/jpeg/webp/bmp）
images = _collect_images(source_dir)

# 2. 调用 DeepSeek-OCR（SiliconFlow）提取题干文本
for img in images:
    ocr_result = _call_ocr_api(img)
    # 解析题号/选项/考点/答案

# 3. 复制原图到错题库，创建 .md 文件，写入 SQLite
# 4. 输出质量报告（OCR 质量/需校验条目）
`

---

## Workflow 6：对话批量入库（已讨论的题一次性写入）

### 触发条件
- 用户说"帮我把以上题目都入库"/"把这些题入库"/"都入库"/"入库题目"
- 用户与你在对话中讨论了多道题（截图/文字），逐一给出正解和错因，然后要求一次性全部入库

### ⚡ 核心行为规则：立即执行，不犹豫

**当用户说「入库题目」时，如果截图和错因分析已在对话上下文中（刚刚分析完），必须立即批量导入，不要：**
- ❌ 先去检查目录结构（ls/树状图）
- ❌ 先去读现有 index.md 确认 last_id
- ❌ 先问用户"确认要入库吗"
- ❌ 先解释步骤流程

**正确动作：** 直接在回复中告知将分配哪些 ID，然后写脚本一次性全部写入。如果缺少某道题的完整信息，跳过该题并在汇总中说明，不等用户补充。

### 关键步骤

1. 从对话提取题型/考点/错因/正确答案/用户答案/来源
2. 分配 ID → 写入 SQLite → 创建 .md 文件 → 复制截图
3. 检查这批题是否有共同陷阱模式，如果有 ≥2 题相同 → 合并写入 
eferences/
4. 输出汇总表

---

## Workflow 5：考前速查整理

### 触发条件
- 用户说"考前速查"/"整理速查表"/"帮我整理薄弱点"

### 三模式

| 模式 | 触发 | 输出 |
|------|------|------|
| **完整指南** | 用户说"完整指南" | 全题型薄弱点分析 + 各题型必背公式/框架/陷阱 + 考场时间分配 |
| **单概念速查** | 用户说"速查 XX 考点" | 该考点的公式/口诀/易错点 + 关联历史错题 |
| **题型方法论** | 用户说"XX 题型方法论" | 该题型的决策框架/first-step 口诀 + 高频陷阱 |

---

## 辅助操作

### 查看进度（stats）
`python
stats = _db.get_stats_db()
# 输出 total / pending / mastered / updated + 各题型分布 + 有截图/无截图统计
`

### 修改错题字段（modify）
可修改字段：knowledge_point / error_reason / correct_answer / source / question_type

若修改 question_type：自动将 .md 和截图移动到新题型目录，重写 SQLite 中的 question_type。

### 删除错题（delete）
删除 {题型}/{ID}.md + {题型}/screenshots/{ID}.png，从 SQLite 删除记录。

### 重建索引（index sync）
**触发条件**：SQLite 数据与 .md 文件数不一致，或怀疑数据陈旧。
**执行**：扫描各题型目录的所有 .md 文件，对 SQLite 中不存在的条目调用 load_card() 读取 frontmatter 后重新入库。

---

## 数据一致性规则（V3 — SQLite 主存储）

1. **SQLite 是主存储**——所有 CRUD 操作优先写入 mistakes.db
2. **双写保证一致性**——mistake_manager.py 的 create_mistake() / update_review_state() / delete_mistake() / modify_mistake() 同时写入 SQLite 和 .md 文件
3. **复习调度从 SQLite 读取**——
eview_engine.select_due_items() 从 mistakes.db 的 get_due_entries_db() 获取到期条目
4. **统计从 SQLite 读取**——cli.py stats 通过 db.get_stats_db() 获取准确统计
5. **标签通过 JSON1 管理**——使用 add_tag() / 
emove_tag() / get_all_tags() 操作，支持 json_each() 高效检索

---

## 配置速查（config.py）

| 变量 | 默认值 | 环境变量覆盖 |
|------|--------|-------------|
| OBSIDIAN_ROOT | E:\obsidianNote\考公 | EXAM_OBSIDIAN_ROOT |
| EXAM_DATE | 2026-11-01 | EXAM_EXAM_DATE |
| DATABASE_PATH | {MISTAKE_ROOT}/mistakes.db | EXAM_MISTAKES_DB |
| OCR_API_URL | https://api.siliconflow.cn/v1/chat/completions | — |
| OCR_MODEL | deepseek-ai/DeepSeek-OCR | — |
| OCR_API_KEY | config 内默认值 | EXAM_OCR_API_KEY |
| REVIEW_BATCH_SIZE | 5 | — |
| MASTERED_STAGE | 6 | — |
| EBBINGHAUS_INTERVALS | [0,1,2,4,7,15] | — |
| FEISHU_WEBHOOK_URL | "" | EXAM_FEISHU_WEBHOOK |

---

## 📎 参考文件

| 文件 | 内容 |
|------|------|
| 
eferences/图形推理-九宫格.md | 九宫格题型方法论：排查顺序、三种典型题型速判、考场速记口诀 |
| 
eferences/图形推理-通用入口口诀.md | 图形推理通用入口决策树 + 四大专项突破 + 高频错因 |
| 
eferences/资料分析-公式速查.md | 资料分析 14 类常用公式 + 高频推论 |
| 
eferences/资料分析-三大陷阱防御.md | 句式陷阱/计算错误/图表对应三大防御框架 + 7 项自检清单 |
| 
eferences/判断推理-高频考点规律速查.md | 面数量/功能元素/黑白运算/搭桥力度比较等 + 口诀+历史错题 |
| 
eferences/资料分析-纯增长率公式速查.md | 5 个只需增速不需绝对量的公式 |
| scripts/database.py | SQLite 数据库层：CRUD + JSON1 标签检索 + 索引导入 |
| scripts/mistake_manager.py | 错题管理器：双写 SQLite + .md 文件 |
| scripts/cli.py | CLI 入口：init-db / add / review / judge / search / stats 等 |
| scripts/scheduler.py | 艾宾浩斯调度：pass / fail / fuzzy 三种结果 |
| scripts/review_engine.py | 复习引擎：到期筛选 + 批量判题 + 状态更新 |
| scripts/config.py | 全局配置：路径 / 考试日期 / API / 艾宾浩斯参数 |
| scripts/tests/ | 测试文件 |

---

## ⚡ 批量效率提示

- **批量更新艾宾浩斯用 Python 脚本，不要逐条 patch**：当用户一次性评价 10 道题（如「055不记得 其他通过」），写一个临时 Python 脚本一次性处理全部 10 个 .md 文件。单独 patch 调用 10 次 + 更新 index 10 行 = 20+ 工具调用；一次 Python 脚本 = 1 次 write_file + 1 次 	erminal。

## 已知限制与注意事项

- **红笔手写答案 OCR 不可靠**：印刷体准确率高，手写答案识别率约 30%，批量导入后建议人工逐题校验
- **判题不核对字母**：_is_forget() 只判断「是否记得」，不做 A/B/C/D 对错比较
- **单字母回复视为失败**：len(answer) <= 1 判定为没有实质内容
- **索引文件格式陷阱**：部分 index.md 行以 || 开头而非 |，或行内嵌入 \n 字面量。用 Python 脚本逐行 split("|") → 逐列更新 → join("|") 重建，避开正则匹配。
- **距考试天数计算**：从 config.EXAM_DATE（默认 2026-11-01）与今日日期之差自动计算。
- **WSL 环境路径陷阱**：必须设置 EXAM_OBSIDIAN_ROOT=/mnt/e/obsidianNote/考公，否则 Python 的 Path("E:\\...") 不会自动映射。



## 👤 用户使用指南（快速上手）

### 首次使用

```
你：你好，我想初始化错题库。
我：请问你是否有已有错题库？如果有，请提供根目录路径（如 E:\obsidianNote\考公\错题库）。
你：有，路径是 E:\obsidianNote\考公\错题库。
我：扫描 index-*.md / index.md → 寻找对应截图 → 导入 SQLite → 返回导入统计。
```

### 日常使用

| 你说 | 我做 |
|------|------|
| "添加错题" / 发截图+标签 | 分配题号、入库、复制截图、回复确认信息 |
| "复习" / "来几题" | 从 SQLite 抽到期题目，显示题号+艾宾浩斯阶段+**直接嵌入截图** |
| "出3题" / "抽几道题" | **只发截图，零文字**，等用户答完再判 |
| "1.B 2.C 3.不记得" | 判题→更新艾宾浩斯阶段→回复结果 |
| "搜索判断推理的集合推理题" | 按题型/标签/关键词组合检索 |
| "统计" / "进度" | 从 SQLite 返回总题数/待复习/已掌握+题型分布 |
| "帮我把以上题目都入库" | 一次性写入对话中刚刚分析过的所有题目 |
| "考前速查" / "完整指南" | 薄弱点分析+各题型必背公式+考场时间分配 |
| "速查增长率公式" | 从 knowledge_section.md 检索对应考点速查 |

### 复习时 AI 必须遵守的规则

> ⚠️ **三条铁律，违反一条即为错误行为：**
>
> 1. **必须直接嵌入图片** — 用 `![错题-{ID}]({绝对路径})` Markdown 语法让图片直接在对话中可见。不得使用 MEDIA:、不得仅提供路径文字、不得使用引用语法。
>
> 2. **无截图不上题** — 若图片文件不存在（image_path 为空且 screenshots/ 下无对应文件），直接跳过该题，不得文字重建题目内容。
>
> 3. **纯截图抽取模式零文字** — 用户说"出N题"时只发截图，不发考点说明/错因分析/口诀/汇总表。等用户答完再判。

#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Improve SKILL.md with concrete examples and better documentation."""
import sys
import os

sys.stdout = open(sys.stdout.fileno(), mode='w', encoding='utf-8', buffering=1)

with open('D:\\work\\exam-mistake-manager\\SKILL.md', 'r', encoding='utf-8') as f:
    content = f.read()

changes = []

# === Improvement 1: Update image finding strategy in Workflow 0 ===
old_img_search = (
    '**图片查找策略**：\n'
    '```\n'
    'for each item in index file:\n'
    '    提取 id = "错题-XXX", 题型 = qtype\n'
    '    在 {root}/{qtype}/screenshots/ 查找文件（按优先级）：\n'
    '        screenshots/{id}.png\n'
    '        screenshots/{id}.jpg\n'
    '        screenshots/{id}.jpeg\n'
    '        screenshots/{id}.webp\n'
    '    如果找到：image_path = 该文件的**绝对路径**（存入 SQLite）\n'
    '    如果找不到：image_path = ""（后续可手动补充）\n'
    '```'
)

new_img_search = (
    '**图片查找策略（双路径回退）**：\n'
    '```\n'
    'for each item in index file:\n'
    '    提取 id = "错题-XXX", 题型 = qtype\n'
    '    # 优先在用户提供的导入目录中查找\n'
    '    路径1 = {target_root}/{qtype}/screenshots/{id}.png/.jpg/.jpeg/.webp\n'
    '    # 回退到默认 Obsidian 错题库目录查找\n'
    '    路径2 = {config.MISTAKE_ROOT}/{qtype}/screenshots/{id}.png/.jpg/.jpeg/.webp\n'
    '    如果 路径1 存在：image_path = 路径1的**绝对路径**\n'
    '    否则如果 路径2 存在：image_path = 路径2的**绝对路径**\n'
    '    否则：image_path = ""（后续可手动补充）\n'
    '```\n'
    '> 双路径回退确保：用户提供的导入目录和默认 Obsidian 错题库目录下的截图都能被自动识别。'
)

if old_img_search in content:
    content = content.replace(old_img_search, new_img_search)
    changes.append('Improvement 1: Image finding strategy updated with dual-path fallback.')
else:
    changes.append('Improvement 1: SKIP - old text not found.')

# === Improvement 2: Add concrete import report example in Workflow 0 Step 3 ===
old_step3 = (
    '### Step 3：向用户报告导入结果\n'
    '\n'
    '报告包含：\n'
    '- 总题数、待复习/已掌握数量\n'
    '- 各题型分布\n'
    '- 成功/跳过/错误数\n'
    '- 有截图 vs 无截图统计'
)

new_step3 = (
    '### Step 3：向用户报告导入结果\n'
    '\n'
    '报告包含：\n'
    '- 总题数、待复习/已掌握数量\n'
    '- 各题型分布\n'
    '- 成功/跳过/错误数\n'
    '- 有截图 vs 无截图统计\n'
    '\n'
    '**导入报告示例**：\n'
    '```\n'
    '## ✅ 迁移到 SQLite 完成\n'
    '\n'
    '### 📊 导入统计\n'
    '\n'
    '| 指标 | 数值 |\n'
    '|------|------|\n'
    '| 总数 | 128 |\n'
    '| 成功导入 | 126 |\n'
    '| 跳过 | 2 |\n'
    '| 错误 | 0 |\n'
    '\n'
    '### 📋 导入明细（前 10 条）\n'
    '\n'
    '| ID | 题型 | 考点 | 状态 | 截图 |\n'
    '|----|------|------|------|------|\n'
    '| 错题-001 | 判断推理 | 加强削弱 | ⏳待复习 | ✅ 有截图 |\n'
    '| 错题-002 | 资料分析 | 增长率计算 | ✅已掌握 | ✅ 有截图 |\n'
    '| 错题-003 | 数量关系 | 行程问题 | ⏳待复习 | ❌ 无截图 |\n'
    '| ... | ... | ... | ... | ... |\n'
    '```'
)

if old_step3 in content:
    content = content.replace(old_step3, new_step3)
    changes.append('Improvement 2: Import report example added.')
else:
    changes.append('Improvement 2: SKIP - old text not found.')

# === Improvement 3: Add concrete review example in Workflow 2 ===
old_review_example = (
    '**V3 展示方法（用户要求：出题时只需要给出题号列表和发送对应图片路径的图片）：**\n'
    '\n'
    '```\n'
    '📝 错题复习 · 第 N 组（复习模式）\n'
    '\n'
    '【题1】错题-{ID}  |  {题型}  |  {考点}  |  艾宾浩斯 {stage}/6\n'
    '![错题-{ID}]({image_path_abs})\n'
    '\n'
    '【题2】错题-{ID}  |  {题型}  |  {考点}  |  艾宾浩斯 {stage}/6\n'
    '![错题-{ID}]({image_path_abs})\n'
    '...\n'
    '\n'
    '请回忆答案并用格式回复：1.B 2.C 3.A ...（或写思路描述，不记得就说「不记得」）\n'
    '```'
)

new_review_example = (
    '**V3 展示方法（用户要求：出题时只需要给出题号列表和直接展示对应图片）：**\n'
    '\n'
    '**实际输出格式示例**（用户看到的效果）：\n'
    '\n'
    '```\n'
    '📝 错题复习 · 第 1 组（复习模式）\n'
    '\n'
    '【题1】错题-050  |  判断推理  |  加强削弱  |  艾宾浩斯 2/6\n'
    '![错题-050](E:\\obsidianNote\\考公\\错题库\\判断推理\\screenshots\\错题-050.png)\n'
    '\n'
    '【题2】错题-078  |  资料分析  |  增长率计算  |  艾宾浩斯 1/6\n'
    '![错题-078](E:\\obsidianNote\\考公\\错题库\\资料分析\\screenshots\\错题-078.png)\n'
    '\n'
    '【题3】错题-112  |  数量关系  |  工程问题  |  艾宾浩斯 3/6\n'
    '![错题-112](E:\\obsidianNote\\考公\\错题库\\数量关系\\screenshots\\错题-112.png)\n'
    '\n'
    '...\n'
    '\n'
    '请回忆答案并用格式回复：1.B 2.C 3.A ...（或写思路描述，不记得就说「不记得」）\n'
    '```\n'
    '\n'
    '> ⚠️ 截图通过 Markdown 图片语法 ![错题-{ID}]({绝对路径}) 直接嵌入回复中，用户在对话中**直接看到图片**，无需手动打开文件。'
)

if old_review_example in content:
    content = content.replace(old_review_example, new_review_example)
    changes.append('Improvement 3: Review example updated with concrete output format.')
else:
    changes.append('Improvement 3: SKIP - old text not found.')

# === Improvement 4: Enhance image sending rules ===
old_image_rules = (
    '**图片发送策略（复习时**必须**遵守）：**\n'
    '\n'
    '1. 从 SQLite mistakes 表读取 image_path 字段（绝对路径）\n'
    '2. 如果 image_path 为空 → 降级查找 {题型}/screenshots/{id}.png/.jpg/.webp\n'
    '3. 如果找到 → 用 Markdown 图片语法 ![{id}]({绝对路径}) 嵌入回复作为**可直接看到的图片**\n'
    '4. 如果没有找到任何截图 → **跳过该题**（不展示无图题目）\n'
    '5. **每条题目都附带题号和艾宾浩斯阶段值**，方便用户定位和评估难度\n'
    '\n'
    '> ⚠️ **不要**使用 MEDIA: 标记或不明确的路径引用——用户需要直接在回复中看到截图。\n'
    '> **必须** 在回复中用 ![错题-XXX](绝对路径) 嵌入图片，让图片直接显示在对话中。\n'
    '> **review 时不仅输题号列表和路径，也直接将对应图片发送给用户。**'
)

new_image_rules = (
    '**图片发送策略（复习时**必须**遵守）：**\n'
    '\n'
    '1. 从 SQLite mistakes 表读取 image_path 字段（**绝对路径**）\n'
    '2. 如果 image_path 为空 → 降级查找 {题型}/screenshots/{id}.png/.jpg/.webp\n'
    '3. 如果找到 → 用 Markdown 图片语法 ![{id}]({绝对路径}) 嵌入回复作为**可直接看到的图片**\n'
    '4. 如果没有找到任何截图 → **跳过该题**（不展示无图题目）\n'
    '5. **每条题目都附带题号和艾宾浩斯阶段值**，方便用户定位和评估难度\n'
    '\n'
    '> ⚠️ **绝对不要**使用 MEDIA: 标记或不明确的路径引用——用户需要直接在回复中看到截图。\n'
    '> **必须** 在回复中用 ![错题-XXX](绝对路径) 嵌入图片，让图片直接显示在对话中。\n'
    '> review 时不仅输出题号列表和路径，也直接将对应图片发送给用户，这是**硬性要求**。'
)

if old_image_rules in content:
    content = content.replace(old_image_rules, new_image_rules)
    changes.append('Improvement 4: Image sending rules enhanced with stronger emphasis.')
else:
    changes.append('Improvement 4: SKIP - old text not found.')

# === Improvement 5: Enhance knowledge base integration section ===
old_kb_start = '## 知识库集成（参考书籍蒸馏）'
old_kb_end_marker = '## Workflow 0：初始化数据库（含现有错题库导入）'

if old_kb_start in content:
    start_idx = content.find(old_kb_start)
    end_idx = content.find(old_kb_end_marker, start_idx)
    old_kb_section = content[start_idx:end_idx]
    
    new_kb_section = (
        '## 知识库集成（参考书籍蒸馏 + cangjie-skill）\n'
        '\n'
        '### 提取方式\n'
        '\n'
        '使用 cangjie-skill 方法对 `E:\\obsidianNote\\考公\\参考书籍` 下的 8 份核心资料进行蒸馏提取：\n'
        '\n'
        '1. 对每份资料执行 Adler 整书理解 + RIA 框架提取\n'
        '2. 将提取的公式/陷阱/方法论按题型分类整理\n'
        '3. 生成 `knowledge_section.md`（22KB）作为**内联知识库**（已包含在当前 skill 中）\n'
        '4. 后续维护：参考书籍内容更新时，重新运行 cangjie-skill 提取并更新 knowledge_section.md\n'
        '\n'
        '### 参考资料列表\n'
        '\n'
        '| 文件 | 覆盖领域 |\n'
        '|------|---------|\n'
        '| 【判断推理讲义（下册）】.md | 判断推理全套方法论 |\n'
        '| 【判断理论讲义（上册）】.md | 判断推理基础理论 |\n'
        '| 数量关系总结笔记.md | 数量关系公式与技巧 |\n'
        '| 资料分析3页纸.md | 资料分析精华 3 页 |\n'
        '| 资料分析·你的专属易错公式卡.md | 资料分析易错公式卡 |\n'
        '| 资料分析公式与抄错原因速查.md | 公式+抄错原因速查表 |\n'
        '| 资料分析公式汇总.md | 资料分析全公式汇总 |\n'
        '| 资料分析常用公式速查.md | 资料分析常用公式速查表 |\n'
        '\n'
        '### 知识库用途\n'
        '\n'
        '知识库为**只读引用**，不随错题 CRUD 修改，通过 cangjie-skill 方法蒸馏后整合到 skill 的 `knowledge_section.md` 中。AI 在分析错题、出题讲评、考前速查时直接从中引用，无需外部读取。\n'
        '\n'
        '| 场景 | 调用方式 |\n'
        '|------|---------|\n'
        '| **入库时自动匹配陷阱模式** | 从知识库检索同类错题，追加到 references/ |\n'
        '| **复习时推送相关速查** | 判题后从知识库拉取对应考点的速查表/口诀 |\n'
        '| **考前速查** | 知识库索引→薄弱点分析→按题型输出速查指南 |\n'
        '| **新增题考点自动分类** | 基于知识库关键词映射表判定考点 |\n'
        '\n'
        '### 知识库维护\n'
        '\n'
        '当参考书籍内容更新时，重新使用 cangjie-skill 方法蒸馏：\n'
        '\n'
        '1. 读取 `E:\\obsidianNote\\考公\\参考书籍` 下的 .md 文件\n'
        '2. 对每份资料执行 Adler 整书理解 + RIA 框架提取\n'
        '3. 将提取的公式/陷阱/方法论追加到 `knowledge_section.md`\n'
        '4. 验证知识点与错题 references/ 的关联一致性\n'
        '\n'
        '> `knowledge_section.md`（22KB）包含了从 8 份参考资料提取的全部知识体系：\n'
        '> 花生十三 ABRX 体系、资料分析 14 类公式、判断推理完整框架（图形推理五定性/六提示/四类图/定义判断/类比推理/逻辑论证）、\n'
        '> 数量关系（工程/行程/排列组合/概率/经济利润/溶液/几何）、政治理论高频考点、常识判断高频考点。\n'
        '\n'
    )
    
    content = content[:start_idx] + new_kb_section + content[end_idx:]
    changes.append('Improvement 5: Knowledge base section enhanced with cangjie-skill reference and content summary.')
else:
    changes.append('Improvement 5: SKIP - old section header not found.')

with open('D:\\work\\exam-mistake-manager\\SKILL.md', 'w', encoding='utf-8') as f:
    f.write(content)

for c in changes:
    print(f'  {c}')
print(f'\nFinal file size: {len(content)} chars')
print('Done.')

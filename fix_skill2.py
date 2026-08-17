import re

with open('D:\\work\\exam-mistake-manager\\SKILL.md', 'r', encoding='utf-8') as f:
    content = f.read()

# === 1. Fix image finding strategy ===
# Find from marker to the next ### heading
marker = '**图片查找策略**'
if marker in content:
    start = content.find(marker)
    rest = content[start:]
    lines = rest.split('\n')
    end = 0
    for i, line in enumerate(lines):
        if line.strip().startswith('### ') or line.strip().startswith('> **'):
            if i > 0:
                end = i
                break
    if end == 0:
        end = len(lines)
    
    old = '\n'.join(lines[:end])
    new = (
        '**图片查找策略（双路径回退）**：\n'
        '  `\n'
        '  for each item in index file:\n'
        '      提取 id = "错题-XXX", 题型 = qtype\n'
        '      # 优先在用户提供的导入目录中查找\n'
        '      路径1 = {target_root}/{qtype}/screenshots/{id}.png/.jpg/.jpeg/.webp\n'
        '      # 回退到默认 Obsidian 错题库目录查找\n'
        '      路径2 = {config.MISTAKE_ROOT}/{qtype}/screenshots/{id}.png/.jpg/.jpeg/.webp\n'
        '      如果 路径1 存在：image_path = 路径1的**绝对路径**\n'
        '      否则如果 路径2 存在：image_path = 路径2的**绝对路径**\n'
        '      否则：image_path = ""（后续可手动补充）\n'
        '  `\n'
        '  > 双路径回退确保：用户提供的导入目录和默认 Obsidian 错题库目录下的截图都能被自动识别。'
    )
    content = content[:start] + new + content[start + len(old):]
    print('1. Image finding -> dual-path')
else:
    print('1. SKIP')

# === 2. Fix review example ===
marker2 = '**V3 展示方法'
if marker2 in content:
    start = content.find(marker2)
    rest = content[start:]
    lines = rest.split('\n')
    end = 0
    for i, line in enumerate(lines):
        if line.strip().startswith('> **图片发送策略'):
            end = i
            break
    if end == 0:
        for i, line in enumerate(lines):
            if line.strip().startswith('### ') and i > 0:
                end = i
                break
    
    if end > 0:
        old = '\n'.join(lines[:end])
        new = (
            '**V3 展示方法（用户要求：出题时只需要给出题号列表和直接展示对应图片）：**\n'
            '  \n'
            '  **实际输出格式示例**（用户看到的效果）：\n'
            '  \n'
            '  ```\n'
            '  📝 错题复习 · 第 1 组（复习模式）\n'
            '  \n'
            '  【题1】错题-050  |  判断推理  |  加强削弱  |  艾宾浩斯 2/6\n'
            '  ![错题-050](E:\\obsidianNote\\考公\\错题库\\判断推理\\screenshots\\错题-050.png)\n'
            '  \n'
            '  【题2】错题-078  |  资料分析  |  增长率计算  |  艾宾浩斯 1/6\n'
            '  ![错题-078](E:\\obsidianNote\\考公\\错题库\\资料分析\\screenshots\\错题-078.png)\n'
            '  \n'
            '  【题3】错题-112  |  数量关系  |  工程问题  |  艾宾浩斯 3/6\n'
            '  ![错题-112](E:\\obsidianNote\\考公\\错题库\\数量关系\\screenshots\\错题-112.png)\n'
            '  \n'
            '  ...\n'
            '  \n'
            '  请回忆答案并用格式回复：1.B 2.C 3.A ...（或写思路描述，不记得就说「不记得」）\n'
            '  ```\n'
            '  \n'
            '  > ⚠️ 截图通过 Markdown 图片语法 ![错题-{ID}]({绝对路径}) 直接嵌入回复中，用户在对话中**直接看到图片**，无需手动打开文件。'
        )
        content = content[:start] + new + content[start + len(old):]
        print('2. Review example -> concrete')
    else:
        print('2. SKIP - boundary not found')
else:
    print('2. SKIP')

# === 3. Fix image sending rules ===
marker3 = '**图片发送策略（复习时'
if marker3 in content:
    start = content.find(marker3)
    rest = content[start:]
    lines = rest.split('\n')
    end = 0
    for i, line in enumerate(lines):
        if line.strip().startswith('### ') and i > 0:
            end = i
            break
    if end == 0:
        # Go until a blank line followed by ###
        for i in range(1, len(lines)):
            if lines[i].strip() == '' and i+1 < len(lines) and lines[i+1].strip().startswith('### '):
                end = i + 1
                break
    
    if end > 0:
        old = '\n'.join(lines[:end])
        new = (
            '**图片发送策略（复习时**必须**遵守）**：\n'
            '  \n'
            '  1. 从 SQLite mistakes 表读取 image_path 字段（**绝对路径**）\n'
            '  2. 如果 image_path 为空 → 降级查找 {题型}/screenshots/{id}.png/.jpg/.webp\n'
            '  3. 如果找到 → 用 Markdown 图片语法 ![{id}]({绝对路径}) 嵌入回复作为**可直接看到的图片**\n'
            '  4. 如果没有找到任何截图 → **跳过该题**（不展示无图题目）\n'
            '  5. **每条题目都附带题号和艾宾浩斯阶段值**，方便用户定位和评估难度\n'
            '  \n'
            '  > ⚠️ **绝对不要**使用 MEDIA: 标记或不明确的路径引用——用户需要直接在回复中看到截图。\n'
            '  > **必须** 在回复中用 ![错题-XXX](绝对路径) 嵌入图片，让图片直接显示在对话中。\n'
            '  > review 时不仅输出题号列表和路径，也直接将对应图片发送给用户，这是**硬性要求**。'
        )
        content = content[:start] + new + content[start + len(old):]
        print('3. Image rules -> strengthened')
    else:
        print('3. SKIP - boundary not found')
else:
    print('3. SKIP')

# === 4. Fix review_engine reference ===
content = content.replace(
    '由 \neview_engine._parse_answers() 处理',
    '由 review_engine._parse_answers() 处理'
)
print('4. Fixed review_engine line break')

# === 5. Remove duplicate import report ===
count = content.count('导入报告示例')
print(f'5. Import report examples found: {count}')
if count > 1:
    # Find all occurrences and remove the first one (it's the old plain-text version)
    first = content.find('导入报告示例')
    # Find the section start (### Step 3)
    sec_start = content.rfind('### Step 3', 0, first)
    # Find the section end (next ### or end)
    sec_end = content.find('\n###', sec_start + 1)
    if sec_end < 0:
        sec_end = len(content)
    # The duplicate is from sec_start to sec_end
    # Remove the old section that doesn't have the example
    # Check which one has the concrete example
    first_section = content[sec_start:sec_end]
    rest_after_first = content[sec_end:]
    second_example_pos = rest_after_first.find('导入报告示例')
    if second_example_pos >= 0:
        # Keep the second (which has the full example with 图示)
        # Remove the first section entirely
        content = content[:sec_start] + rest_after_first
        print('   Removed first duplicate section')

with open('D:\\work\\exam-mistake-manager\\SKILL.md', 'w', encoding='utf-8') as f:
    f.write(content)

print(f'\nFinal size: {len(content)} chars')
print('Done')

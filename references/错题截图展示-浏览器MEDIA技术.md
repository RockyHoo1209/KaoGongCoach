# 错题截图展示 · 浏览器 MEDIA 技术

> 用于在聊天中展示本地 vault 截图的技术方案。当用户要求看原图而非文字描述时使用。

## 问题背景

错题库截图是手机长截图（1080×7457），无法直接在聊天中展示。vision_analyze 只返回文字描述，不能展示原图。browser_vision 提供的 screenshot_path 可以通过 MEDIA: 语法渲染。

## 展示流程

```python
from PIL import Image

# 1. 裁剪顶部 35%（只保留题目区，不保留长尾解析区）
img = Image.open(screenshot_path)
w, h = img.size
crop = img.crop((0, 0, w, int(h * 0.35)))

# 2. PNG → RGB + 白色背景（否则浏览器截图全白）
if crop.mode in ('RGBA', 'P'):
    bg = Image.new('RGB', crop.size, (255, 255, 255))
    bg.paste(crop, mask=crop.split()[-1] if crop.mode == 'RGBA' else None)
    crop = bg

# 3. Resize 宽度到 540px（浏览器友好）
crop = crop.resize((540, int(crop.size[1] * 540 / crop.size[0])), Image.LANCZOS)

# 4. 保存到 /tmp
crop.save(f'/tmp/view_{id}.jpg', 'JPEG', quality=92)

# 5. 浏览器加载 + 截图 + MEDIA:
#    browser_navigate(url=f"file:///tmp/view_{id}.jpg")
#    browser_vision(question="显示这道题的截图")
#    回复中用 MEDIA:{screenshot_path}
```

## 常见失败原因

| 症状 | 原因 | 修复 |
|------|------|------|
| 浏览器截图全白 | PNG 带透明背景 | 裁剪后转 RGB + 白色背景 |
| 浏览器截图全白 | 图片格式不为浏览器支持 | 统一保存为 JPEG，quality ≥ 85 |
| browser_vision 识别不出文字 | 深色模式图片过暗 | 不影响用户看原图，只影响 vision 描述（不需要） |
| 一次多张时部分截图空白 | browser_navigate 覆盖了上一张 | 每张独立加载+截图，不要并发 |

## 原则

- **vision_analyze 只用来看内容做分析，不能替代原图展示**
- **用户说"图呢"/"截图呢"时，必须展示原图，不用文字重建**
- **没有截图的题才走文字重建**（从 index 条目的考点+错因重建）
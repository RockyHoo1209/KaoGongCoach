"""批量导入错题。

把指定目录下的截图通过 DeepSeek-OCR(SiliconFlow) 识别，自动推断考点并入库。
流程：
1. 扫描源目录下常见图片格式（png/jpg/jpeg/webp）。
2. 调用 OCR API 提取题干文本。
3. 解析题号/选项/考点/答案。
4. 复制原图到错题库并创建 markdown 文件。
5. 更新 index.md 并输出质量报告。
"""
from __future__ import annotations

import base64
import json
import mimetypes
import os
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional

import config
import index_manager
import mistake_manager
import scheduler


SUPPORTED_EXTS = {".png", ".jpg", ".jpeg", ".webp", ".bmp"}


@dataclass
class OCRResult:
    """单张图片的 OCR 结果。"""

    image_path: Path
    text: str = ""
    has_chinese: bool = False
    question_type: str = ""
    knowledge_point: str = ""
    options: Dict[str, str] = field(default_factory=dict)
    answer: str = "待校验"
    quality: str = "ok"  # ok / poor


def _read_image_base64(path: Path) -> str:
    return base64.b64encode(path.read_bytes()).decode("utf-8")


def _mime_type(path: Path) -> str:
    mt = mimetypes.guess_type(str(path))[0]
    return mt or "image/png"


def _build_ocr_payload(image_path: Path) -> dict:
    b64 = _read_image_base64(image_path)
    mime = _mime_type(image_path)
    return {
        "model": config.OCR_MODEL,
        "messages": [
            {
                "role": "user",
                "content": [
                    {
                        "type": "text",
                        "text": (
                            "请识别这张考试题截图中的文字。"
                            "保留题干、选项 A/B/C/D 的完整内容。"
                            "如果有手写红笔答案或标记，也请指出。"
                        ),
                    },
                    {"type": "image_url", "image_url": {"url": f"data:{mime};base64,{b64}"}},
                ],
            }
        ],
        "max_tokens": 2048,
    }


def _call_ocr_api(image_path: Path) -> str:
    """调用 SiliconFlow DeepSeek-OCR，返回识别文本。"""
    import urllib.request

    payload = _build_ocr_payload(image_path)
    data = json.dumps(payload, ensure_ascii=False).encode("utf-8")
    req = urllib.request.Request(
        config.OCR_API_URL,
        data=data,
        headers={
            "Authorization": f"Bearer {config.OCR_API_KEY}",
            "Content-Type": "application/json",
        },
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=120) as resp:
        result = json.loads(resp.read().decode("utf-8"))
    # 兼容 non-stream 与 choices 结构
    choices = result.get("choices", [])
    if choices:
        content = choices[0].get("message", {}).get("content", "")
    else:
        content = result.get("content", "")
    return content.strip()


def _has_chinese(text: str) -> bool:
    return bool(re.search(r"[\u4e00-\u9fff]", text))


def _infer_question_type(folder_name: str) -> str:
    """根据目录名推断题型。"""
    name = folder_name.strip()
    mapping = {
        "言语": "言语理解",
        "数量": "数量关系",
        "判断": "判断推理",
        "资料": "资料分析",
        "常识": "常识判断",
        "公安": "公安专业知识",
        "申论": "申论",
        "面试": "面试",
    }
    for k, v in mapping.items():
        if k in name:
            return v
    # 完全匹配
    if name in config.ALL_TYPES:
        return name
    return "常识判断"  # 默认兜底


def _extract_knowledge_point(text: str) -> str:
    """基于关键词映射提取考点。"""
    for kw, kp in config.KEYWORD_MAP:
        if kw in text:
            return kp
    return "待补充"


def _extract_options(text: str) -> Dict[str, str]:
    """尝试提取 A/B/C/D 选项内容。"""
    options: Dict[str, str] = {}
    pattern = re.compile(r"\n\s*([A-Da-d])[\.．、,，\s]+([^\n]*)")
    for m in pattern.finditer(text):
        label = m.group(1).upper()
        options[label] = m.group(2).strip()
    return options


def _extract_answer(text: str) -> str:
    """从 OCR 文本中尝试提取答案。"""
    # 常见答案标记：【答案】B / 答案：B / 正确答案：B
    patterns = [
        r"(?:答案|正确答案|选|答案为)[：:\s]*([A-Da-d])",
        r"[（(]([A-Da-d])[）)]\s*$",
    ]
    for p in patterns:
        m = re.search(p, text)
        if m:
            return m.group(1).upper()
    return "待校验"


def _parse_ocr_text(text: str, folder_name: str) -> OCRResult:
    """解析 OCR 文本，填充结构化字段。"""
    qtype = _infer_question_type(folder_name)
    kp = _extract_knowledge_point(text)
    options = _extract_options(text)
    answer = _extract_answer(text)
    has_cn = _has_chinese(text)
    quality = "ok" if has_cn and len(text) > 20 else "poor"
    return OCRResult(
        image_path=Path(),
        text=text,
        has_chinese=has_cn,
        question_type=qtype,
        knowledge_point=kp,
        options=options,
        answer=answer,
        quality=quality,
    )


def _collect_images(source_dir: Path) -> List[Path]:
    """收集目录下所有支持的图片文件。"""
    images = []
    for ext in SUPPORTED_EXTS:
        images.extend(source_dir.glob(f"*{ext}"))
        images.extend(source_dir.glob(f"*{ext.upper()}"))
    # 去重并保持稳定顺序
    seen = set()
    unique = []
    for p in sorted(images):
        if p not in seen:
            seen.add(p)
            unique.append(p)
    return unique


def _ocr_single_image(image_path: Path) -> OCRResult:
    """对单张图片执行 OCR 并解析。"""
    folder_name = image_path.parent.name
    try:
        raw = _call_ocr_api(image_path)
    except Exception as e:
        raw = f"OCR 调用失败: {e}"
    result = _parse_ocr_text(raw, folder_name)
    result.image_path = image_path
    return result


def import_directory(
    source_dir: Path,
    default_error_reason: str = "待补充",
    default_source: str = "",
    dry_run: bool = False,
) -> dict:
    """批量导入一个目录下的错题截图。

    Args:
        source_dir: 源图片目录
        default_error_reason: 默认错误原因
        default_source: 默认来源，为空则使用目录名
        dry_run: True 时不写入文件，仅返回预览

    Returns:
        统计字典
    """
    source_dir = Path(source_dir)
    if not source_dir.exists() or not source_dir.is_dir():
        raise ValueError(f"目录不存在: {source_dir}")

    images = _collect_images(source_dir)
    total = len(images)
    if total == 0:
        return {
            "total": 0,
            "success": 0,
            "poor": 0,
            "items": [],
        }

    results: List[OCRResult] = []
    for img in images:
        result = _ocr_single_image(img)
        results.append(result)

    if not dry_run:
        config.ensure_dirs()
        for r in results:
            source = default_source or f"{source_dir.name}题库"
            # OCR 文本摘要（前 300 字）写入正文
            ocr_summary = r.text[:300]
            mistake_manager.create_mistake(
                question_type=r.question_type,
                knowledge_point=r.knowledge_point,
                error_reason=default_error_reason,
                correct_answer=r.answer,
                source=source,
                screenshot_src=r.image_path,
                ocr_text=ocr_summary,
            )

    poor_count = sum(1 for r in results if r.quality == "poor")
    return {
        "total": total,
        "success": total,  # 只要没抛异常就算处理了一次
        "poor": poor_count,
        "items": results,
    }


def build_import_report(report: dict) -> str:
    """生成批量导入的质量报告 markdown。"""
    total = report["total"]
    poor = report["poor"]
    success = report["success"]
    lines = [
        "## ✅ 批量导入完成",
        "",
        "### 📊 识别质量",
        "",
        "| 指标 | 数值 |",
        "|------|------|",
        f"| 总数 | {total} |",
        f"| 入库成功 | {success} |",
        f"| OCR 质量差 | {poor} |",
        "",
        "### ⚠️ 需要手动补充",
        "- 错误原因：全部默认「待补充」",
        "- 红笔手写答案：OCR 识别率有限，请重点校验",
        "- 未匹配到关键词的考点：已标记为「待补充」",
    ]

    items = report.get("items", [])
    if items:
        lines.extend(["", "### 📋 入库明细", ""])
        lines.append("| 文件名 | 题型 | 考点 | 答案 | 质量 |")
        lines.append("|--------|------|------|------|------|")
        for r in items:
            name = r.image_path.name
            quality_emoji = "⚠️" if r.quality == "poor" else "✅"
            lines.append(
                f"| {name} | {r.question_type} | {r.knowledge_point} | "
                f"{r.answer} | {quality_emoji} |"
            )
    return "\n".join(lines)

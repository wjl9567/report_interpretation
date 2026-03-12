"""
轻量知识增强：从本地目录按报告类型、科室加载规范/指南片段，注入 system prompt。
目录约定：knowledge/report_type/{report_type}/*.md、knowledge/department/{department_code}/*.md
"""

import logging
from pathlib import Path

from app.core.config import settings

logger = logging.getLogger(__name__)


def get_knowledge_snippets(
    department_code: str = "general",
    report_type: str = "lab",
) -> str:
    """
    根据科室与报告类型加载知识片段，拼接为一段文本（不超过 KNOWLEDGE_MAX_CHARS）。
    未启用或目录不存在时返回空字符串。
    """
    if not getattr(settings, "KNOWLEDGE_ENABLED", False):
        return ""
    base = Path(settings.KNOWLEDGE_DIR)
    if not base.is_absolute():
        base = Path(__file__).resolve().parent.parent.parent / base
    if not base.exists():
        return ""

    max_chars = getattr(settings, "KNOWLEDGE_MAX_CHARS", 4000)
    parts: list[str] = []

    # 报告类型：knowledge/report_type/lab/*.md
    rt_dir = base / "report_type" / report_type
    if rt_dir.exists():
        for f in sorted(rt_dir.glob("*.md")):
            try:
                text = f.read_text(encoding="utf-8").strip()
                if text:
                    parts.append(f"### [{f.stem}]\n{text}")
            except Exception as e:
                logger.warning(f"读取知识文件失败 {f}: {e}")

    # 科室：knowledge/department/hematology/*.md（general 不加载科室专属）
    if department_code and department_code != "general":
        dept_dir = base / "department" / department_code
        if dept_dir.exists():
            for f in sorted(dept_dir.glob("*.md")):
                try:
                    text = f.read_text(encoding="utf-8").strip()
                    if text:
                        parts.append(f"### [{f.stem}]\n{text}")
                except Exception as e:
                    logger.warning(f"读取知识文件失败 {f}: {e}")

    if not parts:
        return ""

    combined = "\n\n".join(parts)
    if len(combined) > max_chars:
        combined = combined[: max_chars - 20] + "\n\n...(内容已截断)"
    return "\n\n## 参考规范与指南\n解读时请优先依据以下规范，并可在结论中简要引用。\n\n" + combined

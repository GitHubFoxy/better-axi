"""Markdown pruning and fit-markdown generator for LLM token efficiency."""
from __future__ import annotations

import re
from typing import Optional


def generate_fit_markdown(html_or_text: str, title: Optional[str] = None) -> str:
    """
    Generate pruned, token-efficient fit-markdown from page content.
    Strips noise, boilerplate headers/footers, ads, and cookies warnings,
    preserving technical requirements, conditions, and core text.
    """
    if not html_or_text:
        return ""

    # If HTML tags present, strip unwanted tags first
    cleaned = re.sub(r"<(script|style|svg|noscript|iframe|nav|footer)[^>]*>.*?</\1>", "", html_or_text, flags=re.DOTALL | re.IGNORECASE)
    
    # Replace headings with markdown headings
    cleaned = re.sub(r"<h1[^>]*>(.*?)</h1>", r"\n# \1\n", cleaned, flags=re.IGNORECASE)
    cleaned = re.sub(r"<h2[^>]*>(.*?)</h2>", r"\n## \1\n", cleaned, flags=re.IGNORECASE)
    cleaned = re.sub(r"<h3[^>]*>(.*?)</h3>", r"\n### \1\n", cleaned, flags=re.IGNORECASE)
    cleaned = re.sub(r"<li[^>]*>(.*?)</li>", r"\n- \1", cleaned, flags=re.IGNORECASE)
    cleaned = re.sub(r"<p[^>]*>(.*?)</p>", r"\n\1\n", cleaned, flags=re.IGNORECASE)
    cleaned = re.sub(r"<br\s*/?>", "\n", cleaned, flags=re.IGNORECASE)
    
    # Strip remaining HTML tags
    cleaned = re.sub(r"<[^>]+>", " ", cleaned)

    # Unescape common entities
    cleaned = cleaned.replace("&nbsp;", " ").replace("&quot;", '"').replace("&amp;", "&").replace("&lt;", "<").replace("&gt;", ">")

    lines = [line.strip() for line in cleaned.split("\n")]
    filtered_lines = []

    # Noise patterns to prune
    noise_patterns = [
        r"^©\s*\d+",
        r"все права защищены",
        r"cookie|куки",
        r"политика конфиденциальности",
        r"поделиться вакансией",
        r"пожаловаться на вакансию",
        r"вход\s*\|\s*регистрация",
        r"скачать приложение",
        r"подписаться на обновления",
    ]
    noise_re = re.compile("|".join(noise_patterns), re.IGNORECASE)

    for line in lines:
        if not line:
            if filtered_lines and filtered_lines[-1] != "":
                filtered_lines.append("")
            continue
        if noise_re.search(line):
            continue
        filtered_lines.append(line)

    result = "\n".join(filtered_lines).strip()
    if title and not result.startswith("#"):
        result = f"# {title}\n\n{result}"

    return result

"""Текст звіту з файлу: .md і .txt як є, .docx — абзаци з заголовками й списками.

PDF не розбираємо: текст із PDF без окремої бібліотеки виходить кашею,
а звіт має читатися на сторінці. PDF додається вкладенням і відкривається
поруч у переглядачі.
"""
from __future__ import annotations

import zipfile
from pathlib import Path
from xml.etree import ElementTree as ET

from fastapi import HTTPException

W = "{http://schemas.openxmlformats.org/wordprocessingml/2006/main}"
MAX_XML_BYTES = 20 * 1024 * 1024        # захист від zip-бомби
MAX_TEXT_CHARS = 500_000


def docx_to_markdown(path: Path) -> str:
    try:
        with zipfile.ZipFile(path) as zf:
            info = zf.getinfo("word/document.xml")
            if info.file_size > MAX_XML_BYTES:
                raise HTTPException(status_code=413, detail="Документ завеликий для перетворення в текст")
            xml = zf.read(info)
    except (KeyError, zipfile.BadZipFile):
        raise HTTPException(status_code=415, detail="Не вдалося прочитати .docx")

    root = ET.fromstring(xml)
    lines: list[str] = []
    for p in root.iter(f"{W}p"):
        text = "".join(t.text or "" for t in p.iter(f"{W}t")).strip()
        if not text:
            continue
        style = p.find(f"{W}pPr/{W}pStyle")
        name = (style.get(f"{W}val") if style is not None else "") or ""
        if name.lower().startswith("heading") and name[-1:].isdigit():
            lines.append("#" * min(int(name[-1]), 6) + " " + text)
        elif p.find(f"{W}pPr/{W}numPr") is not None or name.lower().startswith("list"):
            lines.append("- " + text)
        else:
            lines.append(text)
    return "\n\n".join(lines).strip()


def text_from_file(path: Path, ext: str) -> str:
    if ext in ("md", "txt"):
        text = path.read_text(encoding="utf-8-sig")
    elif ext == "docx":
        text = docx_to_markdown(path)
    else:
        raise HTTPException(status_code=415, detail=(
            "Текст можна взяти лише з .md, .txt або .docx. PDF додайте до звіту вкладенням."))
    return text[:MAX_TEXT_CHARS]

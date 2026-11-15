"""Звіти: створення, читання, статуси, оцінки з середнім, текст із файлу, завдання зі звіту."""
import io
import zipfile

import pytest


async def new_report(c, **kw):
    r = await c.post("/api/admin/reports", json={"title": "Аналіз конкурентів", "kind": "marketing",
                                                 "agent": "Claude маркетолог", "body": "## Висновки\n- раз", **kw})
    assert r.status_code == 201, r.text
    return r.json()


async def test_create_read_and_labels(admin_client):
    rep = await new_report(admin_client, tags=["конкуренти"])
    assert rep["status"] == "new" and rep["status_label"] == "Новий" and rep["kind_label"] == "Маркетинг"
    assert rep["source"] == "manual" and rep["author"] == "Іван" and rep["body"].startswith("## Висновки")
    full = (await admin_client.get(f"/api/admin/reports/{rep['id']}")).json()
    assert full["body"] == rep["body"]
    listed = (await admin_client.get("/api/admin/reports")).json()
    assert "body" not in listed[0] and listed[0]["excerpt"].startswith("## Висновки")


@pytest.mark.parametrize("payload", [{"kind": "spam"}, {"title": ""}, {"source": "api"}])
async def test_create_validation(admin_client, payload):
    body = {"title": "x", **payload}
    assert (await admin_client.post("/api/admin/reports", json=body)).status_code == 422


async def test_status_flow_and_filters(admin_client, session):
    a = await new_report(admin_client)
    await new_report(admin_client, title="Продажі жовтня", kind="sales", tags=["Q4"])
    url = f"/api/admin/reports/{a['id']}"
    r = await admin_client.patch(url, json={"status": "rework", "title": " Новий заголовок ", "tags": ["x"],
                                            "agent": None})
    assert r.json()["status_label"] == "На допрацювання" and r.json()["title"] == "Новий заголовок"
    assert (await admin_client.patch(url, json={"status": "lost"})).status_code == 422
    get = lambda **p: admin_client.get("/api/admin/reports", params=p)
    assert [x["title"] for x in (await get(kind="sales")).json()] == ["Продажі жовтня"]
    assert [x["title"] for x in (await get(status="rework")).json()] == ["Новий заголовок"]
    assert [x["title"] for x in (await get(tag="q4")).json()] == ["Продажі жовтня"]
    assert sorted(x["title"] for x in (await get(q="Claude")).json()) == ["Новий заголовок", "Продажі жовтня"]


async def test_each_admin_has_one_review_and_average_is_shown(admin_client, client_for, make_admin):
    rep = await new_report(admin_client)
    key = {"entity_type": "report", "entity_id": rep["id"]}
    dan, dima = await make_admin(), await make_admin()
    await admin_client.put("/api/admin/reviews", json={**key, "score": 9, "body": "сильно"})
    async with client_for(dan) as d, client_for(dima) as m:
        await d.put("/api/admin/reviews", json={**key, "score": 6})
        await d.put("/api/admin/reviews", json={**key, "score": 7})          # перезапис своєї
        s = (await m.put("/api/admin/reviews", json={**key, "body": "без балу"})).json()
        assert s["average"] == 8.0 and s["count"] == 2 and len(s["items"]) == 3
        assert (await m.put("/api/admin/reviews", json={**key})).status_code == 400
        assert (await m.put("/api/admin/reviews", json={**key, "score": 11})).status_code == 422
        after = (await m.request("DELETE", "/api/admin/reviews", params=key)).json()
        assert len(after["items"]) == 2 and not any(i["mine"] for i in after["items"])
        assert (await m.request("DELETE", "/api/admin/reviews", params=key)).status_code == 200
    listed = (await admin_client.get("/api/admin/reports")).json()[0]
    assert listed["average_score"] == 8.0 and listed["reviews_count"] == 2
    got = (await admin_client.get("/api/admin/reviews", params=key)).json()
    assert got["average"] == 8.0


async def test_create_task_from_report(admin_client, make_admin):
    rep = await new_report(admin_client)
    dan = await make_admin()
    r = await admin_client.post("/api/admin/tasks", json={
        "title": f"За звітом: {rep['title']}", "assignee_id": dan.id,
        "related_type": "report", "related_id": rep["id"]})
    assert r.status_code == 201 and r.json()["related_type"] == "report"


async def test_delete_rights(admin_client, client_for, make_admin):
    dan = await make_admin()
    async with client_for(dan) as d:
        own = await new_report(d)
        rep = await new_report(admin_client)
        assert (await d.delete(f"/api/admin/reports/{rep['id']}")).status_code == 403
        assert (await d.delete(f"/api/admin/reports/{own['id']}")).status_code == 200
    assert (await admin_client.delete(f"/api/admin/reports/{rep['id']}")).status_code == 200
    assert (await admin_client.get(f"/api/admin/reports/{rep['id']}")).status_code == 404


async def test_unread_counter_for_reports(admin_client, client_for, make_admin):
    dan = await make_admin()
    rep = await new_report(admin_client)
    async with client_for(dan) as d:
        assert (await d.get("/api/admin/counters")).json()["reports"] == 1
        assert (await d.get("/api/admin/reports")).json()[0]["unread"] is True
        await d.get(f"/api/admin/reports/{rep['id']}")
        assert (await d.get("/api/admin/counters")).json()["reports"] == 0


def docx_bytes(paragraphs):
    W = 'xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main"'
    body = ""
    for style, text in paragraphs:
        ppr = ""
        if style == "list":
            ppr = "<w:pPr><w:numPr><w:numId w:val='1'/></w:numPr></w:pPr>"
        elif style:
            ppr = f"<w:pPr><w:pStyle w:val='{style}'/></w:pPr>"
        body += f"<w:p>{ppr}<w:r><w:t>{text}</w:t></w:r></w:p>"
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as z:
        z.writestr("[Content_Types].xml", "<Types/>")
        z.writestr("word/document.xml", f"<w:document {W}><w:body>{body}</w:body></w:document>")
    return buf.getvalue()


async def test_extract_text_from_docx_md_txt(admin_client):
    doc = docx_bytes([("Heading1", "Звіт"), ("", "Вступ"), ("", ""), ("list", "пункт"), ("ListParagraph", "ще")])
    r = await admin_client.post("/api/admin/reports/extract", files={"file": ("Звіт за жовтень.docx", doc)})
    assert r.status_code == 200
    assert r.json() == {"text": "# Звіт\n\nВступ\n\n- пункт\n\n- ще", "title": "Звіт за жовтень"}
    r = await admin_client.post("/api/admin/reports/extract", files={"file": ("a.md", "﻿# Привіт".encode())})
    assert r.json()["text"] == "# Привіт"
    r = await admin_client.post("/api/admin/reports/extract", files={"file": ("a.txt", b"plain")})
    assert r.json()["text"] == "plain"


@pytest.mark.parametrize("name,content,code", [
    ("r.pdf", b"%PDF-1.4", 415),                     # PDF — лише вкладенням
    ("r.exe", b"MZ", 415),
    ("r.docx", b"PK\x03\x04garbage", 415),
    ("r.txt", b"\x00\x01binary", 415),
])
async def test_extract_rejects(admin_client, name, content, code):
    r = await admin_client.post("/api/admin/reports/extract", files={"file": (name, content)})
    assert r.status_code == code


async def test_extract_size_limit(admin_client, monkeypatch):
    from app.core.config import settings
    monkeypatch.setattr(settings, "upload_max_mb", 1)
    r = await admin_client.post("/api/admin/reports/extract", files={"file": ("a.txt", b"a" * (1024 * 1024 + 1))})
    assert r.status_code == 413


def test_docx_without_document_or_too_big(tmp_path, monkeypatch):
    from fastapi import HTTPException
    from app.core import doctext
    p = tmp_path / "x.docx"
    with zipfile.ZipFile(p, "w") as z:
        z.writestr("[Content_Types].xml", "<Types/>")
    with pytest.raises(HTTPException):
        doctext.docx_to_markdown(p)
    p.write_bytes(docx_bytes([("", "текст")]))
    monkeypatch.setattr(doctext, "MAX_XML_BYTES", 10)
    with pytest.raises(HTTPException) as e:
        doctext.docx_to_markdown(p)
    assert e.value.status_code == 413
    with pytest.raises(HTTPException):
        doctext.text_from_file(p, "pdf")

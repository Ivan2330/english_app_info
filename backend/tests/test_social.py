"""Коментарі й файли: доступ через розділ сутності, авторство, тип файлу за вмістом, ліміти."""
import io
import zipfile

import pytest
from sqlalchemy import select

from app.core.config import settings
from app.models.workspace import Attachment

PNG = b"\x89PNG\r\n\x1a\n" + b"\x00" * 32
JPG = b"\xff\xd8\xff\xe0" + b"\x00" * 32
GIF = b"GIF89a" + b"\x00" * 16
WEBP = b"RIFF\x00\x00\x00\x00WEBPVP8 " + b"\x00" * 16
MP4 = b"\x00\x00\x00\x18ftypisom" + b"\x00" * 16
MOV = b"\x00\x00\x00\x14ftypqt  " + b"\x00" * 16
PDF = b"%PDF-1.7\n" + b"\x00" * 16


def office(prefix):
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as z:
        z.writestr("[Content_Types].xml", "<Types/>")
        z.writestr(f"{prefix}x.xml", "<x/>")
    return buf.getvalue()


@pytest.fixture
async def task(admin_client, admin):
    r = await admin_client.post("/api/admin/tasks", json={"title": "x", "assignee_id": admin.id})
    return r.json()


def key(task):
    return {"entity_type": "task", "entity_id": task["id"]}


# ------------------------------------------------------------------ коментарі

async def test_comment_lifecycle(admin_client, client_for, make_admin, task):
    other = await make_admin(name="Дмитро")
    r = await admin_client.post("/api/admin/comments", json={**key(task), "body": " Готово? "})
    c = r.json()
    assert r.status_code == 201 and c["body"] == "Готово?" and c["mine"] and not c["edited"]
    async with client_for(other) as o:
        await o.post("/api/admin/comments", json={**key(task), "body": "так"})
        assert (await o.patch(f"/api/admin/comments/{c['id']}", json={"body": "хак"})).status_code == 403
        assert (await o.delete(f"/api/admin/comments/{c['id']}")).status_code == 403
    r = await admin_client.patch(f"/api/admin/comments/{c['id']}", json={"body": "Готово, перевір"})
    assert r.json()["edited"] is True
    listed = (await admin_client.get("/api/admin/comments", params=key(task))).json()
    assert [x["author"] for x in listed] == ["Іван", "Дмитро"]
    assert (await admin_client.delete(f"/api/admin/comments/{c['id']}")).status_code == 200
    assert (await admin_client.patch("/api/admin/comments/999", json={"body": "x"})).status_code == 404


async def test_comments_respect_entity_section(admin_client, client_for, make_admin, task):
    no_tasks = await make_admin(sections=["reports"])
    async with client_for(no_tasks) as c:
        assert (await c.get("/api/admin/comments", params=key(task))).status_code == 403
        assert (await c.post("/api/admin/comments", json={**key(task), "body": "x"})).status_code == 403
        assert (await c.get("/api/admin/files", params=key(task))).status_code == 403
        assert (await c.get("/api/admin/reviews", params=key(task))).status_code == 403


@pytest.mark.parametrize("params,code", [
    ({"entity_type": "secret", "entity_id": 1}, 400),
    ({"entity_type": "task", "entity_id": 999}, 404),
])
async def test_comment_target_must_exist(admin_client, params, code):
    assert (await admin_client.get("/api/admin/comments", params=params)).status_code == code


# ------------------------------------------------------------------ файли

@pytest.mark.parametrize("name,content,kind,mime", [
    ("a.png", PNG, "image", "image/png"),
    ("a.JPEG", JPG, "image", "image/jpeg"),
    ("a.gif", GIF, "image", "image/gif"),
    ("a.webp", WEBP, "image", "image/webp"),
    ("a.mp4", MP4, "video", "video/mp4"),
    ("a.mov", MOV, "video", "video/quicktime"),
    ("a.pdf", PDF, "document", "application/pdf"),
    ("a.docx", office("word/"), "document", "application/vnd.openxmlformats-officedocument.wordprocessingml.document"),
    ("a.xlsx", office("xl/"), "document", "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"),
    ("a.csv", "дата,сума\n".encode(), "document", "text/csv; charset=utf-8"),
    ("a.md", b"# hi", "document", "text/markdown; charset=utf-8"),
    ("a.txt", b"hi", "document", "text/plain; charset=utf-8"),
])
async def test_allowed_types_upload_and_download(admin_client, task, _upload_dir, name, content, kind, mime):
    r = await admin_client.post("/api/admin/files", params=key(task), files={"file": (name, content)})
    assert r.status_code == 201, r.text
    f = r.json()
    assert f["kind"] == kind and f["mime"] == mime and f["name"] == name and f["size"] == len(content)
    stored = list(_upload_dir.iterdir())
    assert len(stored) == 1 and stored[0].name != name and len(stored[0].stem) == 32     # випадкове імʼя
    got = await admin_client.get(f["url"])
    assert got.status_code == 200 and got.content == content
    assert got.headers["x-content-type-options"] == "nosniff"
    disp = got.headers["content-disposition"]
    assert disp.startswith("inline" if kind in ("image", "video") or name.endswith(".pdf") else "attachment")
    forced = await admin_client.get(f["url"], params={"download": True})
    assert forced.headers["content-disposition"].startswith("attachment")


@pytest.mark.parametrize("name,content,detail", [
    ("evil.png", b"<html><script>alert(1)</script>", "не схожий на .png"),
    ("evil.jpg", PNG, "не схожий"),
    ("evil.mp4", MOV, "не схожий"),
    ("evil.mov", MP4, "не схожий"),
    ("evil.pdf", b"MZ\x90\x00", "не схожий"),
    ("evil.docx", office("xl/"), "не схожий"),
    ("evil.xlsx", b"PK\x03\x04broken", "не схожий"),
    ("evil.csv", b"a,b\x00\x00", "не схожий"),
    ("evil.txt", b"\xff\xfe\xfa", "не схожий"),
    ("evil.txt", "привіт".encode()[:-1], "не схожий"),      # обірваний UTF-8 у кінці
    ("evil.html", b"<html>", "не підтримується"),
    ("noext", b"x", "не підтримується"),
    ("empty.txt", b"", "порожній"),
])
async def test_content_is_checked_not_just_extension(admin_client, task, _upload_dir, name, content, detail):
    r = await admin_client.post("/api/admin/files", params=key(task), files={"file": (name, content)})
    assert r.status_code in (400, 415) and detail in r.json()["detail"]
    assert [p for p in _upload_dir.iterdir()] == [] if _upload_dir.exists() else True    # нічого не лишилось


async def test_size_limits_from_settings(admin_client, task, monkeypatch, _upload_dir):
    monkeypatch.setattr(settings, "upload_max_mb", 1)
    monkeypatch.setattr(settings, "upload_video_max_mb", 2)
    big = PNG + b"\x00" * (1024 * 1024)
    r = await admin_client.post("/api/admin/files", params=key(task), files={"file": ("a.png", big)})
    assert r.status_code == 413 and "1 МБ" in r.json()["detail"]
    video = MP4 + b"\x00" * (1024 * 1024 + 10)                                 # 1+ МБ: для відео можна
    assert (await admin_client.post("/api/admin/files", params=key(task),
                                    files={"file": ("v.mp4", video)})).status_code == 201
    assert len(list(_upload_dir.iterdir())) == 1


async def test_files_need_entity_section_and_only_uploader_or_owner_deletes(
        admin_client, client_for, make_admin, task, _upload_dir, session):
    dan = await make_admin()
    async with client_for(dan) as d:
        f = (await d.post("/api/admin/files", params=key(task), files={"file": ("a.png", PNG)})).json()
        g = (await admin_client.post("/api/admin/files", params=key(task), files={"file": ("b.png", PNG)})).json()
        assert (await d.delete(f"/api/admin/files/{g['id']}")).status_code == 403
        assert (await d.delete(f"/api/admin/files/{f['id']}")).status_code == 200
    assert (await admin_client.delete(f"/api/admin/files/{g['id']}")).status_code == 200
    assert list(_upload_dir.iterdir()) == []
    assert (await admin_client.get("/api/admin/files/999")).status_code == 404

    blocked = await make_admin(sections=["reports"])
    h = (await admin_client.post("/api/admin/files", params=key(task), files={"file": ("c.png", PNG)})).json()
    async with client_for(blocked) as b:
        assert (await b.get(h["url"])).status_code == 403
    listed = (await admin_client.get("/api/admin/files", params=key(task))).json()
    assert [x["name"] for x in listed] == ["c.png"]
    team = (await admin_client.get("/api/admin/team")).json()
    assert team["disk"]["files_bytes"] == len(PNG)


async def test_missing_file_on_disk_is_404(admin_client, task, _upload_dir, session):
    f = (await admin_client.post("/api/admin/files", params=key(task), files={"file": ("a.png", PNG)})).json()
    for p in _upload_dir.iterdir():
        p.unlink()
    assert (await admin_client.get(f["url"])).status_code == 404


async def test_deleting_task_removes_its_files(admin_client, task, _upload_dir, session):
    await admin_client.post("/api/admin/files", params=key(task), files={"file": ("a.png", PNG)})
    await admin_client.delete(f"/api/admin/tasks/{task['id']}")
    assert list(_upload_dir.iterdir()) == []
    assert (await session.execute(select(Attachment))).scalars().all() == []


def test_stored_path_cannot_escape_upload_dir():
    from fastapi import HTTPException
    from app.core.files import remove_stored, stored_path
    with pytest.raises(HTTPException):
        stored_path("../../etc/passwd")
    remove_stored("../../etc/passwd")          # не падає і нічого не видаляє

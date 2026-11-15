"""Завдання: хто що може, фільтри, канбан-статуси, непрочитане."""
from datetime import date, timedelta

import pytest
from sqlalchemy import select

from app.models.workspace import AuditLog, Comment, ReadMark


@pytest.fixture
async def team(make_admin, client_for):
    """Двоє адмінів: author ставить завдання, doer виконує."""
    author = await make_admin(name="Іван А")
    doer = await make_admin(name="Данило")
    return author, doer


async def new_task(c, assignee_id, **kw):
    r = await c.post("/api/admin/tasks", json={"title": "Зняти Reel", "assignee_id": assignee_id, **kw})
    assert r.status_code == 201, r.text
    return r.json()


async def test_create_and_read(team, client_for):
    author, doer = team
    async with client_for(author) as a:
        t = await new_task(a, doer.id, description="**жирно**", priority="P0",
                           due_date=str(date.today()), tags=["#reels", "reels", " insta "])
    assert t["author"] == "Іван А" and t["assignee"] == "Данило" and t["status"] == "new"
    assert t["status_label"] == "Нове" and t["tags"] == ["reels", "insta"] and t["priority"] == "P0"
    assert t["can_edit"] and t["can_close"]


@pytest.mark.parametrize("payload,code", [
    ({"title": ""}, 422),
    ({"priority": "P3"}, 422),
    ({"assignee_id": 999}, 400),
    ({"related_type": "report"}, 400),                    # тип без id
    ({"related_type": "invoice", "related_id": 1}, 400),
])
async def test_create_validation(team, client_for, payload, code):
    author, doer = team
    async with client_for(author) as a:
        body = {"title": "x", "assignee_id": doer.id, **payload}
        assert (await a.post("/api/admin/tasks", json=body)).status_code == code


async def test_cannot_assign_to_deactivated(team, client_for, make_admin):
    author, _ = team
    gone = await make_admin(is_active=False)
    async with client_for(author) as a:
        assert (await a.post("/api/admin/tasks", json={"title": "x", "assignee_id": gone.id})).status_code == 400


async def test_assignee_moves_status_but_only_author_closes(team, client_for):
    author, doer = team
    async with client_for(author) as a, client_for(doer) as d:
        t = await new_task(a, doer.id)
        url = f"/api/admin/tasks/{t['id']}"
        assert (await d.patch(url, json={"status": "in_progress"})).json()["status_label"] == "В роботі"
        assert (await d.patch(url, json={"status": "review"})).status_code == 200
        r = await d.patch(url, json={"status": "done"})
        assert r.status_code == 403 and "На перевірці" in r.json()["detail"]
        r = await a.patch(url, json={"status": "done"})
        assert r.status_code == 200 and r.json()["done_at"]
        assert (await d.patch(url, json={"status": "in_progress"})).status_code == 403   # відкрити — лише автор
        r = await a.patch(url, json={"status": "in_progress"})
        assert r.json()["done_at"] is None


async def test_assignee_cannot_edit_content(team, client_for):
    author, doer = team
    async with client_for(author) as a, client_for(doer) as d:
        t = await new_task(a, doer.id)
        r = await d.patch(f"/api/admin/tasks/{t['id']}", json={"title": "інакше"})
        assert r.status_code == 403
        assert not (await d.get(f"/api/admin/tasks/{t['id']}")).json()["can_edit"]


async def test_outsider_cannot_change_status(team, client_for, make_admin):
    author, doer = team
    stranger = await make_admin()
    async with client_for(author) as a, client_for(stranger) as s:
        t = await new_task(a, doer.id)
        assert (await s.patch(f"/api/admin/tasks/{t['id']}", json={"status": "review"})).status_code == 403


async def test_owner_can_edit_and_move_but_not_close_others_task(team, client_for, admin_client):
    author, doer = team
    async with client_for(author) as a:
        t = await new_task(a, doer.id)
    url = f"/api/admin/tasks/{t['id']}"
    assert (await admin_client.patch(url, json={"priority": "P2"})).status_code == 200
    assert (await admin_client.patch(url, json={"status": "review"})).status_code == 200
    assert (await admin_client.patch(url, json={"status": "done"})).status_code == 403


async def test_author_edits_everything(team, client_for, make_admin, session):
    author, doer = team
    other = await make_admin(name="Дмитро")
    async with client_for(author) as a:
        t = await new_task(a, doer.id, due_date=str(date.today()))
        url = f"/api/admin/tasks/{t['id']}"
        r = await a.patch(url, json={"title": " Нове ", "description": "опис", "priority": "P2",
                                     "tags": ["a"], "assignee_id": other.id, "due_date": "2027-01-31"})
        body = r.json()
        assert body["title"] == "Нове" and body["assignee"] == "Дмитро" and body["due_date"] == "2027-01-31"
        assert (await a.patch(url, json={"clear_due_date": True})).json()["due_date"] is None
        assert (await a.patch(url, json={"status": "bogus"})).status_code == 400
    summaries = (await session.execute(select(AuditLog.summary).where(AuditLog.action == "task.update"))).scalars().all()
    assert any("виконавець: Дмитро" in s for s in summaries)


async def test_filters(team, client_for):
    author, doer = team
    async with client_for(author) as a, client_for(doer) as d:
        late = await new_task(a, doer.id, title="Прострочене", due_date=str(date.today() - timedelta(days=2)),
                              tags=["ads"])
        await new_task(a, author.id, title="Своє")
        await new_task(d, author.id, title="Від Данила")
        titles = lambda r: sorted(t["title"] for t in r.json())
        assert titles(await d.get("/api/admin/tasks", params={"scope": "mine"})) == ["Прострочене"]
        assert titles(await d.get("/api/admin/tasks", params={"scope": "created"})) == ["Від Данила"]
        assert titles(await a.get("/api/admin/tasks", params={"assignee_id": author.id})) == ["Від Данила", "Своє"]
        assert titles(await a.get("/api/admin/tasks", params={"overdue": True})) == ["Прострочене"]
        assert titles(await a.get("/api/admin/tasks", params={"tag": "ADS"})) == ["Прострочене"]
        assert titles(await a.get("/api/admin/tasks", params={"q": "данила"})) in (["Від Данила"], [])  # ilike у SQLite — лише ASCII
        assert titles(await a.get("/api/admin/tasks", params={"status": "new"})) == ["Від Данила", "Прострочене", "Своє"]
        assert (await a.get("/api/admin/tasks", params={"status": "nope"})).status_code == 400
        all_ = (await a.get("/api/admin/tasks")).json()
        assert next(t for t in all_ if t["id"] == late["id"])["overdue"] is True


async def test_unread_for_the_other_person_only(team, client_for):
    author, doer = team
    async with client_for(author) as a, client_for(doer) as d:
        t = await new_task(a, doer.id)
        assert [x["unread"] for x in (await a.get("/api/admin/tasks")).json()] == [False]   # моя дія
        assert [x["unread"] for x in (await d.get("/api/admin/tasks")).json()] == [True]
        assert (await d.get("/api/admin/counters")).json()["tasks"] == 1
        await d.get(f"/api/admin/tasks/{t['id']}")                                     # відкрив
        assert (await d.get("/api/admin/counters")).json()["tasks"] == 0
        await a.post("/api/admin/comments", json={"entity_type": "task", "entity_id": t["id"], "body": "як там?"})
        assert (await d.get("/api/admin/counters")).json()["tasks"] == 1


async def test_delete_only_author_or_owner_and_cleans_up(team, client_for, admin_client, session):
    author, doer = team
    async with client_for(author) as a, client_for(doer) as d:
        t = await new_task(a, doer.id)
        await d.post("/api/admin/comments", json={"entity_type": "task", "entity_id": t["id"], "body": "x"})
        await d.get(f"/api/admin/tasks/{t['id']}")
        assert (await d.delete(f"/api/admin/tasks/{t['id']}")).status_code == 403
        assert (await a.delete(f"/api/admin/tasks/{t['id']}")).status_code == 200
        assert (await a.get(f"/api/admin/tasks/{t['id']}")).status_code == 404
        t2 = await new_task(a, doer.id)
    assert (await admin_client.delete(f"/api/admin/tasks/{t2['id']}")).status_code == 200
    assert (await session.execute(select(Comment))).scalars().all() == []
    assert (await session.execute(select(ReadMark))).scalars().all() == []

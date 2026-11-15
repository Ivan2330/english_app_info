"""Нотатки: приватну бачить лише автор (owner теж ні), поділену — усі, правити — лише автор."""
import pytest


@pytest.fixture
async def pair(make_admin):
    return await make_admin(name="Данило"), await make_admin(name="Дмитро")


async def test_private_note_invisible_to_everyone_else_including_owner(pair, client_for, admin_client):
    dan, dima = pair
    async with client_for(dan) as d, client_for(dima) as m:
        n = (await d.post("/api/admin/notes", json={"title": "Ідеї", "body": "# секрет"})).json()
        assert n["mine"] and not n["shared"] and n["author"] == "Данило"
        assert (await m.get("/api/admin/notes")).json() == []
        assert (await m.get(f"/api/admin/notes/{n['id']}")).status_code == 404     # навіть не 403
    assert (await admin_client.get("/api/admin/notes")).json() == []
    assert (await admin_client.get(f"/api/admin/notes/{n['id']}")).status_code == 404
    assert (await admin_client.delete(f"/api/admin/notes/{n['id']}")).status_code == 404


async def test_shared_note_readable_by_all_editable_by_author(pair, client_for):
    dan, dima = pair
    async with client_for(dan) as d, client_for(dima) as m:
        n = (await d.post("/api/admin/notes", json={"title": "Скрипт дзвінка", "shared": True})).json()
        seen = (await m.get("/api/admin/notes")).json()
        assert [x["title"] for x in seen] == ["Скрипт дзвінка"] and not seen[0]["mine"]
        assert (await m.get(f"/api/admin/notes/{n['id']}")).status_code == 200
        assert (await m.patch(f"/api/admin/notes/{n['id']}", json={"body": "x"})).status_code == 403
        assert (await m.delete(f"/api/admin/notes/{n['id']}")).status_code == 403
        r = await d.patch(f"/api/admin/notes/{n['id']}", json={"shared": False, "title": " Своє "})
        assert r.json()["title"] == "Своє"
        assert (await m.get("/api/admin/notes")).json() == []


async def test_empty_note_rejected(client_for, make_admin):
    async with client_for(await make_admin()) as c:
        assert (await c.post("/api/admin/notes", json={"title": "  ", "body": ""})).status_code == 400


async def test_pinned_first_search_and_scopes(pair, client_for):
    dan, dima = pair
    async with client_for(dan) as d, client_for(dima) as m:
        await d.post("/api/admin/notes", json={"title": "old"})
        await d.post("/api/admin/notes", json={"title": "pinned", "pinned": True})
        await d.post("/api/admin/notes", json={"title": "newest", "body": "budget plan"})
        await m.post("/api/admin/notes", json={"title": "theirs pinned", "pinned": True, "shared": True})
        titles = [n["title"] for n in (await d.get("/api/admin/notes")).json()]
        assert titles[0] == "pinned" and titles.index("theirs pinned") > 0   # чуже закріплення не стрибає вгору
        assert [n["title"] for n in (await d.get("/api/admin/notes", params={"q": "budget"})).json()] == ["newest"]
        assert [n["title"] for n in (await d.get("/api/admin/notes", params={"scope": "shared"})).json()] == ["theirs pinned"]
        assert len((await d.get("/api/admin/notes", params={"scope": "mine"})).json()) == 3


async def test_delete_own(client_for, make_admin):
    async with client_for(await make_admin()) as c:
        n = (await c.post("/api/admin/notes", json={"title": "x"})).json()
        assert (await c.delete(f"/api/admin/notes/{n['id']}")).status_code == 200
        assert (await c.get(f"/api/admin/notes/{n['id']}")).status_code == 404


async def test_notes_work_even_with_no_sections(client_for, make_admin):
    async with client_for(await make_admin(sections=[])) as c:
        assert (await c.post("/api/admin/notes", json={"title": "x"})).status_code == 201

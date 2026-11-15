"""Головна: мої завдання на сьогодні, прострочені, на прийняття, нові коментарі, звіти на перегляд."""
from datetime import date, timedelta


async def test_home_summary(admin_client, client_for, make_admin, admin):
    dan = await make_admin(name="Данило")
    today = str(date.today())
    yesterday = str(date.today() - timedelta(days=1))
    async with client_for(dan) as d:
        t_today = (await admin_client.post("/api/admin/tasks", json={
            "title": "Сьогодні", "assignee_id": dan.id, "due_date": today})).json()
        await admin_client.post("/api/admin/tasks", json={"title": "Вчора", "assignee_id": dan.id,
                                                          "due_date": yesterday})
        await d.patch(f"/api/admin/tasks/{t_today['id']}", json={"status": "review"})
        await d.post("/api/admin/comments", json={"entity_type": "task", "entity_id": t_today["id"],
                                                  "body": "здав"})
        rep = (await admin_client.post("/api/admin/reports", json={"title": "Звіт"})).json()
        await admin_client.post("/api/admin/comments", json={"entity_type": "report", "entity_id": rep["id"],
                                                             "body": "глянь"})

        h = (await d.get("/api/admin/home")).json()
        assert h["name"] == "Данило"
        assert [t["title"] for t in h["tasks_today"]] == ["Сьогодні"]
        assert [t["title"] for t in h["tasks_overdue"]] == ["Вчора"]
        assert [r["title"] for r in h["reports_to_review"]] == ["Звіт"]
        assert [c["body"] for c in h["new_comments"]] == ["глянь"] and h["new_comments_total"] == 1
        assert h["counters"] == {"tasks": 1, "reports": 1, "daily": 0, "leads": 0}     # «Сьогодні» востаннє чіпав сам Данило

        await d.put("/api/admin/reviews", json={"entity_type": "report", "entity_id": rep["id"], "score": 8})
        await d.get(f"/api/admin/reports/{rep['id']}")
        h = (await d.get("/api/admin/home")).json()
        assert h["reports_to_review"] == [] and h["new_comments"] == []

    mine = (await admin_client.get("/api/admin/home")).json()
    assert [t["title"] for t in mine["tasks_to_accept"]] == ["Сьогодні"]
    assert [c["body"] for c in mine["new_comments"]] == ["здав"]


async def test_home_hides_closed_sections(client_for, make_admin):
    user = await make_admin(sections=[])
    async with client_for(user) as c:
        h = (await c.get("/api/admin/home")).json()
        assert h["counters"] == {} and "tasks_today" not in h and "reports_to_review" not in h
        assert h["new_comments"] == []
        assert (await c.get("/api/admin/counters")).json() == {}

"""«Команда»: owner створює акаунти, скидає паролі, вмикає розділи, бачить журнал."""
from sqlalchemy import select

from app.core.access import ALL_SECTIONS
from app.core.config import settings
from app.core.security import verify_password
from app.models.admin_user import AdminUser
from app.models.workspace import AuditLog


async def test_create_member_shows_temporary_password_once(admin_client, session):
    r = await admin_client.post("/api/admin/team", json={"name": "Данило", "email": "Dan@Example.com"})
    assert r.status_code == 201
    body = r.json()
    pw = body["temporary_password"]
    assert len(pw) == 14 and not set(pw) & set("0O1lI")
    m = body["member"]
    assert m["email"] == "dan@example.com" and m["role"] == "admin" and m["must_change_password"]
    assert m["sections"] == ALL_SECTIONS                        # зараз усім усе
    user = (await session.execute(select(AdminUser).where(AdminUser.email == "dan@example.com"))).scalar_one()
    assert verify_password(pw, user.password_hash)
    # У списку команди пароля вже немає
    team = (await admin_client.get("/api/admin/team")).json()
    assert pw not in str(team) and len(team["members"]) == 2
    assert {s["key"] for s in team["sections"]} == set(ALL_SECTIONS)
    assert team["disk"]["free_bytes"] > 0 and team["disk"]["files_bytes"] == 0
    # У журналі факт, але не пароль
    log = (await session.execute(select(AuditLog))).scalars().all()
    assert any(l.action == "team.create" for l in log) and pw not in str([vars(l) for l in log])


async def test_create_with_chosen_sections_and_duplicate_email(admin_client):
    r = await admin_client.post("/api/admin/team", json={"name": "Д", "email": "d@example.com",
                                                         "sections": ["tasks", "notes", "bogus", "leads"]})
    assert r.json()["member"]["sections"] == ["leads", "tasks"]
    r = await admin_client.post("/api/admin/team", json={"name": "Д", "email": "D@example.com"})
    assert r.status_code == 409


async def test_new_member_logs_in_and_must_change_password(admin_client, client):
    pw = (await admin_client.post("/api/admin/team", json={"name": "Дмитро", "email": "dm@example.com"})).json()[
        "temporary_password"]
    r = await client.post("/api/admin/login", json={"email": "dm@example.com", "password": pw})
    assert r.status_code == 200 and r.json()["must_change_password"] is True
    client.headers["X-CSRF-Token"] = r.cookies.get(settings.csrf_cookie_name)
    assert (await client.get("/api/admin/tasks")).status_code == 403
    r = await client.post("/api/admin/change-password", json={"current_password": pw, "new_password": "my-own-pass-42"})
    assert r.status_code == 200
    client.headers["X-CSRF-Token"] = r.cookies.get(settings.csrf_cookie_name)
    assert (await client.get("/api/admin/tasks")).status_code == 200


async def test_toggle_sections_takes_effect_immediately(admin_client, client_for, make_admin):
    user = await make_admin()
    async with client_for(user) as c:
        assert (await c.get("/api/admin/reports")).status_code == 200
        r = await admin_client.patch(f"/api/admin/team/{user.id}", json={"sections": ["tasks"]})
        assert r.status_code == 200 and r.json()["sections"] == ["tasks"]
        assert (await c.get("/api/admin/reports")).status_code == 403
        assert (await c.get("/api/admin/tasks")).status_code == 200
        assert (await c.get("/api/admin/me")).json()["sections"] == ["tasks"]


async def test_owner_sections_cannot_be_switched_off(admin_client, admin):
    r = await admin_client.patch(f"/api/admin/team/{admin.id}", json={"sections": []})
    assert r.status_code == 400


async def test_rename(admin_client, make_admin):
    user = await make_admin()
    r = await admin_client.patch(f"/api/admin/team/{user.id}", json={"name": "  Данило  "})
    assert r.json()["name"] == "Данило"


async def test_deactivate_logs_out_and_blocks_login(admin_client, client_for, make_admin, client):
    user = await make_admin(email="gone@example.com")
    async with client_for(user) as c:
        assert (await c.get("/api/admin/me")).status_code == 200
        r = await admin_client.patch(f"/api/admin/team/{user.id}", json={"is_active": False})
        assert r.status_code == 200 and r.json()["is_active"] is False
        assert (await c.get("/api/admin/me")).status_code == 401
    r = await client.post("/api/admin/login", json={"email": "gone@example.com", "password": "user-pass-12345"})
    assert r.status_code == 401
    # Повернути назад
    assert (await admin_client.patch(f"/api/admin/team/{user.id}", json={"is_active": True})).json()["is_active"]
    people = (await admin_client.get("/api/admin/people")).json()
    assert {p["name"] for p in people} == {"Іван", user.name}


async def test_owner_cannot_deactivate_self_or_reset_own_password(admin_client, admin):
    assert (await admin_client.patch(f"/api/admin/team/{admin.id}", json={"is_active": False})).status_code == 400
    assert (await admin_client.post(f"/api/admin/team/{admin.id}/reset-password")).status_code == 400


async def test_reset_password(admin_client, client_for, make_admin, session):
    user = await make_admin()
    async with client_for(user) as c:
        r = await admin_client.post(f"/api/admin/team/{user.id}/reset-password")
        assert r.status_code == 200
        pw = r.json()["temporary_password"]
        assert (await c.get("/api/admin/me")).status_code == 401        # стара сесія закрита
    await session.refresh(user)
    assert user.must_change_password and verify_password(pw, user.password_hash)


async def test_unknown_member_404(admin_client):
    assert (await admin_client.patch("/api/admin/team/999", json={"name": "x"})).status_code == 404
    assert (await admin_client.post("/api/admin/team/999/reset-password")).status_code == 404


async def test_people_hides_inactive_and_marks_me(client_for, make_admin):
    me = await make_admin()
    await make_admin(is_active=False)
    async with client_for(me) as c:
        people = (await c.get("/api/admin/people")).json()
    assert [p["is_me"] for p in people] == [True]


async def test_audit_log_lists_actions_with_actor_name(admin_client, make_admin):
    user = await make_admin()
    await admin_client.patch(f"/api/admin/team/{user.id}", json={"sections": ["tasks"]})
    rows = (await admin_client.get("/api/admin/audit")).json()
    assert rows[0]["action"] == "team.update" and rows[0]["actor"] == "Іван"
    assert rows[0]["summary"].startswith(f"{user.name}: вимкнено: Статистика сайту, Заявки")
    assert "Завдання" not in rows[0]["summary"]
    await admin_client.patch(f"/api/admin/team/{user.id}", json={"sections": ["tasks", "reports"]})
    assert (await admin_client.get("/api/admin/audit")).json()[0]["summary"] == f"{user.name}: увімкнено: Звіти"
    only = (await admin_client.get("/api/admin/audit", params={"action": "task."})).json()
    assert only == []


def test_disk_usage_falls_back_to_existing_parent(monkeypatch, tmp_path):
    from app.api.admin.team import disk_usage
    monkeypatch.setattr(settings, "upload_dir", str(tmp_path / "missing" / "deeper"))
    assert disk_usage()["total_bytes"] > 0

"""Доступ до розділів перевіряється на БЕКЕНДІ, на кожному роуті.

Тест не тримає список роутів руками: він обходить усі роути застосунку.
Новий роут /api/admin без залежності доступу — і тест падає, навіть якщо
про нього ніхто не згадав. Для кожного роуту розділу окремий кейс:
без входу 401, без розділу 403, owner проходить.
"""
import re

import pytest
from fastapi.routing import APIRoute

from app.core import access
from app.core.access import ALL_SECTIONS, SECTIONS, clean_sections, effective_sections
from app.models.admin_user import AdminUser
from tests.conftest import ALL_ROUTERS

OPEN = {"/api/admin/login", "/api/admin/logout"}
# Роути, відкриті будь-кому, хто увійшов. Розділ сутності перевіряють усередині (load_entity),
# нотатки — особисті, головна й лічильники показують лише відкриті розділи.
ANY_PREFIXES = ("/api/admin/comments", "/api/admin/reviews", "/api/admin/files", "/api/admin/notes",
                "/api/admin/home", "/api/admin/counters", "/api/admin/people")
LOGIN_ONLY = {"/api/admin/me", "/api/admin/change-password"}


def _calls(dependant):
    for d in dependant.dependencies:
        yield d.call
        yield from _calls(d)


def guard_of(route: APIRoute) -> str | None:
    calls = list(_calls(route.dependant))
    for c in calls:                               # найвужча перевірка перемагає
        if getattr(c, "section", None):
            return f"section:{c.section}"
    for c, name in ((access.require_owner, "owner"), (access.require_any, "any"),
                    (access.require_login_any, "login")):
        if c in calls:
            return name
    return None


def admin_routes():
    # Ходимо по роутерах напряму: FastAPI 0.16x загортає include_router у ліниві обгортки.
    for route in (r for router in ALL_ROUTERS for r in router.routes):
        if isinstance(route, APIRoute) and route.path.startswith("/api/admin") and route.path not in OPEN:
            for method in sorted(route.methods):
                yield method, route.path, guard_of(route)


ROUTES = list(admin_routes())


def concrete(path):
    return re.sub(r"\{[^}]+\}", "1", path)


def test_every_admin_route_has_an_access_guard():
    missing = [(m, p) for m, p, g in ROUTES if g is None]
    assert missing == [], f"роути без перевірки доступу: {missing}"


def test_broad_guards_only_where_intended():
    for method, path, guard in ROUTES:
        if guard == "login":
            assert path in LOGIN_ONLY, (method, path)
        if guard == "any":
            assert path.startswith(ANY_PREFIXES), f"{method} {path}: відкритий усім — точно так треба?"


def test_matrix_covers_every_section_with_routes():
    covered = {g.split(":")[1] for _, _, g in ROUTES if g and g.startswith("section:")}
    assert {"dashboard", "leads", "quotes", "orders", "certificates", "tasks", "reports"} <= covered


@pytest.mark.parametrize("method,path,guard", ROUTES, ids=[f"{m} {p}" for m, p, _ in ROUTES])
async def test_without_login_401(client, method, path, guard):
    r = await client.request(method, concrete(path))
    assert r.status_code == 401, f"{method} {path} відкритий без входу"


SECTION_ROUTES = [(m, p, g.split(":")[1]) for m, p, g in ROUTES if g and g.startswith("section:")]


@pytest.mark.parametrize("method,path,section", SECTION_ROUTES, ids=[f"{m} {p}" for m, p, _ in SECTION_ROUTES])
async def test_section_closed_403(client_for, make_admin, method, path, section):
    others = [s for s in ALL_SECTIONS if s != section]
    user = await make_admin(sections=others)              # відкрито все, крім цього розділу
    async with client_for(user) as c:
        r = await c.request(method, concrete(path))
    assert r.status_code == 403, f"{method} {path}: розділ «{section}» вимкнено, а доступ є"
    assert SECTIONS[section] in r.json()["detail"]


OWNER_ROUTES = [(m, p) for m, p, g in ROUTES if g == "owner"]


@pytest.mark.parametrize("method,path", OWNER_ROUTES, ids=[f"{m} {p}" for m, p in OWNER_ROUTES])
async def test_owner_only_403_for_admin_with_all_sections(client_for, make_admin, method, path):
    user = await make_admin()
    async with client_for(user) as c:
        r = await c.request(method, concrete(path))
    assert r.status_code == 403 and r.json()["detail"] == "Це може робити лише власник"


@pytest.mark.parametrize("section", ["tasks", "reports", "leads", "certificates"])  # stats — лише PG
async def test_section_open_lets_admin_in(client_for, make_admin, section):
    path = {"tasks": "/api/admin/tasks", "reports": "/api/admin/reports", "leads": "/api/admin/leads",
            "certificates": "/api/admin/certificates"}[section]
    user = await make_admin(sections=[section])
    async with client_for(user) as c:
        assert (await c.get(path)).status_code == 200


async def test_owner_ignores_stored_sections(client_for, make_admin):
    owner = await make_admin(role="owner", sections=[])
    async with client_for(owner) as c:
        assert (await c.get("/api/admin/tasks")).status_code == 200
        assert (await c.get("/api/admin/team")).status_code == 200


def test_unknown_section_is_a_programming_error():
    with pytest.raises(ValueError):
        access.require("nope")


def test_clean_sections_keeps_menu_order_and_drops_unknown():
    assert clean_sections(["tasks", "leads", "tasks", "hacker"]) == ["leads", "tasks"]
    assert effective_sections(AdminUser(role="admin", sections=None)) == []
    assert effective_sections(AdminUser(role="owner", sections=[])) == ALL_SECTIONS

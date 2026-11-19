"""«Звіт дня»: один на день, вікно редагування, видимість (усі / лише свій), зведення, нагадування.

401/403 для кожного роуту розділу перевіряє tests/test_access.py (він обходить усі роути).
Тут — правила самого розділу, зокрема що в режимі «приватно» admin не бачить чужих звітів
ні в списку, ні за id, ні через коментарі, оцінки, файли й лічильники.
"""
from datetime import date, datetime, timedelta, timezone

import pytest
from sqlalchemy import func, select

from app.core import kyiv
from app.models.workspace import DailyReport

TODAY = date(2026, 11, 18)          # середа
PNG = b"\x89PNG\r\n\x1a\n" + b"\x00" * 32


@pytest.fixture(autouse=True)
def frozen_kyiv(monkeypatch):
    """Київський час під контролем тесту: за замовчуванням 18.11.2026, 12:00."""
    state = {"now": datetime(2026, 11, 18, 12, 0, tzinfo=timezone(timedelta(hours=2)))}
    monkeypatch.setattr(kyiv, "kyiv_now", lambda: state["now"])
    monkeypatch.setattr(kyiv, "kyiv_today", lambda: state["now"].date())

    def set_now(dt):
        state["now"] = dt
    return set_now


def body(**over):
    return {"done": "Зняла 2 Reels, відповіла на 14 заявок", "hours": 6.5,
            "links": ["https://instagram.com/p/abc", " "], "blockers": "", "plan": "Монтаж", **over}


@pytest.fixture
async def dan(make_admin):
    return await make_admin(name="Данило")


@pytest.fixture
async def dima(make_admin):
    return await make_admin(name="Дмитро")


async def set_visibility(admin_client, mode):
    r = await admin_client.put("/api/admin/daily-reports/settings", json={"visibility": mode})
    assert r.status_code == 200, r.text
    return r.json()


# ------------------------------------------------------------------ подати звіт

async def test_create_today_and_read_back(client_for, dan):
    async with client_for(dan) as c:
        r = await c.post("/api/admin/daily-reports", json=body(mood=4))
        assert r.status_code == 201, r.text
        rep = r.json()
        assert rep["date"] == "2026-11-18" and rep["author"] == "Данило" and rep["hours"] == 6.5
        assert rep["links"] == ["https://instagram.com/p/abc"] and rep["mood"] == 4
        assert rep["editable"] and rep["editable_until"] == "2026-11-19" and rep["mine"]
        mine = (await c.get("/api/admin/daily-reports/mine")).json()
        assert mine["today"]["report"]["id"] == rep["id"] and mine["yesterday"]["report"] is None
        assert mine["yesterday"]["date"] == "2026-11-17"


async def test_one_report_per_person_per_day(client_for, dan, dima):
    async with client_for(dan) as d, client_for(dima) as m:
        assert (await d.post("/api/admin/daily-reports", json=body())).status_code == 201
        r = await d.post("/api/admin/daily-reports", json=body())
        assert r.status_code == 409 and "уже є" in r.json()["detail"]
        assert (await m.post("/api/admin/daily-reports", json=body())).status_code == 201   # інша людина — можна


@pytest.mark.parametrize("day,code", [("2026-11-17", 201), ("2026-11-16", 400), ("2026-11-19", 400)])
async def test_only_today_or_yesterday(client_for, dan, day, code):
    async with client_for(dan) as c:
        assert (await c.post("/api/admin/daily-reports", json=body(date=day))).status_code == code


@pytest.mark.parametrize("over", [
    {"done": ""}, {"done": "   "}, {"hours": -1}, {"hours": 25}, {"mood": 0}, {"mood": 6},
    {"links": ["javascript:alert(1)"]}, {"links": ["ftp://x"]}, {"links": ["https://x"] * 21},
    {"links": ["https://" + "a" * 600]}, {"secret": 1},
])
async def test_validation(client_for, dan, over):
    async with client_for(dan) as c:
        assert (await c.post("/api/admin/daily-reports", json=body(**over))).status_code == 422


async def test_hours_and_mood_are_optional_details(client_for, dan):
    async with client_for(dan) as c:
        r = await c.post("/api/admin/daily-reports", json={"done": "x", "hours": 0})
        assert r.status_code == 201 and r.json()["mood"] is None and r.json()["links"] == []


async def test_post_metrics_create_update_and_validation(client_for, dan):
    post = {"url": "https://instagram.com/p/abc", "reach": 120, "saves": 8,
            "shares": 3, "comments": 4, "followers": 2, "direct_trial": 1}
    async with client_for(dan) as c:
        created = await c.post("/api/admin/daily-reports", json=body(post_metrics=[post]))
        assert created.status_code == 201, created.text
        rid = created.json()["id"]
        assert created.json()["post_metrics"] == [post]
        assert (await c.patch(f"/api/admin/daily-reports/{rid}", json={"post_metrics": [{**post, "reach": 150}]})).json()["post_metrics"][0]["reach"] == 150
        assert (await c.post("/api/admin/daily-reports", json=body(date="2026-11-17", post_metrics=[{**post, "reach": -1}]))).status_code == 422
        assert (await c.patch(f"/api/admin/daily-reports/{rid}", json={"post_metrics": [{**post, "url": "javascript:bad"}]})).status_code == 422


# ------------------------------------------------------------------ редагування до кінця наступного дня

async def test_author_edits_until_end_of_next_day(client_for, dan, frozen_kyiv):
    async with client_for(dan) as c:
        rep = (await c.post("/api/admin/daily-reports", json=body(mood=3))).json()
        url = f"/api/admin/daily-reports/{rep['id']}"
        frozen_kyiv(datetime(2026, 11, 19, 23, 59, tzinfo=timezone(timedelta(hours=2))))   # кінець наступного дня
        r = await c.patch(url, json={"hours": 7, "plan": "  Новий план ", "links": ["https://a.b"], "clear_mood": True})
        assert r.status_code == 200
        assert (r.json()["hours"], r.json()["plan"], r.json()["links"], r.json()["mood"]) == (7, "Новий план", ["https://a.b"], None)
        assert (await c.patch(url, json={"mood": 5})).json()["mood"] == 5
        assert (await c.patch(url, json={"done": "   "})).status_code == 400
        frozen_kyiv(datetime(2026, 11, 20, 0, 1, tzinfo=timezone(timedelta(hours=2))))     # уже післязавтра
        r = await c.patch(url, json={"hours": 8})
        assert r.status_code == 403 and "до кінця 19.11" in r.json()["detail"]
        assert (await c.get(url)).json()["editable"] is False


async def test_only_author_edits(client_for, admin_client, dan, dima):
    async with client_for(dan) as d, client_for(dima) as m:
        rep = (await d.post("/api/admin/daily-reports", json=body())).json()
        assert (await m.patch(f"/api/admin/daily-reports/{rep['id']}", json={"hours": 1})).status_code == 403
    assert (await admin_client.patch(f"/api/admin/daily-reports/{rep['id']}", json={"hours": 1})).status_code == 403
    assert (await admin_client.get("/api/admin/daily-reports/999")).status_code == 404


# ------------------------------------------------------------------ видимість

async def test_by_default_everyone_sees_everyone(client_for, admin_client, dan, dima):
    async with client_for(dan) as d, client_for(dima) as m:
        rep = (await d.post("/api/admin/daily-reports", json=body())).json()
        settings = (await m.get("/api/admin/daily-reports/settings")).json()
        assert settings["visibility"] == "all" and settings["can_change"] is False
        assert [x["author"] for x in (await m.get("/api/admin/daily-reports")).json()["items"]] == ["Данило"]
        assert (await m.get(f"/api/admin/daily-reports/{rep['id']}")).status_code == 200


async def test_private_mode_hides_others_reports_everywhere(client_for, admin_client, dan, dima, session):
    async with client_for(dan) as d, client_for(dima) as m:
        rep = (await d.post("/api/admin/daily-reports", json=body(blockers="Не працює ноутбук",
            post_metrics=[{"url": "https://example.test/post", "reach": 100}]))).json()
        await m.post("/api/admin/daily-reports", json=body())
        rid = rep["id"]
        await admin_client.post("/api/admin/comments", json={"entity_type": "daily", "entity_id": rid, "body": "Добре"})
        await d.post("/api/admin/files", params={"entity_type": "daily", "entity_id": rid}, files={"file": ("a.png", PNG)})
        before = (await session.execute(select(func.count()).select_from(DailyReport))).scalar_one()

        assert (await set_visibility(admin_client, "owner_only"))["visibility"] == "owner_only"

        # Дмитро: лише свій у списку, чужий за id — 404, і жодних обхідних шляхів
        items = (await m.get("/api/admin/daily-reports")).json()["items"]
        assert [x["author"] for x in items] == ["Дмитро"]
        assert (await m.get("/api/admin/daily-reports", params={"author_id": dan.id})).json()["items"] == []
        assert (await m.get(f"/api/admin/daily-reports/{rid}")).status_code == 404
        assert (await m.patch(f"/api/admin/daily-reports/{rid}", json={"hours": 1})).status_code == 404
        key = {"entity_type": "daily", "entity_id": rid}
        assert (await m.get("/api/admin/comments", params=key)).status_code == 404
        assert (await m.post("/api/admin/comments", json={**key, "body": "x"})).status_code == 404
        assert (await m.get("/api/admin/files", params=key)).status_code == 404
        assert (await m.get("/api/admin/reviews", params=key)).status_code == 404
        assert (await m.get("/api/admin/counters")).json()["daily"] == 0
        week = (await m.get("/api/admin/daily-reports/week")).json()
        assert week["reports_total"] == 1 and week["blockers"] == [] and week["members"] == []
        assert week["post_metrics_total"]["reach"] == 0
        assert (await m.get("/api/admin/daily-reports/authors")).json() == [{"id": dima.id, "name": "Дмитро"}]

        # Автор бачить свій, owner — усі
        assert (await d.get(f"/api/admin/daily-reports/{rid}")).status_code == 200
        assert len((await admin_client.get("/api/admin/daily-reports")).json()["items"]) == 2
        assert (await admin_client.get(f"/api/admin/daily-reports/{rid}")).status_code == 200

        # Перемикання не змінює дані й повертається без міграції
        after = (await session.execute(select(func.count()).select_from(DailyReport))).scalar_one()
        assert after == before == 2
        await set_visibility(admin_client, "all")
        assert (await m.get(f"/api/admin/daily-reports/{rid}")).status_code == 200
        assert (await m.get("/api/admin/comments", params=key)).json()[0]["body"] == "Добре"


async def test_only_owner_changes_visibility(client_for, admin_client, dan):
    async with client_for(dan) as d:
        assert (await d.put("/api/admin/daily-reports/settings", json={"visibility": "owner_only"})).status_code == 403
    assert (await admin_client.put("/api/admin/daily-reports/settings", json={"visibility": "nobody"})).status_code == 422
    r = await set_visibility(admin_client, "owner_only")
    assert r["label"].startswith("Кожен бачить лише свій") and r["can_change"] is True
    audit = (await admin_client.get("/api/admin/audit", params={"action": "daily."})).json()
    assert audit[0]["action"] == "daily.visibility"


async def test_unknown_stored_visibility_falls_back_to_all(admin_client, session):
    from app.models.workspace import WorkspaceSetting
    session.add(WorkspaceSetting(key="daily_reports_visibility", value="weird", updated_at=datetime.now(timezone.utc)))
    await session.commit()
    assert (await admin_client.get("/api/admin/daily-reports/settings")).json()["visibility"] == "all"


# ------------------------------------------------------------------ непрочитане й коментарі

async def test_unread_counter_and_comment_flow(client_for, admin_client, dan):
    async with client_for(dan) as d:
        rep = (await d.post("/api/admin/daily-reports", json=body())).json()
        assert (await d.get("/api/admin/counters")).json()["daily"] == 0          # свій звіт — не нове
        assert (await admin_client.get("/api/admin/counters")).json()["daily"] == 1
        assert (await admin_client.get("/api/admin/daily-reports")).json()["items"][0]["unread"] is True
        await admin_client.get(f"/api/admin/daily-reports/{rep['id']}")
        assert (await admin_client.get("/api/admin/counters")).json()["daily"] == 0
        await admin_client.post("/api/admin/comments", json={"entity_type": "daily", "entity_id": rep["id"],
                                                             "body": "Що з ноутбуком?"})
        assert (await d.get("/api/admin/counters")).json()["daily"] == 1
        home = (await d.get("/api/admin/home")).json()
        assert [c["body"] for c in home["new_comments"]] == ["Що з ноутбуком?"]
        assert home["new_comments"][0]["title"] == "Звіт дня за 18.11"
        listed = (await d.get("/api/admin/daily-reports")).json()["items"][0]
        assert listed["comments_count"] == 1


# ------------------------------------------------------------------ нагадування на головній

@pytest.mark.parametrize("hour,submitted,reminder", [(16, False, False), (17, False, True), (21, False, True),
                                                     (18, True, False)])
async def test_reminder_after_17_kyiv(client_for, dan, frozen_kyiv, hour, submitted, reminder):
    frozen_kyiv(datetime(2026, 11, 18, hour, 5, tzinfo=timezone(timedelta(hours=2))))
    async with client_for(dan) as c:
        if submitted:
            await c.post("/api/admin/daily-reports", json=body())
        h = (await c.get("/api/admin/home")).json()
    assert h["daily_reminder"] is reminder and h["daily_today_submitted"] is submitted


async def test_no_reminder_without_the_section(client_for, make_admin, frozen_kyiv):
    frozen_kyiv(datetime(2026, 11, 18, 19, 0, tzinfo=timezone(timedelta(hours=2))))
    user = await make_admin(sections=["tasks"])
    async with client_for(user) as c:
        h = (await c.get("/api/admin/home")).json()
    assert "daily_reminder" not in h and "daily" not in h["counters"]


# ------------------------------------------------------------------ тижневе зведення (owner)

async def test_week_summary_for_owner(client_for, admin_client, dan, dima, make_admin, frozen_kyiv):
    await make_admin(name="Без розділу", sections=["tasks"])                   # у зведення не потрапляє
    async with client_for(dan) as d, client_for(dima) as m:
        frozen_kyiv(datetime(2026, 11, 17, 12, 0, tzinfo=timezone(timedelta(hours=2))))   # вівторок
        await d.post("/api/admin/daily-reports", json=body(hours=8, blockers="Немає доступу до Canva",
            post_metrics=[{"url": "https://instagram.com/p/abc", "reach": 120, "saves": 8, "shares": 3,
                           "comments": 4, "followers": 2, "direct_trial": 1}]))
        frozen_kyiv(datetime(2026, 11, 18, 12, 0, tzinfo=timezone(timedelta(hours=2))))   # середа
        await d.post("/api/admin/daily-reports", json=body(hours=6.5))
        await m.post("/api/admin/daily-reports", json=body(hours=3, blockers="Хворів"))
    w = (await admin_client.get("/api/admin/daily-reports/week", params={"start": "2026-11-19"})).json()
    assert (w["start"], w["end"]) == ("2026-11-16", "2026-11-22")                  # пн–нд того тижня
    by_name = {m["name"]: m for m in w["members"]}
    assert set(by_name) == {"Іван", "Данило", "Дмитро"}
    assert by_name["Данило"]["hours_total"] == 14.5 and by_name["Данило"]["submitted_count"] == 2
    assert [x["submitted"] for x in by_name["Данило"]["days"]][:3] == [False, True, True]
    assert by_name["Данило"]["missing_workdays"] == ["2026-11-16"]               # понеділок не здав
    assert by_name["Іван"]["missing_workdays"] == ["2026-11-16", "2026-11-17", "2026-11-18"]
    assert [(b["author"], b["text"]) for b in w["blockers"]] == [("Данило", "Немає доступу до Canva"),
                                                                  ("Дмитро", "Хворів")]
    assert w["hours_total"] == 17.5
    assert w["reports_total"] == 3
    assert w["post_metrics_total"] == {"reach": 120, "saves": 8, "shares": 3,
                                        "comments": 4, "followers": 2, "direct_trial": 1}
    default = (await admin_client.get("/api/admin/daily-reports/week")).json()
    assert default["start"] == "2026-11-16"


async def test_list_filters(client_for, admin_client, dan, dima, frozen_kyiv):
    async with client_for(dan) as d, client_for(dima) as m:
        frozen_kyiv(datetime(2026, 11, 17, 12, 0, tzinfo=timezone(timedelta(hours=2))))
        await d.post("/api/admin/daily-reports", json=body(blockers="Canva"))
        frozen_kyiv(datetime(2026, 11, 18, 12, 0, tzinfo=timezone(timedelta(hours=2))))
        await d.post("/api/admin/daily-reports", json=body())
        await m.post("/api/admin/daily-reports", json=body())
    get = lambda **p: admin_client.get("/api/admin/daily-reports", params=p)
    assert [x["date"] for x in (await get(author_id=dan.id)).json()["items"]] == ["2026-11-18", "2026-11-17"]
    assert len((await get(date_from="2026-11-18")).json()["items"]) == 2
    assert len((await get(date_to="2026-11-17")).json()["items"]) == 1
    assert len((await get(has_blockers=True)).json()["items"]) == 1
    assert len((await get(has_blockers=False)).json()["items"]) == 2
    first = (await get(limit=1)).json()
    assert len(first["items"]) == 1 and first["has_more"]
    assert len((await get(limit=1, offset=1)).json()["items"]) == 1
    assert [u["id"] for u in (await admin_client.get("/api/admin/daily-reports/authors")).json()] == [dan.id, dima.id]


# ------------------------------------------------------------------ київський час

def test_kyiv_fallback_rule_matches_dst_switches():
    utc = timezone.utc
    assert kyiv.eet_offset(datetime(2026, 3, 29, 0, 59, tzinfo=utc)) == timedelta(hours=2)
    assert kyiv.eet_offset(datetime(2026, 3, 29, 1, 0, tzinfo=utc)) == timedelta(hours=3)
    assert kyiv.eet_offset(datetime(2026, 10, 25, 0, 59, tzinfo=utc)) == timedelta(hours=3)
    assert kyiv.eet_offset(datetime(2026, 10, 25, 1, 0, tzinfo=utc)) == timedelta(hours=2)
    assert kyiv.eet_offset(datetime(2026, 11, 18, 15, 0, tzinfo=utc)) == timedelta(hours=2)


def test_to_kyiv_without_tz_database(monkeypatch):
    monkeypatch.setattr(kyiv, "_TZ", None)
    local = kyiv.to_kyiv(datetime(2026, 7, 1, 14, 30))                           # без tzinfo = UTC
    assert (local.hour, local.utcoffset()) == (17, timedelta(hours=3))


def test_real_clock_is_kyiv(monkeypatch):
    monkeypatch.undo()                                                          # без заморозки з fixture
    now = kyiv.kyiv_now()
    assert now.utcoffset() in (timedelta(hours=2), timedelta(hours=3)) and kyiv.kyiv_today() == now.date()

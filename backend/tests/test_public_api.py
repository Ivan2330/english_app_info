"""Публічний API: каталог, заявки, форма розрахунку, лічильник відвідувань."""
from datetime import date

import pytest
from fastapi import Request
from sqlalchemy import select

from app.api.public import track
from app.core.clientip import client_ip
from app.core.seed_packages import seed_packages
from app.models.lead import Lead, LeadKind, LeadStatus
from app.models.order import Order
from app.models.package import Audience, Family, Format, Track
from app.models.quote_request import QuoteRequest, QuoteStatus
from app.models.visit import PageVisit


# =============================================================== каталог

async def test_catalogue_filters(client, make_package):
    await make_package(slug="a", family=Family.SUBSCRIPTION, audience=Audience.ADULTS,
                       fmt=Format.GROUP, track=Track.GENERAL, chast_enabled=True)
    await make_package(slug="b", family=Family.COURSE, audience=Audience.TEENS,
                       fmt=Format.INDIVIDUAL, track=Track.EXAM, chast_enabled=False)

    async def slugs(**params):
        return sorted(p["slug"] for p in (await client.get("/api/packages", params=params)).json())

    assert await slugs() == ["a", "b"]
    assert await slugs(family="course") == ["b"]
    assert await slugs(audience="adults") == ["a"]
    assert await slugs(format="group") == ["a"]
    assert await slugs(track="exam") == ["b"]
    assert await slugs(chast="true") == ["a"]
    assert await slugs(chast="false") == ["b"]
    assert await slugs(family="subscription", audience="teens") == []


@pytest.mark.parametrize("param", ["family", "audience", "format", "track"])
async def test_unknown_enum_filter_is_422_not_500(client, param):
    assert (await client.get("/api/packages", params={param: "bogus"})).status_code == 422


async def test_catalogue_order_is_sort_order(client, make_package):
    await make_package(slug="late", sort_order=9)
    await make_package(slug="early", sort_order=1)
    assert [p["slug"] for p in (await client.get("/api/packages")).json()] == ["early", "late"]


async def test_filters_endpoint_lists_only_real_active_combinations(client, make_package):
    await make_package(slug="a", audience=Audience.ADULTS, fmt=Format.GROUP)
    await make_package(slug="a2", audience=Audience.ADULTS, fmt=Format.GROUP)       # дубль не множиться
    await make_package(slug="gone", audience=Audience.KIDS, fmt=Format.PAIR, is_active=False)
    combos = (await client.get("/api/packages/filters")).json()["combinations"]
    assert combos == [{"family": "subscription", "audience": "adults", "format": "group", "track": "general"}]


async def test_package_by_slug(client, make_package):
    await make_package(slug="one", long_description="Довгий опис")
    body = (await client.get("/api/packages/one")).json()
    assert body["long_description"] == "Довгий опис" and body["is_active"] is True
    assert (await client.get("/api/packages/missing")).status_code == 404


async def test_seeded_catalogue_is_what_the_site_sells(client, session):
    await seed_packages(session)
    items = (await client.get("/api/packages")).json()
    assert len(items) == 80
    assert not [i for i in items if i["family"] == "corporate"]
    assert not [i for i in items if i["audience"] == "kids" and i["family"] != "club"]
    assert {i["lessons_count"] for i in items
            if i["family"] == "subscription" and i["format"] != "group"} == {6, 16, 24, 48, 96}


# =============================================================== заявки

async def lead(client, **over):
    body = {"name": "Іван", "phone": "+380991112233"}
    body.update(over)
    return await client.post("/api/leads", json=body)


async def test_lead_created_with_defaults(client, session):
    r = await lead(client, comment="Ціль: IELTS")
    assert r.json()["ok"] is True
    row = (await session.execute(select(Lead))).scalar_one()
    assert (row.status, row.source, row.comment) == (LeadStatus.NEW, "site", "Ціль: IELTS")


async def test_lead_stores_all_contact_channels(client, session):
    await lead(client, telegram="@ivan", viber="v", email="a@b.ua", audience="kids",
               preferred_time="вечір", source="site/pricing", utm="utm_source=ig")
    row = (await session.execute(select(Lead))).scalar_one()
    assert (row.telegram, row.viber, row.email, row.audience) == ("@ivan", "v", "a@b.ua", "kids")
    assert (row.source, row.utm, row.preferred_time) == ("site/pricing", "utm_source=ig", "вечір")


@pytest.mark.parametrize("over", [{"name": ""}, {"name": "   "}, {"name": None}])
async def test_lead_needs_a_name(client, over):
    assert (await lead(client, **over)).status_code == 400


@pytest.mark.parametrize("over", [
    {"comment": "дивіться http://spam.example"},
    {"comment": "https://spam.example"},
    {"name": "https://spam"},
    {"comment": "x" * 2000},
])
async def test_lead_spam_filter(client, over):
    assert (await lead(client, **over)).status_code == 400


async def test_lead_records_real_client_ip_from_proxy(client, session):
    await client.post("/api/leads", json={"name": "I"}, headers={"x-forwarded-for": "6.6.6.6, 203.0.113.9"})
    assert (await session.execute(select(Lead.ip))).scalar_one() == "203.0.113.9"


# =============================================================== адмінка заявок

async def make_lead(session, **kw):
    row = Lead(**{"name": "Тест", "kind": LeadKind.TRIAL, **kw})
    session.add(row)
    await session.commit()
    return row


async def test_admin_leads_filters(admin_client, session):
    await make_lead(session, name="Марія", phone="+380501", status=LeadStatus.NEW)
    await make_lead(session, name="Олег", telegram="@oleg", status=LeadStatus.LOST, kind=LeadKind.QUESTION)
    ids = lambda r: sorted(x["name"] for x in r.json())      # noqa: E731
    assert ids(await admin_client.get("/api/admin/leads")) == ["Марія", "Олег"]
    assert ids(await admin_client.get("/api/admin/leads", params={"status": "lost"})) == ["Олег"]
    assert ids(await admin_client.get("/api/admin/leads", params={"kind": "question"})) == ["Олег"]
    assert ids(await admin_client.get("/api/admin/leads", params={"q": "oleg"})) == ["Олег"]
    assert ids(await admin_client.get("/api/admin/leads", params={"q": "380501"})) == ["Марія"]
    assert (await admin_client.get("/api/admin/leads", params={"status": "bogus"})).status_code == 422


async def test_admin_lead_row_shape(admin_client, session):
    await make_lead(session, source="site/level-quiz", comment="1. A — правильно")
    row = (await admin_client.get("/api/admin/leads")).json()[0]
    assert row["source"] == "site/level-quiz" and row["status"] == "new" and row["kind"] == "trial"


async def test_admin_lead_patch(admin_client, session):
    row = await make_lead(session)
    r = await admin_client.patch(f"/api/admin/leads/{row.id}",
                                 json={"status": "contacted", "phone": "+38099", "comment": None, "id": 999})
    assert r.json() == {"ok": True}
    assert row.phone == "+38099" and row.id != 999
    assert (await admin_client.patch("/api/admin/leads/9999", json={})).status_code == 404


# =============================================================== форма розрахунку

async def quote(client, kind="kids", **over):
    body = {"kind": kind, "name": "Мама", "phone": "+380991112233",
            "params": {"age": 8, "format": "individual", "lessons": 16}}
    if kind == "corporate":
        body["params"] = {"people": 12, "format": "group", "months": 3, "goal": "Співбесіди"}
    body.update(over)
    return await client.post("/api/quote-requests", json=body)


async def only(session):
    return (await session.execute(select(QuoteRequest))).scalar_one()


async def test_quote_stores_params_contact_and_preview(client, session):
    await quote(client, telegram="@mama", comment="після 17:00")
    q = await only(session)
    assert q.params == {"age": 8, "format": "individual", "lessons": 16}
    assert (q.telegram, q.comment, q.status, q.source) == ("@mama", "після 17:00", QuoteStatus.NEW, "site/quote")
    assert q.calc_preview["total"] == 16 * 420


@pytest.mark.parametrize("contact", [{"phone": None, "email": "a@b.ua"}, {"phone": None, "telegram": "@x"}])
async def test_any_single_contact_is_enough(client, contact):
    assert (await quote(client, **contact)).status_code == 200


@pytest.mark.parametrize("over,detail", [
    ({"name": " "}, "name"),
    ({"phone": None}, "потрібен"),
    ({"kind": "other"}, "kind"),
    ({"kind": None}, "kind"),
    ({"comment": "https://spam"}, "spam"),
])
async def test_quote_common_validation(client, over, detail):
    r = await quote(client, **over)
    assert r.status_code == 400 and detail in r.json()["detail"]


@pytest.mark.parametrize("params", [
    {"age": 2, "format": "individual", "lessons": 8},
    {"age": 18, "format": "individual", "lessons": 8},
    {"age": "x", "format": "individual", "lessons": 8},
    {"age": 8, "format": "individual", "lessons": 0},
    {"age": 8, "format": "individual", "lessons": 201},
    {"age": 8, "format": "club", "lessons": 8},
    {"age": 8, "lessons": 8},
    {},
])
async def test_kids_param_validation(client, params):
    assert (await quote(client, params=params)).status_code == 400


@pytest.mark.parametrize("params", [
    {"people": 0, "format": "group", "months": 3, "goal": "x"},
    {"people": 1001, "format": "group", "months": 3, "goal": "x"},
    {"people": 5, "format": "group", "months": 0, "goal": "x"},
    {"people": 5, "format": "group", "months": 37, "goal": "x"},
    {"people": 5, "format": "pair", "months": 3, "goal": "x"},
    {"people": 5, "format": "group", "months": 3, "goal": "  "},
    {"people": 5, "format": "group", "months": 3},
])
async def test_corporate_param_validation(client, params):
    assert (await quote(client, "corporate", params=params)).status_code == 400


async def test_corporate_stores_company_and_preview(client, session):
    await quote(client, "corporate", company="ТОВ Тест")
    q = await only(session)
    assert q.company == "ТОВ Тест" and q.calc_preview["groups"] == 2


async def test_kids_quote_does_not_store_company(client, session):
    await quote(client, company="ТОВ")
    assert (await only(session)).company is None


async def test_kids_age_outside_range_is_flagged_for_manager(client, session):
    await quote(client, params={"age": 15, "format": "group", "lessons": 16})
    assert (await only(session)).calc_preview["age_in_range"] is False


@pytest.mark.parametrize("kind", ["kids", "corporate"])
async def test_response_never_contains_prices(client, kind):
    r = await quote(client, kind)
    assert r.json() == {"ok": True}


async def test_long_text_fields_are_clipped(client, session):
    await quote(client, name="я" * 500, comment="к" * 5000)
    q = await only(session)
    assert len(q.name) == 160 and len(q.comment) == 2000


async def test_admin_quote_queue(admin_client, client, session):
    await quote(client, "kids")
    await quote(client, "corporate")
    items = (await admin_client.get("/api/admin/quote-requests")).json()
    assert {i["kind"] for i in items} == {"kids", "corporate"}
    assert all(i["calc_preview"] for i in items)         # менеджер бачить розрахунок
    assert len((await admin_client.get("/api/admin/quote-requests", params={"kind": "kids"})).json()) == 1
    assert (await admin_client.get("/api/admin/quote-requests", params={"status": "replied"})).json() == []
    assert (await admin_client.get("/api/admin/quote-requests", params={"status": "bogus"})).status_code == 422


async def test_admin_quote_status_and_note(admin_client, client, session):
    await quote(client)
    qid = (await only(session)).id
    r = await admin_client.patch(f"/api/admin/quote-requests/{qid}", json={"status": "replied", "admin_note": "300 грн/урок"})
    assert r.json()["quote"]["status"] == "replied" and r.json()["quote"]["admin_note"] == "300 грн/урок"
    assert (await admin_client.patch(f"/api/admin/quote-requests/{qid}", json={"status": "x"})).status_code == 400
    assert (await admin_client.patch("/api/admin/quote-requests/9999", json={})).status_code == 404


# =============================================================== адмінка пакетів

async def test_admin_package_crud(admin_client, client):
    body = {"slug": "new", "name": "Новий", "family": "course", "audience": "teens", "format": "group",
            "track": "exam", "total_price": 5000, "lessons_count": 10}
    created = await admin_client.post("/api/admin/packages", json=body)
    pid = created.json()["id"]
    assert created.json()["slug"] == "new"
    assert (await admin_client.post("/api/admin/packages", json=body)).status_code == 409

    await admin_client.patch(f"/api/admin/packages/{pid}", json={"total_price": 6000, "format": "pair",
                                                                 "slug": "renamed", "id": 99})
    got = (await client.get("/api/packages/renamed")).json()
    assert (got["total_price"], got["format"], got["id"]) == (6000, "pair", pid)

    assert (await admin_client.delete(f"/api/admin/packages/{pid}")).json() == {"ok": True, "deactivated": "renamed"}
    assert (await client.get("/api/packages/renamed")).status_code == 404            # зник з сайту
    admin_view = (await admin_client.get("/api/admin/packages", params={"active": 0})).json()
    assert [p["slug"] for p in admin_view] == ["renamed"]                           # але лишився в базі


@pytest.mark.parametrize("missing", ["slug", "name", "family", "audience", "format", "track"])
async def test_admin_package_requires_fields(admin_client, missing):
    body = {"slug": "n", "name": "N", "family": "course", "audience": "teens", "format": "group", "track": "exam"}
    body.pop(missing)
    r = await admin_client.post("/api/admin/packages", json=body)
    assert r.status_code == 400 and missing in r.json()["detail"]


@pytest.mark.parametrize("field,value", [("family", "x"), ("audience", "x"), ("format", "x"), ("track", "x")])
async def test_admin_package_rejects_bad_enums(admin_client, make_package, field, value):
    pkg = await make_package(slug="p")
    assert (await admin_client.patch(f"/api/admin/packages/{pkg.id}", json={field: value})).status_code == 400
    body = {"slug": "n", "name": "N", "family": "course", "audience": "teens", "format": "group",
            "track": "exam", field: value}
    assert (await admin_client.post("/api/admin/packages", json=body)).status_code == 400


async def test_admin_package_missing(admin_client):
    assert (await admin_client.patch("/api/admin/packages/9999", json={})).status_code == 404
    assert (await admin_client.delete("/api/admin/packages/9999")).status_code == 404


async def test_admin_package_list_filter(admin_client, make_package):
    await make_package(slug="on")
    await make_package(slug="off", is_active=False)
    slugs = lambda r: sorted(p["slug"] for p in r.json())     # noqa: E731
    assert slugs(await admin_client.get("/api/admin/packages")) == ["off", "on"]
    assert slugs(await admin_client.get("/api/admin/packages", params={"active": 1})) == ["on"]
    assert slugs(await admin_client.get("/api/admin/packages", params={"active": 0})) == ["off"]


async def test_deactivating_a_package_keeps_old_orders_intact(admin_client, make_package, make_order, session):
    pkg = await make_package(slug="sold")
    order = await make_order(package_id=pkg.id, package_slug="sold", package_name="Test package", amount=111)
    await admin_client.delete(f"/api/admin/packages/{pkg.id}")
    row = (await session.execute(select(Order))).scalar_one()
    assert (row.amount, row.package_name, row.package_id) == (111, "Test package", pkg.id)


# =============================================================== лічильник відвідувань

async def hit(client, ua="Mozilla/5.0 (Windows NT 10.0)", **body):
    payload = {"path": "/packages"}
    payload.update(body)
    return await client.post("/api/track", json=payload, headers={"user-agent": ua})


async def visits(session):
    return (await session.execute(select(PageVisit))).scalars().all()


async def test_visit_is_recorded_without_query_string(client, session):
    await hit(client, path="/verify-certificate?code=PA-2026-SECRET")
    (v,) = await visits(session)
    assert v.path == "/verify-certificate" and "SECRET" not in v.path


async def test_visit_never_stores_ip(client, session):
    await client.post("/api/track", json={"path": "/"}, headers={"x-forwarded-for": "198.51.100.77"})
    (v,) = await visits(session)
    assert "198.51.100.77" not in str(v.__dict__) and len(v.visitor_hash) == 64


@pytest.mark.parametrize("ua", ["Googlebot/2.1", "curl/8.0", "python-requests/2.31", "facebookexternalhit/1.1",
                                "Mozilla/5.0 (compatible; AhrefsBot)", "UptimeRobot monitor"])
async def test_bots_are_skipped(client, session, ua):
    r = await hit(client, ua=ua)
    assert r.json() == {"ok": True, "skipped": "bot"} and await visits(session) == []


@pytest.mark.parametrize("ua,device", [
    ("Mozilla/5.0 (iPhone; CPU iPhone OS 17)", "mobile"),
    ("Mozilla/5.0 (Linux; Android 14; Pixel)", "mobile"),
    ("Mozilla/5.0 (iPad; CPU OS 17)", "tablet"),
    ("Mozilla/5.0 (Windows NT 10.0; Win64)", "desktop"),
    ("", "desktop"),
])
async def test_device_detection(client, session, ua, device):
    await hit(client, ua=ua)
    assert (await visits(session))[0].device == device


@pytest.mark.parametrize("referrer,host", [
    ("https://www.google.com/search?q=secret+query", "google.com"),
    ("https://l.instagram.com/?u=x", "l.instagram.com"),
    ("https://my-prime-academy.com/packages", None),
    ("https://www.my-prime-academy.com/", None),
    ("http://localhost:5173/", None),
    ("", None), (None, None), ("not a url", None),
])
async def test_referrer_keeps_only_the_domain(client, session, referrer, host):
    await hit(client, referrer=referrer)
    assert (await visits(session))[0].referrer_host == host


async def test_utm_is_stored(client, session):
    await hit(client, utm_source="instagram", utm_medium="reels", utm_campaign="nov")
    v = (await visits(session))[0]
    assert (v.utm_source, v.utm_medium, v.utm_campaign) == ("instagram", "reels", "nov")


async def test_missing_path_defaults_to_root_and_is_clipped(client, session):
    await client.post("/api/track", json={}, headers={"user-agent": "Mozilla/5.0"})
    await hit(client, path="/" + "a" * 500)
    paths = sorted(v.path for v in await visits(session))
    assert paths[0] == "/" and len(paths[1]) == 300


async def test_same_visitor_gets_same_hash_other_ip_gets_other(client, session):
    for ip in ("203.0.113.1", "203.0.113.1", "203.0.113.2"):
        await client.post("/api/track", json={"path": "/"},
                          headers={"user-agent": "Mozilla/5.0", "x-forwarded-for": ip})
    hashes = [v.visitor_hash for v in await visits(session)]
    assert hashes[0] == hashes[1] != hashes[2]


def test_visitor_hash_changes_every_day(monkeypatch):
    """Завтра той самий відвідувач — інший ідентифікатор: простежити людину в часі неможливо."""
    class Day1(date):
        @classmethod
        def today(cls): return date(2026, 1, 1)

    class Day2(date):
        @classmethod
        def today(cls): return date(2026, 1, 2)

    monkeypatch.setattr(track, "date", Day1)
    first = track._visitor_hash("1.1.1.1", "ua")
    monkeypatch.setattr(track, "date", Day2)
    assert track._visitor_hash("1.1.1.1", "ua") != first


async def test_tracking_failure_never_breaks_the_page(client, session, monkeypatch):
    async def boom():
        raise RuntimeError("db down")
    monkeypatch.setattr(session, "commit", boom)
    r = await hit(client)
    assert r.status_code == 200 and r.json() == {"ok": True}


# =============================================================== реальний IP за проксі

def fake_request(headers=None, host="10.0.0.1"):
    scope = {"type": "http", "headers": [(k.lower().encode(), v.encode()) for k, v in (headers or {}).items()],
             "client": (host, 1234) if host else None}
    return Request(scope)


@pytest.mark.parametrize("headers,host,expected", [
    ({"x-forwarded-for": "203.0.113.9"}, "10.0.0.1", "203.0.113.9"),
    ({"x-forwarded-for": "6.6.6.6, 203.0.113.9"}, "10.0.0.1", "203.0.113.9"),       # лівий підробляється
    ({"x-forwarded-for": "1.1.1.1, 2.2.2.2, 3.3.3.3"}, "10.0.0.1", "3.3.3.3"),
    ({"x-forwarded-for": " 203.0.113.9 , "}, "10.0.0.1", "203.0.113.9"),
    ({"x-forwarded-for": ""}, "10.0.0.1", "10.0.0.1"),
    ({"x-forwarded-for": " , "}, "10.0.0.1", "10.0.0.1"),
    ({}, "10.0.0.1", "10.0.0.1"),
    ({}, None, None),
])
def test_client_ip_trusts_only_the_last_proxy_hop(headers, host, expected):
    assert client_ip(fake_request(headers, host)) == expected

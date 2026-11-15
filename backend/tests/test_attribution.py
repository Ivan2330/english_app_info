"""Джерело трафіку (UTM, fbclid) у заявках і замовленнях; ідемпотентність, honeypot, ліміт."""
import pytest
from sqlalchemy import select

from app.core.attribution import clean_touch, effective_touch
from app.models.lead import Lead, LeadStatus
from app.models.order import Order

FIRST = {"utm_source": "facebook", "utm_medium": "paid", "utm_campaign": "trial_dec", "utm_content": "video1",
         "utm_term": "english", "fbclid": "IwAR123", "referrer": "l.facebook.com", "landing_page": "/trial"}
LAST = {"utm_source": "instagram", "utm_campaign": "retarget", "landing_page": "/packages"}


async def post_lead(client, **over):
    body = {"name": "Марія", "phone": "+380501112233", **over}
    return await client.post("/api/leads", json=body)


# ------------------------------------------------------------------ очищення

def test_clean_touch_trims_and_cuts_long_values():
    out = clean_touch({"utm_source": "  fb  ", "utm_campaign": "x" * 500, "landing_page": "/" + "a" * 900,
                       "evil": "drop table", "utm_term": "", "fbclid": 12345})
    assert out == {"utm_source": "fb", "utm_campaign": "x" * 200, "landing_page": ("/" + "a" * 900)[:300],
                   "fbclid": "12345"}


@pytest.mark.parametrize("raw", [None, "string", 5, [], {}, {"utm_source": None}, {"utm_source": ["a"]},
                                 {"utm_source": True}, {"unknown": "x"}])
def test_clean_touch_ignores_garbage(raw):
    assert clean_touch(raw) is None


def test_clean_touch_strips_control_characters():
    assert clean_touch({"utm_source": "fa\x00ce\nbook\x1f"}) == {"utm_source": "facebook"}


def test_effective_touch_prefers_last_with_campaign_else_first():
    assert effective_touch(FIRST, LAST) == LAST
    assert effective_touch(FIRST, {"referrer": "google.com"}) == FIRST     # останній дотик без кампанії
    assert effective_touch(None, {"referrer": "google.com"}) == {"referrer": "google.com"}
    assert effective_touch(None, None) == {}


# ------------------------------------------------------------------ заявки

async def test_lead_stores_first_last_and_effective_source(client, session):
    r = await post_lead(client, attribution={"first_touch": FIRST, "last_touch": LAST}, fbp="fb.1.1.2",
                        fbc="fb.1.1.IwAR", event_source_url="https://my-prime-academy.com/trial",
                        meta_consent=True, level="B1")
    assert r.status_code == 200
    row = (await session.execute(select(Lead))).scalar_one()
    assert (row.utm_source, row.utm_campaign, row.utm_content) == ("instagram", "retarget", None)
    assert row.first_touch == FIRST and row.last_touch == LAST
    assert (row.fbp, row.fbc, row.meta_consent, row.level) == ("fb.1.1.2", "fb.1.1.IwAR", True, "B1")


async def test_lead_without_utm_still_works(client, session):
    assert (await post_lead(client)).status_code == 200
    row = (await session.execute(select(Lead))).scalar_one()
    assert row.utm_source is None and row.first_touch is None and row.meta_consent is False


@pytest.mark.parametrize("attribution", ["junk", 5, [], {"first_touch": "x", "last_touch": 7}])
async def test_lead_with_broken_attribution_is_saved(client, session, attribution):
    assert (await post_lead(client, attribution=attribution)).status_code == 200


async def test_lead_long_values_are_cut_not_rejected(client, session):
    long = {"utm_source": "s" * 1000, "utm_campaign": "c" * 1000}
    assert (await post_lead(client, attribution={"first_touch": long}, fbp="p" * 999)).status_code == 200
    row = (await session.execute(select(Lead))).scalar_one()
    assert len(row.utm_source) == 200 and len(row.utm_campaign) == 200 and len(row.fbp) == 100


async def test_meta_consent_must_be_literally_true(client, session):
    await post_lead(client, meta_consent="true")
    assert (await session.execute(select(Lead.meta_consent))).scalar_one() is False


# ------------------------------------------------------------------ ідемпотентність, honeypot, ліміт

async def test_same_event_id_returns_same_lead(client, session):
    a = (await post_lead(client, event_id="evt-1")).json()
    b = (await post_lead(client, event_id="evt-1")).json()
    assert a["id"] == b["id"] and b["duplicate"] is True
    assert len((await session.execute(select(Lead))).scalars().all()) == 1


async def test_different_event_ids_make_two_leads(client, session):
    await post_lead(client, event_id="a")
    await post_lead(client, event_id="b")
    assert len((await session.execute(select(Lead))).scalars().all()) == 2


async def test_race_on_event_id_is_resolved_to_the_existing_lead(client, session, monkeypatch):
    """Перший пошук дубля «не бачить» заявку (як при гонці), але INSERT упирається в унікальний event_id."""
    first = (await post_lead(client, event_id="race")).json()
    from app.api.public import leads as api
    real_select = api.select
    state = {"calls": 0}

    def blind_first_lookup(*cols):
        stmt = real_select(*cols)
        state["calls"] += 1
        if state["calls"] == 1:
            return stmt.where(Lead.event_id == "never-matches")
        return stmt

    monkeypatch.setattr(api, "select", blind_first_lookup)
    r = (await post_lead(client, event_id="race")).json()
    assert r["id"] == first["id"] and r["duplicate"] is True


async def test_honeypot_looks_like_success_but_saves_nothing(client, session):
    r = await post_lead(client, website="http://bot.example")
    assert r.status_code == 200 and r.json() == {"ok": True, "id": 0}
    assert (await session.execute(select(Lead))).scalars().all() == []


async def test_rate_limit_per_ip(client, session):
    for i in range(5):
        assert (await post_lead(client, event_id=f"e{i}")).status_code == 200
    r = await post_lead(client, event_id="e5")
    assert r.status_code == 429 and "пізніше" in r.json()["detail"]
    other = await client.post("/api/leads", json={"name": "Інший"}, headers={"x-forwarded-for": "198.51.100.7"})
    assert other.status_code == 200


async def test_unknown_kind_falls_back_to_trial(client, session):
    await post_lead(client, kind="bogus")
    assert (await session.execute(select(Lead.kind))).scalar_one().value == "trial"


# ------------------------------------------------------------------ замовлення

async def test_order_stores_attribution(client, make_package, session):
    pkg = await make_package()
    r = await client.post("/api/orders", json={
        "package_slug": pkg.slug, "customer_name": "Олена", "customer_phone": "+380501112233",
        "attribution": {"first_touch": FIRST, "last_touch": None}, "fbp": "fb.1.1.2", "meta_consent": True})
    assert r.status_code == 200
    order = (await session.execute(select(Order))).scalar_one()
    assert (order.utm_source, order.utm_campaign, order.utm_content) == ("facebook", "trial_dec", "video1")
    assert order.fbp == "fb.1.1.2" and order.meta_consent is True
    body = r.json()["order"]
    assert "utm_source" not in body and "fbp" not in body                  # клієнту атрибуція не віддається


async def test_order_without_attribution(client, make_package, session):
    pkg = await make_package()
    r = await client.post("/api/orders", json={"package_slug": pkg.slug, "customer_name": "О", "customer_phone": "1"})
    assert r.status_code == 200
    assert (await session.execute(select(Order.utm_source))).scalar_one() is None


# ------------------------------------------------------------------ адмінка

async def make_lead(session, **kw):
    row = Lead(name=kw.pop("name", "X"), status=kw.pop("status", LeadStatus.NEW), **kw)
    session.add(row)
    await session.commit()
    return row


async def test_admin_leads_show_and_filter_by_source(admin_client, session):
    await make_lead(session, name="З реклами", utm_source="facebook", utm_campaign="dec", utm_content="v1")
    await make_lead(session, name="З інсти", utm_source="instagram", utm_campaign="dec")
    await make_lead(session, name="Пряма")
    names = lambda r: sorted(x["name"] for x in r.json())
    assert names(await admin_client.get("/api/admin/leads")) == ["З реклами", "З інсти", "Пряма"]
    assert names(await admin_client.get("/api/admin/leads", params={"utm_source": "facebook"})) == ["З реклами"]
    assert names(await admin_client.get("/api/admin/leads", params={"utm_source": "__none__"})) == ["Пряма"]
    assert names(await admin_client.get("/api/admin/leads", params={"utm_campaign": "dec"})) == ["З реклами", "З інсти"]
    row = (await admin_client.get("/api/admin/leads", params={"utm_source": "facebook"})).json()[0]
    assert row["attribution"]["utm_content"] == "v1"
    sources = (await admin_client.get("/api/admin/leads/sources")).json()
    assert {s["value"] for s in sources} == {"facebook", "instagram", "__none__"}
    assert next(s for s in sources if s["value"] == "__none__")["label"].startswith("без UTM")


@pytest.mark.parametrize("status", ["contacted", "trial_scheduled", "trial_done", "converted", "lost", "new"])
async def test_admin_can_set_every_lead_status(admin_client, session, status):
    row = await make_lead(session)
    assert (await admin_client.patch(f"/api/admin/leads/{row.id}", json={"status": status})).status_code == 200
    await session.refresh(row)
    assert row.status.value == status


async def test_admin_rejects_unknown_lead_status(admin_client, session):
    row = await make_lead(session)
    assert (await admin_client.patch(f"/api/admin/leads/{row.id}", json={"status": "bogus"})).status_code == 400


async def test_admin_orders_show_and_filter_by_source(admin_client, make_order, session):
    a = await make_order(utm_source="facebook", utm_campaign="dec")
    await make_order()
    items = (await admin_client.get("/api/admin/orders", params={"utm_source": "facebook"})).json()["items"]
    assert [o["public_id"] for o in items] == [a.public_id] and items[0]["attribution"]["utm_campaign"] == "dec"
    none = (await admin_client.get("/api/admin/orders", params={"utm_source": "__none__"})).json()["items"]
    assert len(none) == 1 and none[0]["attribution"]["utm_source"] is None
    assert len((await admin_client.get("/api/admin/orders", params={"utm_campaign": "dec"})).json()["items"]) == 1
    sources = (await admin_client.get("/api/admin/orders/sources")).json()
    assert {s["value"] for s in sources} == {"facebook", "__none__"}


async def test_new_leads_counter_in_menu(admin_client, session):
    assert (await admin_client.get("/api/admin/counters")).json()["leads"] == 0
    await make_lead(session, name="Нова 1")
    await make_lead(session, name="Нова 2")
    await make_lead(session, name="Стара", status=LeadStatus.CONTACTED)
    assert (await admin_client.get("/api/admin/counters")).json()["leads"] == 2

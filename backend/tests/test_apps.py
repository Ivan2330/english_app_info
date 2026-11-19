from urllib.parse import parse_qs, urlsplit


ROOT = "/api/admin/apps"


async def test_templates_and_phrase_bank_have_section_permissions(admin_client, client_for, make_admin):
    user = await make_admin(sections=["apps"])
    denied = await make_admin(sections=["creatives"])
    async with client_for(user) as client, client_for(denied) as other:
        assert (await other.get(f"{ROOT}/entries", params={"kind": "phrase"})).status_code == 403
        assert (await other.put(f"{ROOT}/economy", json={})).status_code == 403
        tags = {"kind": "hashtags", "topic": "Розмова", "text": "#англійська"}
        saved = await client.post(f"{ROOT}/entries", json=tags)
        assert saved.status_code == 201
        result = await admin_client.get(f"{ROOT}/entries", params={"kind": "hashtags", "q": "Розмова"})
        assert [row["topic"] for row in result.json()["items"]] == ["Розмова"]
        caption = {"kind": "caption", "title": "Заклик", "text": "Готові почати?"}
        assert (await client.post(f"{ROOT}/entries", json=caption)).json()["cta"] == "Напиши ПРОБНИЙ у Direct"
        phrase = {"kind": "phrase", "text": "I agree.", "mistake": "I am agree.", "source": "Редакція",
                  "tags": [" граматика ", "граматика", ""]}
        created = (await admin_client.post(f"{ROOT}/entries", json=phrase)).json()
        assert created["tags"] == ["граматика"]
        assert (await client.get(f"{ROOT}/entries", params={"kind": "phrase"})).json()["items"][0]["can_delete"] is False
        assert (await client.delete(f"{ROOT}/entries/{created['id']}")).status_code == 403
        assert (await admin_client.delete(f"{ROOT}/entries/{created['id']}")).status_code == 200


async def test_utm_history_preserves_link_and_is_private(admin_client, client_for, make_admin):
    member = await make_admin(sections=["apps"])
    payload = {"kind": "utm", "url": "https://example.com/trial?ref=x&utm_source=older&utm_content=stale#info",
               "utm_source": "instagram", "utm_medium": "paid_social", "utm_campaign": "курс 2026"}
    saved = await admin_client.post(f"{ROOT}/entries", json=payload)
    assert saved.status_code == 201
    link = urlsplit(saved.json()["result"])
    assert link.fragment == "info"
    assert parse_qs(link.query) == {"ref": ["x"], "utm_source": ["instagram"], "utm_medium": ["paid_social"],
                                    "utm_campaign": ["курс 2026"]}
    assert (await admin_client.get(f"{ROOT}/entries", params={"kind": "utm"})).json()["items"][0]["id"] == saved.json()["id"]
    async with client_for(member) as client:
        assert (await client.get(f"{ROOT}/entries", params={"kind": "utm"})).json()["items"] == []
        assert (await client.delete(f"{ROOT}/entries/{saved.json()['id']}")).status_code == 404
    assert (await admin_client.post(f"{ROOT}/entries", json={**payload, "url": "javascript:bad"})).status_code == 422


async def test_economy_group_rates_only_card_fee_and_personal_settings(admin_client, client_for, make_admin):
    init = (await admin_client.get(f"{ROOT}/economy")).json()
    assert init["inputs"]["individual_rate"] == 100 and init["inputs"]["group_rate"] == 400
    result = (await admin_client.put(f"{ROOT}/economy", json={"format": "group", "group_size": 5, "lessons": 10,
        "price": 2000, "card_share": 60, "cpl": 60, "show": 50, "trial_paid": 40, "renewal": 50})).json()
    assert result["results"] == {"cac": 300, "teacher": 800, "fee": 30, "tax": 100, "margin": 1070,
                                 "margin_percent": 53.5, "ltv": 4000, "ltv_contribution": 2140, "payback_months": 0.28}
    assert (await admin_client.get(f"{ROOT}/economy")).json() == result
    member = await make_admin(sections=["apps"])
    async with client_for(member) as client:
        assert (await client.get(f"{ROOT}/economy")).json() == init
        edge = (await client.put(f"{ROOT}/economy", json={"price": 0, "show": 0})).json()["results"]
        assert edge["margin_percent"] is None and edge["cac"] is None and edge["payback_months"] is None

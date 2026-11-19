from io import BytesIO

from PIL import Image


IDEAS = "/api/admin/ideas"


async def test_idea_filters_and_ratings(admin_client, client_for, make_admin):
    member = await make_admin(sections=["ideas"])
    async with client_for(member) as client:
        response = await client.post(IDEAS, json={"title": "  Quiz Friday  ", "description": "Try it",
                                                 "topic": "Граматика", "format": "reels"})
        assert response.status_code == 201, response.text
        idea = response.json()
        review = {"entity_type": "idea", "entity_id": idea["id"], "score": 5, "body": "Підходить"}
        assert (await client.put("/api/admin/reviews", json=review)).status_code == 200
        assert (await client.put("/api/admin/reviews", json={**review, "score": 6})).status_code == 422
        assert (await client.put("/api/admin/reviews", json={**review, "score": None})).status_code == 422
    assert (await admin_client.put("/api/admin/reviews", json={**review, "score": 3})).json()["average"] == 4
    assert (await admin_client.post(IDEAS, json={"title": "Other"})).status_code == 201
    saved = await admin_client.put(f"{IDEAS}/{idea['id']}", json={"title": idea["title"], "format": "reels",
                                                                  "topic": "Граматика", "status": "suitable"})
    assert saved.json()["author_id"] == member.id
    result = await admin_client.get(IDEAS, params={"q": "quiz", "format": "reels", "topic": "Граматика",
                                                  "status": "suitable", "author_id": member.id,
                                                  "min_rating": 4, "sort": "rating"})
    assert [(i["title"], i["average"]) for i in result.json()["items"]] == [("Quiz Friday", 4)]
    assert (await admin_client.put(f"{IDEAS}/9999", json={"title": "Missing"})).status_code == 404
    assert (await admin_client.post(IDEAS, json={"title": "Bad", "reference_url": "javascript:bad"})).status_code == 422


async def test_idea_file_and_permissions(admin_client, client_for, make_admin):
    idea = (await admin_client.post(IDEAS, json={"title": "Reference"})).json()
    key = {"entity_type": "idea", "entity_id": idea["id"]}
    exact = BytesIO()
    Image.new("RGB", (800, 400)).save(exact, format="PNG")
    uploaded = await admin_client.post("/api/admin/files", params=key, files={"file": ("ref.png", exact.getvalue())})
    assert uploaded.status_code == 201, uploaded.text
    url = uploaded.json()["url"]
    thumb = await admin_client.get(url, params={"thumbnail": True})
    assert Image.open(BytesIO(thumb.content)).size == (640, 320)
    assert (await admin_client.get(IDEAS)).json()["items"][0]["cover_id"] == uploaded.json()["id"]
    assert (await admin_client.post("/api/admin/files", params=key, files={"file": ("ref.txt", b"text")})).status_code == 415
    assert (await admin_client.post("/api/admin/files", params=key, files={"file": ("ref.png", b"\x89PNG\r\n\x1a\n")})).status_code == 415

    denied = await make_admin(sections=["reports"])
    async with client_for(denied) as client:
        assert (await client.get(IDEAS)).status_code == 403
        assert (await client.get("/api/admin/reviews", params=key)).status_code == 403
        assert (await client.get(url, params={"thumbnail": True})).status_code == 403
    assert (await admin_client.delete(url)).status_code == 200
    assert (await admin_client.get(url, params={"thumbnail": True})).status_code == 404

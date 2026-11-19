from io import BytesIO
from zipfile import ZipFile

from PIL import Image


ROOT = "/api/admin/creatives"


def picture(format="PNG"):
    image = BytesIO()
    Image.new("RGB", (720, 900), (40, 150, 242)).save(image, format=format)
    return image.getvalue()


async def test_creative_permissions(admin_client, client_for, make_admin):
    author = await make_admin(sections=["ideas", "creatives"], name="Данило")
    denied = await make_admin(sections=["ideas"])
    body = {"title": "Три фрази", "topic": "Мова", "format": "carousel", "caption": "Learn more"}
    async with client_for(author) as client, client_for(denied) as other:
        assert (await other.get(ROOT)).status_code == 403
        assert (await client.post(ROOT, json={**body, "status": "approved"})).status_code == 403
        result = await client.post(ROOT, json=body)
        assert result.status_code == 201, result.text
        id = result.json()["id"]
        assert (await client.put(f"{ROOT}/{id}", json={**body, "status": "approved"})).status_code == 403
        assert (await client.put(f"{ROOT}/settings/upload", json={"max_mb": 1})).status_code == 403
        assert (await client.post(f"{ROOT}/bulk", json={"ids": [id], "status": "approved"})).status_code == 403
        assert (await admin_client.put(f"{ROOT}/{id}", json={**body, "status": "approved"})).status_code == 200
        assert (await client.put(f"{ROOT}/{id}", json={**body, "status": "published"})).status_code == 200
        assert (await other.get(f"{ROOT}/{id}/reviews")).status_code == 403


async def test_creative_from_idea_filters_dates_bulk_and_ranking(admin_client, client_for, make_admin):
    idea = (await admin_client.post("/api/admin/ideas", json={"title": "Reels 1", "description": "A new angle",
                                                            "format": "reels", "topic": "Курс"})).json()
    creative_only = await make_admin(sections=["creatives"])
    async with client_for(creative_only) as editor:
        assert (await editor.post(f"{ROOT}/from-idea/{idea['id']}")).status_code == 403
    first = (await admin_client.post(f"{ROOT}/from-idea/{idea['id']}")).json()
    again = (await admin_client.post(f"{ROOT}/from-idea/{idea['id']}")).json()
    assert first["id"] == again["id"] and first["description"] == "A new angle"
    assert first["format"] == "reels" and first["idea_id"] == idea["id"]
    assert (await admin_client.post(f"{ROOT}/from-idea/9999")).status_code == 404
    id = first["id"]
    schedule = "2026-11-20T12:00:00+02:00"
    assert (await admin_client.patch(f"{ROOT}/{id}/schedule", json={"scheduled_at": schedule})).status_code == 200
    assert (await admin_client.post(f"{ROOT}/bulk", json={"ids": [id], "tag": "осінь", "status": "draft"})).json()["updated"] == 1
    assert (await admin_client.post(f"{ROOT}/bulk", json={"ids": [9999], "tag": "осінь"})).status_code == 404
    assert (await admin_client.post(f"{ROOT}/bulk", json={"ids": [id]})).status_code == 422
    review = {"idea": 5, "design": 4, "copy": 3, "brand": 4, "advertising": 4, "comment": "Вдала ідея"}
    result = await admin_client.put(f"{ROOT}/{id}/reviews", json=review)
    assert result.json()["average"] == 4 and result.json()["items"][0]["mine"]
    assert (await admin_client.put(f"{ROOT}/{id}/reviews", json={**review, "idea": 6})).status_code == 422
    async with client_for(creative_only) as editor:
        assert (await editor.put(f"{ROOT}/{id}/reviews", json={**review, "copy": 5})).json()["average"] == 4.2
    rank = (await admin_client.get(f"{ROOT}/rankings")).json()
    assert rank["format"]["reels"][0]["id"] == id and rank["topic"]["Курс"][0]["average"] == 4.2
    result = await admin_client.get(ROOT, params={"q": "reels", "format": "reels", "purpose": "organic", "topic": "Курс",
                                                 "status": "draft", "tag": "осінь", "min_rating": 4, "author_id": first["author_id"],
                                                 "date_from": "2026-11-20", "date_to": "2026-11-20",
                                                 "scheduled_from": "2026-11-20T00:00:00Z", "scheduled_to": "2026-11-21T00:00:00Z"})
    assert [item["id"] for item in result.json()["items"]] == [id]
    assert not (await admin_client.get(ROOT, params={"tag": "осін"})).json()["items"]
    assert (await admin_client.get(f"{ROOT}/9999")).status_code == 404


async def test_media_history_order_archive_and_duplication(admin_client, client_for, make_admin):
    first = (await admin_client.post(ROOT, json={"title": "Carousel"})).json()
    id = first["id"]
    assert (await admin_client.get(f"{ROOT}/settings/upload")).json()["max_mb"] == 100
    assert (await admin_client.put(f"{ROOT}/settings/upload", json={"max_mb": 1})).status_code == 200
    assert (await admin_client.get(f"{ROOT}/{id}/archive")).status_code == 404
    assert (await admin_client.post(f"{ROOT}/{id}/media", files={"file": ("doc.txt", b"x")})).status_code == 415
    assert (await admin_client.post(f"{ROOT}/{id}/media", files={"file": ("large.png", b"x" * 1_048_577)})).status_code == 413
    for name in ("cover.png", "next.png"):
        result = await admin_client.post(f"{ROOT}/{id}/media", files={"file": (name, picture())})
        assert result.status_code == 201, result.text
        assert result.json()["width"] == 720
    slots = (await admin_client.get(f"{ROOT}/{id}")).json()["media"]
    first_slot = slots[0]["id"]
    second_slot = slots[1]["id"]
    original = slots[0]["current"]
    result = await admin_client.post(f"{ROOT}/{id}/media/{first_slot}", files={"file": ("cover-new.png", picture())})
    assert result.json()["version"] == 2
    thumb = await admin_client.get(result.json()["thumbnail"])
    assert Image.open(BytesIO(thumb.content)).size == (512, 640)
    assert (await admin_client.get(original["url"])).status_code == 200
    assert (await admin_client.post(f"{ROOT}/{id}/media/{second_slot + 99}", files={"file": ("x.png", picture())})).status_code == 404
    assert (await admin_client.put(f"{ROOT}/{id}/media-order", json={"ids": [first_slot, first_slot]})).status_code == 422
    assert (await admin_client.put(f"{ROOT}/{id}/media-order", json={"ids": [second_slot, first_slot]})).status_code == 200
    after = (await admin_client.get(f"{ROOT}/{id}")).json()["media"]
    assert [file["id"] for file in after] == [second_slot, first_slot]
    assert [file["version"] for file in after[1]["versions"]] == [2, 1]
    zip_result = await admin_client.get(f"{ROOT}/{id}/archive")
    with ZipFile(BytesIO(zip_result.content)) as archive:
        assert archive.namelist() == ["01-next.png", "02-cover-new.png"]
    duplicate = (await admin_client.post(f"{ROOT}/{id}/duplicate")).json()
    files = (await admin_client.get(f"{ROOT}/{duplicate['id']}")).json()["media"]
    assert duplicate["status"] == "draft" and len(files) == 2
    assert files[0]["current"]["id"] != after[0]["current"]["id"]
    assert files[1]["current"]["version"] == 1
    assert (await admin_client.get(original["url"].replace(f"/{id}/", f"/{duplicate['id']}/"))).status_code == 404
    denied = await make_admin(sections=["ideas"])
    async with client_for(denied) as other:
        assert (await other.get(original["url"])).status_code == 403
        assert (await other.get(f"{ROOT}/{id}/archive")).status_code == 403


async def test_video_uses_upload_metadata_and_poster(admin_client, monkeypatch):
    monkeypatch.setattr("app.api.admin.creative_media.shutil.which", lambda _: None)
    id = (await admin_client.post(ROOT, json={"title": "Video"})).json()["id"]
    video = await admin_client.post(f"{ROOT}/{id}/media", data={"width": 1080, "height": 1920},
        files={"file": ("sample.mp4", b"\x00\x00\x00\x18ftypisom" + b"\x00" * 16),
               "poster": ("poster.jpg", picture("JPEG"))})
    assert video.status_code == 201, video.text
    payload = video.json()
    assert payload["kind"] == "video" and payload["width"] == 1080 and payload["height"] == 1920
    assert (await admin_client.get(payload["thumbnail"])).status_code == 200

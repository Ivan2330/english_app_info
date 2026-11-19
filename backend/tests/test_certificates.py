"""Сертифікати: номер і контрольний символ, публічна перевірка, адмінка, PDF."""
import random
import re

import pytest
from sqlalchemy import select

from app.core import certificate_pdf
from app.core import certificates as C
from app.models.certificate import Certificate, CertificateKind


# =============================================================== номер

def test_generated_serial_format_and_checksum():
    for _ in range(200):
        s = C.generate_serial(2026)
        assert re.fullmatch(r"PA-2026-[2-9A-HJKMNP-Z]{6}", s)
        assert C.is_well_formed(s)


def test_alphabet_has_no_confusing_characters():
    assert not set("01OIL") & set(C.ALPHABET)
    assert len(C.ALPHABET) == C.BASE == 31


def test_default_year_is_current():
    from datetime import datetime
    assert C.generate_serial().startswith(f"PA-{datetime.utcnow().year}-")


@pytest.mark.parametrize("raw", ["pa 2026 7k3f9x", "PA20267K3F9X", "pa-2026-7k3f9x", " Pa_2026_7K3F9X "])
def test_normalize_variants_give_one_canonical_form(raw):
    assert C.normalize(raw) == "PA-2026-7K3F9X"


@pytest.mark.parametrize("raw,expected", [("", ""), (None, ""), ("abc", "ABC"), ("хз-123", "123")])
def test_normalize_edge_cases(raw, expected):
    assert C.normalize(raw) == expected


def test_single_character_typos_are_always_caught():
    """Контрольний символ ловить усі одиничні одруківки (заявлено у модулі)."""
    rng = random.Random(7)
    for _ in range(300):
        good = C.generate_serial(2026)
        pos = rng.randrange(len("PA-2026-"), len(good))
        wrong = rng.choice([c for c in C.ALPHABET if c != good[pos]])
        assert not C.is_well_formed(good[:pos] + wrong + good[pos + 1:])


@pytest.mark.parametrize("code", ["", "PA-2026", "XX-2026-ABCDEF", "PA-26-ABCDEF", "PA-2026-ABCDE", "random text"])
def test_malformed_codes(code):
    assert not C.is_well_formed(code)


def test_verify_url():
    assert C.verify_url("PA-2026-ABCDEF", "https://x.ua/") == "https://x.ua/verify-certificate?code=PA-2026-ABCDEF"


# =============================================================== публічна перевірка

@pytest.fixture
async def cert(session):
    c = Certificate(serial_number=C.generate_serial(2026), kind=CertificateKind.LEVEL,
                    student_full_name="Тест Тестенко", course_title="General English",
                    level_from="A2", level_to="B1", lessons_count=48, teacher_name="Викладач",
                    meta="ВНУТРІШНЄ", package_slug="secret-slug")
    session.add(c)
    await session.commit()
    return c


async def verify(client, code):
    return await client.get("/api/certificates/verify", params={"code": code})


async def test_verify_valid(client, cert):
    body = (await verify(client, cert.serial_number)).json()
    assert body["status"] == "valid" and body["student_full_name"] == "Тест Тестенко"
    assert (body["level_from"], body["level_to"]) == ("A2", "B1")


async def test_verify_never_leaks_internal_fields(client, cert):
    body = (await verify(client, cert.serial_number)).json()
    assert "meta" not in body and "package_slug" not in body and "id" not in body
    assert "ВНУТРІШНЄ" not in str(body) and "secret-slug" not in str(body)


@pytest.mark.parametrize("fmt", [lambda s: s.lower(), lambda s: s.replace("-", ""), lambda s: s.replace("-", " "),
                                 lambda s: f"  {s}  "])
async def test_verify_is_forgiving_about_how_the_number_was_typed(client, cert, fmt):
    assert (await verify(client, fmt(cert.serial_number))).json()["status"] == "valid"


async def test_verify_old_public_code_still_works(client, session):
    """Старі сертифікати з руками вигаданими кодами перевіряються й надалі."""
    session.add(Certificate(serial_number="LEGACY-SERIAL-1", public_code="OLD-CODE-77",
                            kind=CertificateKind.COURSE, student_full_name="Стара",
                            course_title="Old course"))
    await session.commit()
    assert (await verify(client, "old-code-77")).json()["status"] == "valid"
    assert (await verify(client, "LEGACY-SERIAL-1")).json()["status"] == "valid"


async def test_verify_revoked_hides_personal_data(client, cert, session):
    from datetime import datetime
    cert.is_revoked, cert.revoked_at, cert.revoked_reason = True, datetime.utcnow(), "приватна причина"
    await session.commit()
    body = (await verify(client, cert.serial_number)).json()
    assert body["status"] == "revoked" and body["serial_number"] == cert.serial_number
    assert "student_full_name" not in body and "приватна причина" not in str(body)


async def test_verify_unknown_distinguishes_typo_from_nonexistent(client):
    good_format = C.generate_serial(2026)
    assert (await verify(client, good_format)).json() == {"status": "invalid", "looks_valid": True}
    typo = good_format[:-1] + ("2" if good_format[-1] != "2" else "3")
    assert (await verify(client, typo)).json() == {"status": "invalid", "looks_valid": False}


@pytest.mark.parametrize("code", ["", "ab", "x" * 81])
async def test_verify_param_limits(client, code):
    assert (await verify(client, code)).status_code == 422


async def test_check_format_endpoint(client):
    s = C.generate_serial(2026)
    r = await client.get("/api/certificates/check-format", params={"code": s.lower()})
    assert r.json() == {"normalized": s, "looks_valid": True}
    assert (await client.get("/api/certificates/check-format", params={"code": "zzz"})).json()["looks_valid"] is False


# =============================================================== адмінка

BASE = "/api/admin/certificates"


async def issue(client, **over):
    body = {"student_full_name": "Іван Іванов", "course_title": "IELTS", "kind": "course"}
    body.update(over)
    return await client.post(BASE, json=body)


async def test_issue_generates_valid_serial(admin_client):
    r = await issue(admin_client, level_from="B1", level_to="B2", started_at="2026-01-01T00:00:00Z")
    c = r.json()["certificate"]
    assert C.is_well_formed(c["serial_number"])
    assert c["verify_url"].endswith(f"/verify-certificate?code={c['serial_number']}")
    assert c["issued_by"] == "Prime Academy" and c["started_at"].startswith("2026-01-01")


async def test_serial_cannot_be_supplied_by_hand(admin_client):
    r = await issue(admin_client, serial_number="PA-2026-FAKE12", public_code="MINE")
    assert r.json()["certificate"]["serial_number"] != "PA-2026-FAKE12"


@pytest.mark.parametrize("missing", ["student_full_name", "course_title"])
async def test_issue_requires_name_and_course(admin_client, missing):
    assert (await issue(admin_client, **{missing: "  "})).status_code == 400


async def test_issue_ignores_bad_dates(admin_client):
    c = (await issue(admin_client, started_at="not-a-date")).json()["certificate"]
    assert c["started_at"] is None


async def test_patch_certificate(admin_client):
    c = (await issue(admin_client)).json()["certificate"]
    r = await admin_client.patch(f"{BASE}/{c['id']}", json={
        "student_full_name": "Нове Імʼя", "level_to": "C1", "finished_at": "2026-05-01T00:00:00Z",
        "kind": "level", "serial_number": "PA-HACKED"})
    body = r.json()["certificate"]
    assert body["student_full_name"] == "Нове Імʼя" and body["kind"] == "level"
    assert body["serial_number"] == c["serial_number"]          # номер недоторканний


async def test_patch_clears_date_and_rejects_bad_ones(admin_client):
    c = (await issue(admin_client, started_at="2026-01-01T00:00:00Z")).json()["certificate"]
    cleared = await admin_client.patch(f"{BASE}/{c['id']}", json={"started_at": None})
    assert cleared.json()["certificate"]["started_at"] is None
    assert (await admin_client.patch(f"{BASE}/{c['id']}", json={"started_at": "xx"})).status_code == 400
    assert (await admin_client.patch(f"{BASE}/{c['id']}", json={"kind": "bogus"})).status_code == 400
    assert (await admin_client.patch(f"{BASE}/9999", json={})).status_code == 404


async def test_issue_and_update_validate_counts(admin_client):
    assert (await issue(admin_client, hours="2.5")).status_code == 400
    issued = await issue(admin_client, hours="56", lessons_count=0)
    assert issued.status_code == 200
    cert = issued.json()["certificate"]
    url = f"{BASE}/{cert['id']}"
    assert (cert["hours"], cert["lessons_count"]) == (56, 0)
    for invalid in (-1, True, "abc", 2_147_483_648):
        response = await admin_client.patch(url, json={"hours": invalid, "level_to": "B2"})
        assert response.status_code == 400 and "Годин" in response.json()["detail"]
    cleared = (await admin_client.patch(url, json={"hours": ""})).json()["certificate"]
    assert cleared["hours"] is None and cleared["level_to"] is None


async def test_revoke_restore_cycle(admin_client, client):
    c = (await issue(admin_client)).json()["certificate"]
    assert (await admin_client.post(f"{BASE}/{c['id']}/revoke", json={"reason": "помилка"})).status_code == 200
    public = (await client.get("/api/certificates/verify", params={"code": c["serial_number"]})).json()
    assert public["status"] == "revoked" and public["revoked_at"]
    listing = (await admin_client.get(BASE, params={"revoked": True})).json()["items"][0]
    assert listing["revoked_reason"].startswith("помилка") and "admin@example.com" in listing["revoked_reason"]
    await admin_client.post(f"{BASE}/{c['id']}/restore")
    assert (await client.get("/api/certificates/verify", params={"code": c["serial_number"]})).json()["status"] == "valid"


async def test_revoke_without_reason_and_unknown(admin_client):
    c = (await issue(admin_client)).json()["certificate"]
    await admin_client.post(f"{BASE}/{c['id']}/revoke", json={})
    item = (await admin_client.get(BASE)).json()["items"][0]
    assert "без пояснення" in item["revoked_reason"]
    assert (await admin_client.post(f"{BASE}/9999/revoke", json={})).status_code == 404
    assert (await admin_client.post(f"{BASE}/9999/restore")).status_code == 404


async def test_delete_only_unissued_documents(admin_client, session):
    fresh = (await issue(admin_client)).json()["certificate"]
    assert (await admin_client.delete(f"{BASE}/{fresh['id']}")).status_code == 200
    with_pdf = (await issue(admin_client, pdf_url="/static/x.pdf")).json()["certificate"]
    assert (await admin_client.delete(f"{BASE}/{with_pdf['id']}")).status_code == 409
    revoked = (await issue(admin_client)).json()["certificate"]
    await admin_client.post(f"{BASE}/{revoked['id']}/revoke", json={})
    assert (await admin_client.delete(f"{BASE}/{revoked['id']}")).status_code == 409
    assert (await admin_client.delete(f"{BASE}/9999")).status_code == 404
    assert len((await session.execute(select(Certificate))).scalars().all()) == 2


async def test_list_filters_and_search(admin_client):
    await issue(admin_client, student_full_name="Марія Коваль", course_title="IELTS", kind="course")
    second = (await issue(admin_client, student_full_name="Олег Шевчук", course_title="Level up", kind="level")).json()
    await admin_client.post(f"{BASE}/{second['certificate']['id']}/revoke", json={})
    assert (await admin_client.get(BASE)).json()["total"] == 2
    assert (await admin_client.get(BASE, params={"kind": "level"})).json()["total"] == 1
    assert (await admin_client.get(BASE, params={"revoked": False})).json()["total"] == 1
    assert (await admin_client.get(BASE, params={"q": "Марія"})).json()["total"] == 1
    assert (await admin_client.get(BASE, params={"q": second["certificate"]["serial_number"].lower()})).json()["total"] == 1
    assert (await admin_client.get(BASE, params={"limit": 1})).json()["items"].__len__() == 1
    assert (await admin_client.get(BASE, params={"kind": "bogus"})).status_code == 422


# =============================================================== PDF

@pytest.fixture
def pdf_dir(tmp_path, monkeypatch):
    monkeypatch.setattr(certificate_pdf, "CERT_DIR", tmp_path / "certs")
    return tmp_path / "certs"


async def test_generate_pdf_writes_file_named_after_serial(admin_client, pdf_dir):
    c = (await issue(admin_client, kind="level", level_from="A2", level_to="B1",
                     student_full_name="Дуже Довге Складне Прізвище-Імʼя По-Батькові Тестенко")).json()["certificate"]
    r = await admin_client.post(f"{BASE}/{c['id']}/pdf")
    assert r.status_code == 200
    assert r.json()["pdf_url"] == f"/static/certificates/{c['serial_number']}.pdf"
    data = (pdf_dir / f"{c['serial_number']}.pdf").read_bytes()
    assert data.startswith(b"%PDF") and len(data) > 5_000


@pytest.mark.parametrize("kind", [k.value for k in CertificateKind])
async def test_pdf_renders_for_every_kind(admin_client, pdf_dir, kind):
    c = (await issue(admin_client, kind=kind, organization="ТОВ Тест", hours=40, lessons_count=20,
                     teacher_name="Викладач")).json()["certificate"]
    assert (await admin_client.post(f"{BASE}/{c['id']}/pdf")).status_code == 200


async def test_regenerate_keeps_same_number_and_url(admin_client, pdf_dir):
    c = (await issue(admin_client)).json()["certificate"]
    first = (await admin_client.post(f"{BASE}/{c['id']}/pdf")).json()["pdf_url"]
    await admin_client.patch(f"{BASE}/{c['id']}", json={"student_full_name": "Виправлене"})
    second = (await admin_client.post(f"{BASE}/{c['id']}/pdf")).json()
    assert second["pdf_url"] == first and second["certificate"]["serial_number"] == c["serial_number"]


async def test_revoked_certificate_cannot_get_pdf(admin_client, pdf_dir):
    c = (await issue(admin_client)).json()["certificate"]
    await admin_client.post(f"{BASE}/{c['id']}/revoke", json={})
    assert (await admin_client.post(f"{BASE}/{c['id']}/pdf")).status_code == 409
    assert (await admin_client.post(f"{BASE}/9999/pdf")).status_code == 404


async def test_pdf_failure_is_reported_not_crashed(admin_client, monkeypatch):
    import app.api.admin.certificates as admin_certs
    monkeypatch.setattr(admin_certs, "save_pdf", lambda cert: (_ for _ in ()).throw(RuntimeError("no font")))
    c = (await issue(admin_client)).json()["certificate"]
    r = await admin_client.post(f"{BASE}/{c['id']}/pdf")
    assert r.status_code == 500 and "no font" in r.json()["detail"]

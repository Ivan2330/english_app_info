"""Лист власнику про нову заявку: налаштування з оточення, фонова відправка, збої не ламають заявку."""
import logging

import pytest

from app.core import background, notify
from app.core.config import settings
from app.models.lead import Lead


class FakeSMTP:
    instances = []

    def __init__(self, host, port, timeout=None, context=None):
        self.host, self.port, self.tls, self.login_args, self.sent = host, port, False, None, []
        FakeSMTP.instances.append(self)

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False

    def starttls(self, context=None):
        self.tls = True

    def login(self, user, password):
        self.login_args = (user, password)

    def send_message(self, msg):
        self.sent.append(msg)


@pytest.fixture
def smtp(monkeypatch):
    FakeSMTP.instances = []
    monkeypatch.setattr(notify.smtplib, "SMTP", FakeSMTP)
    monkeypatch.setattr(notify.smtplib, "SMTP_SSL", FakeSMTP)
    monkeypatch.setattr(settings, "smtp_host", "smtp.example.com")
    monkeypatch.setattr(settings, "smtp_port", 587)
    monkeypatch.setattr(settings, "smtp_user", "bot@example.com")
    monkeypatch.setattr(settings, "smtp_password", "pw-not-in-logs")
    monkeypatch.setattr(settings, "smtp_from", "Prime Academy <bot@example.com>")
    monkeypatch.setattr(settings, "lead_notify_email", "owner@example.com")
    return FakeSMTP


async def post(client, **over):
    r = await client.post("/api/leads", json={"name": "Марія", "phone": "+380501112233", "audience": "kids",
                                              "level": "A1-A2", "preferred_time": "Вечір", "source": "site/trial",
                                              "attribution": {"first_touch": {"utm_source": "facebook",
                                                                              "utm_campaign": "dec"}}, **over})
    await background.drain()
    return r


async def test_new_lead_sends_one_email_to_the_owner(client, smtp):
    assert (await post(client)).status_code == 200
    [server] = smtp.instances
    assert (server.host, server.port, server.tls, server.login_args) == ("smtp.example.com", 587, True,
                                                                         ("bot@example.com", "pw-not-in-logs"))
    [msg] = server.sent
    body = msg.get_content()
    assert msg["To"] == "owner@example.com" and msg["From"] == "Prime Academy <bot@example.com>"
    assert "Марія" in msg["Subject"]
    for fragment in ("+380501112233", "дитина 5–12", "A1-A2", "Вечір", "facebook / dec", "/admin/leads"):
        assert fragment in body, fragment


async def test_not_configured_means_no_mail_and_no_error(client, monkeypatch):
    monkeypatch.setattr(settings, "smtp_host", "")
    monkeypatch.setattr(settings, "lead_notify_email", "owner@example.com")
    assert notify.enabled() is False
    assert (await post(client)).status_code == 200


async def test_duplicate_submit_sends_one_email(client, smtp):
    await post(client, event_id="same")
    await post(client, event_id="same")
    assert sum(len(s.sent) for s in smtp.instances) == 1


async def test_honeypot_lead_sends_nothing(client, smtp):
    await post(client, website="x")
    assert smtp.instances == []


async def test_smtp_failure_does_not_break_the_lead_and_does_not_log_addresses(client, smtp, monkeypatch, caplog):
    def boom(*a, **k):
        raise OSError("cannot reach smtp for owner@example.com / +380501112233")

    monkeypatch.setattr(notify.smtplib, "SMTP", boom)
    with caplog.at_level(logging.DEBUG, logger="app.notify"):
        r = await post(client)
    assert r.status_code == 200 and r.json()["ok"] is True
    assert "OSError" in caplog.text
    for secret in ("owner@example.com", "+380501112233", "pw-not-in-logs"):
        assert secret not in caplog.text


async def test_port_465_uses_implicit_tls_without_starttls(client, smtp, monkeypatch):
    monkeypatch.setattr(settings, "smtp_port", 465)
    await post(client)
    [server] = smtp.instances
    assert server.port == 465 and server.tls is False


async def test_no_login_when_user_is_empty(client, smtp, monkeypatch):
    monkeypatch.setattr(settings, "smtp_user", "")
    await post(client)
    assert smtp.instances[0].login_args is None
    assert smtp.instances[0].sent[0]["From"] == "Prime Academy <bot@example.com>"


def test_message_for_a_lead_without_contact_or_comment():
    lead = Lead(name="Х", comment="Питання про ціни")
    msg = notify.build_message(lead)
    body = msg.get_content()
    assert "без контакту" in body and "Питання про ціни" in body and "не вказано" in body

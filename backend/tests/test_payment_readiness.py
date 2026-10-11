"""Actual payment handlers, isolated SQLite and mocked bank. No secrets/charges."""
import os
import sys
import json
import base64
import unittest
from pathlib import Path
from unittest.mock import AsyncMock, patch
os.environ.update(DATABASE_URL="sqlite+aiosqlite:///:memory:", ADMIN_EMAIL="test@example.com", ADMIN_PASSWORD="test-only", PAYMENTS_ENABLED="true")
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import httpx
from fastapi import FastAPI
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import ec
from app.api.public import orders as api
from app.db.database import Base, get_async_session
from app.models.order import Order, Payment, PaymentStatus as PS, PaymentMethod as PM, OrderStatus as OS
from app.models.package import Package, Family, Audience, Format, Track
from app.core.payments import plata, chast

class Payments(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.engine = create_async_engine("sqlite+aiosqlite:///:memory:")
        async with self.engine.begin() as connection:
            await connection.run_sync(Base.metadata.create_all)
        self.session = async_sessionmaker(self.engine, expire_on_commit=False)()
        self.order = Order(public_id="PA-TEST", package_slug="test", package_name="Test", amount=10000, customer_name="Test", currency="UAH", payments=[])
        self.session.add(self.order)
        await self.session.commit()
        self.app = FastAPI()
        self.app.include_router(api.router)
        async def session_override():
            yield self.session
        self.app.dependency_overrides[get_async_session] = session_override
        self.client = httpx.AsyncClient(transport=httpx.ASGITransport(app=self.app), base_url="https://test")

    async def asyncTearDown(self):
        await self.client.aclose()
        await self.session.close()
        await self.engine.dispose()

    async def payment(self, method=PM.CARD, status=PS.PROCESSING):
        p = Payment(order=self.order, method=method, status=status, amount=10000, currency="UAH", provider_invoice_id="invoice" if method == PM.CARD else None, provider_order_id="bank-uuid" if method == PM.CHAST else None)
        self.session.add(p)
        await self.session.commit()
        return p

    def card_state(self, **overrides):
        return {"invoiceId":"invoice", "amount":10000, "ccy":980, "reference":"PA-TEST", "status":"success", **overrides}

    async def test_unsigned_webhook_rejected(self):
        p = await self.payment()
        response = await self.client.post("/api/payments/plata/webhook", json=self.card_state())
        self.assertEqual(response.status_code, 403)
        self.assertEqual(p.status, PS.PROCESSING)

    async def test_bank_unavailable_never_trusts_webhook_body(self):
        p = await self.payment()
        with patch.object(plata, "verify_webhook", AsyncMock(return_value=True)), patch.object(plata, "get_invoice_status", AsyncMock(side_effect=plata.PlataError("offline"))):
            response = await self.client.post("/api/payments/plata/webhook", json=self.card_state())
        self.assertEqual(response.status_code, 503)
        self.assertEqual(p.status, PS.PROCESSING)

    async def test_card_poll_recovers_missing_callback(self):
        await self.payment()
        with patch.object(plata, "get_invoice_status", AsyncMock(return_value=self.card_state())):
            response = await self.client.get("/api/orders/PA-TEST/state")
        self.assertEqual(response.json()["order"]["status"], "paid")

    async def test_amount_mismatch_not_paid(self):
        p = await self.payment()
        with self.assertRaises(plata.PlataError):
            await api._apply_plata_state(self.session, self.order, p, self.card_state(amount=1))
        self.assertEqual(p.status, PS.PROCESSING)

    async def test_partial_refund_updates_net_receipts(self):
        p = await self.payment()
        await api._apply_plata_state(self.session, self.order, p, self.card_state(cancelList=[{"status":"success", "amount":2500}]))
        self.assertEqual(self.order.paid_amount, 7500)
        self.assertEqual(self.order.status, OS.PARTIAL)

    async def test_full_refund_removes_paid_status(self):
        p = await self.payment(status=PS.SUCCESS)
        self.order.status = OS.PAID
        await api._apply_plata_state(self.session, self.order, p, self.card_state(status="reversed"))
        self.assertEqual(self.order.status, OS.REFUNDED)
        self.assertEqual(self.order.paid_amount, 0)

    async def test_chast_confirm_checks_response(self):
        p = await self.payment(PM.CHAST)
        state = {"state":"IN_PROCESS", "order_sub_state":"WAITING_FOR_STORE_CONFIRM"}
        with patch.object(chast, "confirm", AsyncMock(return_value={"state":"IN_PROCESS"})) as confirm:
            await api._apply_chast_state(self.session, self.order, p, state)
        confirm.assert_awaited_once_with("bank-uuid")
        self.assertNotEqual(self.order.status, OS.PAID)
        with patch.object(chast, "confirm", AsyncMock(return_value={"state":"SUCCESS", "order_sub_state":"ACTIVE"})):
            await api._apply_chast_state(self.session, self.order, p, state)
        self.assertEqual(self.order.status, OS.PAID)

    async def test_chast_returned_not_success(self):
        p = await self.payment(PM.CHAST, PS.SUCCESS)
        await api._apply_chast_state(self.session, self.order, p, {"state":"SUCCESS", "order_sub_state":"RETURNED"})
        self.assertEqual(p.status, PS.REVERSED)
        self.assertEqual(self.order.status, OS.REFUNDED)

    async def test_duplicate_pay_reuses_invoice(self):
        p = await self.payment()
        p.checkout_url = "https://pay.example/invoice"
        await self.session.commit()
        with patch.object(plata, "create_invoice", AsyncMock()) as create:
            for _ in range(2):
                response = await self.client.post("/api/orders/PA-TEST/pay", json={"method":"card"})
                self.assertEqual(response.json()["checkout_url"], p.checkout_url)
        create.assert_not_awaited()

    async def test_card_timeout_blocks_second_invoice(self):
        with patch.object(plata, "create_invoice", AsyncMock(side_effect=plata.PlataError("timeout"))) as create:
            first = await self.client.post("/api/orders/PA-TEST/pay", json={"method":"card"})
            second = await self.client.post("/api/orders/PA-TEST/pay", json={"method":"card"})
        self.assertEqual(first.status_code, 502)
        self.assertEqual(second.status_code, 200)
        self.assertEqual(create.await_count, 1)

    async def test_chast_callback_matches_bank_uuid(self):
        p = await self.payment(PM.CHAST)
        body = json.dumps({"order_id":"bank-uuid", "state":"FAIL"}).encode()
        with patch.object(chast, "get_state", AsyncMock(return_value={"state":"FAIL", "order_sub_state":"REJECTED_BY_CLIENT"})):
            response = await self.client.post("/api/payments/chast/callback", content=body, headers={"signature":chast._sign(body)})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(p.status, PS.FAILED)

    async def test_signed_webhook_updates_order(self):
        await self.payment()
        with patch.object(plata, "verify_webhook", AsyncMock(return_value=True)), patch.object(plata, "get_invoice_status", AsyncMock(return_value=self.card_state())):
            for _ in range(2):
                response = await self.client.post("/api/payments/plata/webhook", json=self.card_state())
                self.assertEqual(response.status_code, 200)
        self.assertEqual(self.order.paid_amount, 10000)

    async def test_success_not_downgraded_by_old_status(self):
        p = await self.payment(status=PS.SUCCESS)
        await api._sync_order_totals(self.session, self.order)
        await api._apply_plata_state(self.session, self.order, p, self.card_state(status="processing"))
        self.assertEqual(self.order.status, OS.PAID)

    async def test_full_refund_with_success_status(self):
        p = await self.payment()
        await api._apply_plata_state(self.session, self.order, p, self.card_state(cancelList=[{"status":"success","amount":10000}]))
        self.assertEqual(self.order.status, OS.REFUNDED)

    async def test_partial_reversed_still_has_net_receipts(self):
        p = await self.payment()
        await api._apply_plata_state(self.session, self.order, p, self.card_state(status="reversed",cancelList=[{"status":"success","amount":2500}]))
        self.assertEqual(self.order.paid_amount,7500)

    async def test_unknown_method_rejected(self):
        response = await self.client.post("/api/orders/PA-TEST/pay",json={"method":"banana"})
        self.assertEqual(response.status_code,400)

    async def test_invalid_chast_signature_rejected(self):
        response = await self.client.post("/api/payments/chast/callback",json={"order_id":"bank-uuid"})
        self.assertEqual(response.status_code,403)

    async def test_checkout_key_reuses_created_order(self):
        self.order.public_id = "PA-123456781234423482341234"
        await self.session.commit()
        response = await self.client.post("/api/orders",json={"checkout_key":"12345678-1234-4234-8234-123456789abc"})
        self.assertEqual(response.status_code,200)
        self.assertEqual(response.json()["order"]["id"], self.order.id)

    async def enable_chast(self):
        package = Package(slug="test", name="Test", family=Family.SUBSCRIPTION, audience=Audience.ADULTS, fmt=Format.INDIVIDUAL, track=Track.GENERAL, total_price=100, chast_enabled=True, chast_max_parts=6)
        self.session.add(package)
        await self.session.flush()
        self.order.package_id = package.id
        self.order.customer_phone = "050 123 45 64"
        await self.session.commit()

    async def test_chast_creation_saves_bank_id(self):
        await self.enable_chast()
        with patch.object(chast, "create_order", AsyncMock(return_value={"order_id":"bank-uuid"})) as create:
            response = await self.client.post("/api/orders/PA-TEST/pay",json={"method":"chast","parts_count":3})
        self.assertEqual(response.status_code,200)
        await self.session.refresh(self.order,["payments"])
        self.assertEqual(self.order.payments[0].provider_order_id,"bank-uuid")
        self.assertEqual(create.call_args.kwargs["client_phone"],"+380501234564")
        self.assertEqual(create.call_args.kwargs["amount_kop"],10000)

    async def test_chast_timeout_never_opens_card_invoice(self):
        await self.enable_chast()
        with patch.object(chast,"create_order",AsyncMock(side_effect=chast.ChastError("timeout"))) as create, patch.object(plata,"create_invoice",AsyncMock()) as card:
            response = await self.client.post("/api/orders/PA-TEST/pay",json={"method":"chast"})
            self.assertEqual(response.status_code,503)
            await self.client.post("/api/orders/PA-TEST/pay",json={"method":"card"})
        self.assertEqual(create.await_count,1)
        card.assert_not_awaited()

    async def test_chast_parts_validated_before_bank(self):
        await self.enable_chast()
        with patch.object(chast,"create_order",AsyncMock()) as create:
            for parts in (2,7,"invalid"):
                response=await self.client.post("/api/orders/PA-TEST/pay",json={"method":"chast","parts_count":parts})
                self.assertEqual(response.status_code,400)
        create.assert_not_awaited()

    async def test_early_card_callback_recovers_missing_invoice_id(self):
        p=await self.payment(status=PS.CREATED)
        p.provider_invoice_id=None
        await self.session.commit()
        with patch.object(plata,"verify_webhook",AsyncMock(return_value=True)),patch.object(plata,"get_invoice_status",AsyncMock(return_value=self.card_state())):
            response=await self.client.post("/api/payments/plata/webhook",json=self.card_state())
        self.assertEqual(response.status_code,200)
        self.assertEqual(p.provider_invoice_id,"invoice")
        self.assertEqual(self.order.status,OS.PAID)

class Signatures(unittest.IsolatedAsyncioTestCase):
    async def test_real_ecdsa_valid_and_tampered(self):
        private = ec.generate_private_key(ec.SECP256R1())
        pem = private.public_key().public_bytes(serialization.Encoding.PEM, serialization.PublicFormat.SubjectPublicKeyInfo)
        body = b'{"invoiceId":"test"}'
        signature = base64.b64encode(private.sign(body, ec.ECDSA(hashes.SHA256()))).decode()
        transport = httpx.MockTransport(lambda request: httpx.Response(200, json={"key":base64.b64encode(pem).decode()}))
        real_client = httpx.AsyncClient
        with patch.object(plata.httpx, "AsyncClient", side_effect=lambda **kw: real_client(transport=transport, **kw)):
            self.assertTrue(await plata.verify_webhook(body, signature))
            self.assertFalse(await plata.verify_webhook(body+b" ", signature))

    async def test_chast_payload_and_signature(self):
        requests = []
        def handle(request):
            requests.append(request)
            return httpx.Response(200, json={"order_id":"bank-id"})
        real_client = httpx.AsyncClient
        with patch.object(chast.httpx, "AsyncClient", side_effect=lambda **kw: real_client(transport=httpx.MockTransport(handle), **kw)):
            await chast.create_order(order_id="test", amount_kop=12345, parts_count=3, products=[{"name":"Test", "count":1, "sum":123.45}], client_phone="+380501234561")
            await chast.get_state("bank-id")
            await chast.confirm("bank-id")
        payload = json.loads(requests[0].content)
        self.assertEqual(payload["total_sum"], 123.45)
        self.assertEqual(payload["available_programs"][0]["available_parts_count"], [3])
        for request in requests:
            self.assertTrue(chast.verify_callback(request.content, request.headers["signature"]))
        self.assertEqual(json.loads(requests[1].content), {"order_id":"bank-id"})
        self.assertEqual(json.loads(requests[2].content), {"order_id":"bank-id"})

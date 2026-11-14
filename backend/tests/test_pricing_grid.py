"""Цінова сітка Фази 1: ціни, бонуси, каталог, заявки на розрахунок, ПЧ.

Ізольований SQLite, банк замоканий, жодних секретів і списань.
"""
import os
import sys
import unittest
from datetime import datetime
from pathlib import Path
from unittest.mock import AsyncMock, patch

os.environ.update(DATABASE_URL="sqlite+aiosqlite:///:memory:", ADMIN_EMAIL="test@example.com",
                  ADMIN_PASSWORD="test-only", PAYMENTS_ENABLED="true")
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import httpx
from fastapi import FastAPI
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker

from app.api.public import orders as orders_api, packages as packages_api, quotes as quotes_api
from app.core import pricing as P
from app.core.payments import chast
from app.core.seed_packages import build_catalogue, seed_packages
from app.db.database import Base, get_async_session
from app.models.order import Order, OrderStatus, Payment
from app.models.package import Package
from app.models.quote_request import QuoteRequest


class PricingConfig(unittest.TestCase):
    def test_individual_grid(self):
        self.assertEqual(P.ADULT_LADDER, [6, 16, 24, 48, 96])
        self.assertEqual(P.ADULT_INDIVIDUAL, [550, 470, 450, 430, 390])

    def test_pair_grid_per_person(self):
        self.assertEqual(P.ADULT_PAIR, [385, 330, 315, 300, 275])

    def test_group_plans(self):
        totals = [g["lessons"] * g["price"] for g in P.GROUP_PLANS]
        self.assertEqual(totals, [2360, 8480, 12000])
        self.assertEqual([g["lessons"] for g in P.GROUP_PLANS],
                         [P.GROUP_LESSONS_PER_MONTH * m for m in (1, 4, 6)])

    def test_group_dates_come_from_config(self):
        self.assertEqual(P.GROUP_START_DATE.isoformat(), "2026-12-15")
        self.assertEqual(P.GROUP_ENROLL_UNTIL.isoformat(), "2026-12-12")

    def test_bonus_first_purchase(self):
        got = [P.bonus_for("individual", n, 1) for n in P.ADULT_LADDER]
        self.assertEqual(got, [0, 2, 4, 10, 24])
        self.assertEqual([P.bonus_for("pair", n, 1) for n in P.ADULT_LADDER], got)
        self.assertEqual([P.bonus_for("group", n, 1) for n in P.GROUP_LADDER], [0, 0, 0])

    def test_bonus_later_purchases_empty_but_configurable(self):
        for idx in (2, 3, 7):
            self.assertEqual(P.bonus_for("individual", 96, idx), 0)
        with patch.dict(P.BONUS_LESSONS["individual"], {16: (2, 3, 5)}):
            self.assertEqual(P.bonus_for("individual", 16, 2), 3)
            self.assertEqual(P.bonus_for("individual", 16, 3), 5)
            self.assertEqual(P.bonus_for("individual", 16, 9), 5)   # остання клітинка діє далі

    def test_bonus_unknown_is_zero(self):
        self.assertEqual(P.bonus_for("individual", 64, 1), 0)
        self.assertEqual(P.bonus_for("club", 4, 1), 0)

    def test_club_min_participants(self):
        self.assertEqual(P.CLUB_MIN_PARTICIPANTS, 4)

    def test_referral_is_twenty_percent(self):
        self.assertEqual(P.REFERRAL_PERCENT, 20)
        self.assertEqual(P.discount_breakdown(100_000, ["referral"])["final"], 80_000)


class Catalogue(unittest.TestCase):
    def setUp(self):
        self.items = build_catalogue()

    def test_counts_per_combination(self):
        key = ("general", "adults")
        by_fmt = {}
        for i in self.items:
            if i["family"].value == "subscription" and (i["track"].value, i["audience"].value) == key:
                by_fmt.setdefault(i["fmt"].value, []).append(i)
        self.assertEqual({k: len(v) for k, v in by_fmt.items()}, {"individual": 5, "pair": 5, "group": 3})

    def test_slugs_unique(self):
        slugs = [i["slug"] for i in self.items]
        self.assertEqual(len(slugs), len(set(slugs)))

    def test_visible_courses_exactly_nine(self):
        courses = sorted(i["slug"] for i in self.items if i["family"].value == "course")
        self.assertEqual(courses, sorted(P.VISIBLE_COURSES))
        self.assertEqual(len(courses), 9)

    def test_five_clubs_prices_unchanged(self):
        clubs = {i["slug"]: i["total_price"] for i in self.items if i["family"].value == "club"}
        self.assertEqual(clubs, {"club-a2b1": 690, "club-b2c1": 690, "club-x2": 1190,
                                 "club-teens": 590, "club-kids": 490})

    def test_kids_and_corporate_not_in_catalogue(self):
        self.assertFalse([i for i in self.items if i["family"].value == "corporate"])
        self.assertFalse([i for i in self.items
                          if i["audience"].value == "kids" and i["family"].value != "club"])

    def test_anchor_and_discount_kept(self):
        i = next(x for x in self.items if x["slug"] == "general-adults-individual-96")
        self.assertEqual(i["total_price"], 96 * 390)
        self.assertEqual(i["not_true_price"], 96 * 550)
        self.assertEqual(i["discount_percent"], 29)

    def test_popular_only_16_and_not_group(self):
        pop = [i for i in self.items if i["family"].value == "subscription" and i["is_popular"]]
        self.assertTrue(pop)
        self.assertTrue(all(i["lessons_count"] == 16 and i["fmt"].value != "group" for i in pop))


class DbTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.engine = create_async_engine("sqlite+aiosqlite:///:memory:")
        async with self.engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
        self.session = async_sessionmaker(self.engine, expire_on_commit=False)()
        self.app = FastAPI()
        for r in (orders_api.router, packages_api.router, quotes_api.router):
            self.app.include_router(r)

        async def override():
            yield self.session
        self.app.dependency_overrides[get_async_session] = override
        self.client = httpx.AsyncClient(transport=httpx.ASGITransport(app=self.app), base_url="https://test")

    async def asyncTearDown(self):
        await self.client.aclose()
        await self.session.close()
        await self.engine.dispose()

    async def count(self):
        return (await self.session.execute(select(func.count(Package.id)))).scalar_one()

    async def test_seed_is_idempotent(self):
        await seed_packages(self.session)
        first = await self.count()
        again = await seed_packages(self.session)
        self.assertEqual(await self.count(), first)
        self.assertEqual(again["created"], 0)
        self.assertEqual(again["deactivated"], 0)

    async def test_seed_hides_not_deletes(self):
        tpl = build_catalogue()[0]
        old = Package(slug="general-adults-individual-250", name="old", family=tpl["family"],
                      audience=tpl["audience"], fmt=tpl["fmt"], track=tpl["track"],
                      total_price=1, is_active=True,
                      created_at=datetime.utcnow(), updated_at=datetime.utcnow())
        self.session.add(old)
        await self.session.commit()
        res = await seed_packages(self.session)
        self.assertEqual(res["deactivated"], 1)
        row = (await self.session.execute(select(Package).where(Package.slug == old.slug))).scalar_one()
        self.assertFalse(row.is_active)
        self.assertEqual((await self.client.get(f"/api/packages/{old.slug}")).status_code, 404)

    async def test_hidden_never_in_public_list(self):
        await seed_packages(self.session)
        p = (await self.session.execute(select(Package).where(Package.slug == "club-kids"))).scalar_one()
        p.is_active = False
        await self.session.commit()
        for q in ("", "?active=0"):
            slugs = [x["slug"] for x in (await self.client.get(f"/api/packages{q}")).json()]
            self.assertNotIn("club-kids", slugs)

    async def test_public_dict_has_bonus_and_group_dates(self):
        await seed_packages(self.session)
        ind = (await self.client.get("/api/packages/general-adults-individual-16")).json()
        self.assertEqual(ind["bonus_lessons"], 2)
        self.assertIsNone(ind["starts_on"])
        grp = (await self.client.get("/api/packages/general-adults-group-32")).json()
        self.assertEqual(grp["bonus_lessons"], 0)
        self.assertEqual(grp["starts_on"], "2026-12-15")
        self.assertEqual(grp["enroll_until"], "2026-12-12")

    async def order(self, slug, phone="+380991112233"):
        r = await self.client.post("/api/orders", json={
            "package_slug": slug, "customer_name": "Тест", "customer_phone": phone,
            "offer_accepted": True})
        self.assertEqual(r.status_code, 200, r.text)
        return r.json()["order"]

    async def test_order_bonus_follows_purchase_number(self):
        await seed_packages(self.session)
        first = await self.order("general-adults-individual-48")
        self.assertEqual((first["bonus_lessons"], first["purchase_index"]), (10, 1))
        # поки перше не оплачене, друге теж перше
        again = await self.order("general-adults-individual-48")
        self.assertEqual(again["purchase_index"], 1)

        o = (await self.session.execute(select(Order).where(Order.public_id == first["public_id"]))).scalar_one()
        o.status = OrderStatus.PAID
        await self.session.commit()

        second = await self.order("general-adults-individual-48")
        self.assertEqual((second["bonus_lessons"], second["purchase_index"]), (0, 2))   # порожньо в конфігу
        other_person = await self.order("general-adults-individual-48", phone="+380509998877")
        self.assertEqual(other_person["purchase_index"], 1)

    async def test_bonus_does_not_change_amount(self):
        await seed_packages(self.session)
        o = await self.order("general-adults-individual-16")
        self.assertEqual(o["amount"], 16 * 470 * 100)

    async def test_chast_amount_independent_of_parts(self):
        await seed_packages(self.session)
        amounts = {}
        for parts in (3, 4, 5, 6):
            # Нове замовлення на кожну спробу: після першого /pay воно pending,
            # і повторний виклик віддав би той самий платіж замість нового.
            o = await self.order("general-adults-individual-24", phone=f"+38099111223{parts}")   # 10 800 грн, до 6 частин
            mock = AsyncMock(return_value={"state": "IN_PROCESS", "order_id": f"bank-{parts}",
                                           "invoice_url": f"https://bank/{parts}"})
            with patch.object(chast, "create_order", mock):
                r = await self.client.post(f"/api/orders/{o['public_id']}/pay",
                                           json={"method": "chast", "parts_count": parts})
            self.assertEqual(r.status_code, 200, r.text)
            kw = mock.call_args.kwargs
            self.assertEqual(kw["parts_count"], parts)
            amounts[parts] = kw["amount_kop"]
            self.assertEqual(kw["products"][0]["sum"], 10800.0)
        self.assertEqual(set(amounts.values()), {1_080_000})
        sums = (await self.session.execute(select(Payment.amount))).scalars().all()
        self.assertEqual(set(sums), {1_080_000})

    async def quote(self, **over):
        body = {"kind": "kids", "name": "Мама", "phone": "+380991112233",
                "params": {"age": 8, "format": "individual", "lessons": 16}}
        body.update(over)
        return await self.client.post("/api/quote-requests", json=body)

    async def test_quote_response_has_no_prices(self):
        r = await self.quote()
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.json(), {"ok": True})
        row = (await self.session.execute(select(QuoteRequest))).scalar_one()
        self.assertEqual(row.calc_preview["total"], 16 * 420)      # менеджер бачить
        self.assertEqual(row.status.value, "new")

    async def test_corporate_quote(self):
        r = await self.quote(kind="corporate", company="ТОВ Тест",
                             params={"people": 12, "format": "group", "months": 3, "goal": "Співбесіди"})
        self.assertEqual(r.json(), {"ok": True})
        row = (await self.session.execute(select(QuoteRequest))).scalar_one()
        self.assertEqual(row.calc_preview["groups"], 2)
        self.assertEqual(row.calc_preview["discount_percent"], 5)

    async def test_quote_validation(self):
        self.assertEqual((await self.quote(phone=None)).status_code, 400)
        self.assertEqual((await self.quote(params={"age": 8, "format": "x", "lessons": 4})).status_code, 400)
        self.assertEqual((await self.quote(kind="nope")).status_code, 400)
        self.assertEqual((await self.quote(comment="https://spam")).status_code, 400)


class QuotePreview(unittest.TestCase):
    def test_kids_rate_picks_next_step(self):
        self.assertEqual(P.kids_preview(8, "individual", 8)["rate"], 470)
        self.assertEqual(P.kids_preview(8, "individual", 20)["rate"], 390)
        self.assertEqual(P.kids_preview(8, "pair", 16)["rate"], 295)

    def test_corporate_discount_by_groups(self):
        self.assertEqual(P.corporate_preview(6, "group", 1)["discount_percent"], 0)
        self.assertEqual(P.corporate_preview(30, "group", 1)["discount_percent"], 10)


if __name__ == "__main__":
    unittest.main()

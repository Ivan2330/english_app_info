"""Цінова логіка: повернення, знижки, пороги ПЧ, інваріанти каталогу, CLI."""
import pytest

from app import cli
from app.core import pricing as P
from app.core.seed_packages import build_catalogue, seed_packages
from app.models.package import Family, Format


# =============================================================== знижки

@pytest.mark.parametrize("kinds,percent,capped", [
    ([], 0, False),
    (["referral"], 20, False),
    (["referral_reward"], 20, False),
    (["family"], 10, False),
    (["second_course"], 10, False),
    (["family", "second_course"], 20, False),
    (["referral", "family"], 20, True),                 # 30% зрізається до стелі
    (["referral", "referral_reward", "family", "second_course"], 20, True),
    (["bogus"], 0, False),
    (["family", "family", "family"], 10, False),         # дублі не множаться
])
def test_discount_percent_and_cap(kinds, percent, capped):
    calc = P.discount_breakdown(1_000_000, kinds)
    assert calc["percent"] == percent and calc["capped"] is capped
    assert calc["total"] == 1_000_000 * percent // 100
    assert calc["final"] == 1_000_000 - calc["total"]


def test_discount_lines_explain_each_reason():
    calc = P.discount_breakdown(100_000, ["family", "second_course"])
    assert [l["kind"] for l in calc["lines"]] == ["family", "second_course"]
    assert all(l["label"] and l["percent"] == 10 for l in calc["lines"])


@pytest.mark.parametrize("amount", [1, 99, 100_001, 7_520_00, 123_456_789])
def test_discount_never_goes_negative_and_stays_integer(amount):
    calc = P.discount_breakdown(amount, ["referral"])
    assert isinstance(calc["final"], int) and 0 <= calc["final"] <= amount
    assert calc["final"] + calc["total"] == amount


def test_percentages_are_summed_not_compounded():
    """10% + 10% = 20% від початкової, а не 19%: клієнту це не пояснити."""
    assert P.discount_breakdown(100_000, ["family", "second_course"])["final"] == 80_000


def test_every_discount_kind_has_label_and_percent():
    assert set(P.DISCOUNT_LABELS) == set(P.DISCOUNT_PERCENTS)
    assert P.MAX_TOTAL_DISCOUNT_PERCENT == 20


# =============================================================== повернення

IND = (P.ADULT_LADDER, P.ADULT_INDIVIDUAL)      # 6/16/24/48/96 по 550/470/450/430/390


def test_refund_example_from_offer():
    """Оферта п. 10.2: оплачено 48, проведено 6 — мінус ціна пакета на 6, решта назад."""
    paid = 48 * 430                                  # 20 640
    assert P.refund_amount(paid, 6, *IND) == paid - 6 * 550 == 17_340


@pytest.mark.parametrize("used,cost", [
    (0, 0),
    (1, 6 * 550),        # найближчий не менший пакет — 6 уроків
    (6, 6 * 550),
    (7, 16 * 470),       # між сходинками — ціна пакета на 16
    (16, 16 * 470),
    (24, 24 * 450),
    (48, 48 * 430),
    (96, 96 * 390),
])
def test_used_cost_is_price_of_nearest_not_smaller_package(used, cost):
    assert P.refund_used_cost(used, *IND) == cost


def test_no_admin_fee_any_more():
    """Збір 300 ₴ прибрано: нічого не проведено — повертаємо все до копійки."""
    assert P.refund_amount(48 * 430, 0, *IND) == 48 * 430
    assert not hasattr(P, "REFUND_ADMIN_FEE")


@pytest.mark.parametrize("paid,used,expected", [
    (6 * 550, 6, 0),                 # усе відходив
    (16 * 470, 7, 0),                # проведене за ціною пакета на 16 = сплаченому
    (1_000, 6, 0),                   # проведене перекриває сплачене — не в мінус
    (0, 0, 0),
])
def test_refund_never_negative(paid, used, expected):
    assert P.refund_amount(paid, used, *IND) == expected


def test_refund_uses_price_list_passed_in_not_current():
    """«За прайсом на момент оплати»: ставки приходять аргументом, а не з поточної сітки."""
    old_prices = [600, 500, 480, 460, 420]
    assert P.refund_amount(48 * 460, 6, P.ADULT_LADDER, old_prices) == 48 * 460 - 6 * 600


def test_refund_cannot_be_gamed_by_buying_the_cheapest_rate():
    """Купити 96 по 390, відходити 10 і забрати решту: проведені рахуються як пакет на 16."""
    paid = 96 * 390
    back = P.refund_amount(paid, 10, *IND)
    assert back == paid - 16 * 470 < paid - 10 * 390


# =============================================================== ПЧ, строки, заморозка

@pytest.mark.parametrize("total,expected", [
    (0, (False, None)), (None, (False, None)),
    (1, (True, 3)), (10_000, (True, 3)),
    (10_001, (True, 6)), (30_000, (True, 6)),
    (30_001, (False, None)),
])
def test_chast_tiers(total, expected):
    assert P.chast_for(total) == expected


@pytest.mark.parametrize("lessons,days", [(6, 60), (16, 120), (48, 300), (96, 480), (250, 900)])
def test_validity_table(lessons, days):
    assert P.validity_for(lessons) == days


@pytest.mark.parametrize("lessons", [1, 5, 7, 40, 100, 300])
def test_validity_for_unlisted_sizes_has_floor(lessons):
    assert P.validity_for(lessons) >= 60


def test_validity_is_monotonic_over_the_grid():
    days = [P.validity_for(n) for n in sorted(P.VALIDITY_DAYS)]
    assert days == sorted(days)


@pytest.mark.parametrize("lessons,days", [(6, 30), (47, 30), (48, 60), (250, 60)])
def test_freeze_days(lessons, days):
    assert P.freeze_days_for(lessons) == days


@pytest.mark.parametrize("lessons,limit", [(0, 0), (6, 3), (16, 8), (96, 48)])
def test_carry_over_is_half_of_new_package(lessons, limit):
    assert P.carry_over_limit(lessons) == limit


@pytest.mark.parametrize("groups,percent", [(1, 0), (2, 5), (3, 10), (4, 10), (5, 15), (6, 15), (7, 20), (50, 20)])
def test_corporate_volume_discount(groups, percent):
    assert P.corporate_discount(groups) == percent


@pytest.mark.parametrize("value,expected", [(283.5, 280), (273, 270), (285, 280), (295, 300), (0, 0)])
def test_r10(value, expected):
    assert P.r10(value) == expected


@pytest.mark.parametrize("lessons,fmt,rate", [
    (8, "individual", 620), (9, "individual", 590), (64, "individual", 480), (500, "individual", 480),
    (8, "group", 400), (20, "group", 360), (8, "pair", 435),
])
def test_course_rate_picks_next_step_up(lessons, fmt, rate):
    assert P.course_rate(lessons, fmt) == rate


# =============================================================== попередній розрахунок

@pytest.mark.parametrize("fmt,lessons,rate,minutes", [
    ("individual", 8, 470, 40), ("individual", 17, 390, 40), ("individual", 96, 345, 40),
    ("pair", 16, 295, 40), ("group", 16, 280, 60), ("group", 96, 225, 60), ("group", 500, 225, 60),
])
def test_kids_preview_matches_published_kids_grid(fmt, lessons, rate, minutes):
    p = P.kids_preview(9, fmt, lessons)
    assert (p["rate"], p["lesson_minutes"], p["total"]) == (rate, minutes, rate * lessons)
    assert p["per_person"] is (fmt == "pair")


@pytest.mark.parametrize("age,ok", [(None, True), (5, True), (12, True), (4, False), (13, False)])
def test_kids_preview_flags_age(age, ok):
    assert P.kids_preview(age, "individual", 8)["age_in_range"] is ok


@pytest.mark.parametrize("fmt,lessons", [("club", 8), ("individual", 0), ("individual", -1)])
def test_kids_preview_rejects_nonsense(fmt, lessons):
    with pytest.raises(ValueError):
        P.kids_preview(8, fmt, lessons)


@pytest.mark.parametrize("people,fmt,slug,groups", [
    (1, "group", "corp-group6-90", 1), (6, "group", "corp-group6-90", 1),
    (7, "group", "corp-group10-90", 1), (10, "group", "corp-group10-90", 1),
    (11, "group", "corp-group10-90", 2), (31, "group", "corp-group10-90", 4),
    (5, "individual", "corp-solo-50", 5),
])
def test_corporate_preview_grouping(people, fmt, slug, groups):
    p = P.corporate_preview(people, fmt, 3)
    assert (p["package"], p["groups"]) == (slug, groups)


def test_corporate_preview_money():
    p = P.corporate_preview(12, "group", 3)        # 2 групи по 10: 1350 × 24 заняття, −5%
    assert p["sessions_per_group"] == 24 and p["discount_percent"] == 5 and p["assessment_free"] is True
    assert p["total"] == 1350 * 24 * 2 * 95 // 100


def test_corporate_individual_defaults_to_the_50_minute_rate():
    """РЕГРЕСІЯ: без довжини заняття індивідуальне рахувалося за 60-хвилинним тарифом."""
    p = P.corporate_preview(2, "individual", 1)
    assert p["package"] == "corp-solo-50" and p["price_per_session"] == 520


def test_corporate_individual_gets_no_group_discount():
    assert P.corporate_preview(30, "individual", 1)["discount_percent"] == 0


def test_corporate_preview_lesson_length_and_validation():
    assert P.corporate_preview(3, "group", 1, lesson_minutes=60)["package"] == "corp-group6-60"
    assert P.corporate_preview(3, "individual", 1, lesson_minutes=60)["package"] == "corp-solo-60"
    for people, months in ((0, 1), (1, 0)):
        with pytest.raises(ValueError):
            P.corporate_preview(people, "group", months)


# =============================================================== інваріанти каталогу

@pytest.fixture(scope="module")
def catalogue():
    return build_catalogue()


def test_every_item_total_equals_rate_times_lessons(catalogue):
    for it in catalogue:
        if it["family"] in (Family.SUBSCRIPTION, Family.COURSE):
            assert it["total_price"] == it["price_per_lesson"] * it["lessons_count"], it["slug"]


def test_price_per_lesson_never_rises_with_pack_size(catalogue):
    groups = {}
    for it in catalogue:
        if it["family"] == Family.SUBSCRIPTION:
            groups.setdefault((it["audience"], it["track"], it["fmt"]), []).append(it)
    for key, items in groups.items():
        rates = [i["price_per_lesson"] for i in sorted(items, key=lambda i: i["lessons_count"])]
        assert rates == sorted(rates, reverse=True), key


def test_anchor_is_smallest_pack_rate_times_lessons(catalogue):
    for it in catalogue:
        if it.get("not_true_price"):
            rate0 = {Format.INDIVIDUAL: 550, Format.PAIR: 385, Format.GROUP: 295}[it["fmt"]]
            assert it["not_true_price"] == rate0 * it["lessons_count"], it["slug"]
            assert it["discount_percent"] == round((it["not_true_price"] - it["total_price"])
                                                   / it["not_true_price"] * 100)


def test_smallest_pack_has_no_fake_discount(catalogue):
    firsts = [i for i in catalogue if i["family"] == Family.SUBSCRIPTION and i["lessons_count"] in (6, 8)
              and i["fmt"] in (Format.INDIVIDUAL, Format.PAIR, Format.GROUP)
              and i["slug"].endswith(("-6", "-8"))]
    assert firsts and all(not i["not_true_price"] and not i["discount_percent"] for i in firsts)


def test_pair_is_priced_per_person_and_cheaper_than_individual(catalogue):
    pair = {i["lessons_count"]: i for i in catalogue
            if i["slug"].startswith("general-adults-pair-")}
    solo = {i["lessons_count"]: i for i in catalogue
            if i["slug"].startswith("general-adults-individual-")}
    for n in pair:
        assert pair[n]["price_per_person"] is True
        assert pair[n]["price_per_lesson"] < solo[n]["price_per_lesson"]
        assert 0.69 <= pair[n]["price_per_lesson"] / solo[n]["price_per_lesson"] <= 0.72


def test_lesson_duration_by_format(catalogue):
    for it in catalogue:
        if it["family"] == Family.SUBSCRIPTION:
            assert it["lesson_duration_min"] == (90 if it["fmt"] == Format.GROUP else 50), it["slug"]


def test_chast_flags_follow_the_tiers(catalogue):
    for it in catalogue:
        if it["family"] == Family.CLUB:
            assert not it.get("chast_enabled")          # клуби частинами не продаються
            continue
        assert (it["chast_enabled"], it["chast_max_parts"]) == P.chast_for(it["total_price"]), it["slug"]
    assert max(i["total_price"] for i in catalogue if i.get("chast_enabled")) <= P.CHAST_MAX_TOTAL


def test_validity_present_on_everything_but_clubs(catalogue):
    for it in catalogue:
        if it["family"] in (Family.SUBSCRIPTION, Family.COURSE):
            assert it["validity_days"] == P.validity_for(it["lessons_count"])


def test_bonus_table_covers_exactly_the_published_sizes():
    assert set(P.BONUS_LESSONS["individual"]) == set(P.ADULT_LADDER)
    assert set(P.BONUS_LESSONS["pair"]) == set(P.ADULT_LADDER)
    assert set(P.BONUS_LESSONS["group"]) == set(P.GROUP_LADDER)
    for table in P.BONUS_LESSONS.values():
        for row in table.values():
            assert len(row) == 3 and all(isinstance(v, int) and v >= 0 for v in row)


def test_bonus_never_decreases_with_pack_size():
    for fmt in ("individual", "pair"):
        firsts = [P.bonus_for(fmt, n, 1) for n in P.ADULT_LADDER]
        assert firsts == sorted(firsts)


def test_popular_label_only_on_sixteen(catalogue):
    pops = [i for i in catalogue if i["family"] == Family.SUBSCRIPTION and i["is_popular"]]
    assert pops and {i["lessons_count"] for i in pops} == {16}


def test_teens_follow_adult_grid_without_coefficient(catalogue):
    by = lambda a: {i["lessons_count"]: i["price_per_lesson"] for i in catalogue      # noqa: E731
                    if i["slug"].startswith(f"general-{a}-individual-")}
    assert by("teens") == by("adults")


# =============================================================== сід і CLI

async def test_seed_result_counts(session):
    first = await seed_packages(session)
    second = await seed_packages(session)
    assert first["created"] == 80 and first["updated"] == 0 and first["total"] == 80
    assert second == {"created": 0, "updated": 80, "deactivated": 0, "total": 80}


async def test_seed_reactivates_and_restores_prices(session):
    from sqlalchemy import select
    from app.models.package import Package
    await seed_packages(session)
    p = (await session.execute(select(Package).where(Package.slug == "general-adults-individual-16"))).scalar_one()
    p.total_price, p.is_active = 1, False
    await session.commit()
    await seed_packages(session)
    assert (p.total_price, p.is_active) == (16 * 470, True)


def test_show_catalogue_prints_without_database(capsys):
    cli._show_catalogue()
    out = capsys.readouterr().out
    assert "SUBSCRIPTION" in out and "COURSE" in out and "CLUB" in out
    assert "CORPORATE" not in out and "Усього: 80 позицій" in out


def test_cli_unknown_command_exits(monkeypatch, capsys):
    monkeypatch.setattr("sys.argv", ["cli"])
    with pytest.raises(SystemExit) as exc:
        cli.main()
    assert exc.value.code == 1 and "seed-packages" in capsys.readouterr().out


def test_cli_dispatches_known_command(monkeypatch):
    called = []
    monkeypatch.setitem(cli.COMMANDS, "show-catalogue", lambda: called.append(1))
    monkeypatch.setattr("sys.argv", ["cli", "show-catalogue"])
    cli.main()
    assert called == [1]


async def test_cli_seed_command_end_to_end(session, monkeypatch, capsys):
    from sqlalchemy.ext.asyncio import async_sessionmaker
    maker = async_sessionmaker(session.bind, expire_on_commit=False)
    monkeypatch.setattr(cli, "async_session_maker", maker)
    await cli._seed_packages()
    assert "створено 80" in capsys.readouterr().out


async def test_cli_waits_for_tables_then_gives_up(monkeypatch, capsys):
    """Без таблиць CLI чекає й виходить із підказкою, а не висить вічно."""
    from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    monkeypatch.setattr(cli, "async_session_maker", async_sessionmaker(engine))

    async def no_sleep(_):
        return None
    monkeypatch.setattr(cli.asyncio, "sleep", no_sleep)
    import asyncio
    import itertools
    ticks = itertools.count(0, 40)
    monkeypatch.setattr(asyncio.get_event_loop(), "time", lambda: next(ticks))
    with pytest.raises(SystemExit):
        await cli._wait_for_tables(timeout=60)
    assert "міграції" in capsys.readouterr().out.lower()
    await engine.dispose()

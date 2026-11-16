"""Тексти сайту, які мають збігатися з офертою (редакція від 15.11.2026).

Фронт тут не запускається, перевіряються вихідні файли: так само,
як test_offer_revision_matches_frontend. Ловить рівно ті розбіжності,
за які соромно перед клієнтом: стара дата редакції, старі пороги
гарантії, зниклі посилання на оферту.
"""
import re
from pathlib import Path

import pytest

from app.core import pricing as P
from app.core.legal import OFFER_REVISION

ROOT = Path(__file__).resolve().parents[2]
SRC = ROOT / "frontend" / "src"


def read(rel: str) -> str:
    return (SRC / rel).read_text(encoding="utf-8")


def frontend_sources():
    for p in SRC.rglob("*"):
        if p.suffix in {".js", ".jsx"}:
            yield p, p.read_text(encoding="utf-8")


# ------------------------------------------------------------- дата редакції

def test_offer_revision_matches_frontend():
    """Сервер пише в замовлення ту саму редакцію, що показує /offer."""
    found = re.search(r'OFFER_REVISION\s*=\s*"([^"]+)"', read("lib/legal/seller.js"))
    assert found and found.group(1) == OFFER_REVISION


def test_revision_date_is_the_published_one():
    assert OFFER_REVISION == "15 листопада 2026 року"


def test_revision_date_lives_only_in_seller_js():
    """Дата редакції — одна константа. Будь-яка дата «… 2026 року» поруч зі
    словом «редакц» деінде у фронті означала б другу, незалежну копію."""
    date_re = re.compile(r"\d{1,2} [а-яії]+ 20\d\d року")
    offenders = []
    for path, text in frontend_sources():
        if path.name == "seller.js":
            continue
        for line in text.splitlines():
            if "редакц" in line.lower() and date_re.search(line):
                offenders.append(f"{path.relative_to(SRC)}: {line.strip()}")
    assert offenders == []


def test_offer_page_and_checkout_take_revision_from_constant():
    assert "OFFER_REVISION" in read("pages/Offer.jsx")
    assert "29 вересня" not in read("pages/Offer.jsx") + read("lib/legal/offer.js")


# ------------------------------------------------------------- гарантія

OLD_THRESHOLDS = re.compile(r"\b(50|75)\s*(занять|уроків|годин)")


@pytest.mark.parametrize("rel", [
    "lib/content.js", "lib/legal/offer.js", "lib/legal/guarantee.js",
    "pages/About.jsx", "components/LevelScale.jsx", "pages/Checkout.jsx",
])
def test_no_old_guarantee_thresholds(rel):
    assert not OLD_THRESHOLDS.search(read(rel)), rel


def test_no_old_guarantee_thresholds_in_course_descriptions():
    for c in P.COURSES:
        assert not OLD_THRESHOLDS.search(c.get("desc") or ""), c["slug"]


def test_guarantee_block_matches_offer_section_9():
    content = read("lib/content.js")
    block = content[content.index("export const LEVEL_GUARANTEE"):content.index("export const CERTIFICATE_BLOCK")]
    assert '"48"' in block and '"72"' in block and "20" in block
    assert "поки не отримаєте" not in block and "кожні 10" not in block
    offer = read("lib/legal/offer.js")
    assert "48 уроків" in offer and "72 уроки" in offer and "не більше 20 додаткових уроків" in offer


# ------------------------------------------------------------- посилання на оферту

def test_footer_links_offer_next_to_privacy():
    footer = read("components/Footer.jsx")
    i_offer = footer.index('to="/offer"')
    i_privacy = footer.index('to="/privacy"')
    assert 0 < i_privacy - i_offer < 600          # в одному блоці, поруч


def test_footer_anchors_point_to_current_offer_sections():
    footer = read("components/Footer.jsx")
    sections = re.findall(r'title: "(\d+)\. ([^"]+)"', read("lib/legal/offer.js"))
    titles = {f"#p{n}": t for n, t in sections}
    assert titles["#p5"].startswith("Ціна та оплата") and 'to="/offer#p5"' in footer
    assert titles["#p10"].startswith("Повернення") and 'to="/offer#p10"' in footer
    assert titles["#p15"].startswith("Реквізити") and 'to="/offer#p15"' in footer
    assert titles["#p9"].startswith("Гарантія") and 'to="/offer#p9"' in read("pages/About.jsx")


def test_checkout_has_consent_line_with_offer_link_and_no_checkbox():
    co = read("pages/Checkout.jsx")
    assert "Оплачуючи, ви підтверджуєте, що ознайомлені та погоджуєтесь із" in co
    link = re.search(r'<Link to="/offer"[^>]*>договором публічної оферти</Link>', co)
    assert link and 'target="_blank"' in link.group(0)
    assert "offerAccepted" not in co and 'type="checkbox"' not in co.split("co__consent")[1][:400]


# ------------------------------------------------------------- IBAN

def test_iban_only_in_offer():
    iban = re.compile(r"UA\d{27}")
    shown = [p.relative_to(SRC).as_posix() for p, t in frontend_sources() if iban.search(t)]
    # seller.js — джерело, offer.js бере звідти для розділу 15. Більше ніде.
    assert shown == ["lib/legal/seller.js"]
    assert "SELLER.iban" in read("lib/legal/offer.js")
    assert "iban" not in read("pages/LegalPage.jsx").lower()


# ------------------------------------------------------------- групи

def test_groups_from_two_to_six():
    assert (P.GROUP_SIZE_MIN, P.GROUP_SIZE_MAX) == (2, 6)
    assert P.CLUB_MIN_PARTICIPANTS == 4


# ------------------------------------------------------------- цифри на головній (реклама в Meta)

def test_home_stats_have_no_unverified_results():
    """Перед рекламою прибрано «500+ студентів», «95% з першого разу» і «4 місяці до розмов».
    Тест не дає їм непомітно повернутись у блок цифр."""
    content = read("lib/content.js")
    block = content[content.index("export const STATS"):content.index("/* ============ НАПРЯМКИ")]
    for forbidden in ("500", "95", "студентів", "з першого разу", "місяці до"):
        assert forbidden not in block, forbidden
    assert "до " in block and "90" in block and "CEFR" in block        # перевірювані: CEFR, група до 6, 90 хв


def test_group_size_in_stats_matches_the_code():
    assert P.GROUP_SIZE_MAX == 6


# ------------------------------------------------------------- SEO (src/lib/seoData.js, scripts/prerender.mjs)

def seo_routes() -> dict[str, str]:
    """Маршрут → блок його опису в seoData.js."""
    text = read("lib/seoData.js")
    body = text[text.index("export const ROUTES = {"):text.index("export const NOT_FOUND")]
    return {m.group(1): m.group(2) for m in re.finditer(r'^\s+"(/[^"]*)": \{(.*?)\n?\s*\},?$', body, re.M | re.S)}


def app_routes() -> set[str]:
    paths = set(re.findall(r'<Route path="([^"]+)"', read("App.jsx")))
    return {p for p in paths if p != "*" and not p.startswith("/admin")}


def test_every_site_route_has_its_own_title_and_description():
    routes = seo_routes()
    missing = app_routes() - set(routes)
    assert missing == set(), f"маршрути без SEO-тегів у seoData.js: {missing}"
    titles = re.findall(r'title: "([^"]+)"', read("lib/seoData.js"))
    assert len(titles) == len(set(titles)), "однакові title на різних сторінках"


def test_service_pages_are_noindex_and_landing_pages_are_not():
    routes = seo_routes()
    for path in ("/thanks", "/checkout", "/payment/result"):
        assert "noindex: true" in routes[path], path
    for path in ("/", "/trial", "/packages", "/programs"):
        assert "noindex" not in routes[path], path


def test_index_html_has_the_tags_prerender_replaces():
    """scripts/prerender.mjs шукає ці теги регулярками; без них збірка в Docker падає."""
    html = (ROOT / "frontend" / "index.html").read_text(encoding="utf-8")
    for pattern in (r"<title>[\s\S]*?</title>", r'<meta\s+name="description"[\s\S]*?/>', r'<link rel="canonical"[^>]*/>',
                    r'<meta property="og:url"[^>]*/>', r'<meta property="og:title"[^>]*/>',
                    r'<meta\s+property="og:description"[\s\S]*?/>'):
        assert re.search(pattern, html), pattern


def test_no_counters_load_before_consent():
    """GA4 і Meta Pixel вантажить лише lib/analytics.js після згоди; у HTML їх бути не повинно."""
    html = (ROOT / "frontend" / "index.html").read_text(encoding="utf-8")
    assert "googletagmanager.com/gtag" not in html and "fbevents.js" not in html


def test_robots_closes_service_pages_and_points_to_sitemap():
    robots = (ROOT / "frontend" / "public" / "robots.txt").read_text(encoding="utf-8")
    for line in ("Disallow: /admin", "Disallow: /thanks", "Disallow: /checkout",
                 "Sitemap: https://my-prime-academy.com/sitemap.xml"):
        assert line in robots, line
    # sitemap.xml генерується зі seoData під час збірки, статичної копії бути не повинно
    assert not (ROOT / "frontend" / "public" / "sitemap.xml").exists()


def test_every_trial_button_leads_to_trial_page():
    """Усі кнопки «Пробний урок» ведуть на /trial, не на /contacts."""
    offenders = []
    for path, text in frontend_sources():
        for m in re.finditer(r'navigate\("/contacts"\)|to="/contacts"', text):
            around = text[m.start():m.start() + 260]
            if "робн" in around:          # «Пробний», «пробний»
                offenders.append(path.relative_to(SRC).as_posix())
    assert offenders == []


# ------------------------------------------------------------- «Покупка Частинами» на чекауті

def test_chast_shows_parts_count_and_approximate_part_without_changing_the_total():
    """Кількість частин видно завжди; частина лише орієнтовна («≈»), сума та сама, що карткою.
    Округлене «3 × 2 507 ₴» = 7 521 ₴ читалося б як зміна ціни, що заборонено правилами monobank."""
    co = read("pages/Checkout.jsx")
    assert 'data-testid="chast-parts"' in co and "chastPart(" in co and "paymentsWord(" in co
    assert "платежі по" not in co
    assert "так само, як карткою" in co
    assert "≈" in read("lib/labels.js")
    assert "Math.round(pkg.total_price / pkg.chast_max_parts)" not in read("pages/Contacts.jsx")


def test_cookie_banner_is_not_shown_in_the_cabinet():
    """Кабінет — службова частина: банер там перекривав кнопки форм на телефоні."""
    banner = read("components/CookieBanner.jsx")
    assert 'pathname.startsWith("/admin/")' in banner and 'pathname === "/admin"' in banner


def test_privacy_policy_describes_meta_and_cookie_choice():
    """Політика має збігатися з тим, що робить сайт: Meta Pixel і Conversions API за згодою,
    мітки реклами, можливість змінити вибір. Банер cookie веде на розділ 6 (/privacy#p6)."""
    privacy = read("lib/legal/privacy.js")
    for fragment in ("Meta Pixel", "Conversions API", "мітки рекламної кампанії", "хешовані",
                     "Налаштування cookie", "Поки ви не погодилися"):
        assert fragment in privacy, fragment
    assert "не передаємо їх для реклами третіх осіб" not in privacy
    assert '"6. Файли cookie"' in privacy and "privacy#p6" in read("components/CookieBanner.jsx")

"""Генерація PDF сертифіката з QR-кодом.

ЧОМУ reportlab, А НЕ HTML→PDF
=============================

Спокуса взяти wkhtmltopdf або WeasyPrint і намалювати сертифікат розміткою
велика, але для одного документа фіксованого макета це тягне в образ
цілий рендерер: WeasyPrint підтягує Pango, Cairo і купу системних бібліотек
і роздуває контейнер у рази. reportlab малює векторно, важить небагато
й дає точний контроль над міліметрами — а сертифікат друкують.

КИРИЛИЦЯ
========

Вбудовані шрифти reportlab (Helvetica й решта Type-1) **не мають кириличних
гліфів** — українські імена вийшли б чорними квадратами. Тому реєструємо
DejaVu, який лежить у системі; шлях шукаємо серед кількох типових,
бо в різних базових образах він відрізняється.

Якщо шрифт не знайдено, документ усе одно згенерується — але латиницею,
і про це буде видно з логів. Мовчазна підміна на квадрати гірша за
явний запис у лог.

QR
==

Веде на публічну сторінку перевірки з підставленим номером. Це головна
причина, чому сертифікат узагалі перевіряють: переписувати номер із PDF
руками ніхто не хоче.
"""

from __future__ import annotations

import io
import os
from datetime import datetime
from pathlib import Path

import qrcode
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4, landscape
from reportlab.lib.units import mm
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.pdfgen import canvas

from app.core import certificates as C
from app.core.config import settings

# Фірмові кольори — ті самі, що в `styles/variables.css`
VIOLET = colors.HexColor("#6D4BFF")
CYAN = colors.HexColor("#1FD6E8")
INK = colors.HexColor("#0A0A16")
MUTED = colors.HexColor("#5A5A74")
LINE = colors.HexColor("#E4E2F0")

# Тони британського знака. Свідомо приглушені: чисті #012169/#C8102A
# поруч із фірмовим фіолетовим читаються як наліпка, а не як частина макета.
UK_NAVY = colors.HexColor("#2E3A6E")
UK_RED = colors.HexColor("#B23A4C")

CERT_DIR = Path("static/certificates")

# DejaVu лежить у різних місцях залежно від базового образу.
# python:3.11-slim потребує `apt-get install fonts-dejavu-core`.
FONT_CANDIDATES = [
    "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
    "/usr/share/fonts/dejavu/DejaVuSans.ttf",
    "/usr/share/fonts/TTF/DejaVuSans.ttf",
]
FONT_BOLD_CANDIDATES = [
    "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
    "/usr/share/fonts/dejavu/DejaVuSans-Bold.ttf",
    "/usr/share/fonts/TTF/DejaVuSans-Bold.ttf",
]

_FONTS_READY = False
FONT = "Helvetica"
FONT_BOLD = "Helvetica-Bold"


def _register_fonts() -> None:
    """Підключити кириличний шрифт. Викликається один раз."""
    global _FONTS_READY, FONT, FONT_BOLD
    if _FONTS_READY:
        return

    regular = next((p for p in FONT_CANDIDATES if os.path.exists(p)), None)
    bold = next((p for p in FONT_BOLD_CANDIDATES if os.path.exists(p)), None)

    if regular and bold:
        pdfmetrics.registerFont(TTFont("DejaVu", regular))
        pdfmetrics.registerFont(TTFont("DejaVu-Bold", bold))
        FONT, FONT_BOLD = "DejaVu", "DejaVu-Bold"
    else:
        # Не падаємо, але й не мовчимо: кирилиця перетвориться на квадрати,
        # і краще побачити причину в логах, ніж ламати голову над PDF.
        print(
            "[certificate_pdf] УВАГА: DejaVu не знайдено, кирилиця не відрендериться. "
            "Додайте в Dockerfile: apt-get install -y fonts-dejavu-core"
        )

    _FONTS_READY = True


def _qr_image(url: str) -> io.BytesIO:
    qr = qrcode.QRCode(
        version=None,
        # Висока корекція: сертифікат можуть роздрукувати й зігнути,
        # а код має лишитися читабельним.
        error_correction=qrcode.constants.ERROR_CORRECT_H,
        box_size=10,
        border=1,
    )
    qr.add_data(url)
    qr.make(fit=True)
    img = qr.make_image(fill_color="#0A0A16", back_color="white")

    buf = io.BytesIO()
    img.save(buf, format="PNG")
    buf.seek(0)
    return buf


def _fmt_date(dt: datetime | None) -> str:
    if not dt:
        return ""
    months = ["січня", "лютого", "березня", "квітня", "травня", "червня",
              "липня", "серпня", "вересня", "жовтня", "листопада", "грудня"]
    return f"{dt.day} {months[dt.month - 1]} {dt.year}"


KIND_TITLE = {
    "level": "СЕРТИФІКАТ ПРО ПІДВИЩЕННЯ РІВНЯ",
    "course": "СЕРТИФІКАТ ПРО ЗАВЕРШЕННЯ КУРСУ",
    "club": "СЕРТИФІКАТ УЧАСНИКА SPEAKING CLUB",
    "corporate": "СЕРТИФІКАТ КОРПОРАТИВНОЇ ПРОГРАМИ",
    "intensive": "СЕРТИФІКАТ ПРО ПРОХОДЖЕННЯ ІНТЕНСИВУ",
}


# =============================================================================
# ДЕКОР
# =============================================================================
# Малюємо векторно, а не картинками: PDF лишається легким, масштабується
# без втрат і не залежить від зовнішніх файлів, які можуть загубитися
# при переїзді контейнера.


def _draw_corner(c, x, y, size, sx, sy):
    """Кутовий орнамент — подвійний куточок.

    sx/sy задають напрямок (1 або -1), щоб одним кодом намалювати всі чотири
    кути, а не копіювати блок чотири рази з різними знаками.
    """
    c.setStrokeColor(VIOLET)
    c.setLineWidth(1.4)
    c.line(x, y, x + sx * size, y)
    c.line(x, y, x, y + sy * size)

    c.setStrokeColor(CYAN)
    c.setLineWidth(0.6)
    off = 2.2 * mm
    c.line(x + sx * off, y + sy * off, x + sx * (size * 0.62), y + sy * off)
    c.line(x + sx * off, y + sy * off, x + sx * off, y + sy * (size * 0.62))


# Тони панорами. Свідомо константи, а не setFillAlpha: у reportlab
# setFillColor скидає альфу, тож напівпрозорість тут ламалася б від
# будь-якої перестановки рядків. Готовий світлий тон передбачуваний.
SKY_FAR = colors.HexColor("#F2EFFC")   # дальній план
SKY_NEAR = colors.HexColor("#E9E4F9")  # ближній план і вежі
SKY_LINE = colors.HexColor("#DED8F4")  # набережна


def _spire(c, cx, base, w, h):
    """Шпиль: вузький стовбур і гострий конус. З них зібрано весь гребінь."""
    c.rect(cx - w / 2, base, w, h * 0.45, fill=1, stroke=0)
    path = c.beginPath()
    path.moveTo(cx - w * 0.62, base + h * 0.45)
    path.lineTo(cx + w * 0.62, base + h * 0.45)
    path.lineTo(cx, base + h)
    path.close()
    c.drawPath(path, fill=1, stroke=0)


def _gothic_tower(c, cx, base, w, h):
    """Готична вежа Вестмінстера: стовбур, кутові пінаклі, шпиль."""
    body = h * 0.74
    c.rect(cx - w / 2, base, w, body, fill=1, stroke=0)

    # кутові пінаклі — саме вони роблять силует упізнаваним
    pw = w * 0.16
    for sx in (cx - w / 2, cx + w / 2 - pw):
        c.rect(sx, base + body, pw, h * 0.10, fill=1, stroke=0)

    path = c.beginPath()
    path.moveTo(cx - w * 0.44, base + body)
    path.lineTo(cx + w * 0.44, base + body)
    path.lineTo(cx, base + h)
    path.close()
    c.drawPath(path, fill=1, stroke=0)


def _draw_skyline(c, x0, y0, width, height):
    """Панорама Вестмінстера світлим фоном по низу аркуша.

    Малюється ПЕРШОЮ, одразу після рамки: увесь текст, печатка і QR лягають
    поверх. Через це QR зберігає білу підкладку й лишається читабельним
    для камери.

    Попередній варіант — маленький Біг-Бен у правому куті шапки — читався
    як іконка поруч із логотипом, а не як частина документа.
    """
    c.saveState()

    # --- дальній план: низька забудова обабіч ------------------------------
    c.setFillColor(SKY_FAR)
    for off, w_, h_ in (
        (0.005, 0.055, 0.22), (0.735, 0.085, 0.30),
        (0.825, 0.065, 0.42), (0.895, 0.100, 0.25),
    ):
        c.rect(x0 + width * off, y0, width * w_, height * h_, fill=1, stroke=0)

    # --- корпус Парламенту --------------------------------------------------
    c.setFillColor(SKY_NEAR)
    body_x = x0 + width * 0.10
    body_w = width * 0.50
    body_h = height * 0.36
    c.rect(body_x, y0, body_w, body_h, fill=1, stroke=0)

    # Гребінь шпилів. Ритм повторюваних вертикалей — головна прикмета
    # будівлі; без нього вийшла б просто коробка.
    for i in range(13):
        sx = body_x + body_w * (i + 0.5) / 13
        tall = i % 2 == 0
        _spire(c, sx, y0 + body_h, width * 0.009,
               height * (0.16 if tall else 0.10))

    # --- Вікторія-тауер, ліворуч -------------------------------------------
    _gothic_tower(c, x0 + width * 0.075, y0, width * 0.050, height * 0.66)

    # --- Біг-Бен ------------------------------------------------------------
    bb_x = x0 + width * 0.60
    bb_w = width * 0.030
    bb_h = height * 1.06

    c.rect(bb_x - bb_w / 2, y0, bb_w, bb_h * 0.66, fill=1, stroke=0)

    # ярус циферблата ширший за стовбур — це його впізнають першим
    cl_y = y0 + bb_h * 0.66
    cl_h = bb_h * 0.12
    c.rect(bb_x - bb_w * 0.66, cl_y, bb_w * 1.32, cl_h, fill=1, stroke=0)

    # циферблат вирізаний світлішим тоном, без стрілок:
    # у такому масштабі стрілки читалися б як бруд
    c.setFillColor(colors.white)
    c.circle(bb_x, cl_y + cl_h / 2, cl_h * 0.30, fill=1, stroke=0)
    c.setFillColor(SKY_FAR)
    c.circle(bb_x, cl_y + cl_h / 2, cl_h * 0.30, fill=1, stroke=0)

    # дзвіниця й шпиль
    c.setFillColor(SKY_NEAR)
    b_y = cl_y + cl_h
    b_h = bb_h * 0.09
    c.rect(bb_x - bb_w * 0.58, b_y, bb_w * 1.16, b_h, fill=1, stroke=0)
    for sx in (bb_x - bb_w * 0.58, bb_x + bb_w * 0.58 - bb_w * 0.12):
        c.rect(sx, b_y + b_h, bb_w * 0.12, bb_h * 0.04, fill=1, stroke=0)
    path = c.beginPath()
    path.moveTo(bb_x - bb_w * 0.50, b_y + b_h)
    path.lineTo(bb_x + bb_w * 0.50, b_y + b_h)
    path.lineTo(bb_x, y0 + bb_h)
    path.close()
    c.drawPath(path, fill=1, stroke=0)

    # --- лінія набережної ---------------------------------------------------
    c.setFillColor(SKY_LINE)
    c.rect(x0, y0 - 1.0 * mm, width, 0.9 * mm, fill=1, stroke=0)

    c.restoreState()


def _draw_circular_text(c, cx, cy, radius, text, font, size, color, top=True):
    """Текст по колу — для печатки.

    reportlab не вміє цього з коробки: кожен символ повертаємо окремо
    навколо центра. Знизу букви йдуть у зворотному порядку й перевернуті,
    інакше читалися б догори ногами.
    """
    import math
    c.setFont(font, size)
    c.setFillColor(color)

    widths = [pdfmetrics.stringWidth(ch, font, size) for ch in text]
    total = sum(widths)
    arc = total / radius                  # кут, який займе весь рядок
    angle = (math.pi / 2 + arc / 2) if top else (-math.pi / 2 - arc / 2)

    for ch, w in zip(text, widths):
        step = w / radius
        a = angle - step / 2 if top else angle + step / 2
        c.saveState()
        c.translate(cx + radius * math.cos(a), cy + radius * math.sin(a))
        rot = math.degrees(a) + (-90 if top else 90)
        c.rotate(rot)
        c.drawCentredString(0, 0, ch)
        c.restoreState()
        angle = angle - step if top else angle + step


def _draw_seal(c, cx, cy, r, year):
    """Печатка школи.

    Не імітує державну: без тризуба, без «мокрого» вигляду й без слова
    «печатка». Це фірмовий знак — те, що ставлять на дипломи мовні школи
    по всьому світу, і чого бракувало документу, щоб виглядати завершеним.
    """
    c.saveState()
    c.setFillAlpha(0.92)

    c.setStrokeColor(VIOLET)
    c.setLineWidth(1.5)
    c.circle(cx, cy, r, fill=0, stroke=1)

    c.setLineWidth(0.5)
    c.circle(cx, cy, r * 0.86, fill=0, stroke=1)

    c.setStrokeColor(CYAN)
    c.setLineWidth(0.4)
    c.circle(cx, cy, r * 0.58, fill=0, stroke=1)

    _draw_circular_text(c, cx, cy, r * 0.72, "PRIME ACADEMY",
                        FONT_BOLD, 6.2, VIOLET, top=True)
    _draw_circular_text(c, cx, cy, r * 0.72, "ONLINE ENGLISH SCHOOL",
                        FONT, 5, VIOLET, top=False)

    # зірочки-роздільники по боках
    c.setFillColor(CYAN)
    for dx in (-r * 0.74, r * 0.74):
        c.setFont(FONT_BOLD, 6)
        c.drawCentredString(cx + dx, cy - 2, "\u2726")

    # центр: монограма й рік
    c.setFillColor(VIOLET)
    c.setFont(FONT_BOLD, 13)
    c.drawCentredString(cx, cy + 1.2 * mm, "PA")
    c.setFont(FONT, 6)
    c.drawCentredString(cx, cy - 2.6 * mm, str(year))

    c.restoreState()


# Лого лежить ВСЕРЕДИНІ бекенда. Раніше шлях вів у `../frontend/src/assets/`,
# але Dockerfile копіює лише теку `backend/` — у контейнері такого шляху немає,
# і лого мовчки не малювалося. Копія у `app/assets/` їде разом із кодом.
#
# Якщо оновлюєте логотип — оновіть обидва файли:
#   frontend/src/assets/icons/logo_circle.png  (сайт та іконки)
#   backend/app/assets/logo.png                (сертифікати)
LOGO_FILE = Path(__file__).resolve().parent.parent / "assets" / "logo.png"


def _draw_union_flag(c, x, y, w):
    """Британський прапор як декоративний знак у шапці.

    Робиться через відсічний контур: діагоналі виходять за межі поля,
    і без `clipPath` вони лізли б на решту аркуша.

    Пропорції 2:1 — офіційні. Знак **декоративний**: стоїть окремо від
    будь-яких формулювань про видачу документа, щоб не читався як чужа
    акредитація. Документ видає українська школа, і це сказано текстом.
    """
    h = w / 2
    c.saveState()

    clip = c.beginPath()
    clip.rect(x, y, w, h)
    c.clipPath(clip, stroke=0, fill=0)

    c.setFillColor(UK_NAVY)
    c.rect(x, y, w, h, fill=1, stroke=0)

    cx, cy = x + w / 2, y + h / 2

    # --- діагоналі ----------------------------------------------------------
    c.setStrokeColor(colors.white)
    c.setLineWidth(h * 0.30)
    c.line(x, y, x + w, y + h)
    c.line(x, y + h, x + w, y)

    # Червоні діагоналі зміщені перпендикулярно й розрізані по центру —
    # це «контрзміна» справжнього прапора. Без зсуву виходить симетричний
    # хрест, якого на прапорі немає.
    off = h * 0.07
    c.setStrokeColor(UK_RED)
    c.setLineWidth(h * 0.10)
    for sx, sy, ex, ey in (
        (x, y, x + w, y + h),
        (x, y + h, x + w, y),
    ):
        dx, dy = ex - sx, ey - sy
        n = (dx * dx + dy * dy) ** 0.5
        px, py = -dy / n * off, dx / n * off
        c.line(sx + px, sy + py, cx + px, cy + py)
        c.line(cx - px, cy - py, ex - px, ey - py)

    # --- прямий хрест святого Георгія ---------------------------------------
    c.setStrokeColor(colors.white)
    c.setLineWidth(h * 0.34)
    c.line(x, cy, x + w, cy)
    c.line(cx, y, cx, y + h)

    c.setStrokeColor(UK_RED)
    c.setLineWidth(h * 0.20)
    c.line(x, cy, x + w, cy)
    c.line(cx, y, cx, y + h)

    c.restoreState()

    # тонка рамка: без неї світлі краї прапора зливаються з аркушем
    c.setStrokeColor(LINE)
    c.setLineWidth(0.5)
    c.rect(x, y, w, h, fill=0, stroke=1)


def _draw_divider(c, cx, y, half):
    """Розділювач із ромбом посередині.

    Закриває порожнечу між шапкою й назвою документа. Тонкі лінії
    з розривом читаються як поліграфія, суцільна риска — як межа таблиці.
    """
    gap = 4 * mm
    c.setStrokeColor(LINE)
    c.setLineWidth(0.6)
    c.line(cx - half, y, cx - gap, y)
    c.line(cx + gap, y, cx + half, y)

    d = 1.6 * mm
    c.setFillColor(VIOLET)
    path = c.beginPath()
    path.moveTo(cx, y + d)
    path.lineTo(cx + d, y)
    path.lineTo(cx, y - d)
    path.lineTo(cx - d, y)
    path.close()
    c.drawPath(path, fill=1, stroke=0)

    for s in (-1, 1):
        c.setFillColor(LINE)
        c.circle(cx + s * (d + 2.2 * mm), y, 0.8 * mm, fill=1, stroke=0)


def build_pdf(cert, logo_path: str | None = None) -> bytes:
    """Намалювати сертифікат. Повертає готові байти PDF."""
    _register_fonts()

    buf = io.BytesIO()
    W, H = landscape(A4)          # 297 × 210 мм
    c = canvas.Canvas(buf, pagesize=landscape(A4))
    c.setTitle(f"Prime Academy · {cert.serial_number}")

    # --- рамка ---------------------------------------------------------------
    # Тонка подвійна рамка замість «золотих завитків»: документ має
    # виглядати як документ, а не як грамота з канцелярії.
    c.setStrokeColor(LINE)
    c.setLineWidth(0.7)
    c.rect(12 * mm, 12 * mm, W - 24 * mm, H - 24 * mm)
    c.setLineWidth(2.2)
    c.setStrokeColor(VIOLET)
    c.line(12 * mm, H - 12 * mm, W - 12 * mm, H - 12 * mm)

    # Панорама Вестмінстера фоном. Малюється ПЕРШОЮ — усе інше лягає поверх,
    # тож QR зберігає білу підкладку й лишається читабельним.
    _draw_skyline(c, 15 * mm, 17 * mm, W - 30 * mm, 40 * mm)

    # кутові орнаменти
    m, s = 14 * mm, 8 * mm
    _draw_corner(c, m, m, s, 1, 1)
    _draw_corner(c, W - m, m, s, -1, 1)
    _draw_corner(c, m, H - m, s, 1, -1)
    _draw_corner(c, W - m, H - m, s, -1, -1)



    # --- шапка ---------------------------------------------------------------
    # Координати абсолютні, а не накопичувальні. Перша версія віднімала
    # відступи послідовно, і будь-яка зміна в середині зсувала все нижче —
    # через це в макеті зʼявилася діра, а деталі злиплися з номером.

    if logo_path is None:
        logo_path = str(LOGO_FILE)

    if os.path.exists(logo_path):
        try:
            c.drawImage(logo_path, 24 * mm, H - 38 * mm, width=17 * mm, height=17 * mm,
                        mask="auto", preserveAspectRatio=True)
        except Exception:
            pass   # відсутнє лого — не причина не видати документ

    c.setFont(FONT_BOLD, 14)
    c.setFillColor(INK)
    c.drawString(46 * mm, H - 28 * mm, "PRIME ACADEMY")
    c.setFont(FONT, 8.5)
    c.setFillColor(MUTED)
    c.drawString(46 * mm, H - 33 * mm, "Онлайн школа англійської мови")

    # Британський знак навпроти лого — шапка була порожньою праворуч.
    _draw_union_flag(c, W - 46 * mm, H - 33 * mm, 22 * mm)

    # Розділювач між шапкою й назвою документа
    _draw_divider(c, W / 2, H - 47 * mm, 46 * mm)

    # --- тип документа -------------------------------------------------------
    c.setFont(FONT_BOLD, 10)
    c.setFillColor(VIOLET)
    kind = getattr(cert.kind, "value", cert.kind)
    c.drawCentredString(W / 2, H - 58 * mm, KIND_TITLE.get(kind, "СЕРТИФІКАТ"))

    # --- імʼя ----------------------------------------------------------------
    c.setFont(FONT, 10.5)
    c.setFillColor(MUTED)
    c.drawCentredString(W / 2, H - 74 * mm, "цим підтверджується, що")

    # Довге прізвище не має вилізти за поля — зменшуємо кегль, поки не влізе
    name = cert.student_full_name or ""
    size = 29
    while size > 13 and pdfmetrics.stringWidth(name, FONT_BOLD, size) > W - 74 * mm:
        size -= 1
    c.setFont(FONT_BOLD, size)
    c.setFillColor(INK)
    c.drawCentredString(W / 2, H - 89 * mm, name)

    c.setStrokeColor(LINE)
    c.setLineWidth(0.6)
    c.line(W / 2 - 62 * mm, H - 94 * mm, W / 2 + 62 * mm, H - 94 * mm)

    # --- курс ----------------------------------------------------------------
    # Формулювання залежить від типу: «завершив програму» не пасує
    # ані клубу, ані корпоративній програмі компанії.
    lead = {
        "club": "брав(-ла) участь у розмовному клубі",
        "corporate": "пройшов(-ла) корпоративну програму",
        "intensive": "пройшов(-ла) інтенсив",
    }.get(kind, "успішно завершив(-ла) програму")

    c.setFont(FONT, 10.5)
    c.setFillColor(MUTED)
    c.drawCentredString(W / 2, H - 106 * mm, lead)

    course = cert.course_title or ""
    size = 14
    while size > 9 and pdfmetrics.stringWidth(course, FONT_BOLD, size) > W - 84 * mm:
        size -= 1
    c.setFont(FONT_BOLD, size)
    c.setFillColor(INK)
    c.drawCentredString(W / 2, H - 115 * mm, course)

    # --- прогрес рівнів ------------------------------------------------------
    # Головне на сертифікаті мовної школи: не «пройшов курс»,
    # а з якого рівня на який людина перейшла.
    if cert.level_from and cert.level_to:
        c.setFont(FONT_BOLD, 18)
        c.setFillColor(VIOLET)
        c.drawCentredString(W / 2, H - 133 * mm, f"{cert.level_from}  \u2192  {cert.level_to}")
        c.setFont(FONT, 8.5)
        c.setFillColor(MUTED)
        c.drawCentredString(W / 2, H - 140 * mm, "рівень за шкалою CEFR")
    elif cert.level_to:
        c.setFont(FONT_BOLD, 18)
        c.setFillColor(VIOLET)
        c.drawCentredString(W / 2, H - 133 * mm, f"Рівень {cert.level_to}")

    # --- деталі ліворуч ------------------------------------------------------
    # Починаємо достатньо високо, щоб чотири рядки не дістали до номера
    # внизу: раніше вони злипалися з ним в один блок.
    details = []
    if cert.lessons_count:
        details.append(f"Занять: {cert.lessons_count}")
    if cert.hours:
        details.append(f"Годин: {cert.hours}")
    if cert.started_at and cert.finished_at:
        details.append(f"Період: {_fmt_date(cert.started_at)} \u2014 {_fmt_date(cert.finished_at)}")
    if cert.teacher_name:
        details.append(f"Викладач: {cert.teacher_name}")

    c.setFont(FONT, 9)
    c.setFillColor(MUTED)
    for i, line in enumerate(details):
        c.drawString(24 * mm, 62 * mm - i * 5.5 * mm, line)

    # --- підпис по центру ----------------------------------------------------
    c.setStrokeColor(LINE)
    c.setLineWidth(0.6)
    c.line(W / 2 - 28 * mm, 38 * mm, W / 2 + 28 * mm, 38 * mm)
    c.setFont(FONT, 9)
    c.setFillColor(MUTED)
    c.drawCentredString(W / 2, 32 * mm, cert.issued_by or "Prime Academy")

    # Печатка між підписом і QR — саме там її й шукають очима на дипломі
    year = cert.issued_at.year if cert.issued_at else datetime.utcnow().year
    _draw_seal(c, W - 84 * mm, 44 * mm, 16 * mm, year)

    # --- QR праворуч ---------------------------------------------------------
    verify = C.verify_url(cert.serial_number, settings.site_url)
    qr_size = 28 * mm
    qr_x = W - 24 * mm - qr_size
    qr_y = 26 * mm

    try:
        from reportlab.lib.utils import ImageReader
        c.drawImage(ImageReader(_qr_image(verify)), qr_x, qr_y,
                    width=qr_size, height=qr_size, mask="auto")
    except Exception as exc:
        print(f"[certificate_pdf] QR не намальовано: {exc}")

    c.setFont(FONT, 7.5)
    c.setFillColor(MUTED)
    c.drawCentredString(qr_x + qr_size / 2, 22 * mm, "Перевірити справжність")

    # --- номер і дата --------------------------------------------------------
    c.setFont(FONT_BOLD, 10.5)
    c.setFillColor(INK)
    c.drawString(24 * mm, 33 * mm, cert.serial_number)

    c.setFont(FONT, 8)
    c.setFillColor(MUTED)
    c.drawString(24 * mm, 28 * mm, f"Видано {_fmt_date(cert.issued_at)}")
    c.drawString(24 * mm, 23.5 * mm, verify)

    c.showPage()
    c.save()
    buf.seek(0)
    return buf.read()


def save_pdf(cert, logo_path: str | None = None) -> str:
    """Згенерувати й зберегти. Повертає публічний URL файлу."""
    CERT_DIR.mkdir(parents=True, exist_ok=True)

    # Імʼя файлу з номера: документ легко знайти на диску за номером
    # із звернення клієнта, не лазячи в базу.
    filename = f"{cert.serial_number}.pdf"
    (CERT_DIR / filename).write_bytes(build_pdf(cert, logo_path))

    return f"/static/certificates/{filename}"

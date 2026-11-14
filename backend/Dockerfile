FROM python:3.12-slim

WORKDIR /app

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    # Мережа до PyPI буває нестабільною: без цих значень збірка падає
    # з «Could not find a version that satisfies the requirement …
    # (from versions: none)» просто через обрив з'єднання.
    PIP_DEFAULT_TIMEOUT=120 \
    PIP_RETRIES=10 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    PIP_NO_CACHE_DIR=1

# Кириличний шрифт для PDF-сертифікатів. Вбудовані шрифти reportlab
# не мають кириличних гліфів — українські імена вийшли б квадратами.
RUN apt-get update \
 && apt-get install -y --no-install-recommends fonts-dejavu-core \
 && rm -rf /var/lib/apt/lists/*

COPY requirements.txt requirements.lock ./

# Свідомо НЕ робимо `pip install --upgrade pip`: це підтягує іншу версію pip
# при кожній збірці, тобто образ перестає бути відтворюваним, а поведінка
# резолвера може змінитися між двома однаковими білдами.
#
# requirements.lock - точні версії всіх пакетів (включно з транзитивними). Без нього кожна
# перезбірка образу тягне "найсвіжіше", і так уже ламалися bcrypt, greenlet і PyJWT
# (вхід в адмінку давав 401). Оновлювати свідомо: `make lock`, потім тести.
RUN pip install -r requirements.txt -c requirements.lock

COPY . .

# Правильний шлях до застосунку — app.main, а не main.
# Раніше тут було `main:app`, що просто не запустилося б; рятувало лише те,
# що docker-compose перевизначає команду своїм `command:`.
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]

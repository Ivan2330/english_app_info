# Оновлення сервера

Локальний `backend/.env` переведений на production-адреси;
`PAYMENTS_ENABLED=true`. За вказівкою власника активовані бойові
`MONO_CHAST_STORE_ID` і `MONO_CHAST_SIGN_KEY`, які були в коментарях.
Адреса ПЧ — `https://u2.monobank.com.ua`. `MONO_PLATA_TOKEN` збережено.
Бойові ключі ПЧ активовані в конфігурації, але реальна оплата ними не перевірялася.

На сервері зберегти чинні `POSTGRES_USER`, `POSTGRES_PASSWORD`, `POSTGRES_DB`,
`DATABASE_URL`, `SECRET_KEY` та облікові дані адміністратора.
Локальна база `prime_dev` не підтверджена як серверна. Не копіювати її
реквізити поверх серверних навмання. У Docker хост БД — `db`, не `localhost`.
Зміна POSTGRES_PASSWORD у файлі не змінює пароль на існуючому томі БД.

## Команди у каталозі репозиторію на сервері

Спочатку зберегти старий env і дамп працюючої БД, потім відредагувати env:

```bash
set -e
umask 077
mkdir -p backups
stamp=$(date +%Y%m%d-%H%M%S)
cp backend/.env "backups/backend.env.$stamp"
docker compose exec -T db sh -c 'pg_dump -U "$POSTGRES_USER" -d "$POSTGRES_DB" -Fc' > "backups/database.$stamp.dump"
nano backend/.env
chmod 600 backend/.env
```

Production-значення, які потрібно внести:

```dotenv
APP_ENV=production
DEBUG_SQL=false
AUTO_CREATE_TABLES=false
SITE_URL=https://my-prime-academy.com
ALLOWED_ORIGINS=https://my-prime-academy.com,https://www.my-prime-academy.com
MONO_PLATA_BASE_URL=https://api.monobank.ua
MONO_CHAST_BASE_URL=https://u2.monobank.com.ua
PAYMENTS_ENABLED=true
```

Токени й ключі переносити вручну, без публікації в Git.
Після збереження env, коли зміни коду вже закомічені й відправлені у remote:

```bash
git pull --ff-only
docker compose build backend nginx
# Backend має bind mount коду: зупиняємо його перед зміною схеми.
docker compose stop backend
docker compose run --rm --no-deps backend alembic upgrade head
docker compose up -d --no-deps --force-recreate backend
docker compose up -d --no-deps --force-recreate nginx
docker compose ps
docker compose exec backend alembic current
docker compose logs --tail=80 backend nginx
```

Міграція має бути `0008_payment_refunds`. При помилці міграції не переходити
до запуску нової версії. Команди не видаляють том БД. `down -v` не потрібен.
`restart` недостатньо для зміни env: потрібен `up --force-recreate`.

Коли бойові ключі обох продуктів внесені, встановити
`PAYMENTS_ENABLED=true` та застосувати:

```bash
docker compose up -d --no-deps --force-recreate backend
```

Відкрити `/payment/result` прямим посиланням і виконати контрольне замовлення
через checkout: повернення з банку та статус paid у кабінеті.
Оновлення каталогу через seed-packages — окрема зміна цін; ця інструкція
не перезаписує каталог і не вмикає тестові ключі на production.

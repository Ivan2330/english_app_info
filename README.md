# Prime Academy

Сайт онлайн-школи англійської: FastAPI + PostgreSQL на бекенді, React + Vite на фронті,
nginx і Let's Encrypt на проді.

---

## Швидкий старт (локально)

Треба мати Docker і Node 18+.

```bash
# 1. Налаштування бекенду
cp backend/.env.example backend/.env
#    За замовчуванням усе вже робоче — можна нічого не міняти.
#    Хіба що admin_email / admin_password під себе.

# 2. База + бекенд у докері (міграції прогоняються автоматично)
docker compose -f docker-compose.dev.yml up -d --build

# 3. Наповнити каталог пакетів із тарифної сітки
docker compose -f docker-compose.dev.yml exec backend python -m app.cli seed-packages

# 4. Фронт — окремо, з гарячим перезавантаженням
cd frontend
npm install
npm run dev
```

Готово:

| Що | Де |
|---|---|
| Сайт | http://localhost:5173 |
| API | http://localhost:8000 |
| Swagger | http://localhost:8000/docs |
| Postgres | `localhost:5433`, база `prime_dev`, `postgres` / `postgres` |

> Порт **5433**, а не стандартний 5432 — щоб не конфліктувати з нативним
> PostgreSQL, який часто вже стоїть на машині як служба. Усередині docker-мережі
> база слухає звичайний 5432, тож `DATABASE_URL` міняти не треба.

### Якщо порт зайнятий

`Bind for 0.0.0.0:8000 failed: port is already allocated` — щось інше вже слухає цей порт.

Знайти винуватця:

```powershell
netstat -ano | findstr :8000        # останнє число — PID
tasklist /FI "PID eq <PID>"         # хто це
```

Або підняти бекенд на іншому порту, не шукаючи:

```powershell
$env:BACKEND_PORT=8001
docker compose -f docker-compose.dev.yml up -d
```

І тоді сказати фронту, куди ходити — `frontend/.env.local`:

```
VITE_API_URL=http://localhost:8001
```

Логін в адмінку — той, що вказаний у `backend/.env` як `admin_email` / `admin_password`.
Він створюється автоматично при першому старті, якщо в базі ще немає жодного адміна.

### Корисні команди

```bash
# логи бекенду
docker compose -f docker-compose.dev.yml logs -f backend

# перезапустити тільки бекенд
docker compose -f docker-compose.dev.yml restart backend

# зайти в базу
docker compose -f docker-compose.dev.yml exec db psql -U postgres -d prime_dev

# підключитись до бази ззовні (DBeaver / psql):
#   host localhost, port 5433, db prime_dev, user postgres, pass postgres

# знести базу і почати з нуля
docker compose -f docker-compose.dev.yml down -v
docker compose -f docker-compose.dev.yml up -d
docker compose -f docker-compose.dev.yml exec backend python -m app.cli seed-packages
```

### Без докера взагалі

Якщо Postgres уже стоїть на машині:

```bash
cd backend
python -m venv .venv && source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -r requirements.txt

# у backend/.env замінити host на localhost:
# DATABASE_URL=postgresql+asyncpg://postgres:postgres@localhost:5432/prime_dev

alembic upgrade head
python -m app.cli seed-packages
uvicorn app.main:app --reload
```

---

## Ціни та каталог пакетів

**Уся тарифна сітка живе в одному файлі: `backend/app/core/pricing.py`.**
Більше ніде цін немає — ні в базі як «джерела правди», ні у фронті.

Щоб змінити ціну:

```bash
# 1. правимо backend/app/core/pricing.py
# 2. дивимось, що вийшло, НЕ чіпаючи базу:
docker compose -f docker-compose.dev.yml exec backend python -m app.cli show-catalogue
# 3. застосовуємо:
docker compose -f docker-compose.dev.yml exec backend python -m app.cli seed-packages
```

`seed-packages` робить upsert за `slug`. Пакети, яких більше немає в сітці,
не видаляються, а деактивуються (`is_active = false`) — щоб не ламати посилання
та історію замовлень.

### Структура каталогу

Чотири незалежні осі замість колишніх `type` + `audience`:

| Поле | Значення | Що означає |
|---|---|---|
| `family` | `subscription` · `course` · `club` · `corporate` | тип продукту |
| `audience` | `adults` · `teens` · `kids` · `corporate` | для кого |
| `format` | `individual` · `pair` · `group` · `club` | як вчимося |
| `track` | `general` · `speaking` · `business` · `school` · `nmt` · `exam` · `job_ready` · `it` · `travel` | що вивчаємо |

Тарифного рівня Standard/Premium **більше немає**. Апсейл іде через тематичні
курси (`family=course`), а не через абстрактний «рівень сервісу».

Приклад запиту з фронту:

```
GET /api/packages?family=subscription&audience=adults&format=group&track=general
GET /api/packages/filters      # які комбінації реально існують
GET /api/packages/{slug}
```

### Тривалість уроку

Різна за форматом, тому зберігається числом (`lesson_duration_min`):

| | Дорослі та підлітки | Діти 7–12 |
|---|---|---|
| Індивідуально | 50 хв | 40 хв |
| У парі | 50 хв | 40 хв |
| Група (до 6) | 90 хв | 60 хв |

Ціна парного формату вказана **за одну людину** (`price_per_person = true`).

---

## Міграції

Схемою керує Alembic. `create_all()` більше не викликається — він уміє лише
створювати відсутні таблиці й не робить `ALTER`, тому нові колонки просто
не з'являлися б у наявній базі.

```bash
cd backend

alembic upgrade head            # накотити
alembic downgrade -1            # відкотити на крок
alembic history                 # список ревізій
alembic revision --autogenerate -m "опис"   # згенерувати нову після правки моделі
```

> Автозгенеровану ревізію **обов'язково читати руками** перед застосуванням.
> Alembic часто не бачить перейменувань і оформлює їх як `drop` + `add`,
> тобто з втратою даних.

### Накатити на вже існуючу базу

Якщо база створена старим `create_all()` і таблиці вже є, першу ревізію
треба не виконувати, а позначити як пройдену:

```bash
alembic stamp 0001_baseline
alembic upgrade head
```

---

## Прод

```bash
docker compose up -d --build
```

⚠️ **Перед першим запуском після цих змін** прогнати міграції — автостворення
таблиць прибрано, само воно вже не запуститься:

```bash
docker compose exec backend alembic upgrade head
docker compose exec backend python -m app.cli seed-packages
```

У `docker-compose.yml` міграції поки що **не** вбудовані в `command` — щоб
не чіпати файл, у якому є незакомічені правки. Коли будеш готовий, у сервіс
`backend` варто підставити:

```yaml
command: >
  sh -c "alembic upgrade head &&
         uvicorn app.main:app --host 0.0.0.0 --port 8000"
```

---

## Структура

```
backend/
  alembic/                  міграції
  app/
    api/public/             відкриті ендпоінти
    api/admin/              адмінка (кукі-сесія)
    core/
      pricing.py            ← ТАРИФНА СІТКА, єдине джерело правди по цінах
      seed_packages.py      генератор каталогу зі сітки
      bootstrap_admin.py    створення першого адміна
    models/                 SQLAlchemy-моделі
    cli.py                  разові команди
frontend/
  src/pages/                сторінки
  src/components/           компоненти
  styles/                   CSS (без фреймворка)
nginx/                      конфіг і сертифікати (тільки прод)
```

---

## Що варто знати про поточний стан

**`backend/.env` лежить у git.** Там `SECRET_KEY`, пароль бази й пароль адміна.
Прибрати з індексу (файл на диску залишиться):

```bash
git rm --cached backend/.env
git commit -m "прибрати .env з репозиторію"
```

Після цього **провернути секрети** — старі значення назавжди лишаються в історії git.

**Перенос рядків.** У репозиторії змішані CRLF і LF, через що `git diff` показує
цілі файли як змінені. Щоб дивитись реальні правки:

```bash
git diff --ignore-cr-at-eol
```

**Оплати ще немає.** Ні моделі замовлення, ні платежу. monobank Покупка Частинами
й plata by mono — наступний етап. У моделі пакета вже є `chast_enabled`
і `chast_max_parts`: ПЧ вмикається не глобально, а по кожному пакету, бо на
великих сумах комісія з'їдає маржу, а особистий ліміт клієнта їх однаково
не пропускає.

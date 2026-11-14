# Як вносити зміни

Правило одне: **у `main` нічого не потрапляє напряму**. Кожна зміна йде
окремою гілкою, через Pull Request, і зливається лише коли CI зелений.

## Гілки

Від свіжого `main`, імʼя за типом зміни:

| Префікс | Для чого | Приклад |
|---|---|---|
| `feat/` | нова можливість | `feat/phase1-pricing-grid` |
| `fix/` | виправлення помилки | `fix/chast-callback-signature` |
| `chore/` | інфраструктура, залежності, CI | `chore/dev-workflow` |
| `docs/` | лише документація | `docs/deploy-steps` |

Одна гілка — одна тема. Два незалежні зміни — два PR.

## Коміти

Формат [Conventional Commits](https://www.conventionalcommits.org/):
`тип(область): що зроблено`, англійською, в наказовому способі.

    feat(pricing): add three group plans
    fix(orders): count only paid orders for purchase index
    docs: record phase 1 decisions

Тіло коміту пояснює **чому**, а не що: що видно з diff.

## Pull Request

1. `make check` локально (бекенд-тести + збірка фронту).
2. Пуш гілки, PR у `main`, заповнити шаблон.
3. CI має бути зеленим. Червоний PR не зливаємо.
4. Squash-merge, щоб історія `main` лишалась читабельною.

## Тести

| Команда | Що робить | Час |
|---|---|---|
| `make test` | бекенд-тести на всіх ядрах, SQLite, без Docker | ~12 с |
| `make test-pg` | те саме + PostgreSQL: міграції, дашборд (потрібен `make up`) | ~20 с |
| `make cov` / `make check-all` | як CI: Postgres + покриття, нижче 95% падає | ~35 с |

Кожен тест має власну базу, тому набір безпечно ганяти паралельно.
Тести ніколи не ходять у справжній банк і не читають ваші ключі з `.env`.
Тести PostgreSQL створюють власні бази `pa_test_*` / `pa_mig_*`, а `prime_dev` не чіпають.

Нова логіка без тестів не пройде поріг покриття. Для змін у грошах (`orders.py`,
`chast.py`, `plata.py`, знижки, ціни) тест обов'язковий, а не бажаний.

## Чого не роблять у PR

- Не комітять `.env`, ключі, токени (CI це блокує).
- Не міняють `PAYMENTS_ENABLED` і ключі оплати.
- Не пишуть ціни ніде, окрім `backend/app/core/pricing.py`.

## Налаштування репозиторію на GitHub (один раз, вручну)

Settings → Branches → Add branch ruleset для `main`:

- Require a pull request before merging
- Require status checks to pass: **Backend tests (py3.12)**, **Frontend build**, **No secrets in diff**
- Block force pushes

Settings → General → Pull Requests: увімкнути лише «Allow squash merging»
і «Automatically delete head branches».

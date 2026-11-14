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

## Чого не роблять у PR

- Не комітять `.env`, ключі, токени (CI це блокує).
- Не міняють `PAYMENTS_ENABLED` і ключі оплати.
- Не пишуть ціни ніде, окрім `backend/app/core/pricing.py`.

## Налаштування репозиторію на GitHub (один раз, вручну)

Settings → Branches → Add branch ruleset для `main`:

- Require a pull request before merging
- Require status checks to pass: **Backend tests**, **Frontend build**, **No secrets in diff**
- Block force pushes

Settings → General → Pull Requests: увімкнути лише «Allow squash merging»
і «Automatically delete head branches».

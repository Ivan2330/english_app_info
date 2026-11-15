"""CLI для разових операцій.

    python -m app.cli seed-packages     # наповнити каталог із тарифної сітки
    python -m app.cli create-admin      # створити owner-а; пароль вводиться інтерактивно
    python -m app.cli show-catalogue    # надрукувати каталог, нічого не пишучи в базу

У docker:
    docker compose exec backend python -m app.cli seed-packages
"""

from __future__ import annotations

import asyncio
import sys

from app.db.database import async_session_maker


async def _wait_for_tables(timeout: int = 60) -> None:
    """Чекає, поки Alembic створить таблиці.

    `docker compose up -d` повертає керування, щойно контейнер стартував —
    а міграції всередині ще виконуються. Без цієї паузи сід, запущений одразу
    після up, падає з «relation "packages" does not exist».
    """
    from sqlalchemy import text

    deadline = asyncio.get_event_loop().time() + timeout
    while True:
        try:
            async with async_session_maker() as session:
                await session.execute(text("SELECT 1 FROM packages LIMIT 1"))
            return
        except Exception as exc:
            if asyncio.get_event_loop().time() > deadline:
                print(
                    "Таблиці так і не з'явилися. Схоже, міграції не пройшли.\n"
                    "Подивіться логи:  docker compose -f docker-compose.dev.yml logs backend\n"
                    "Або прожените вручну:  alembic upgrade head\n"
                    f"\nОстання помилка: {type(exc).__name__}"
                )
                sys.exit(1)
            print("Чекаю на міграції…")
            await asyncio.sleep(2)


async def _seed_packages() -> None:
    from app.core.seed_packages import seed_packages
    await _wait_for_tables()
    async with async_session_maker() as session:
        result = await seed_packages(session)
    print(
        f"Каталог оновлено: створено {result['created']}, "
        f"оновлено {result['updated']}, деактивовано {result['deactivated']}. "
        f"Усього в сітці — {result['total']}."
    )


def _ask_owner(ask=input, ask_secret=None) -> tuple[str, str, str]:
    """Пошта, імʼя й пароль з консолі. Пароль не відображається і не потрапляє в історію shell."""
    import getpass
    from app.core.config import settings
    ask_secret = ask_secret or getpass.getpass
    email = ask("Пошта (логін): ").strip().lower()
    if "@" not in email:
        raise SystemExit("Це не схоже на пошту.")
    name = ask("Імʼя, як показувати в кабінеті: ").strip() or email.split("@")[0]
    password = ask_secret(f"Пароль (не коротше {settings.password_min_length} символів): ")
    if len(password) < settings.password_min_length:
        raise SystemExit("Пароль закороткий.")
    if ask_secret("Пароль ще раз: ") != password:
        raise SystemExit("Паролі не збігаються.")
    return email, name, password


async def _create_admin(ask=input, ask_secret=None) -> None:
    """Створює owner-а. Якщо пошта вже є — робить цей акаунт owner-ом і ставить новий пароль.

    Друге потрібно на випадок, коли owner забув пароль: інших способів
    його скинути немає (скидати чужі паролі може лише owner).
    """
    from sqlalchemy import select
    from app.core.access import ALL_SECTIONS
    from app.core.security import hash_password
    from app.models.admin_user import AdminRole, AdminUser

    email, name, password = _ask_owner(ask, ask_secret)
    async with async_session_maker() as session:
        user = (await session.execute(select(AdminUser).where(AdminUser.email == email))).scalar_one_or_none()
        if user is None:
            user = AdminUser(email=email, name=name, role=AdminRole.OWNER, is_active=True,
                             sections=list(ALL_SECTIONS), password_hash=hash_password(password))
            session.add(user)
            verb = "створено"
        else:
            user.role = AdminRole.OWNER
            user.is_active = True
            user.name = user.name or name
            user.password_hash = hash_password(password)
            user.must_change_password = False
            user.token_version = int(user.token_version or 0) + 1
            verb = "оновлено (тепер owner, пароль змінено)"
        await session.commit()
    print(f"Owner {verb}: {email}")


def _show_catalogue() -> None:
    """Друкує каталог без доступу до бази — зручно перевіряти ціни після правок."""
    from app.core.seed_packages import build_catalogue
    items = build_catalogue()
    by_family: dict = {}
    for it in items:
        by_family.setdefault(it["family"].value, []).append(it)

    for family, rows in by_family.items():
        print(f"\n=== {family.upper()} — {len(rows)} позицій ===")
        for r in rows[:8]:
            price = r.get("total_price")
            ppl = r.get("price_per_lesson")
            print(f"  {r['slug']:<42} {r.get('lessons_count') or '-':>4} ур · "
                  f"{ppl:>5} ₴/ур · {price:>7} ₴")
        if len(rows) > 8:
            print(f"  … і ще {len(rows) - 8}")
    print(f"\nУсього: {len(items)} позицій")


COMMANDS = {
    "seed-packages": lambda: asyncio.run(_seed_packages()),
    "create-admin": lambda: asyncio.run(_create_admin()),
    "show-catalogue": _show_catalogue,
}


def main() -> None:
    if len(sys.argv) < 2 or sys.argv[1] not in COMMANDS:
        print("Доступні команди:")
        for name in COMMANDS:
            print(f"  python -m app.cli {name}")
        sys.exit(1)
    COMMANDS[sys.argv[1]]()


if __name__ == "__main__":
    main()

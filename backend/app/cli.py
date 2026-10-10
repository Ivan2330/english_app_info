"""CLI для разових операцій.

    python -m app.cli seed-packages     # наповнити каталог із тарифної сітки
    python -m app.cli ensure-admin      # створити OWNER-адміна, якщо його немає
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


async def _ensure_admin() -> None:
    from app.core.bootstrap_admin import ensure_owner_admin
    async with async_session_maker() as session:
        info = await ensure_owner_admin(session)
    print(f"Адмін: {'створено' if info['created'] else 'вже існує'} — {info['email']}")


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
    "ensure-admin": lambda: asyncio.run(_ensure_admin()),
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

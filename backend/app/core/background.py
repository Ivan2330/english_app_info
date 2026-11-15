"""Фонові задачі, які не повинні ні блокувати відповідь, ні валити запит.

Використовується для відправки подій у Meta і листів про нову заявку:
користувач не чекає на чужий сервер, а збій там нічого не ламає.
"""
from __future__ import annotations

import asyncio
from typing import Awaitable

_tasks: set[asyncio.Task] = set()


def fire_and_forget(coro: Awaitable) -> None:
    """Запустити у фоні. Посилання тримаємо, інакше задачу може прибрати збирач сміття."""
    try:
        task = asyncio.get_running_loop().create_task(coro)
    except RuntimeError:                                 # немає циклу подій: нічого не робимо
        coro.close()  # type: ignore[attr-defined]
        return
    _tasks.add(task)
    task.add_done_callback(_tasks.discard)


async def drain() -> None:
    """Дочекатися фонових задач (тести, коректне завершення)."""
    if _tasks:
        await asyncio.gather(*list(_tasks), return_exceptions=True)

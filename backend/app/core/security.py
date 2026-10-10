"""Хешування паролів.

Раніше використовувався `passlib.hash.bcrypt`. Його довелося прибрати:
passlib не оновлювався з 2020 року й читає `bcrypt.__about__.__version__`,
який видалили в bcrypt 4.1. Оскільки версії в requirements.txt не були
зафіксовані, будь-яка свіжа збірка образу підтягувала новий bcrypt — і логін
разом зі створенням адміна падали з `ValueError: password cannot be longer
than 72 bytes`.

Тепер працюємо з бібліотекою bcrypt напряму. Формат хешу той самий ($2b$...),
тому вже наявні паролі в базі перевіряються без жодної міграції.
"""

from __future__ import annotations

import bcrypt

# bcrypt за специфікацією враховує лише перші 72 байти пароля.
# Довші треба обрізати самостійно, інакше сучасні версії кидають виняток.
_MAX_BYTES = 72


def _prepare(password: str) -> bytes:
    return password.encode("utf-8")[:_MAX_BYTES]


def hash_password(password: str) -> str:
    """Повертає bcrypt-хеш у вигляді рядка."""
    return bcrypt.hashpw(_prepare(password), bcrypt.gensalt()).decode("utf-8")


def verify_password(password: str, password_hash: str) -> bool:
    """Перевіряє пароль. Ніколи не кидає винятків — тільки True/False."""
    if not password_hash:
        return False
    try:
        return bcrypt.checkpw(_prepare(password), password_hash.encode("utf-8"))
    except (ValueError, TypeError):
        # Пошкоджений або хеш чужого формату в базі — це не привід валити запит.
        return False

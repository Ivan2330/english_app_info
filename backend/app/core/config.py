from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    database_url: str = "postgresql+asyncpg://postgres:12345@localhost:5432/school_db"
    secret_key: str = "CHANGE_ME_SECRET"
    cookie_name: str = "admin_session"
    debug_sql: bool = False
    auto_create_tables: bool = True

    # ↓↓↓ дефолти для ініціалізації адміна (можеш задати в .env)
    admin_email: str
    admin_password: str

    # Публічна адреса сайту — потрібна, щоб зібрати посилання повернення
    # та вебхуків. На проді задається в .env.
    site_url: str = "https://my-prime-academy.com"

    # =========================================================================
    # ОПЛАТИ
    # =========================================================================
    # Вимикач на випадок, коли реквізити ФОПа ще не внесені в оферту:
    # без них приймати гроші не можна. Тримаємо в конфізі, а не в коді,
    # щоб увімкнути оплату без релізу.
    payments_enabled: bool = False

    # --- Покупка Частинами monobank | Universal Bank -------------------------
    # Ключі вже видані й лежать у .env. Дефолти нижче — це ПІСОЧНИЦЯ,
    # вона відкрита без узгоджень і безпечна для експериментів.
    mono_chast_store_id: str = "test_store_with_confirm"
    mono_chast_sign_key: str = "secret_98765432--123-123"
    mono_chast_base_url: str = "https://u2-demo-ext.mono.st4g3.com"
    mono_chast_timeout: float = 20.0

    # Мінімум платежів. Правило monobank: якщо маржі не вистачає, вихід —
    # підняти цю межу або вимкнути ПЧ для товару, але НЕ націнювати ціну.
    mono_chast_min_parts: int = 3

    @property
    def mono_chast_callback_url(self) -> str:
        return f"{self.site_url}/api/payments/chast/callback"

    # --- plata by mono, звичайний еквайринг ----------------------------------
    mono_plata_token: str = ""
    mono_plata_base_url: str = "https://api.monobank.ua"
    mono_plata_timeout: float = 20.0
    # Рахунок живе добу: покинуті оплати мають закриватися самі,
    # інакше адмінка заростає «вічно очікує оплати».
    mono_plata_validity_sec: int = 86_400

    @property
    def mono_plata_redirect_url(self) -> str:
        return f"{self.site_url}/payment/result"

    @property
    def mono_plata_webhook_url(self) -> str:
        return f"{self.site_url}/api/payments/plata/webhook"

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )


settings = Settings()

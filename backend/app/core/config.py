from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    database_url: str = "postgresql+asyncpg://postgres:12345@localhost:5432/school_db"
    secret_key: str = "CHANGE_ME_SECRET"
    cookie_name: str = "admin_session"
    debug_sql: bool = False
    auto_create_tables: bool = True

    # =========================================================================
    # КАБІНЕТ: ВХІД І СЕСІЇ
    # =========================================================================
    # Перший owner створюється ТІЛЬКИ командою `python -m app.cli create-admin`
    # (пароль вводиться інтерактивно). ADMIN_EMAIL / ADMIN_PASSWORD у .env
    # більше не читаються: extra="ignore" їх мовчки пропускає, тож старий .env
    # нічого не ламає.
    #
    # Secure: кука ходить лише по HTTPS. Браузери вважають http://localhost
    # безпечним контекстом, тож у dev теж працює; вимкнути можна COOKIE_SECURE=false.
    cookie_secure: bool = True
    csrf_cookie_name: str = "admin_csrf"
    session_hours: int = 12                 # сесія без активності живе 12 годин
    session_refresh_minutes: int = 10       # як часто продовжувати куку при активності
    login_max_failures: int = 5             # невдалих спроб на одну пошту…
    login_window_minutes: int = 15          # …за стільки хвилин, далі 429
    login_max_failures_per_ip: int = 20     # і з однієї IP-адреси за те саме вікно
    password_min_length: int = 10

    # =========================================================================
    # ЛИСТ ВЛАСНИКУ ПРО НОВУ ЗАЯВКУ (необовʼязково)
    # =========================================================================
    # Порожній SMTP_HOST або LEAD_NOTIFY_EMAIL: листи не шлються, заявка все одно
    # зберігається в базі й видна в кабінеті. Пароль лише з оточення.
    smtp_host: str = ""
    smtp_port: int = 587
    smtp_user: str = ""
    smtp_password: str = ""
    smtp_from: str = ""
    lead_notify_email: str = ""

    # =========================================================================
    # META (Pixel і Conversions API)
    # =========================================================================
    # Лише з оточення, у репозиторії їх немає. Порожній META_PIXEL_ID: Pixel на сайті
    # не вантажиться; порожній META_CAPI_TOKEN: сервер нічого не відправляє в Meta.
    # META_TEST_EVENT_CODE береться з Events Manager → «Тестові події»: поки він
    # заданий, події йдуть у тестову вкладку й не впливають на рекламу. На бойовому
    # запуску його треба ПРИБРАТИ.
    meta_pixel_id: str = ""
    meta_capi_token: str = ""
    meta_test_event_code: str = ""
    meta_api_version: str = "v23.0"

    # =========================================================================
    # ФАЙЛИ КАБІНЕТУ
    # =========================================================================
    # Окремий docker-том поза кодом і поза веб-коренем; nginx їх не бачить,
    # віддає лише API після перевірки прав.
    upload_dir: str = "/data/uploads"
    upload_max_mb: int = 20                 # картинки й документи
    upload_video_max_mb: int = 300          # mp4, mov

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

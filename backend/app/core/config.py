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

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

settings = Settings()

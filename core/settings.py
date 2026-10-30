from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    database_url: str = "sqlite:///./test.db"
    secret_key: str
    debug: bool = False
    cloud_name: str
    cloud_api_key: str
    cloud_api_secret: str
    cloud_signed_upload_preset: str | None = None
    access_token_expire_minutes: int = 60
    db_ssl_enabled: bool = False
    db_ssl_ca_file: str | None = None

    class Config:
        env_file = ".env"
        extra = "ignore"

settings = Settings()

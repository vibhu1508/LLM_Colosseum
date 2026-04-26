from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")

    app_title: str = "Prompt Engineering Healthcare Lab"
    app_origin: str = "http://localhost:4200"
    ollama_base_url: str = "http://127.0.0.1:11434"
    openrouter_api_key: str = ""
    openrouter_base_url: str = "https://openrouter.ai/api/v1"
    database_url: str = "sqlite:///./prompt_lab.db"


settings = Settings()

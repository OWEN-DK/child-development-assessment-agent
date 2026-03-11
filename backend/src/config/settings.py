import os
from pydantic import Field
from pydantic_settings import BaseSettings

# 尝试导入 BaseSettings，如果失败则使用简单的类
try:
    from pydantic_settings import BaseSettings
except ImportError:
    from pydantic import BaseModel
    
    class BaseSettings(BaseModel):
        pass

class Settings(BaseSettings):
    app_name: str = "Child Development Assessment Agent"
    app_version: str = "0.1.0"
    debug: bool = True
    app_host: str = "0.0.0.0"
    app_port: int = 8000
    app_reload: bool = True
    
    # Model Config
    openai_api_key: str = os.getenv("OPENAI_API_KEY", "")
    model_name: str = "gpt-4-turbo"
    
    # Log Config
    LOG_LEVEL: str = "INFO"
    LOG_FILE: str = "logs/app.log"
    
    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"

settings = Settings()

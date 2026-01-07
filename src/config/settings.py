import os

from dotenv import load_dotenv

load_dotenv(dotenv_path=r"C:\Users\11257\Documents\AIPlayground\src\config\.env")

# API Keys
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
DEEPSEEK_API_KEY = os.getenv("DEEPSEEK_API_KEY")
KIMI_API_KEY = os.getenv("KIMI_API_KEY")

# Model configurations
DEFAULT_MODEL = "kimi-k2-turbo-preview"  # 默认使用 Kimi 模型名称
MAX_TOKENS = 2000
TEMPERATURE = 0.7
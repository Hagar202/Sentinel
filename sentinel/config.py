"""All settings in one place. The values come from the .env file."""
import os
from pathlib import Path

from dotenv import load_dotenv

ROOT = Path(__file__).parent.parent
load_dotenv(ROOT / ".env")

# Which LLM to use: gemini, groq, openai or offline (no LLM, rules only)
LLM_PROVIDER = os.getenv("LLM_PROVIDER", "offline")
GOOGLE_API_KEY = os.getenv("GOOGLE_API_KEY", "")
GEMINI_MODEL = os.getenv("GEMINI_MODEL", "gemini-flash-latest")   # "latest" = always the newest Flash model (old names get retired)
GEMINI_BACKUP_MODEL = os.getenv("GEMINI_BACKUP_MODEL", "gemini-flash-lite-latest")  # used when the main model is busy
GEMINI_EMBEDDING_MODEL = os.getenv("GEMINI_EMBEDDING_MODEL", "models/gemini-embedding-001")  # text -> vector (RAG)
AGENT_MAX_STEPS = int(os.getenv("AGENT_MAX_STEPS", "6"))      # how many rounds of tool calls an agent may do
LLM_RETRY_WAIT = float(os.getenv("LLM_RETRY_WAIT", "5"))       # seconds to wait before asking a slow/busy LLM again
GROQ_API_KEY = os.getenv("GROQ_API_KEY", "")
GROQ_MODEL = os.getenv("GROQ_MODEL", "openai/gpt-oss-120b")       # free, fast, supports tools
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")

# The company Sentinel protects
COMPANY_DOMAIN = os.getenv("COMPANY_DOMAIN", "sentinel-demo.com")
EXEC_NAMES = os.getenv("EXEC_NAMES", "Ahmed Hassan,Mona Fathy").split(",")
SECURITY_TEAM_EMAIL = os.getenv("SECURITY_TEAM_EMAIL", "security@sentinel-demo.com")
ONCALL_EMAIL = os.getenv("ONCALL_EMAIL", "oncall@sentinel-demo.com")
CTO_EMAIL = os.getenv("CTO_EMAIL", "cto@sentinel-demo.com")
PRODUCT_EMAIL = os.getenv("PRODUCT_EMAIL", "product@sentinel-demo.com")

# Cost Watchdog
CURRENT_MODEL = os.getenv("CURRENT_MODEL", "gpt-4o")                 # the model the company uses today
CHEAP_MODEL = os.getenv("CHEAP_MODEL", "gpt-4.1-mini")               # suggested for simple tasks
AI_MONTHLY_BUDGET = float(os.getenv("AI_MONTHLY_BUDGET", "60000"))   # dollars per month

# Sending emails. DRY_RUN=true saves them in data/outbox instead of sending.
DRY_RUN = os.getenv("DRY_RUN", "true").lower() == "true"
SMTP_USER = os.getenv("SMTP_USER", "")
SMTP_PASSWORD = os.getenv("SMTP_PASSWORD", "")

# Folders
MODELS_DIR = ROOT / "models"
KNOWLEDGE_DIR = ROOT / "knowledge"
DB_PATH = ROOT / "data" / "sentinel.db"
OUTBOX_DIR = ROOT / "data" / "outbox"

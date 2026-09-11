"""Bot sozlamalari — barcha maxfiy qiymatlar .env faylidan o'qiladi."""

from __future__ import annotations

import os
from pathlib import Path

from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent
load_dotenv(BASE_DIR / ".env")


def _env(name: str, default: str | None = None, *, required: bool = False) -> str:
    value = os.getenv(name, default)
    if required and not value:
        raise RuntimeError(f"{name} .env faylida ko'rsatilmagan")
    return value or ""


# --- Telegram ---------------------------------------------------------------
BOT_TOKEN = _env("BOT_TOKEN", required=True)

# Bo'sh bo'lsa — bot hamma uchun ochiq. Aks holda faqat shu ID'lar kira oladi.
ALLOWED_USER_IDS: set[int] = {
    int(x) for x in _env("ALLOWED_USER_IDS").replace(" ", "").split(",") if x
}

# --- OpenAI -----------------------------------------------------------------
OPENAI_API_KEY = _env("OPENAI_API_KEY", required=True)

# Hujjat tahlili — chuqur fikrlash talab qiladi
MODEL = _env("OPENAI_MODEL", "gpt-5.5")
# Tranzaksiya ajratish — qisqa, tez-tez takrorlanadigan vazifa
PARSER_MODEL = _env("OPENAI_PARSER_MODEL", "gpt-5.4-mini")


def supports_reasoning(model: str) -> bool:
    """`reasoning` parametrini qabul qiladigan modellarni ajratadi."""
    return model.startswith(("gpt-5", "gpt-6", "o1", "o3", "o4"))

# --- Google Sheets ----------------------------------------------------------
GOOGLE_CREDENTIALS_FILE = _env("GOOGLE_CREDENTIALS_FILE", str(BASE_DIR / "credentials.json"))
SPREADSHEET_ID = _env("SPREADSHEET_ID", required=True)
WORKSHEET_NAME = _env("WORKSHEET_NAME", "Tranzaksiyalar")

# --- Ovozni matnga o'girish -------------------------------------------------
# OpenAI transkripsiyasi `language="uz"` ni qabul qilmaydi, shuning uchun til
# `prompt` orqali bildiriladi — sinovda bu eng aniq natija bergan usul.
STT_MODEL = _env("OPENAI_STT_MODEL", "gpt-transcribe")
STT_PROMPT = (
    "Ushbu audio o'zbek tilida. Moliyaviy xarajat va daromad haqida. "
    "Matnni o'zbek lotin alifbosida yoz. "
    "Masalan: \"taksiga 25 ming so'm berdim\", \"mijozdan 12 million tushdi\"."
)

# --- Biznes mantiq ----------------------------------------------------------
DEFAULT_CURRENCY = _env("DEFAULT_CURRENCY", "UZS")
TIMEZONE = _env("TIMEZONE", "Asia/Tashkent")

INCOME_CATEGORIES = [
    "Maosh",
    "Savdo tushumi",
    "Xizmat ko'rsatish",
    "Investitsiya daromadi",
    "Qarz olindi",
    "Qarz qaytarildi (menga)",
    "Sovg'a / yordam",
    "Boshqa kirim",
]

EXPENSE_CATEGORIES = [
    "Oziq-ovqat",
    "Transport",
    "Kommunal to'lovlar",
    "Ijara",
    "Aloqa va internet",
    "Sog'liq",
    "Ta'lim",
    "Kiyim-kechak",
    "Ko'ngilochar",
    "Xodimlar maoshi",
    "Tovar xaridi",
    "Marketing / reklama",
    "Soliq va yig'imlar",
    "Bank komissiyasi",
    "Qarz berildi",
    "Qarz qaytarildi (mendan)",
    "Boshqa chiqim",
]

ALL_CATEGORIES = INCOME_CATEGORIES + EXPENSE_CATEGORIES

CURRENCIES = ["UZS", "USD", "EUR", "RUB"]
PAYMENT_METHODS = ["naqd", "karta", "o'tkazma", "boshqa"]

# Telegram Bot API orqali yuklab olish chegarasi
MAX_FILE_MB = 20

EXPORT_DIR = BASE_DIR / "exports"
EXPORT_DIR.mkdir(exist_ok=True)

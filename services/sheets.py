"""Google Sheets — tranzaksiyalar ombori.

gspread sinxron ishlaydi, shuning uchun har bir ommaviy funksiya
`asyncio.to_thread` orqali chaqiriladi (handler'lar bloklanmasligi uchun).
"""

from __future__ import annotations

import asyncio
import json
import uuid
from datetime import datetime
from pathlib import Path
from typing import Any

import gspread
from google.oauth2.service_account import Credentials

import config

SCOPES = [
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive",
]

HEADER = [
    "ID",
    "Sana",
    "Vaqt",
    "User ID",
    "Username",
    "Turi",
    "Summa",
    "Valyuta",
    "Kategoriya",
    "Tavsif",
    "To'lov usuli",
    "Kontragent",
    "Manba",
    "Ishonch",
    "Xom matn",
]

_worksheet: gspread.Worksheet | None = None
_lock = asyncio.Lock()


def _credentials() -> Credentials:
    """Servis akkaunt kalitini muhit o'zgaruvchisidan yoki fayldan oladi."""
    if config.GOOGLE_CREDENTIALS_JSON:
        try:
            info = json.loads(config.GOOGLE_CREDENTIALS_JSON)
        except json.JSONDecodeError as exc:
            raise RuntimeError(
                "GOOGLE_CREDENTIALS_JSON yaroqli JSON emas — servis akkaunt "
                "faylining butun mazmunini o'zgartirmasdan joylang"
            ) from exc
        return Credentials.from_service_account_info(info, scopes=SCOPES)

    if not Path(config.GOOGLE_CREDENTIALS_FILE).exists():
        raise RuntimeError(
            f"Servis akkaunt kaliti topilmadi: {config.GOOGLE_CREDENTIALS_FILE}. "
            "Faylni joylang yoki GOOGLE_CREDENTIALS_JSON o'zgaruvchisini bering."
        )
    return Credentials.from_service_account_file(
        config.GOOGLE_CREDENTIALS_FILE, scopes=SCOPES
    )


def _open_worksheet() -> gspread.Worksheet:
    """Ish varag'ini ochadi, bo'lmasa yaratadi va sarlavhani qo'yadi."""
    spreadsheet = gspread.authorize(_credentials()).open_by_key(config.SPREADSHEET_ID)

    try:
        ws = spreadsheet.worksheet(config.WORKSHEET_NAME)
    except gspread.WorksheetNotFound:
        ws = spreadsheet.add_worksheet(
            title=config.WORKSHEET_NAME, rows=1000, cols=len(HEADER)
        )

    if ws.row_values(1) != HEADER:
        ws.update(values=[HEADER], range_name="A1")
        ws.freeze(rows=1)
        ws.format("A1:O1", {"textFormat": {"bold": True}})
    return ws


def _ws() -> gspread.Worksheet:
    global _worksheet
    if _worksheet is None:
        _worksheet = _open_worksheet()
    return _worksheet


# ---------------------------------------------------------------------------
# Yozish
# ---------------------------------------------------------------------------

def _append_sync(
    user_id: int, username: str, transactions: list[dict[str, Any]], source: str, raw: str
) -> list[dict[str, Any]]:
    now = datetime.now()
    rows, saved = [], []

    for txn in transactions:
        txn_id = uuid.uuid4().hex[:10]
        record = {
            "id": txn_id,
            "date": txn.get("date") or now.strftime("%Y-%m-%d"),
            "time": now.strftime("%H:%M:%S"),
            "user_id": user_id,
            "username": username,
            "type": txn.get("type", "chiqim"),
            "amount": float(txn.get("amount", 0)),
            "currency": txn.get("currency", config.DEFAULT_CURRENCY),
            "category": txn.get("category", "Boshqa chiqim"),
            "description": txn.get("description", ""),
            "payment_method": txn.get("payment_method", "boshqa"),
            "counterparty": txn.get("counterparty", ""),
            "source": source,
            "confidence": float(txn.get("confidence", 0)),
        }
        rows.append(
            [
                record["id"],
                record["date"],
                record["time"],
                record["user_id"],
                record["username"],
                record["type"],
                record["amount"],
                record["currency"],
                record["category"],
                record["description"],
                record["payment_method"],
                record["counterparty"],
                record["source"],
                record["confidence"],
                raw[:500],
            ]
        )
        saved.append(record)

    if rows:
        # RAW — Sheets sanalarni seriya raqamga aylantirib yubormasligi uchun
        _ws().append_rows(rows, value_input_option="RAW")
    return saved


async def append_transactions(
    user_id: int, username: str, transactions: list[dict[str, Any]], source: str, raw: str
) -> list[dict[str, Any]]:
    async with _lock:
        return await asyncio.to_thread(
            _append_sync, user_id, username, transactions, source, raw
        )


# ---------------------------------------------------------------------------
# O'qish
# ---------------------------------------------------------------------------

def _normalize(row: dict[str, Any]) -> dict[str, Any]:
    try:
        amount = float(str(row.get("Summa", 0)).replace(" ", "").replace(",", "."))
    except ValueError:
        amount = 0.0
    return {
        "id": str(row.get("ID", "")),
        "date": str(row.get("Sana", "")),
        "time": str(row.get("Vaqt", "")),
        "user_id": row.get("User ID"),
        "username": str(row.get("Username", "")),
        "type": str(row.get("Turi", "")),
        "amount": amount,
        "currency": str(row.get("Valyuta", config.DEFAULT_CURRENCY)),
        "category": str(row.get("Kategoriya", "")),
        "description": str(row.get("Tavsif", "")),
        "payment_method": str(row.get("To'lov usuli", "")),
        "counterparty": str(row.get("Kontragent", "")),
        "source": str(row.get("Manba", "")),
    }


def _fetch_sync(
    user_id: int | None, date_from: str | None, date_to: str | None
) -> list[dict[str, Any]]:
    records = [_normalize(r) for r in _ws().get_all_records()]
    result = []
    for r in records:
        if user_id is not None and str(r["user_id"]) != str(user_id):
            continue
        if date_from and r["date"] < date_from:
            continue
        if date_to and r["date"] > date_to:
            continue
        result.append(r)
    result.sort(key=lambda r: (r["date"], r["time"]))
    return result


async def fetch_transactions(
    user_id: int | None = None,
    date_from: str | None = None,
    date_to: str | None = None,
) -> list[dict[str, Any]]:
    return await asyncio.to_thread(_fetch_sync, user_id, date_from, date_to)


# ---------------------------------------------------------------------------
# O'zgartirish / o'chirish
# ---------------------------------------------------------------------------

def _find_row(txn_id: str) -> int | None:
    cell = _ws().find(txn_id, in_column=1)
    return cell.row if cell else None


def _delete_sync(txn_id: str) -> bool:
    row = _find_row(txn_id)
    if row is None:
        return False
    _ws().delete_rows(row)
    return True


async def delete_transaction(txn_id: str) -> bool:
    async with _lock:
        return await asyncio.to_thread(_delete_sync, txn_id)


def _update_category_sync(txn_id: str, category: str) -> bool:
    row = _find_row(txn_id)
    if row is None:
        return False
    col = HEADER.index("Kategoriya") + 1
    _ws().update_cell(row, col, category)
    return True


async def update_category(txn_id: str, category: str) -> bool:
    async with _lock:
        return await asyncio.to_thread(_update_category_sync, txn_id, category)


async def healthcheck() -> str:
    """Ishga tushishda ulanishni tekshiradi, jadval nomini qaytaradi."""
    return await asyncio.to_thread(lambda: _ws().spreadsheet.title)

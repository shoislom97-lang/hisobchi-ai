"""Matn formatlash yordamchilari."""

from __future__ import annotations

from collections import defaultdict
from datetime import date, timedelta
from html import escape
from typing import Any

import config

TELEGRAM_LIMIT = 4000  # 4096 dan biroz past — xavfsizlik zaxirasi

MONTHS_UZ = [
    "yanvar", "fevral", "mart", "aprel", "may", "iyun",
    "iyul", "avgust", "sentabr", "oktabr", "noyabr", "dekabr",
]


def month_name(d: date) -> str:
    return f"{d.year}-yil {MONTHS_UZ[d.month - 1]}"


def fmt_amount(amount: float, currency: str = "") -> str:
    """1234567.0 -> '1 234 567' ; 12.5 -> '12.5'"""
    if amount == int(amount):
        body = f"{int(amount):,}".replace(",", " ")
    else:
        body = f"{amount:,.2f}".replace(",", " ")
    return f"{body} {currency}".strip()


def txn_card(txn: dict[str, Any]) -> str:
    """Saqlangan tranzaksiya kartochkasi (HTML)."""
    is_income = txn["type"] == "kirim"
    icon = "🟢 KIRIM" if is_income else "🔴 CHIQIM"
    sign = "+" if is_income else "−"

    lines = [
        f"{icon}",
        f"<b>{sign}{escape(fmt_amount(txn['amount'], txn['currency']))}</b>",
        f"📁 {escape(txn['category'])}",
    ]
    if txn.get("description"):
        lines.append(f"📝 {escape(txn['description'])}")
    if txn.get("counterparty"):
        lines.append(f"👤 {escape(txn['counterparty'])}")
    lines.append(f"💳 {escape(txn.get('payment_method', ''))}  •  📅 {escape(txn['date'])}")

    if txn.get("confidence", 1) < 0.6:
        lines.append("\n⚠️ <i>Ishonch past — raqamni tekshiring</i>")
    return "\n".join(lines)


def summary_text(transactions: list[dict[str, Any]], period_label: str) -> str:
    """Hisobot matni (HTML)."""
    if not transactions:
        return f"<b>{escape(period_label)}</b>\n\nBu davr uchun yozuv topilmadi."

    by_currency: dict[str, dict[str, float]] = defaultdict(
        lambda: {"kirim": 0.0, "chiqim": 0.0}
    )
    by_category: dict[str, float] = defaultdict(float)

    for txn in transactions:
        by_currency[txn["currency"]][txn["type"]] += txn["amount"]
        if txn["type"] == "chiqim" and txn["currency"] == config.DEFAULT_CURRENCY:
            by_category[txn["category"]] += txn["amount"]

    lines = [f"📊 <b>{escape(period_label)}</b>", f"Yozuvlar: {len(transactions)} ta", ""]

    for currency, totals in sorted(by_currency.items()):
        balance = totals["kirim"] - totals["chiqim"]
        mark = "✅" if balance >= 0 else "⚠️"
        lines += [
            f"<b>{escape(currency)}</b>",
            f"  🟢 Kirim:  {escape(fmt_amount(totals['kirim']))}",
            f"  🔴 Chiqim: {escape(fmt_amount(totals['chiqim']))}",
            f"  {mark} Balans: <b>{escape(fmt_amount(balance))}</b>",
            "",
        ]

    if by_category:
        total_expense = sum(by_category.values())
        lines.append(f"<b>Eng katta chiqimlar ({escape(config.DEFAULT_CURRENCY)})</b>")
        top = sorted(by_category.items(), key=lambda kv: kv[1], reverse=True)[:7]
        for category, amount in top:
            share = amount / total_expense * 100 if total_expense else 0
            lines.append(
                f"  • {escape(category)} — {escape(fmt_amount(amount))} ({share:.0f}%)"
            )
    return "\n".join(lines)


def recent_list(transactions: list[dict[str, Any]], limit: int = 10) -> str:
    """Oxirgi yozuvlar ro'yxati (HTML)."""
    if not transactions:
        return "Hozircha yozuv yo'q."
    ordered = sorted(transactions, key=lambda t: (t["date"], t["time"]), reverse=True)
    lines = [f"🧾 <b>Oxirgi {min(limit, len(ordered))} ta yozuv</b>\n"]
    for txn in ordered[:limit]:
        sign = "+" if txn["type"] == "kirim" else "−"
        icon = "🟢" if txn["type"] == "kirim" else "🔴"
        note = f" — {escape(txn['description'][:40])}" if txn.get("description") else ""
        lines.append(
            f"{icon} <code>{escape(txn['date'])}</code>  "
            f"<b>{sign}{escape(fmt_amount(txn['amount'], txn['currency']))}</b>\n"
            f"     {escape(txn['category'])}{note}"
        )
    return "\n".join(lines)


def period_range(key: str) -> tuple[str | None, str | None, str]:
    """Davr kalitini (sana_dan, sana_gacha, sarlavha) ga aylantiradi."""
    today = date.today()
    if key == "today":
        return today.isoformat(), today.isoformat(), "Bugun"
    if key == "week":
        start = today - timedelta(days=today.weekday())
        return start.isoformat(), today.isoformat(), "Joriy hafta"
    if key == "month":
        start = today.replace(day=1)
        return start.isoformat(), today.isoformat(), month_name(today)
    if key == "prev_month":
        last_day = today.replace(day=1) - timedelta(days=1)
        return (
            last_day.replace(day=1).isoformat(),
            last_day.isoformat(),
            month_name(last_day),
        )
    if key == "year":
        return today.replace(month=1, day=1).isoformat(), today.isoformat(), f"{today.year}-yil"
    return None, None, "Butun tarix"


def split_message(text: str, limit: int = TELEGRAM_LIMIT) -> list[str]:
    """Uzun matnni Telegram chegarasiga sig'adigan bo'laklarga bo'ladi."""
    if len(text) <= limit:
        return [text]

    chunks, current = [], ""
    for paragraph in text.split("\n"):
        # Bitta xatboshining o'zi chegaradan uzun bo'lsa — majburan kesamiz
        while len(paragraph) > limit:
            if current:
                chunks.append(current)
                current = ""
            chunks.append(paragraph[:limit])
            paragraph = paragraph[limit:]

        if len(current) + len(paragraph) + 1 > limit:
            chunks.append(current)
            current = paragraph
        else:
            current = f"{current}\n{paragraph}" if current else paragraph

    if current:
        chunks.append(current)
    return chunks

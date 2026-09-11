"""Klaviaturalar va callback ma'lumotlari."""

from __future__ import annotations

from aiogram.types import (
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    KeyboardButton,
    ReplyKeyboardMarkup,
)

import config

# --- Asosiy menyu -----------------------------------------------------------
BTN_REPORT = "📊 Hisobot"
BTN_EXCEL = "📥 Excel"
BTN_RECENT = "🧾 Oxirgi yozuvlar"
BTN_ADVISOR = "🤖 AI maslahatchi"
BTN_HELP = "❓ Yordam"

main_menu = ReplyKeyboardMarkup(
    keyboard=[
        [KeyboardButton(text=BTN_REPORT), KeyboardButton(text=BTN_EXCEL)],
        [KeyboardButton(text=BTN_RECENT), KeyboardButton(text=BTN_ADVISOR)],
        [KeyboardButton(text=BTN_HELP)],
    ],
    resize_keyboard=True,
    input_field_placeholder="Xarajat yoki daromadni yozing / ayting…",
)


# --- Davr tanlash -----------------------------------------------------------
PERIODS = [
    ("today", "Bugun"),
    ("week", "Hafta"),
    ("month", "Joriy oy"),
    ("prev_month", "O'tgan oy"),
    ("year", "Yil"),
    ("all", "Hammasi"),
]


def period_keyboard(action: str) -> InlineKeyboardMarkup:
    """action: 'report' yoki 'excel'."""
    buttons = [
        InlineKeyboardButton(text=title, callback_data=f"{action}:{key}")
        for key, title in PERIODS
    ]
    rows = [buttons[i : i + 3] for i in range(0, len(buttons), 3)]
    return InlineKeyboardMarkup(inline_keyboard=rows)


# --- Saqlangan tranzaksiya ustidagi amallar ---------------------------------
def txn_actions(txn_id: str, txn_type: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="✏️ Kategoriya", callback_data=f"cat:{txn_type}:{txn_id}"
                ),
                InlineKeyboardButton(text="🗑 O'chirish", callback_data=f"del:{txn_id}"),
            ]
        ]
    )


def category_keyboard(txn_type: str, txn_id: str) -> InlineKeyboardMarkup:
    """Kategoriyalar ro'yxati. Callback qisqa bo'lishi uchun indeks uzatiladi."""
    categories = (
        config.INCOME_CATEGORIES if txn_type == "kirim" else config.EXPENSE_CATEGORIES
    )
    offset = 0 if txn_type == "kirim" else len(config.INCOME_CATEGORIES)

    buttons = [
        InlineKeyboardButton(text=name, callback_data=f"setcat:{offset + i}:{txn_id}")
        for i, name in enumerate(categories)
    ]
    rows = [buttons[i : i + 2] for i in range(0, len(buttons), 2)]
    rows.append([InlineKeyboardButton(text="⬅️ Orqaga", callback_data=f"back:{txn_id}")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


# --- Maslahatchi rejimi -----------------------------------------------------
advisor_exit = InlineKeyboardMarkup(
    inline_keyboard=[
        [InlineKeyboardButton(text="⬅️ Hisobchi rejimiga qaytish", callback_data="advisor:exit")]
    ]
)

"""Hisobotlar va Excel eksporti."""

from __future__ import annotations

import logging

from aiogram import F, Router
from aiogram.filters import Command
from aiogram.types import CallbackQuery, FSInputFile, Message

import keyboards as kb
from services import ai, excel, sheets
from utils.formatting import period_range, recent_list, split_message, summary_text

logger = logging.getLogger(__name__)
router = Router(name="reports")


@router.message(Command("hisobot"))
@router.message(F.text == kb.BTN_REPORT)
async def cmd_report(message: Message) -> None:
    await message.answer(
        "📊 Qaysi davr uchun hisobot kerak?",
        reply_markup=kb.period_keyboard("report"),
    )


@router.message(Command("excel"))
@router.message(F.text == kb.BTN_EXCEL)
async def cmd_excel(message: Message) -> None:
    await message.answer(
        "📥 Qaysi davr ma'lumotlarini yuklab beray?",
        reply_markup=kb.period_keyboard("excel"),
    )


@router.message(Command("oxirgi"))
@router.message(F.text == kb.BTN_RECENT)
async def cmd_recent(message: Message) -> None:
    try:
        transactions = await sheets.fetch_transactions(user_id=message.from_user.id)
    except Exception:
        logger.exception("Sheets'dan o'qishda xato")
        await message.answer("⚠️ Ma'lumotlarni o'qiy olmadim. Keyinroq urinib ko'ring.")
        return
    await message.answer(recent_list(transactions))


@router.callback_query(F.data.startswith("report:"))
async def cb_report(callback: CallbackQuery) -> None:
    period = callback.data.split(":", 1)[1]
    date_from, date_to, label = period_range(period)

    await callback.message.edit_text(f"⏳ «{label}» hisoboti tayyorlanmoqda…")
    await callback.answer()

    try:
        transactions = await sheets.fetch_transactions(
            user_id=callback.from_user.id, date_from=date_from, date_to=date_to
        )
    except Exception:
        logger.exception("Sheets'dan o'qishda xato")
        await callback.message.edit_text("⚠️ Ma'lumotlarni o'qiy olmadim.")
        return

    text = summary_text(transactions, label)
    await callback.message.edit_text(text)

    # Yetarli ma'lumot bo'lsa — qisqa AI izohi
    if len(transactions) >= 3:
        try:
            comment = await ai.comment_on_report(text)
        except Exception:
            logger.exception("Hisobot izohida xato")
            return
        if comment:
            for chunk in split_message(f"🤖 Buxgalter izohi:\n\n{comment}"):
                await callback.message.answer(chunk, parse_mode=None)


@router.callback_query(F.data.startswith("excel:"))
async def cb_excel(callback: CallbackQuery) -> None:
    period = callback.data.split(":", 1)[1]
    date_from, date_to, label = period_range(period)

    await callback.message.edit_text(f"⏳ «{label}» uchun Excel tayyorlanmoqda…")
    await callback.answer()

    try:
        transactions = await sheets.fetch_transactions(
            user_id=callback.from_user.id, date_from=date_from, date_to=date_to
        )
    except Exception:
        logger.exception("Sheets'dan o'qishda xato")
        await callback.message.edit_text("⚠️ Ma'lumotlarni o'qiy olmadim.")
        return

    if not transactions:
        await callback.message.edit_text(
            f"«{label}» uchun yozuv topilmadi — eksport qiladigan narsa yo'q."
        )
        return

    try:
        path = await excel.build_report(transactions, label, callback.from_user.id)
    except Exception:
        logger.exception("Excel yaratishda xato")
        await callback.message.edit_text("⚠️ Excel faylini yarata olmadim.")
        return

    await callback.message.edit_text(f"✅ «{label}» — {len(transactions)} ta yozuv")
    await callback.message.answer_document(
        FSInputFile(path, filename=f"Hisobot_{label.replace(' ', '_')}.xlsx"),
        caption=f"📊 {label}\n\nVaraqlar: «Tranzaksiyalar» va «Xulosa» (diagrammalar bilan).",
    )
    path.unlink(missing_ok=True)

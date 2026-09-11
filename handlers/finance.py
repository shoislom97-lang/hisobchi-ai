"""Matn va ovozli xabarlardan moliyaviy yozuv yaratish."""

from __future__ import annotations

import logging
from collections import OrderedDict
from io import BytesIO
from typing import Any

from aiogram import Bot, F, Router
from aiogram.types import CallbackQuery, Message

import config
import keyboards as kb
from services import ai, sheets, stt
from utils.formatting import txn_card

logger = logging.getLogger(__name__)
router = Router(name="finance")

# Tugmalar bosilganda kartochkani qayta chizish uchun yaqinda saqlangan yozuvlar
_RECENT_CARDS: OrderedDict[str, dict[str, Any]] = OrderedDict()
_RECENT_LIMIT = 500


def _remember(txn: dict[str, Any]) -> None:
    _RECENT_CARDS[txn["id"]] = txn
    while len(_RECENT_CARDS) > _RECENT_LIMIT:
        _RECENT_CARDS.popitem(last=False)


async def _process(message: Message, text: str, source: str) -> None:
    """Matnni tahlil qilib, topilgan yozuvlarni saqlaydi."""
    status = await message.answer("🧠 Tahlil qilinmoqda…")

    try:
        parsed = await ai.parse_transactions(text)
    except Exception:
        logger.exception("AI tahlilida xato")
        await status.edit_text(
            "⚠️ Tahlil qilishda xatolik yuz berdi. Biroz kutib, qayta urinib ko'ring."
        )
        return

    transactions = parsed.get("transactions") or []
    if not parsed.get("is_financial") or not transactions:
        reply = parsed.get("reply") or (
            "Bu xabarda pul harakatini topa olmadim.\n\n"
            "Masalan shunday yozing: «taksiga 25 ming berdim»"
        )
        await status.edit_text(reply)
        return

    try:
        saved = await sheets.append_transactions(
            user_id=message.from_user.id,
            username=message.from_user.username or message.from_user.full_name,
            transactions=transactions,
            source=source,
            raw=text,
        )
    except Exception:
        logger.exception("Google Sheets'ga yozishda xato")
        await status.edit_text(
            "⚠️ Google Sheets'ga saqlay olmadim. Ulanishni tekshiring."
        )
        return

    header = (
        "✅ <b>Saqlandi</b>"
        if len(saved) == 1
        else f"✅ <b>{len(saved)} ta yozuv saqlandi</b>"
    )
    await status.edit_text(header)

    for txn in saved:
        _remember(txn)
        await message.answer(
            txn_card(txn), reply_markup=kb.txn_actions(txn["id"], txn["type"])
        )


# ---------------------------------------------------------------------------
# Kirish nuqtalari
# ---------------------------------------------------------------------------

@router.message(F.voice | F.audio)
async def handle_voice(message: Message, bot: Bot) -> None:
    status = await message.answer("🎧 Ovozni tinglayapman…")

    media = message.voice or message.audio
    if media.file_size and media.file_size > config.MAX_FILE_MB * 1024 * 1024:
        await status.edit_text(f"⚠️ Fayl juda katta ({config.MAX_FILE_MB} MB gacha).")
        return

    buffer = BytesIO()
    await bot.download(media, destination=buffer)

    try:
        text = await stt.transcribe(buffer.getvalue())
    except stt.STTError as exc:
        logger.warning("STT xatosi: %s", exc)
        await status.edit_text(
            "⚠️ Ovozni matnga o'gira olmadim. Iltimos, matn ko'rinishida yozing."
        )
        return

    if not text:
        await status.edit_text(
            "🤔 Ovozda nutq topilmadi. Yaqinroq va tiniqroq gapirib ko'ring."
        )
        return

    await status.edit_text(f"🗣 <i>«{text}»</i>")
    await _process(message, text, source="ovoz")


@router.message(F.text & ~F.text.startswith("/"))
async def handle_text(message: Message) -> None:
    await _process(message, message.text, source="matn")


# ---------------------------------------------------------------------------
# Yozuv ustidagi amallar
# ---------------------------------------------------------------------------

@router.callback_query(F.data.startswith("del:"))
async def cb_delete(callback: CallbackQuery) -> None:
    txn_id = callback.data.split(":", 1)[1]
    try:
        deleted = await sheets.delete_transaction(txn_id)
    except Exception:
        logger.exception("O'chirishda xato")
        await callback.answer("Xatolik yuz berdi", show_alert=True)
        return

    if not deleted:
        await callback.answer("Yozuv topilmadi — u allaqachon o'chirilgan", show_alert=True)
        return

    _RECENT_CARDS.pop(txn_id, None)
    await callback.message.edit_text("🗑 <s>Yozuv o'chirildi</s>", reply_markup=None)
    await callback.answer("O'chirildi")


@router.callback_query(F.data.startswith("cat:"))
async def cb_choose_category(callback: CallbackQuery) -> None:
    _, txn_type, txn_id = callback.data.split(":", 2)
    await callback.message.edit_reply_markup(
        reply_markup=kb.category_keyboard(txn_type, txn_id)
    )
    await callback.answer("Yangi kategoriyani tanlang")


@router.callback_query(F.data.startswith("back:"))
async def cb_back(callback: CallbackQuery) -> None:
    txn_id = callback.data.split(":", 1)[1]
    txn = _RECENT_CARDS.get(txn_id)
    txn_type = txn["type"] if txn else "chiqim"
    await callback.message.edit_reply_markup(
        reply_markup=kb.txn_actions(txn_id, txn_type)
    )
    await callback.answer()


@router.callback_query(F.data.startswith("setcat:"))
async def cb_set_category(callback: CallbackQuery) -> None:
    _, index, txn_id = callback.data.split(":", 2)
    category = config.ALL_CATEGORIES[int(index)]

    try:
        updated = await sheets.update_category(txn_id, category)
    except Exception:
        logger.exception("Kategoriyani yangilashda xato")
        await callback.answer("Xatolik yuz berdi", show_alert=True)
        return

    if not updated:
        await callback.answer("Yozuv topilmadi", show_alert=True)
        return

    txn = _RECENT_CARDS.get(txn_id)
    if txn:
        txn["category"] = category
        await callback.message.edit_text(
            txn_card(txn), reply_markup=kb.txn_actions(txn_id, txn["type"])
        )
    else:
        await callback.message.edit_reply_markup(
            reply_markup=kb.txn_actions(txn_id, "chiqim")
        )
    await callback.answer(f"Kategoriya: {category}")

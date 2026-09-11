"""AI maslahatchi — yuklangan hujjatlarni chuqur tahlil qilish."""

from __future__ import annotations

import logging
from io import BytesIO
from typing import Any

from aiogram import Bot, F, Router
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message

import config
import keyboards as kb
from services import ai, documents
from utils.formatting import split_message

from .states import AdvisorStates

logger = logging.getLogger(__name__)
router = Router(name="advisor")

# Foydalanuvchining joriy hujjati:
#   {user_id: {"blocks": [...], "filename": str, "response_id": str | None}}
# `response_id` orqali keyingi savollarda hujjat qayta yuborilmaydi —
# suhbat OpenAI tomonida davom ettiriladi. `blocks` esa zaxira nusxa.
_DOCS: dict[int, dict[str, Any]] = {}

INTRO = """🤖 <b>AI maslahatchi rejimi</b>

Menga hujjat yuboring — men uni professional tahlilchi sifatida chuqur o'rganib beraman:

• 📌 Hujjat mohiyati va asosiy ko'rsatkichlar
• 📈 Raqamlar tahlili va tendensiyalar
• ⚠️ Xavflar, yashirin shartlar, ogohlantirishlar
• ✅ Aniq tavsiyalar

<b>Qabul qilinadigan formatlar:</b>
PDF, DOCX, XLSX, PPTX, CSV, TXT, JSON va rasmlar (chek, skrinshot, skan).

Tahlildan keyin hujjat bo'yicha istalgan savolni berishingiz mumkin.

<i>Chiqish uchun /bekor</i>"""


async def _send_long(message: Message, text: str) -> None:
    """Uzun tahlilni bo'laklab yuboradi (AI matni — HTML sifatida talqin qilinmaydi)."""
    for chunk in split_message(text):
        await message.answer(chunk, parse_mode=None)


@router.message(Command("maslahat"))
@router.message(F.text == kb.BTN_ADVISOR)
async def cmd_advisor(message: Message, state: FSMContext) -> None:
    await state.set_state(AdvisorStates.chatting)
    await message.answer(INTRO)


@router.callback_query(F.data == "advisor:exit")
async def cb_exit(callback: CallbackQuery, state: FSMContext) -> None:
    await state.clear()
    _DOCS.pop(callback.from_user.id, None)
    await callback.message.answer(
        "✅ Hisobchi rejimiga qaytdik.", reply_markup=kb.main_menu
    )
    await callback.answer()


# ---------------------------------------------------------------------------
# Hujjat qabul qilish — rejimdan qat'i nazar ishlaydi
# ---------------------------------------------------------------------------

@router.message(F.document | F.photo)
async def handle_document(message: Message, bot: Bot, state: FSMContext) -> None:
    if message.document:
        media = message.document
        filename = media.file_name or "hujjat"
        mime = media.mime_type or ""
    else:
        media = message.photo[-1]  # eng yuqori sifatli variant
        filename = "rasm.jpg"
        mime = "image/jpeg"

    if media.file_size and media.file_size > config.MAX_FILE_MB * 1024 * 1024:
        await message.answer(
            f"⚠️ Fayl juda katta. Telegram orqali {config.MAX_FILE_MB} MB gacha "
            f"fayl qabul qila olaman."
        )
        return

    status = await message.answer(f"📄 <b>{filename}</b>\n\n⏳ O'qiyapman…")

    buffer = BytesIO()
    await bot.download(media, destination=buffer)

    try:
        blocks = await documents.to_content_blocks(buffer.getvalue(), filename, mime)
    except documents.UnsupportedDocument as exc:
        await status.edit_text(f"⚠️ {exc}")
        return
    except Exception:
        logger.exception("Hujjatni o'qishda xato")
        await status.edit_text("⚠️ Faylni o'qiy olmadim. Boshqa formatda yuborib ko'ring.")
        return

    await status.edit_text(
        f"📄 <b>{filename}</b>\n\n🧠 Chuqur tahlil qilinmoqda… Bu 1-2 daqiqa olishi mumkin."
    )
    await bot.send_chat_action(message.chat.id, "typing")

    try:
        analysis = await ai.analyze_document(blocks)
    except Exception:
        logger.exception("Hujjat tahlilida xato")
        await status.edit_text(
            "⚠️ Tahlil qilishda xatolik yuz berdi. Biroz kutib, qayta urinib ko'ring."
        )
        return

    _DOCS[message.from_user.id] = {
        "blocks": blocks,
        "filename": filename,
        "response_id": analysis.get("response_id"),
    }
    await state.set_state(AdvisorStates.chatting)

    await status.edit_text(f"📄 <b>{filename}</b> — tahlil tayyor 👇")
    await _send_long(message, analysis["text"])
    await message.answer(
        "💬 Ushbu hujjat bo'yicha savolingiz bormi? Shu yerga yozing.\n"
        "<i>Masalan: «Eng xavfli band qaysi?» yoki «Foyda marjasini hisoblab ber»</i>",
        reply_markup=kb.advisor_exit,
    )


# ---------------------------------------------------------------------------
# Hujjat bo'yicha savol-javob
# ---------------------------------------------------------------------------

@router.message(AdvisorStates.chatting, F.text & ~F.text.startswith("/"))
async def handle_followup(message: Message, bot: Bot) -> None:
    document = _DOCS.get(message.from_user.id)
    if not document:
        await message.answer(
            "📎 Avval tahlil qilinadigan hujjatni yuboring.\n\n"
            "<i>Hisobchi rejimiga qaytish uchun /bekor</i>"
        )
        return

    status = await message.answer("🧠 O'ylayapman…")
    await bot.send_chat_action(message.chat.id, "typing")

    try:
        if document.get("response_id"):
            # Suhbat serverda davom etadi — hujjat qayta yuborilmaydi
            answer = await ai.ask_followup(
                document["response_id"], message.text, document["blocks"]
            )
        else:
            answer = await ai.analyze_document(document["blocks"], question=message.text)
    except Exception:
        logger.exception("Savolga javob berishda xato")
        await status.edit_text("⚠️ Javob tayyorlashda xatolik yuz berdi.")
        return

    document["response_id"] = answer.get("response_id")
    await status.delete()
    await _send_long(message, answer["text"])

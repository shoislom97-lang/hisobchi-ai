"""Hisobchi AI — Telegram bot.

Ishga tushirish:
    python bot.py
"""

from __future__ import annotations

import asyncio
import logging
from typing import Any, Awaitable, Callable

from aiogram import BaseMiddleware, Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.types import BotCommand, CallbackQuery, Message, TelegramObject

import config
from handlers import routers
from services import sheets

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
)
logging.getLogger("aiogram.event").setLevel(logging.WARNING)
logger = logging.getLogger("hisobchi")


class AccessMiddleware(BaseMiddleware):
    """ALLOWED_USER_IDS bo'sh bo'lmasa — faqat ro'yxatdagilarni o'tkazadi."""

    async def __call__(
        self,
        handler: Callable[[TelegramObject, dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: dict[str, Any],
    ) -> Any:
        if not config.ALLOWED_USER_IDS:
            return await handler(event, data)

        user = data.get("event_from_user")
        if user and user.id in config.ALLOWED_USER_IDS:
            return await handler(event, data)

        logger.warning("Ruxsatsiz urinish: %s", user.id if user else "noma'lum")
        if isinstance(event, Message):
            await event.answer("⛔️ Kechirasiz, sizda bu botdan foydalanish huquqi yo'q.")
        elif isinstance(event, CallbackQuery):
            await event.answer("⛔️ Ruxsat yo'q", show_alert=True)
        return None


COMMANDS = [
    BotCommand(command="start", description="Botni ishga tushirish"),
    BotCommand(command="hisobot", description="Moliyaviy xulosa"),
    BotCommand(command="excel", description="Excel faylini yuklab olish"),
    BotCommand(command="oxirgi", description="Oxirgi 10 ta yozuv"),
    BotCommand(command="maslahat", description="AI maslahatchi — hujjat tahlili"),
    BotCommand(command="kategoriyalar", description="Kategoriyalar ro'yxati"),
    BotCommand(command="bekor", description="Joriy rejimdan chiqish"),
    BotCommand(command="help", description="Yordam"),
]


async def main() -> None:
    bot = Bot(
        token=config.BOT_TOKEN,
        default=DefaultBotProperties(parse_mode=ParseMode.HTML),
    )

    dispatcher = Dispatcher(storage=MemoryStorage())
    dispatcher.message.middleware(AccessMiddleware())
    dispatcher.callback_query.middleware(AccessMiddleware())
    for router in routers:
        dispatcher.include_router(router)

    # Sozlamalar to'g'riligini darhol tekshiramiz — xato bo'lsa ishga tushmaydi
    try:
        title = await sheets.healthcheck()
        logger.info("Google Sheets ulandi: %s", title)
    except Exception:
        logger.exception(
            "Google Sheets'ga ulana olmadim. SPREADSHEET_ID va "
            "GOOGLE_CREDENTIALS_FILE ni tekshiring, hamda jadvalni servis "
            "akkaunt e-mailiga ulashganingizga ishonch hosil qiling."
        )
        raise

    await bot.set_my_commands(COMMANDS)
    me = await bot.get_me()
    logger.info("Bot ishga tushdi: @%s", me.username)

    try:
        await dispatcher.start_polling(bot, allowed_updates=dispatcher.resolve_used_update_types())
    finally:
        await bot.session.close()


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("Bot to'xtatildi")

"""/start, /help va umumiy buyruqlar."""

from __future__ import annotations

from aiogram import F, Router
from aiogram.filters import Command, CommandStart
from aiogram.fsm.context import FSMContext
from aiogram.types import Message

import config
import keyboards as kb

router = Router(name="common")

WELCOME = """👋 <b>Salom, {name}!</b>

Men — sizning <b>Hisobchi AI</b> yordamchingizman. Ikkita ishni bajaraman:

<b>1️⃣ Buxgalteriya</b>
Menga xarajat yoki daromadingizni oddiy tilda — <b>matn</b> yoki <b>ovozli xabar</b> bilan ayting. Men uni tahlil qilib, kerakli kategoriyaga joylayman va Google Sheets'ga saqlayman.

<i>Masalan:</i>
• «Bugun taksiga 25 ming berdim»
• «Korzinkadan 180k oziq-ovqat, yana 50 ming benzin»
• «Mijozdan 12 mln tushdi, karta orqali»

<b>2️⃣ AI maslahatchi</b>
Istalgan hujjatni yuboring — shartnoma, hisobot, biznes-reja, chek — men uni professional tahlilchi sifatida chuqur tahlil qilib beraman: asosiy raqamlar, xavflar, tavsiyalar.

📥 Istalgan payt <b>Excel</b> tugmasini bosib, barcha ma'lumotlaringizni yuklab olishingiz mumkin.

Boshlaymizmi? Birinchi xarajatingizni yozing 👇"""

HELP = """📖 <b>Qo'llanma</b>

<b>Yozuv qo'shish</b>
Shunchaki yozing yoki ayting:
• «85 ming non va sut» → 🔴 Chiqim / Oziq-ovqat
• «maosh 6 mln tushdi» → 🟢 Kirim / Maosh
• «kecha 200$ ijaraga to'ladim» → 🔴 Chiqim / Ijara

Bir xabarda bir nechta yozuv bo'lishi mumkin — hammasini alohida saqlayman.
Har bir yozuv tagida <b>✏️ Kategoriya</b> va <b>🗑 O'chirish</b> tugmalari bo'ladi.

<b>Buyruqlar</b>
/start — botni qayta ishga tushirish
/hisobot — davr bo'yicha moliyaviy xulosa
/excel — ma'lumotlarni .xlsx faylda olish
/oxirgi — oxirgi 10 ta yozuv
/maslahat — AI maslahatchi rejimi (hujjat tahlili)
/kategoriyalar — kategoriyalar ro'yxati
/bekor — joriy rejimdan chiqish

<b>AI maslahatchi</b>
Hujjatni yuboring — PDF, DOCX, XLSX, PPTX, CSV, TXT yoki rasm.
Tahlildan keyin hujjat bo'yicha qo'shimcha savollar berishingiz mumkin.

<b>Ovozli xabar</b>
Mikrofonni bosib gapiring — men eshitib, yozuvga aylantiraman.

⚠️ <i>AI tahlili — dastlabki maslahat. Muhim moliyaviy va yuridik qarorlar uchun mutaxassisga murojaat qiling.</i>"""


@router.message(CommandStart())
async def cmd_start(message: Message, state: FSMContext) -> None:
    await state.clear()
    name = message.from_user.first_name or "do'stim"
    await message.answer(WELCOME.format(name=name), reply_markup=kb.main_menu)


@router.message(Command("help"))
@router.message(F.text == kb.BTN_HELP)
async def cmd_help(message: Message) -> None:
    await message.answer(HELP, reply_markup=kb.main_menu)


@router.message(Command("bekor", "cancel"))
async def cmd_cancel(message: Message, state: FSMContext) -> None:
    await state.clear()
    await message.answer(
        "✅ Hisobchi rejimiga qaytdik. Xarajat yoki daromadingizni yozing.",
        reply_markup=kb.main_menu,
    )


@router.message(Command("kategoriyalar"))
async def cmd_categories(message: Message) -> None:
    income = "\n".join(f"  • {c}" for c in config.INCOME_CATEGORIES)
    expense = "\n".join(f"  • {c}" for c in config.EXPENSE_CATEGORIES)
    await message.answer(
        f"📁 <b>Kategoriyalar</b>\n\n"
        f"🟢 <b>Kirim</b>\n{income}\n\n"
        f"🔴 <b>Chiqim</b>\n{expense}\n\n"
        f"<i>Yozuv saqlangach, «✏️ Kategoriya» tugmasi orqali o'zgartirishingiz mumkin.</i>"
    )

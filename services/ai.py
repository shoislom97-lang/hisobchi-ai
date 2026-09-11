"""OpenAI bilan ishlash: tranzaksiya ajratish va hujjat tahlili.

Responses API ishlatiladi — u PDF va rasmlarni to'g'ridan-to'g'ri qabul qiladi,
`previous_response_id` orqali suhbatni serverda davom ettiradi va uzun
prefikslarni avtomatik keshlaydi.
"""

from __future__ import annotations

import json
from datetime import date
from typing import Any, NotRequired, TypedDict

from openai import AsyncOpenAI, NOT_GIVEN, NotFoundError

import config

# Chuqur tahlil bir necha daqiqa olishi mumkin
client = AsyncOpenAI(api_key=config.OPENAI_API_KEY, timeout=300.0, max_retries=3)


class Analysis(TypedDict):
    """Tahlil natijasi va uni davom ettirish uchun javob identifikatori."""

    text: str
    response_id: NotRequired[str | None]


def _reasoning(model: str, effort: str) -> Any:
    """Model qo'llab-quvvatlasa `reasoning` parametrini beradi."""
    return {"effort": effort} if config.supports_reasoning(model) else NOT_GIVEN


# ---------------------------------------------------------------------------
# 1-vazifa: matn/ovozdan moliyaviy yozuv ajratish
# ---------------------------------------------------------------------------

BOOKKEEPER_SYSTEM = f"""Sen — O'zbekistondagi kichik biznes va shaxsiy moliya uchun ishlaydigan
tajribali buxgaltersan. Foydalanuvchi senga erkin shaklda (matn yoki ovozli xabar
transkripsiyasi) pul harakati haqida yozadi. Sening vazifang — har bir pul
harakatini aniq yozuvga aylantirish.

QOIDALAR:
1. Bitta xabarda bir nechta tranzaksiya bo'lishi mumkin — har birini alohida yozuv qil.
2. Summani har doim to'liq songa aylantir:
   "500 ming" / "500k" / "500 mingta" -> 500000
   "2 mln" / "2 million" / "2 limon" -> 2000000
   "3,5 mln" -> 3500000
   "20$" -> 20 (valyuta USD)
3. Valyuta aytilmasa — {config.DEFAULT_CURRENCY}.
4. Turi:
   - "kirim"  — pul kelgan bo'lsa (oldim, tushdi, sotdim, to'lashdi, kirim)
   - "chiqim" — pul ketgan bo'lsa (berdim, to'ladim, oldim=xarid, sarfladim)
   Diqqat: "non oldim" — bu XARID, ya'ni chiqim. "maosh oldim" — bu kirim.
5. Kategoriyani faqat ruxsat etilgan ro'yxatdan tanla. Mos kelmasa
   "Boshqa kirim" yoki "Boshqa chiqim" ni ishlat.
6. Sana: "kecha", "3 kun oldin", "1-mart" kabi so'zlarni foydalanuvchi xabaridagi
   bugungi sanaga tayanib YYYY-MM-DD ga aylantir. Sana aytilmasa — bugungi sana.
7. `description` — qisqa, aniq izoh (masalan "Korzinka'dan oziq-ovqat").
8. `confidence` — 0 dan 1 gacha: summa va kategoriyaga qanchalik ishonching.
   Summa noaniq bo'lsa 0.5 dan past qo'y.
9. Matn ovozli xabardan olingan bo'lishi mumkin — unda so'zlar biroz buzilgan
   bo'ladi ("Miyozdan" = "Mijozdan", "Qarzinka" = "Korzinka"). Ma'noga qarab tushun.
10. Agar xabarda umuman pul harakati bo'lmasa: `is_financial` = false,
    `transactions` = [] va `reply` da foydalanuvchiga o'zbek tilida qisqa javob yoz.
11. `reply` — foydalanuvchiga ko'rsatiladigan bitta qisqa jumla (o'zbek tilida).
    Tranzaksiya topilgan bo'lsa bo'sh qatorni ("") qaytar.

Hech qachon summani o'ylab topma. Aniq bo'lmasa `confidence` ni pasaytir."""


TRANSACTION_SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {
        "is_financial": {
            "type": "boolean",
            "description": "Xabarda kamida bitta pul harakati bormi",
        },
        "reply": {
            "type": "string",
            "description": "Moliyaviy bo'lmagan xabarga qisqa javob, aks holda bo'sh satr",
        },
        "transactions": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "type": {"type": "string", "enum": ["kirim", "chiqim"]},
                    "amount": {"type": "number"},
                    "currency": {"type": "string", "enum": config.CURRENCIES},
                    "category": {"type": "string", "enum": config.ALL_CATEGORIES},
                    "description": {"type": "string"},
                    "date": {"type": "string", "description": "YYYY-MM-DD"},
                    "payment_method": {"type": "string", "enum": config.PAYMENT_METHODS},
                    "counterparty": {
                        "type": "string",
                        "description": "Kim bilan muomala; noma'lum bo'lsa bo'sh satr",
                    },
                    "confidence": {"type": "number"},
                },
                "required": [
                    "type",
                    "amount",
                    "currency",
                    "category",
                    "description",
                    "date",
                    "payment_method",
                    "counterparty",
                    "confidence",
                ],
                "additionalProperties": False,
            },
        },
    },
    "required": ["is_financial", "reply", "transactions"],
    "additionalProperties": False,
}

NOT_UNDERSTOOD = {
    "is_financial": False,
    "reply": "Bu xabarni qayta ishlay olmadim. Boshqacha yozib ko'ring.",
    "transactions": [],
}


async def parse_transactions(text: str, today: date | None = None) -> dict[str, Any]:
    """Erkin matndan tranzaksiyalar ro'yxatini ajratadi."""
    today = today or date.today()

    response = await client.responses.create(
        model=config.PARSER_MODEL,
        instructions=BOOKKEEPER_SYSTEM,
        input=f"Bugungi sana: {today.isoformat()}\n\nXabar:\n{text}",
        text={
            "format": {
                "type": "json_schema",
                "name": "moliyaviy_yozuvlar",
                "schema": TRANSACTION_SCHEMA,
                "strict": True,
            }
        },
        reasoning=_reasoning(config.PARSER_MODEL, "low"),
        max_output_tokens=4000,
    )

    raw = (response.output_text or "").strip()
    if not raw:
        return dict(NOT_UNDERSTOOD)
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        return dict(NOT_UNDERSTOOD)


# ---------------------------------------------------------------------------
# 2-vazifa: AI maslahatchi — hujjat tahlili
# ---------------------------------------------------------------------------

ANALYST_SYSTEM = """Sen — moliyaviy hisobot, shartnoma, biznes-reja va boshqa ishbilarmonlik
hujjatlarini tahlil qiluvchi professional tahlilchisan. 15 yillik tajribang bor:
audit, moliyaviy modellashtirish va yuridik risklarni baholash.

Har bir hujjatni quyidagi tartibda chuqur tahlil qil va javobni O'ZBEK TILIDA yoz:

1. HUJJAT HAQIDA — turi, maqsadi, kimga tegishli, qaysi davrni qamraydi.
2. ASOSIY KO'RSATKICHLAR — eng muhim raqamlar, summalar, muddatlar, foizlar.
   Raqamlarni hujjatdan aynan ol, o'zingdan hisoblaganingni alohida belgila.
3. CHUQUR TAHLIL — raqamlar nimani anglatadi, tendensiyalar, nisbatlar,
   normadan chetga chiqishlar. Taqqoslash mumkin bo'lsa taqqosla.
4. XAVFLAR VA OGOHLANTIRISHLAR — yashirin shartlar, jarimalar, noaniq
   formulalar, ziddiyatli bandlar, moliyaviy risklar. Har birining jiddiyligini
   belgila: 🔴 yuqori / 🟡 o'rta / 🟢 past.
5. TAVSIYALAR — aniq, bajarish mumkin bo'lgan qadamlar (3-7 ta).
6. SAVOLLAR — hujjatda javobi yo'q, lekin aniqlashtirish zarur bo'lgan nuqtalar.

MUHIM QOIDALAR:
- Hujjatda bo'lmagan ma'lumotni o'ylab topma. Ma'lumot yetishmasa, shuni ayt.
- Raqamlar bilan ishlaganda hisob-kitobingni ko'rsat.
- Yuridik yoki soliq masalalarida: bu dastlabki tahlil ekanini va yakuniy qaror
  uchun mutaxassisga murojaat qilish kerakligini eslatib o't.
- Javobni Telegram uchun yoz: qisqa xatboshilar, sarlavhalar, emoji belgilar.
  Markdown jadval va ** yulduzchalarni ishlatma — oddiy matn va ro'yxat ishlat.
- Uzunligi: hujjat hajmiga qarab 400-1200 so'z.

Keyingi savollarga javob berayotganda ham shu qoidalarga amal qil, lekin
javobni savolga moslab qisqa tut — butun tahlilni qaytadan yozma."""

FULL_ANALYSIS_PROMPT = (
    "Ushbu hujjatni yuqoridagi tartib bo'yicha to'liq va chuqur tahlil qil."
)


async def analyze_document(
    content_blocks: list[dict[str, Any]], question: str | None = None
) -> Analysis:
    """Hujjatni tahlil qiladi. Javob identifikatori keyingi savollar uchun saqlanadi."""
    blocks = list(content_blocks)
    blocks.append({"type": "input_text", "text": question or FULL_ANALYSIS_PROMPT})

    response = await client.responses.create(
        model=config.MODEL,
        instructions=ANALYST_SYSTEM,
        input=[{"role": "user", "content": blocks}],
        reasoning=_reasoning(config.MODEL, "high"),
        max_output_tokens=16000,
    )
    text = (response.output_text or "").strip()
    return {
        "text": text or "Tahlil natijasi bo'sh qaytdi. Qayta urinib ko'ring.",
        "response_id": response.id,
    }


async def ask_followup(
    previous_response_id: str, question: str, fallback_blocks: list[dict[str, Any]]
) -> Analysis:
    """Tahlil qilingan hujjat bo'yicha qo'shimcha savol.

    Avval suhbatni serverda davom ettirishga urinadi (hujjat qayta yuborilmaydi).
    Javob eskirgan bo'lsa — hujjatni to'liq qayta yuboradi.
    """
    try:
        response = await client.responses.create(
            model=config.MODEL,
            previous_response_id=previous_response_id,
            input=[{"role": "user", "content": [{"type": "input_text", "text": question}]}],
            reasoning=_reasoning(config.MODEL, "high"),
            max_output_tokens=16000,
        )
    except NotFoundError:
        # Javob muddati o'tgan — hujjatni qaytadan yuboramiz
        return await analyze_document(fallback_blocks, question=question)

    text = (response.output_text or "").strip()
    return {
        "text": text or "Javob bo'sh qaytdi. Savolni boshqacha berib ko'ring.",
        "response_id": response.id,
    }


# ---------------------------------------------------------------------------
# Moliyaviy hisobotga qisqa AI izoh
# ---------------------------------------------------------------------------

async def comment_on_report(summary_text: str) -> str:
    """Tayyor hisobot raqamlariga qisqa buxgalterlik izohi."""
    response = await client.responses.create(
        model=config.PARSER_MODEL,
        instructions=(
            "Sen tajribali buxgaltersan. Berilgan hisobot raqamlariga qarab "
            "o'zbek tilida 3-5 ta qisqa, aniq kuzatuv va tavsiya yoz. "
            "Raqamlarni o'ylab topma — faqat berilganini ishlat. "
            "Sarlavha yozma, to'g'ridan-to'g'ri ro'yxat bilan boshla. "
            "Markdown belgilarini (**, ##) ishlatma."
        ),
        input=summary_text,
        reasoning=_reasoning(config.PARSER_MODEL, "low"),
        max_output_tokens=2000,
    )
    return (response.output_text or "").strip()

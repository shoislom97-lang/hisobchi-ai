"""Ovozli xabarni matnga o'girish — OpenAI transkripsiyasi.

Telegram ovozli xabarlari OGG/Opus formatida keladi; OpenAI uni to'g'ridan-to'g'ri
qabul qiladi, shuning uchun ffmpeg yoki konvertatsiya kerak emas.

Muhim: OpenAI transkripsiyasi `language="uz"` ni qabul qilmaydi
("Language 'uz' is not supported"). Shuning uchun til `prompt` orqali
bildiriladi — sinovda bu eng aniq natija bergan usul.
"""

from __future__ import annotations

from openai import APIError, AsyncOpenAI

import config

client = AsyncOpenAI(api_key=config.OPENAI_API_KEY, timeout=120.0, max_retries=2)


class STTError(RuntimeError):
    """Ovozni matnga o'girishda yuz bergan xato."""


async def transcribe(audio: bytes, filename: str = "voice.ogg") -> str:
    """Ovoz baytlarini matnga aylantiradi. Bo'sh natija — nutq tanilmadi."""
    try:
        result = await client.audio.transcriptions.create(
            model=config.STT_MODEL,
            file=(filename, audio, "audio/ogg"),
            prompt=config.STT_PROMPT,
        )
    except APIError as exc:
        raise STTError(str(exc)) from exc
    except Exception as exc:  # noqa: BLE001 — foydalanuvchiga tushunarli xabar kerak
        raise STTError(str(exc)) from exc

    return (result.text or "").strip()

# 🤖 Hisobchi AI — Telegram bot

Ikkita vazifani bajaradigan AI yordamchi:

1. **Buxgalteriya** — foydalanuvchi matn yoki ovozli xabar yuboradi, AI uni tahlil
   qilib kategoriyaga joylaydi va Google Sheets'ga saqlaydi. Buyruq bilan barcha
   ma'lumotlar formatlangan **Excel** faylda beriladi.
2. **AI maslahatchi** — yuklangan istalgan hujjatni (PDF, DOCX, XLSX, PPTX, CSV,
   rasm) professional tahlilchi sifatida chuqur tahlil qiladi va undan keyin
   hujjat bo'yicha savol-javob qilish mumkin.

---

## Loyiha tuzilishi

```
exelbot/
├── bot.py                 # Ishga tushirish nuqtasi, ruxsat middleware'i
├── config.py              # .env dan sozlamalar, kategoriyalar ro'yxati
├── keyboards.py           # Tugmalar va callback'lar
├── handlers/
│   ├── common.py          # /start, /help, kategoriyalar
│   ├── finance.py         # Matn/ovoz -> tranzaksiya -> Sheets
│   ├── reports.py         # /hisobot, /excel, /oxirgi
│   └── advisor.py         # Hujjat tahlili va savol-javob
├── services/
│   ├── ai.py              # OpenAI: tranzaksiya ajratish + hujjat tahlili
│   ├── sheets.py          # Google Sheets ombori
│   ├── excel.py           # .xlsx hisobot (diagrammalar bilan)
│   ├── stt.py             # Ovoz -> matn (OpenAI transkripsiyasi)
│   └── documents.py       # Fayllardan Responses API uchun bloklar
└── utils/formatting.py    # Matn formatlash, davrlar, bo'laklash
```

---

## O'rnatish

### 1. Kutubxonalar

```bash
pip install -r requirements.txt
```

### 2. Telegram bot tokeni

[@BotFather](https://t.me/BotFather) → `/newbot` → tokenni nusxa oling.

### 3. OpenAI API kaliti

[platform.openai.com](https://platform.openai.com/api-keys) → **Create new secret key**.

Ishlatiladigan modellar (`.env` orqali o'zgartiriladi):

| Vazifa | Model | Nima uchun |
|---|---|---|
| Tranzaksiya ajratish | `gpt-5.4-mini` | Tez (~1-3s), arzon, o'zbekcha summalarni to'g'ri tushunadi |
| Hujjat tahlili | `gpt-5.5` | Chuqur fikrlash, PDF'ni o'zi o'qiydi |
| Ovoz → matn | `gpt-transcribe` | O'zbek nutqini eng aniq tanigan model |

### 4. Google Sheets

1. [console.cloud.google.com](https://console.cloud.google.com) da loyiha yarating.
2. **APIs & Services → Library** da yoqing:
   - `Google Sheets API`
   - `Google Drive API`
3. **IAM & Admin → Service Accounts** → servis akkaunt yarating →
   **Keys → Add Key → JSON** → faylni `credentials.json` nomi bilan loyiha
   papkasiga saqlang.
4. Google Sheets'da yangi jadval yarating va uni servis akkaunt e-mailiga
   (`...@....iam.gserviceaccount.com`) **Editor** huquqi bilan ulashing.
5. Jadval ID'si — havoladagi qism:
   `docs.google.com/spreadsheets/d/`**`SHU_YER`**`/edit`

> Ish varag'i va sarlavhalar bot birinchi ishga tushganda avtomatik yaratiladi.

### 5. Sozlamalar

`.env.example` faylidan nusxa oling va to'ldiring:

```bash
copy .env.example .env
```

```env
BOT_TOKEN=123456:AA...
OPENAI_API_KEY=sk-proj-...
SPREADSHEET_ID=1AbCdEf...
GOOGLE_CREDENTIALS_FILE=credentials.json
ALLOWED_USER_IDS=123456789        # bo'sh = hamma uchun ochiq
```

Telegram ID'ingizni bilmasangiz — [@userinfobot](https://t.me/userinfobot) ga
yozing, u ID'ni qaytaradi.

### 6. Ishga tushirish

```bash
python bot.py
```

---

## Ovozli xabarlar

Telegram ovozni OGG/Opus formatida yuboradi — OpenAI uni to'g'ridan-to'g'ri
qabul qiladi, shuning uchun ffmpeg yoki konvertatsiya kerak emas.

**Muhim texnik nuqta:** OpenAI transkripsiyasi `language="uz"` parametrini
qabul qilmaydi (`Language 'uz' is not supported`). Shuning uchun til `prompt`
orqali bildiriladi — `config.STT_PROMPT` da. Sinovda taqqoslash natijasi:

| Model | Natija |
|---|---|
| `gpt-transcribe` + prompt | ✅ «Bugun taksiga yigirma besh ming so'm berdim» |
| `gpt-4o-transcribe` + prompt | ✅ Deyarli bir xil, ba'zan «orkali» |
| `whisper-1` | ❌ Turkchaga burib yuboradi: «Bugün taksiye yirmi beş bin som verdim» |

Shuning uchun standart model — `gpt-transcribe`.

---

## Foydalanish

**Yozuv qo'shish** — shunchaki yozing yoki ayting:

| Xabar | Natija |
|---|---|
| «Bugun taksiga 25 ming berdim» | 🔴 Chiqim · 25 000 UZS · Transport |
| «Korzinkadan 180k oziq-ovqat, yana 50 ming benzin» | 2 ta alohida yozuv |
| «Mijozdan 12 mln tushdi, karta orqali» | 🟢 Kirim · 12 000 000 UZS · Savdo tushumi |
| «kecha 200$ ijaraga to'ladim» | 🔴 Chiqim · 200 USD · Ijara · kechagi sana |

Har bir yozuv tagida **✏️ Kategoriya** va **🗑 O'chirish** tugmalari chiqadi.

**Buyruqlar**

| Buyruq | Vazifasi |
|---|---|
| `/hisobot` | Davr bo'yicha xulosa + AI buxgalter izohi |
| `/excel` | `.xlsx` fayl: «Tranzaksiyalar» + «Xulosa» (doiraviy va ustunli diagrammalar) |
| `/oxirgi` | Oxirgi 10 ta yozuv |
| `/maslahat` | AI maslahatchi rejimi |
| `/kategoriyalar` | Kategoriyalar ro'yxati |
| `/bekor` | Joriy rejimdan chiqish |

---

## Texnik yechimlar

- **Aniq kategoriyalar.** Modelga `strict: true` bilan JSON Schema beriladi va
  kategoriya maydoni `enum` bilan cheklanadi — model hech qachon ro'yxatdan
  tashqari kategoriya qaytara olmaydi, javob har doim yaroqli JSON bo'ladi.
- **Suhbatni davom ettirish.** Hujjat tahlilidan keyingi savollarda hujjat qayta
  yuborilmaydi: `previous_response_id` orqali suhbat OpenAI tomonida davom
  etadi. Sinovda to'liq tahlil 42 s, keyingi savol atigi **4 s** oldi.
  Javob muddati o'tgan bo'lsa — kod hujjatni avtomatik qayta yuboradi.
- **Xarajatni kamaytirish.** Tranzaksiya ajratish — qisqa vazifa, shuning uchun
  arzonroq model va `reasoning: {"effort": "low"}`; hujjat tahlili —
  `effort: "high"`.
- **PDF va rasmlar** modelga o'z holicha yuboriladi — u jadvallar, grafiklar va
  skanlarni o'qiy oladi. DOCX/XLSX/PPTX dan matn lokal ajratiladi.
- **Bloklanmaydigan I/O.** `gspread` va `openpyxl` sinxron ishlaydi, shuning uchun
  ular `asyncio.to_thread` ichida chaqiriladi; Google Sheets yozuvlari `asyncio.Lock`
  bilan himoyalangan.

---

## Cheklovlar

- Telegram Bot API orqali **20 MB** gacha fayl qabul qilinadi.
- Ma'lumotlar bitta Google Sheets varag'ida saqlanadi va `User ID` bo'yicha
  filtrlanadi. Foydalanuvchilar soni ko'payganda (~50k qatordan oshganda)
  ma'lumotlar bazasiga (PostgreSQL) o'tish tavsiya etiladi.
- FSM holati xotirada (`MemoryStorage`) saqlanadi — bot qayta ishga tushganda
  maslahatchi rejimidagi joriy hujjat yo'qoladi. Doimiy saqlash uchun Redis
  storage'ga o'tish mumkin.
- AI tahlili — dastlabki maslahat. Muhim moliyaviy va yuridik qarorlar uchun
  mutaxassis bilan maslahatlashish kerak.

---

## Railway'ga joylashtirish

Bot doimiy ishlashi uchun uni serverga joylash kerak. Railway `Procfile` va
`railway.json` orqali avtomatik sozlanadi — bot **worker** sifatida ishlaydi
(HTTP porti kerak emas, chunki u Telegram'dan o'zi so'rab turadi).

### 1. Kodni GitHub'ga yuklang

```bash
git push -u origin main
```

### 2. Railway loyihasi

[railway.app](https://railway.app) → **New Project** → **Deploy from GitHub repo**
→ `hisobchi-ai` reposini tanlang.

### 3. Muhit o'zgaruvchilari

Railway'da `.env` fayli bo'lmaydi. Loyiha → **Variables** bo'limiga quyidagilarni
qo'shing:

| O'zgaruvchi | Qiymat |
|---|---|
| `BOT_TOKEN` | @BotFather bergan token |
| `OPENAI_API_KEY` | `sk-proj-...` |
| `ALLOWED_USER_IDS` | Telegram ID'ingiz |
| `SPREADSHEET_ID` | Jadval havolasidagi ID |
| `GOOGLE_CREDENTIALS_JSON` | `credentials.json` faylining **butun mazmuni** |
| `OPENAI_MODEL` | `gpt-5.5` |
| `OPENAI_PARSER_MODEL` | `gpt-5.4-mini` |
| `OPENAI_STT_MODEL` | `gpt-transcribe` |

> `GOOGLE_CREDENTIALS_JSON` — faylni matn muharririda oching, hammasini nusxalab
> (`Ctrl+A`, `Ctrl+C`) qiymat maydoniga qo'ying. Qatorlarni o'zgartirmang.
> Kod uni `GOOGLE_CREDENTIALS_FILE` dan ustun qo'yadi, shuning uchun serverda
> fayl kerak emas.

### 4. Ishga tushirish

Railway o'zi build qilib ishga tushiradi. **Deploy Logs** da quyidagi qatorlarni
ko'rsangiz — hammasi joyida:

```
Google Sheets ulandi: Hisobchi AI — Tranzaksiyalar
Bot ishga tushdi: @<bot_nomi>
Run polling for bot ...
```

### Muhim: bir vaqtda faqat bitta nusxa

Telegram bitta botga bir vaqtda faqat bitta `getUpdates` oqimiga ruxsat beradi.
Railway'da ishga tushirgandan keyin **kompyuteringizdagi botni to'xtating**, aks
holda ikkalasi navbat bilan xabarlarni tortib oladi va bot xato ishlaydi.

```powershell
Get-CimInstance Win32_Process -Filter "name='python.exe'" |
  Where-Object CommandLine -like '*bot.py*' |
  ForEach-Object { Stop-Process -Id $_.ProcessId }
```

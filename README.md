# AI Sales Agent

O'zbekiston bozori uchun ko'p tashkilotli (multi-tenant) AI sotuv platformasi: Telegram bot, sayt chat widgeti va to'liq SaaS boshqaruv paneli. AI hujjatlar (RAG) va mahsulot bazasi asosida javob beradi, buyurtma qabul qiladi, operatorga uzatadi.

## Imkoniyatlar

- **Autentifikatsiya** — email/parol, access + refresh token, parol tiklash, rollar (Super Admin, Owner, Manager, Operator).
- **Tashkilotlar** — har bir ma'lumot `org_id` bilan izolyatsiya qilinadi; boshqa tashkilot resursi `404` qaytaradi.
- **Bilim bazasi** — PDF, DOCX, TXT, CSV, MD yuklash, bo'limlarga asoslangan chunking, embedding, semantik + leksik qidiruv, manba iqtiboslari, qayta indekslash.
- **AI agent** — ism/persona, UZ/RU/EN, byudjet va kategoriya bo'yicha mahsulot tanlash, narx/ombor tekshiruvi, bosqichma-bosqich buyurtma, operatorga handoff, noto'g'ri javobni aniqlash.
- **Telegram** — token bilan ulash, webhook (secret header + dedupe), operator rejimi.
- **Sayt widgeti** — Shadow DOM, rang/sarlavha sozlash, anonim tashrif buyuruvchi tarixi, `data-ai-widget` orqali embed.
- **Mahsulot va buyurtmalar** — CRUD, qoldiq, buyurtma raqami, statuslar, bekor qilganda qoldiqni tiklash.
- **Analitika** — suhbat, xabar, buyurtma, tushum, konversiya, kanallar va top mahsulotlar.
- **Billing** — Starter / Pro / Business, oylik to'lov tarixi, limitlar (suhbat, hujjat, xodim).

## Texnologiyalar

FastAPI · SQLAlchemy 2 (async) · SQLite/aiosqlite · Pydantic v2 · JWT + bcrypt · Fernet · pypdf/python-docx · NumPy · vanilla JS SPA · pytest

LLM kaliti bo'lmasa ham tizim to'liq ishlaydi: deterministik offline agent va lokal 384-o'lchamli hashing embeddinglar ishlatiladi. `LLM_API_KEY` qo'shilsa, OpenAI-mos chat + tool calling va `text-embedding-3-small` yoqiladi.

To'liq manba kodi bitta hujjatda: [`PROJECT_CODE.md`](PROJECT_CODE.md) — barcha backend, frontend va test fayllari.

## Tez boshlash (Windows)

```bash
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
copy .env.example .env
uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
```

Linux/macOS:

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
```

Birinchi ishga tushishda `data/app.db` yaratiladi va demo ma'lumotlar seed qilinadi.

| Sahifa | Manzil |
| --- | --- |
| Landing | http://127.0.0.1:8000/ |
| Kirish / ro'yxatdan o'tish | http://127.0.0.1:8000/login |
| Boshqaruv paneli | http://127.0.0.1:8000/dashboard |
| Demo do'kon + widget | http://127.0.0.1:8000/demo |
| API hujjati | http://127.0.0.1:8000/api/docs |

### Demo hisoblar

| Rol | Email | Parol |
| --- | --- | --- |
| Owner (TechNova Store) | `demo@aisales.uz` | `Demo12345` |
| Super Admin | `admin@aisales.uz` | `Admin12345` |

Demo widget kaliti: `demo-store-widget`.

## Sozlamalar (`.env`)

| O'zgaruvchi | Tavsif |
| --- | --- |
| `SECRET_KEY` | JWT va token shifrlash kaliti (productionda ≥32 belgi) |
| `DATABASE_URL` | `sqlite+aiosqlite:///./data/app.db` yoki PostgreSQL URL |
| `PUBLIC_BASE_URL` | Widget kodi va Telegram webhook uchun tashqi manzil (`https://...`) |
| `TELEGRAM_POLLING` | Bo'sh bo'lsa avtomatik: http manzilda polling, https manzilda webhook |
| `LLM_API_KEY` | Bo'sh bo'lsa offline agent ishlaydi |
| `LLM_BASE_URL`, `LLM_MODEL` | OpenAI-mos provayder |
| `SEED_DEMO` | `false` qilinsa demo ma'lumot yozilmaydi |
| `INGEST_SYNC` | `false` bo'lsa hujjat fonda indekslanadi |
| `RATE_LIMIT_PER_MINUTE` | Public API uchun daqiqalik limit |
| `MAX_UPLOAD_MB` | Fayl hajmi chegarasi |

## Telegram botni ulash

1. [@BotFather](https://t.me/BotFather) orqali `/newbot` bilan bot yarating va tokenni oling.
2. Dashboard → **Integratsiyalar** → Telegram bo'limiga tokenni kiriting.
3. Token ulangach bot avtomatik ishga tushadi:
   - **Lokal (default)** — `PUBLIC_BASE_URL` http bo'lsa long polling yoqiladi; ngrok shart emas, `uvicorn` ishlab turishi kifoya.
   - **Production** — `PUBLIC_BASE_URL=https://domen` bo'lsa webhook rejimi ishlatiladi; **Webhookni o'rnatish** tugmasini bosing.
4. Telegramda botga `/start` yozib tekshiring.

Rejimni majburan tanlash: `TELEGRAM_POLLING=true` (polling) yoki `false` (webhook).

Webhook: `POST /api/v1/telegram/webhook/{secret}`. `X-Telegram-Bot-Api-Secret-Token` noto'g'ri bo'lsa `403`, takroriy `update_id` e'tiborsiz qoldiriladi. Polling rejimida `getUpdates` ishlatiladi, webhook avtomatik o'chiriladi.

## Widgetni saytga qo'shish

Dashboard → **Integratsiyalar** → Widget bo'limidan kodni nusxalang:

```html
<script src="https://sizning-domen/static/js/widget.js" data-ai-widget="PUBLIC_KEY" defer></script>
```

Widget Shadow DOM ichida ishlaydi, sayt CSS'i bilan to'qnashmaydi. Dasturiy boshqaruv:

```js
AISalesWidget["PUBLIC_KEY"].open();
AISalesWidget["PUBLIC_KEY"].prefill("Noutbuk kerak");
```

## Testlar

```bash
.venv\Scripts\python.exe -m pytest -q
```

18 ta integratsion test alohida `data/test_app.db` bazasida ishlaydi (demo baza tegmaydi): autentifikatsiya/refresh, parol tiklash, RBAC, tashkilotlar izolyatsiyasi, bilim bazasi yuklash/qidirish/o'chirish, offline agent (byudjet, narx, buyurtma, handoff), widget, Telegram webhook/polling va billing limitlari.

## Loyiha tuzilishi

```
app/
  main.py            # FastAPI, middleware, sahifalar
  config.py          # sozlamalar va tariflar
  models.py          # SQLAlchemy modellari
  schemas.py         # Pydantic kontraktlar
  security.py        # JWT, parol, Context, RBAC
  crypto.py          # Telegram tokenini shifrlash
  routers/           # auth, orgs, knowledge, products, orders, ...
  services/          # agent, rag, embeddings, extract, chat, limits, ...
  services/telegram_bot.py     # Telegram update ishlovi (webhook + polling)
  services/telegram_polling.py # long polling runner
  seed.py            # demo ma'lumotlar
static/
  js/dashboard.js    # SPA panel
  js/widget.js       # embeddable chat
templates/           # landing, auth, dashboard, demo
tests/               # pytest integratsion testlar
scripts/seed.py      # bazani qo'lda seed qilish
```

## API qisqacha

Barcha biznes endpointlar `/api/v1` ostida. Avtorizatsiya: `Authorization: Bearer <access>`; faol tashkilot: `X-Org-Id` (yoki token ichidagi `org`).

| Guruh | Endpointlar |
| --- | --- |
| Auth | `POST /auth/register`, `/login`, `/refresh`, `/logout`, `/forgot-password`, `/reset-password`, `GET /auth/me` |
| Tashkilot | `GET/PATCH /orgs`, `GET/POST /orgs/members`, `PATCH/DELETE /orgs/members/{id}`, `GET/PUT /orgs/agent` |
| Bilim bazasi | `POST /knowledge/upload`, `GET /knowledge`, `DELETE /knowledge/{id}`, `POST /knowledge/{id}/reindex`, `POST /knowledge/query` |
| Mahsulotlar | `GET/POST /products`, `PATCH/DELETE /products/{id}` |
| Buyurtmalar | `GET/POST /orders`, `GET /orders/{id}`, `PATCH /orders/{id}/status` |
| Suhbatlar | `GET /conversations`, `GET /conversations/{id}`, `POST .../reply`, `.../handoff`, `.../resume-ai` |
| Analitika | `GET /analytics/overview`, `GET /analytics/audit-logs` |
| Billing | `GET /billing`, `POST /billing/subscribe`, `GET /billing/payments` |
| Integratsiya | `GET/POST/DELETE /integrations/telegram`, `POST .../set-webhook`, `GET/PUT /integrations/widget` |
| Public | `GET /public/widget/{key}/config`, `POST .../messages`, `GET .../history`, `GET /public/demo` |
| Super Admin | `GET /admin/stats`, `GET /admin/orgs`, `PATCH /admin/orgs/{id}/plan` |

## Production eslatmalari

- `SECRET_KEY` almashtirilmasa startupda ogohlantirish chiqadi.
- SQLite o'rniga PostgreSQL ishlatish tavsiya etiladi; migratsiyalar uchun Alembic qo'shilishi mumkin.
- `PUBLIC_BASE_URL` HTTPS bo'lsa webhook, http bo'lsa long polling ishlatiladi (productionda HTTPS tavsiya etiladi).
- Telegram tokenlari Fernet bilan shifrlangan holda saqlanadi.
- Har bir muhim amal `audit_logs` jadvaliga yoziladi.

from __future__ import annotations

import logging
from datetime import timedelta

from sqlalchemy import select

from app.config import settings
from app.database import SessionLocal
from app.models import (
    AgentSettings,
    Conversation,
    KnowledgeDocument,
    Membership,
    Message,
    Order,
    Organization,
    Product,
    User,
    Widget,
    utcnow,
)
from app.security import hash_password
from app.services.knowledge import ingest_bytes

logger = logging.getLogger(__name__)

DEMO_EMAIL = "demo@aisales.uz"
DEMO_PASSWORD = "Demo12345"
DEMO_SLUG = "demo-store"
DEMO_WIDGET_KEY = "demo-store-widget"

DEMO_PRODUCTS = [
    ("MacBook Air M3 13\"", "Apple", "laptop", 15_990_000, 17_500_000, 6, ["8/256 GB", "18 soat batareya"], "Yengil va kuchli noutbuk. Talabalar va dizaynerlar uchun ideal.", "MAC-AIR-M3"),
    ("Lenovo IdeaPad Slim 5", "Lenovo", "laptop", 8_490_000, 9_200_000, 12, ["16/512 GB", "Ryzen 7"], "Kundalik ish va o'qish uchun ishonchli noutbuk.", "LEN-IP5"),
    ("ASUS ROG Strix G16", "ASUS", "laptop", 21_500_000, None, 4, ["RTX 4060", "16\" 165 Hz"], "O'yinlar va 3D ishlash uchun kuchli gaming noutbuk.", "ASUS-G16"),
    ("iPhone 15 Pro 128 GB", "Apple", "phone", 14_200_000, 15_200_000, 9, ["Titanium", "A17 Pro"], "Titanium korpus, A17 Pro chip va 48 MP kamera.", "IPH-15P"),
    ("Samsung Galaxy S24", "Samsung", "phone", 11_900_000, None, 15, ["8/256 GB", "120 Hz"], "Yorqin AMOLED ekran va Snapdragon 8 Gen 3.", "SAM-S24"),
    ("Xiaomi 14", "Xiaomi", "phone", 9_800_000, 10_400_000, 18, ["12/256 GB", "Leica 50 MP"], "Leica kamerali, tez quvvatlanadigan flagman.", "XIA-14"),
    ("AirPods Pro 2 (USB-C)", "Apple", "audio", 2_750_000, None, 24, ["ANC", "6+30 soat"], "Faol shovqin so'ndirish va qulay o'tirish.", "AP-PRO2"),
    ("Sony WH-1000XM5", "Sony", "audio", 4_200_000, 4_600_000, 8, ["ANC", "30 soat"], "Sanoatdagi eng yaxshi shovqin so'ndirishlardan biri.", "SONY-XM5"),
    ("iPad Air M2 11\"", "Apple", "tablet", 9_900_000, None, 6, ["M2 chip", "11\""], "Ish va ijod uchun yengil planshet.", "IPAD-AIR"),
    ("Apple Watch Series 9 45mm", "Apple", "watch", 5_400_000, None, 11, ["45 mm", "ECG"], "Sog'liqni kuzatish va faol hayot uchun.", "AW-S9"),
    ("Samsung Galaxy Watch 6", "Samsung", "watch", 3_100_000, 3_500_000, 14, ["44 mm", "GPS"], "Zamonaviy dizayn va sog'liq funksiyalari.", "SAM-W6"),
    ("Logitech MX Master 3S", "Logitech", "accessory", 1_250_000, None, 30, ["8K DPI", "70 kun"], "Ish uchun eng qulay simsiz sichqoncha.", "LOG-MX3S"),
    ("Anker PowerCore 20 000", "Anker", "accessory", 690_000, None, 40, ["20 000 mAh", "22.5 W"], "Sayohat uchun ishonchli quvvat banki.", "ANK-PB20"),
]

DEMO_KB = """TechNova onlayn elektronika do'koni ma'lumotlari.

YETKAZIB BERISH
Toshkent shahri bo'ylab yetkazib berish 24 soat ichida amalga oshiriladi va bepul.
Viloyatlarga yetkazib berish 1-3 ish kuni, narxi 50 000 so'm.
5 000 000 so'mdan yuqori buyurtmalarga yetkazib berish butun O'zbekiston bo'ylab bepul.

TO'LOV
Payme, Click, Uzum Bank, plastik karta va naqd pul orqali to'lash mumkin.
12 oygacha 0% foizli bo'lib to'lash mavjud. Buning uchun pasport ma'lumotlari kerak.
Onlayn buyurtmada to'lov yetkazib berish vaqtida ham amalga oshirilishi mumkin.

KAFOLAT
Barcha mahsulotlarga 12 oy rasmiy kafolat beriladi.
Nosozlik aniqlansa, 14 kun ichida mahsulot almashtiriladi yoki pul qaytariladi.
Kafolat rasmiy servis markazlari orqali amalga oshiriladi.

QAYTARISH
Mahsulot qadoqlanmagan va ishlatilmagan holatda 14 kun ichida qaytarilishi mumkin.
Qaytarish uchun xarid cheki yoki buyurtma raqami kerak.

ISH VAQTI
Onlayn do'kon 24/7 ishlaydi.
Operatorlar dushanbadan shanbagacha, 09:00 dan 20:00 gacha javob beradi.

ALOQA
Telefon: +998 71 200 00 00
Telegram: @technova_sales
Manzil: Toshkent, Amir Temur ko'chasi 108.

CHEGIRMALAR
Ikki va undan ortiq mahsulotga 5% chegirma avtomatik qo'llaniladi.
NOVA10 promo kodi birinchi buyurtmaga 10% chegirma beradi.
Talabalar uchun har seshanba 7% chegirma mavjud.

BUYURTMA
Buyurtma berish uchun mahsulotni tanlang, ism va telefon raqamini qoldiring.
Operator 15 daqiqa ichida tasdiqlash uchun bog'lanadi.
Buyurtma holatini operator orqali telefon raqami bilan tekshirish mumkin.
"""


async def seed_demo() -> None:
    async with SessionLocal() as db:
        existing = await db.scalar(select(Organization.id).where(Organization.slug == DEMO_SLUG))
        if existing:
            return

        demo_user = (
            await db.execute(select(User).where(User.email == DEMO_EMAIL))
        ).scalar_one_or_none()
        if demo_user is None:
            demo_user = User(
                email=DEMO_EMAIL,
                password_hash=hash_password(DEMO_PASSWORD),
                full_name="Demo Menejer",
            )
            db.add(demo_user)
            await db.flush()

        org = Organization(
            name="TechNova Store",
            slug=DEMO_SLUG,
            plan="pro",
            owner_id=demo_user.id,
            description="Toshkentdagi elektronika do'koni. 2019 yildan beri.",
            contact_phone="+998 71 200 00 00",
            contact_telegram="@technova_sales",
        )
        db.add(org)
        await db.flush()
        db.add(Membership(org_id=org.id, user_id=demo_user.id, role="owner"))
        db.add(
            AgentSettings(
                org_id=org.id,
                agent_name="Nova",
                persona=(
                    "Siz TechNova do'konining xushmuomala va professional sotuv yordamchisisiz. "
                    "Mijozga eng mos mahsulotni tanlashga yordam berasiz."
                ),
                greeting=(
                    "Assalomu alaykum! Men Nova — TechNova AI yordamchisiman. "
                    "Mahsulot tanlash, narxlar va buyurtma bo'yicha yordam beraman."
                ),
                handoff_keywords=["operator", "менеджер", "odam", "qo'ng'iroq"],
                language="uz",
            )
        )
        db.add(Widget(org_id=org.id, public_key=DEMO_WIDGET_KEY, title="TechNova yordamchisi"))
        await db.flush()

        products: list[Product] = []
        for name, brand, category, price, old_price, stock, specs, description, sku in DEMO_PRODUCTS:
            product = Product(
                org_id=org.id,
                name=name,
                sku=sku,
                category=category,
                description=f"{description} ({brand}; {', '.join(specs)})",
                price=price,
                old_price=old_price,
                currency="UZS",
                in_stock=True,
                stock_qty=stock,
            )
            db.add(product)
            products.append(product)
        await db.flush()

        document = KnowledgeDocument(
            org_id=org.id,
            filename="TechNova-malumotlar.txt",
            content_type="text/plain",
            size_bytes=len(DEMO_KB.encode()),
            status="processing",
            created_by=demo_user.id,
        )
        db.add(document)
        await db.flush()

        now = utcnow()
        first = Conversation(
            org_id=org.id,
            channel="widget",
            external_id="demo-visitor-1",
            customer_name="Aziz Karimov",
            ai_enabled=True,
            state={"lang": "uz", "last_products": [products[0].id]},
            last_message_at=now - timedelta(hours=2),
            created_at=now - timedelta(days=1, hours=3),
        )
        second = Conversation(
            org_id=org.id,
            channel="telegram",
            external_id="558899001",
            customer_name="Dilnoza R.",
            ai_enabled=True,
            state={"lang": "ru"},
            last_message_at=now - timedelta(minutes=40),
            created_at=now - timedelta(hours=6),
        )
        third = Conversation(
            org_id=org.id,
            channel="widget",
            external_id="demo-visitor-2",
            customer_name="Sardor T.",
            ai_enabled=False,
            is_handoff=True,
            handoff_reason="Mijoz operator bilan bog'lanishni so'radi",
            state={"lang": "uz"},
            last_message_at=now - timedelta(minutes=15),
            created_at=now - timedelta(hours=2),
        )
        db.add_all([first, second, third])
        await db.flush()

        messages = [
            (first, "user", "Salom, 15 mln gacha noutbuk kerak", 0),
            (first, "assistant", "Assalomu alaykum! Byudjetingizga mos variantlar: Lenovo IdeaPad Slim 5 — 8 490 000 so'm va MacBook Air M3 — 15 990 000 so'm. Qaysi biri qiziqtirdi?", 900),
            (first, "user", "MacBook haqida batafsil", 0),
            (first, "assistant", "MacBook Air M3 — 15 990 000 so'm. 8/256 GB, 18 soat batareya, 13.6\" ekran. 12 oyga bo'lib to'lashda oyiga ~1 332 500 so'm. Savatga qo'shaymi?", 1100),
            (second, "user", "Есть рассрочка на iPhone 15 Pro?", 0),
            (second, "assistant", "Да, на iPhone 15 Pro 128 GB действует рассрочка 0% до 12 месяцев — около 1 183 333 сум в месяц. Оформляем?", 1250),
            (third, "user", "Операторга уланинг", 0),
            (third, "assistant", "Tushunarli. Operatorimiz tez orada bog'lanadi: +998 71 200 00 00.", 700),
        ]
        for conversation, role, content, latency in messages:
            db.add(
                Message(
                    org_id=org.id,
                    conversation_id=conversation.id,
                    role=role,
                    content=content,
                    latency_ms=latency,
                    meta={"channel": conversation.channel},
                    created_at=now - timedelta(minutes=latency // 10 + 5),
                )
            )

        db.add_all(
            [
                Order(
                    org_id=org.id,
                    number="TEC-240101-A1B2",
                    customer_name="Aziz Karimov",
                    customer_phone="+998 90 123 45 67",
                    items=[
                        {
                            "product_id": products[0].id,
                            "name": products[0].name,
                            "price": products[0].price,
                            "qty": 1,
                            "currency": "UZS",
                        }
                    ],
                    total=products[0].price,
                    status="delivered",
                    source="ai",
                    conversation_id=first.id,
                    created_at=now - timedelta(days=2),
                ),
                Order(
                    org_id=org.id,
                    number="TEC-240102-C3D4",
                    customer_name="Dilnoza R.",
                    customer_phone="+998 91 555 22 11",
                    items=[
                        {
                            "product_id": products[3].id,
                            "name": products[3].name,
                            "price": products[3].price,
                            "qty": 1,
                            "currency": "UZS",
                        },
                        {
                            "product_id": products[6].id,
                            "name": products[6].name,
                            "price": products[6].price,
                            "qty": 2,
                            "currency": "UZS",
                        },
                    ],
                    total=products[3].price + products[6].price * 2,
                    status="pending",
                    source="ai",
                    conversation_id=second.id,
                    created_at=now - timedelta(hours=5),
                ),
            ]
        )

        admin = (
            await db.execute(select(User).where(User.email == settings.super_admin_email))
        ).scalar_one_or_none()
        if admin is None:
            db.add(
                User(
                    email=settings.super_admin_email,
                    password_hash=hash_password(settings.super_admin_password),
                    full_name="Platform Admin",
                    is_super_admin=True,
                )
            )

        await db.commit()
        await ingest_bytes(db, document, DEMO_KB.encode())
        logger.info("Demo data seeded: %s / %s", DEMO_EMAIL, DEMO_PASSWORD)

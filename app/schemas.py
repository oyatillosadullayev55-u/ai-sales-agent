from __future__ import annotations

from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, EmailStr, Field

Role = Literal["owner", "manager", "operator"]
Plan = Literal["starter", "pro", "business"]
OrderStatus = Literal["pending", "confirmed", "processing", "delivered", "cancelled"]


class ORMModel(BaseModel):
    model_config = ConfigDict(from_attributes=True)


# ---------- auth ----------
class RegisterIn(BaseModel):
    email: EmailStr
    password: str = Field(min_length=8, max_length=72)
    full_name: str = Field(default="", max_length=120)
    org_name: str = Field(min_length=2, max_length=160)


class LoginIn(BaseModel):
    email: EmailStr
    password: str


class RefreshIn(BaseModel):
    refresh_token: str


class ForgotIn(BaseModel):
    email: EmailStr


class ResetIn(BaseModel):
    token: str = Field(min_length=10)
    password: str = Field(min_length=8, max_length=72)


class SwitchOrgIn(BaseModel):
    org_id: str


class UserOut(ORMModel):
    id: str
    email: str
    full_name: str
    is_super_admin: bool


class OrgOut(ORMModel):
    id: str
    name: str
    slug: str
    plan: str
    plan_expires_at: datetime | None = None
    description: str = ""
    contact_phone: str = ""
    contact_telegram: str = ""


class TokenOut(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    user: UserOut
    org: OrgOut | None = None
    role: str | None = None


class MeOut(BaseModel):
    user: UserOut
    orgs: list[OrgOut]
    active_org_id: str | None = None
    role: str | None = None


class OrgUpdateIn(BaseModel):
    name: str | None = Field(default=None, min_length=2, max_length=160)
    description: str | None = Field(default=None, max_length=2000)
    contact_phone: str | None = Field(default=None, max_length=40)
    contact_telegram: str | None = Field(default=None, max_length=80)


class MemberOut(BaseModel):
    id: str
    user_id: str
    email: str
    full_name: str
    role: str
    created_at: datetime


class InviteIn(BaseModel):
    email: EmailStr
    full_name: str = ""
    role: Role = "operator"
    password: str | None = Field(default=None, min_length=8, max_length=72)


class MemberRoleIn(BaseModel):
    role: Role


# ---------- knowledge ----------
class DocumentOut(ORMModel):
    id: str
    filename: str
    content_type: str
    size_bytes: int
    status: str
    error: str | None = None
    chunk_count: int
    created_at: datetime


class QueryIn(BaseModel):
    question: str = Field(min_length=1, max_length=2000)


class SourceOut(BaseModel):
    document_id: str
    document_name: str
    chunk_index: int
    score: float
    snippet: str


class QueryOut(BaseModel):
    answer: str
    sources: list[SourceOut]
    latency_ms: int


# ---------- products / orders ----------
class ProductIn(BaseModel):
    name: str = Field(min_length=1, max_length=200)
    description: str = ""
    price: float = Field(ge=0)
    old_price: float | None = Field(default=None, ge=0)
    currency: str = "UZS"
    category: str = "umumiy"
    sku: str | None = None
    in_stock: bool = True
    stock_qty: int = Field(default=0, ge=0)


class ProductOut(ORMModel):
    id: str
    name: str
    description: str
    price: float
    old_price: float | None = None
    currency: str
    category: str
    sku: str | None
    in_stock: bool
    stock_qty: int
    created_at: datetime


class ProductUpdateIn(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=200)
    description: str | None = None
    price: float | None = Field(default=None, ge=0)
    old_price: float | None = Field(default=None, ge=0)
    currency: str | None = None
    category: str | None = None
    sku: str | None = None
    in_stock: bool | None = None
    stock_qty: int | None = Field(default=None, ge=0)


class OrderItemIn(BaseModel):
    product_id: str
    qty: int = Field(default=1, ge=1, le=999)


class OrderIn(BaseModel):
    customer_name: str = Field(min_length=1, max_length=160)
    customer_phone: str = Field(min_length=5, max_length=40)
    items: list[OrderItemIn] = Field(min_length=1)
    note: str = ""


class OrderStatusIn(BaseModel):
    status: OrderStatus


class OrderOut(ORMModel):
    id: str
    number: str
    customer_name: str
    customer_phone: str
    items: list[dict[str, Any]]
    total: float
    currency: str
    status: str
    source: str
    note: str
    conversation_id: str | None
    created_at: datetime


# ---------- conversations ----------
class ConversationOut(ORMModel):
    id: str
    channel: str
    external_id: str
    customer_name: str
    ai_enabled: bool
    is_handoff: bool
    handoff_reason: str
    assigned_to: str | None
    last_message_at: datetime
    created_at: datetime


class MessageOut(ORMModel):
    id: str
    role: str
    content: str
    meta: dict[str, Any]
    latency_ms: int
    created_at: datetime


class ConversationDetailOut(BaseModel):
    conversation: ConversationOut
    messages: list[MessageOut]


class ReplyIn(BaseModel):
    text: str = Field(min_length=1, max_length=4000)


class HandoffIn(BaseModel):
    ai_enabled: bool | None = None
    assigned_to: str | None = None
    reason: str = ""


# ---------- agent settings ----------
class AgentSettingsIn(BaseModel):
    agent_name: str | None = Field(default=None, max_length=60)
    persona: str | None = Field(default=None, max_length=4000)
    language: Literal["uz", "ru", "en"] | None = None
    greeting: str | None = Field(default=None, max_length=1000)
    handoff_keywords: list[str] | None = None
    temperature: float | None = Field(default=None, ge=0, le=1.5)


class AgentSettingsOut(ORMModel):
    agent_name: str
    persona: str
    language: str
    greeting: str
    handoff_keywords: list[str]
    temperature: float
    model: str | None
    updated_at: datetime


# ---------- integrations ----------
class TelegramConnectIn(BaseModel):
    token: str = Field(min_length=20, max_length=200)


class TelegramOut(BaseModel):
    bot_username: str
    webhook_url: str
    active: bool


class WidgetUpdateIn(BaseModel):
    title: str | None = Field(default=None, max_length=80)
    color: str | None = Field(default=None, max_length=16)
    greeting: str | None = Field(default=None, max_length=1000)


class WidgetOut(ORMModel):
    public_key: str
    title: str
    color: str
    greeting: str
    active: bool


class WidgetInfoOut(WidgetOut):
    embed_code: str


# ---------- public chat ----------
class PublicChatIn(BaseModel):
    visitor_id: str = Field(min_length=4, max_length=120)
    text: str = Field(min_length=1, max_length=4000)
    name: str | None = Field(default=None, max_length=160)


class ChatReplyOut(BaseModel):
    conversation_id: str
    text: str
    products: list[dict[str, Any]] = []
    sources: list[SourceOut] = []
    quick: list[str] = []
    handoff: bool = False
    ai_enabled: bool = True
    order: dict[str, Any] | None = None


# ---------- analytics / billing / admin ----------
class AnalyticsOut(BaseModel):
    range_days: int
    conversations: int
    new_customers: int
    messages: int
    ai_messages: int
    orders: int
    revenue: float
    handoffs: int
    conversion_rate: float
    avg_response_ms: int
    by_channel: dict[str, int]
    series: list[dict[str, Any]]
    top_products: list[dict[str, Any]]
    recent_conversations: list[dict[str, Any]]


class SubscribeIn(BaseModel):
    plan: Plan
    months: int = Field(default=1, ge=1, le=24)


class PaymentOut(ORMModel):
    id: str
    plan: str
    months: int
    amount: float
    status: str
    provider: str
    created_at: datetime


class BillingOut(BaseModel):
    plan: str
    plan_expires_at: datetime | None
    plans: dict[str, Any]
    usage: dict[str, Any]
    payments: list[PaymentOut]


class AdminOrgOut(BaseModel):
    id: str
    name: str
    slug: str
    plan: str
    owner_email: str
    users: int
    conversations: int
    orders: int
    revenue: float
    created_at: datetime


class PlanUpdateIn(BaseModel):
    plan: Plan


class AdminStatsOut(BaseModel):
    orgs: int
    users: int
    conversations: int
    orders: int
    revenue: float
    ai_messages: int
    by_plan: dict[str, int]
    recent_orgs: list[AdminOrgOut]

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field


PaymentStatus = Literal["pending", "authorized", "submitted", "settled", "failed", "expired"]
PurchaseAction = Literal["skip", "buy_now", "needs_approval"]
OperatorPaymentAction = Literal["mark_failed", "mark_compensated", "mark_settled"]


class ChainInfo(BaseModel):
    chain: str = "tron"
    channel_scheme: str = "tron-contract"
    network: str = "nile"
    chain_id: int | None = None
    settlement_backend: str | None = None
    seller_address: str
    contract_address: str
    asset_address: str
    asset_symbol: str = "USDT"
    asset_decimals: int = 6


class CapabilityBudgetHint(BaseModel):
    typical_units: int | None = Field(default=None, ge=0)
    min_units: int | None = Field(default=None, ge=0)
    suggested_prepaid_atomic: int | None = Field(default=None, ge=0)
    notes: str | None = None


class MerchantRoute(BaseModel):
    path: str
    price_atomic: int = Field(ge=0)
    method: str = "POST"
    enabled: bool = True
    description: str | None = None
    capability_id: str | None = None
    capability_type: str = "api"
    pricing_model: str = "fixed_per_call"
    usage_unit: str = "request"
    delivery_mode: str = "sync"
    response_format: str | None = "json"
    expected_latency_ms: int | None = Field(default=None, ge=0)
    minimum_prepaid_atomic: int | None = Field(default=None, ge=0)
    suggested_prepaid_atomic: int | None = Field(default=None, ge=0)
    requires_human_approval: bool = False
    supports_auto_purchase: bool = True
    safe_retry_policy: str | None = None
    auth_requirements: list[str] = Field(default_factory=list)
    capability_tags: list[str] = Field(default_factory=list)
    budget_hint: CapabilityBudgetHint | None = None


class MerchantPlan(BaseModel):
    plan_id: str
    name: str
    amount_atomic: int = Field(ge=0)
    enabled: bool = True
    billing_interval: str = "month"
    description: str | None = None
    subscribe_path: str | None = None
    features: list[str] = Field(default_factory=list)


class MerchantManifest(BaseModel):
    version: str = "v1"
    kind: str = "aimipay-merchant"
    transport: str = "http+aimipay"
    service_name: str
    service_description: str
    primary_chain: ChainInfo
    routes: list[MerchantRoute] = Field(default_factory=list)
    plans: list[MerchantPlan] = Field(default_factory=list)
    endpoints: dict[str, str]


class CapabilityOffer(BaseModel):
    capability_id: str
    capability_type: str
    route_path: str
    method: str
    description: str | None = None
    pricing_model: str
    usage_unit: str
    amount_atomic: int = Field(ge=0)
    unit_price_atomic: int = Field(ge=0)
    delivery_mode: str
    response_format: str | None = None
    expected_latency_ms: int | None = Field(default=None, ge=0)
    minimum_prepaid_atomic: int | None = Field(default=None, ge=0)
    suggested_prepaid_atomic: int | None = Field(default=None, ge=0)
    requires_human_approval: bool = False
    supports_auto_purchase: bool = True
    safe_retry_policy: str | None = None
    auth_requirements: list[str] = Field(default_factory=list)
    capability_tags: list[str] = Field(default_factory=list)
    budget_hint: CapabilityBudgetHint | None = None
    settlement_backend: str | None = None
    chain: str
    chain_id: int | None = None
    seller_address: str
    contract_address: str
    token_address: str


class TaskBudget(BaseModel):
    capability_id: str
    units: int = Field(ge=0)
    unit_amount_atomic: int = Field(ge=0)
    estimated_total_atomic: int = Field(ge=0)
    suggested_prepaid_atomic: int | None = Field(default=None, ge=0)
    pricing_model: str
    usage_unit: str
    notes: str | None = None


class PurchaseDecision(BaseModel):
    capability_id: str
    action: PurchaseAction
    reason: str
    estimated_total_atomic: int = Field(ge=0)
    suggested_prepaid_atomic: int | None = Field(default=None, ge=0)
    seller_address: str
    route_path: str
    score: float | None = None
    score_breakdown: dict[str, float] = Field(default_factory=dict)


class OpenChannelRequest(BaseModel):
    buyer_address: str
    deposit_atomic: int | None = Field(default=None, ge=0)
    ttl_s: int | None = Field(default=None, ge=60)
    route_path: str | None = None


class OpenChannelResponse(BaseModel):
    channel_id: str | None = None
    channel_id_source: str = "unavailable"
    chain: str
    chain_id: int | None = None
    channel_scheme: str
    seller: str
    contract_address: str
    token_address: str
    deposit_atomic: int
    expires_at: int


class SettlementExecuteRequest(BaseModel):
    payment_id: str | None = None


class OperatorPaymentActionRequest(BaseModel):
    action: OperatorPaymentAction
    note: str = Field(min_length=1)
    tx_id: str | None = None
    settled_at: int | None = Field(default=None, ge=0)


class CreatePaymentRequest(BaseModel):
    payment_id: str | None = None
    idempotency_key: str | None = None
    route_path: str | None = None
    amount_atomic: int | None = Field(default=None, ge=0)
    buyer_address: str
    channel_id: str
    voucher_nonce: int = Field(ge=0)
    expires_at: int = Field(ge=0)
    request_deadline: int = Field(ge=0)
    request_method: str = "POST"
    request_path: str | None = None
    request_body: str = ""
    request_digest: str | None = None
    buyer_signature: str | None = None


class CreatePaymentIntentRequest(CreatePaymentRequest):
    pass


class PaymentLifecycleAdvice(BaseModel):
    action_required: str | None = None
    next_step: str | None = None
    safe_to_retry: bool = False
    human_approval_required: bool = False


class PaymentRecord(BaseModel):
    payment_id: str
    idempotency_key: str | None = None
    route_path: str | None = None
    amount_atomic: int
    chain: str = "tron"
    buyer_address: str | None = None
    seller_address: str | None = None
    channel_id: str | None = None
    contract_address: str | None = None
    token_address: str | None = None
    voucher_nonce: int | None = Field(default=None, ge=0)
    expires_at: int | None = Field(default=None, ge=0)
    request_deadline: int | None = Field(default=None, ge=0)
    request_method: str | None = None
    request_path: str | None = None
    request_body: str | None = None
    request_digest: str | None = None
    buyer_signature: str | None = None
    status: PaymentStatus = "pending"
    status_reason: str | None = None
    tx_id: str | None = None
    processing_stage: str | None = None
    processing_token: str | None = None
    processing_started_at: int | None = Field(default=None, ge=0)
    confirmation_status: str | None = None
    confirmation_error: str | None = None
    confirmation_attempts: int = Field(default=0, ge=0)
    error_code: str | None = None
    error_message: str | None = None
    error_retryable: bool | None = None
    created_at: int | None = Field(default=None, ge=0)
    updated_at: int | None = Field(default=None, ge=0)
    settled_at: int | None = Field(default=None, ge=0)
    confirmed_at: int | None = Field(default=None, ge=0)

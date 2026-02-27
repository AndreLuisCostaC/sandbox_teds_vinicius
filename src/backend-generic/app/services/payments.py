from __future__ import annotations

import os
from dataclasses import dataclass
from decimal import Decimal

import httpx


@dataclass
class PaymentIntentResult:
    provider: str
    external_id: str
    client_secret: str


class PaymentIntentError(RuntimeError):
    """Raised when a payment intent cannot be created."""


def _is_placeholder_key(value: str) -> bool:
    """Return True if the key looks like a placeholder (not a real API key)."""
    if not value:
        return True
    lower = value.lower()
    return "replace" in lower or "change_me" in lower or value == "sk_test_replace_me"


class PaymentService:
    def __init__(self) -> None:
        self._provider = (os.getenv("PAYMENT_PROVIDER") or "stripe").strip().lower()
        self._stripe_secret_key = os.getenv("STRIPE_SECRET_KEY", "").strip()
        self._mercado_pago_access_token = os.getenv("MERCADO_PAGO_ACCESS_TOKEN", "").strip()
        self._mock_mode = (os.getenv("PAYMENT_INTENT_MODE") or "").strip().lower()
        # When Stripe key is missing or placeholder, default to mock success for dev/mock phase
        if (
            self._provider == "stripe"
            and _is_placeholder_key(self._stripe_secret_key)
            and self._mock_mode not in ("failure", "success")
        ):
            self._mock_mode = "success"

    def create_payment_intent(
        self,
        *,
        amount: Decimal,
        currency: str,
        order_id: int,
    ) -> PaymentIntentResult:
        provider = self._resolve_provider()
        if provider == "mercado_pago":
            return self._create_mercado_pago_intent(amount=amount, currency=currency, order_id=order_id)
        return self._create_stripe_intent(amount=amount, currency=currency, order_id=order_id)

    def _resolve_provider(self) -> str:
        if self._provider in {"mercado_pago", "mercadopago"}:
            return "mercado_pago"
        if self._provider == "stripe":
            if self._stripe_secret_key and not _is_placeholder_key(self._stripe_secret_key):
                return "stripe"
            if self._mock_mode == "success":
                return "stripe"  # Mock phase: no real key needed
            if self._mercado_pago_access_token and not _is_placeholder_key(
                self._mercado_pago_access_token
            ):
                return "mercado_pago"
        raise PaymentIntentError(
            "No payment provider credentials configured. Set STRIPE_SECRET_KEY or "
            "MERCADO_PAGO_ACCESS_TOKEN."
        )

    def _create_stripe_intent(
        self,
        *,
        amount: Decimal,
        currency: str,
        order_id: int,
    ) -> PaymentIntentResult:
        try:
            import stripe  # type: ignore
        except Exception as exc:  # pragma: no cover - import path depends on runtime deps
            raise PaymentIntentError("Stripe SDK is not available.") from exc

        if self._mock_mode == "failure":
            raise PaymentIntentError("Mocked Stripe payment intent failure.")
        if self._mock_mode == "success":
            return PaymentIntentResult(
                provider="stripe",
                external_id=f"pi_mock_{order_id}",
                client_secret=f"pi_mock_{order_id}_secret_mock",
            )

        try:
            stripe.api_key = self._stripe_secret_key
            amount_cents = int((amount * Decimal("100")).quantize(Decimal("1")))
            intent = stripe.PaymentIntent.create(
                amount=amount_cents,
                currency=currency.lower(),
                metadata={"order_id": str(order_id)},
            )
            return PaymentIntentResult(
                provider="stripe",
                external_id=str(intent["id"]),
                client_secret=str(intent["client_secret"]),
            )
        except Exception as exc:
            raise PaymentIntentError("Failed to create Stripe payment intent.") from exc

    def _create_mercado_pago_intent(
        self,
        *,
        amount: Decimal,
        currency: str,
        order_id: int,
    ) -> PaymentIntentResult:
        if self._mock_mode == "failure":
            raise PaymentIntentError("Mocked Mercado Pago payment intent failure.")
        if self._mock_mode == "success":
            return PaymentIntentResult(
                provider="mercado_pago",
                external_id=f"mp_mock_{order_id}",
                client_secret=f"mp_mock_{order_id}_secret_mock",
            )

        if not self._mercado_pago_access_token:
            raise PaymentIntentError("MERCADO_PAGO_ACCESS_TOKEN is not configured.")
        try:
            payload = {
                "transaction_amount": float(amount),
                "description": f"Order #{order_id}",
                "payment_method_id": "pix",
                "external_reference": str(order_id),
                "payer": {"email": f"order-{order_id}@example.com"},
            }
            headers = {"Authorization": f"Bearer {self._mercado_pago_access_token}"}
            response = httpx.post(
                "https://api.mercadopago.com/v1/payments",
                json=payload,
                headers=headers,
                timeout=20,
            )
            response.raise_for_status()
            body = response.json()
            secret = body.get("point_of_interaction", {}).get("transaction_data", {}).get("qr_code")
            if not secret:
                secret = str(body.get("id", ""))
            external_id = str(body.get("id", ""))
            if not external_id:
                raise PaymentIntentError("Mercado Pago response did not include payment id.")
            return PaymentIntentResult(
                provider="mercado_pago",
                external_id=external_id,
                client_secret=secret,
            )
        except PaymentIntentError:
            raise
        except Exception as exc:
            raise PaymentIntentError("Failed to create Mercado Pago payment intent.") from exc

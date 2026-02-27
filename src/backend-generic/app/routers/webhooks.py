from __future__ import annotations

import os

import stripe
from fastapi import APIRouter, Depends, HTTPException, Request, status
from fastapi.responses import JSONResponse
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db import get_db
from app.models.order import Order
from app.models.payment import Payment


router = APIRouter(prefix="/webhooks", tags=["webhooks"])


@router.post("/stripe")
async def stripe_webhook(
    request: Request,
    db: Session = Depends(get_db),
) -> JSONResponse:
    webhook_secret = os.getenv("STRIPE_WEBHOOK_SECRET", "").strip()
    if not webhook_secret:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="STRIPE_WEBHOOK_SECRET is not configured.",
        )

    payload = await request.body()
    signature = request.headers.get("stripe-signature")
    if not signature:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Missing Stripe signature header.",
        )

    try:
        event = stripe.Webhook.construct_event(
            payload=payload,
            sig_header=signature,
            secret=webhook_secret,
        )
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid Stripe webhook signature.",
        ) from exc

    try:
        with db.begin_nested():
            if event["type"] == "payment_intent.succeeded":
                payment_intent = event["data"]["object"]
                external_id = str(payment_intent.get("id", ""))
                if external_id:
                    payment = (
                        db.execute(
                            select(Payment)
                            .where(
                                Payment.external_id == external_id,
                                Payment.provider == "stripe",
                            )
                            .with_for_update()
                        )
                        .scalar_one_or_none()
                    )
                    if payment is not None:
                        if payment.status != "confirmed":
                            payment.status = "confirmed"
                        order = db.get(Order, payment.order_id)
                        if order is not None and order.status != "paid":
                            order.status = "paid"
        db.commit()
    except Exception:
        # For webhook delivery stability, successful signature verification
        # is acknowledged with 200 even when processing fails internally.
        db.rollback()
        return JSONResponse(status_code=status.HTTP_200_OK, content={"received": True})

    return JSONResponse(status_code=status.HTTP_200_OK, content={"received": True})

"""
Payment Service API
===================
A simulated payment processing microservice.
Demonstrates a real-world FastAPI application
with GenAI-powered analysis endpoint.

Endpoints:
  GET  /health          - Health check
  GET  /payments/{id}   - Get payment status
  POST /payments        - Process a payment
  POST /analyze         - AI-powered log/alert analysis

Part of : GenAI for DevOps & SRE — Phase 3
Author  : Bhagyashree
Day     : 16
"""

import uuid
import random
from datetime import datetime
from typing import Optional
import os
import json

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from groq import Groq
from dotenv import load_dotenv

load_dotenv()

# ─────────────────────────────────────────
# APP SETUP
# ─────────────────────────────────────────
app = FastAPI(
    title="Payment Service API",
    description="Simulated payment microservice with GenAI analysis",
    version="1.0.0"
)

groq_client = Groq(api_key=os.getenv("GROQ_API_KEY"))

# In-memory payment store
# In production this would be a database
PAYMENTS = {}


# ─────────────────────────────────────────
# DATA MODELS
# Pydantic models define the shape of
# request and response data
# FastAPI validates all inputs automatically
# ─────────────────────────────────────────
class PaymentRequest(BaseModel):
    """
    Model for creating a new payment.
    All fields are validated automatically by FastAPI.
    """
    amount: float
    currency: str = "INR"
    merchant: str
    customer_id: str
    description: Optional[str] = None


class PaymentResponse(BaseModel):
    """Model for payment response."""
    payment_id: str
    status: str
    amount: float
    currency: str
    merchant: str
    created_at: str
    message: str


class AnalyzeRequest(BaseModel):
    """Model for GenAI analysis request."""
    content: str
    content_type: str = "log"  # log, alert, terraform, cicd


class AnalyzeResponse(BaseModel):
    """Model for GenAI analysis response."""
    content_type: str
    severity: str
    summary: str
    root_cause: str
    recommended_action: str


# ─────────────────────────────────────────
# ENDPOINTS
# ─────────────────────────────────────────

@app.get("/health")
def health_check():
    """
    Health check endpoint.
    Returns service status and basic metrics.
    Used by Kubernetes liveness and readiness probes.
    Load balancers check this before routing traffic.
    """
    return {
        "status": "healthy",
        "service": "payment-service",
        "version": "1.0.0",
        "timestamp": datetime.utcnow().isoformat(),
        "total_payments": len(PAYMENTS)
    }


@app.get("/payments/{payment_id}")
def get_payment(payment_id: str):
    """
    Get payment status by ID.
    Returns 404 if payment not found.
    FastAPI automatically handles the HTTPException.
    """
    if payment_id not in PAYMENTS:
        raise HTTPException(
            status_code=404,
            detail=f"Payment {payment_id} not found"
        )
    return PAYMENTS[payment_id]


@app.post("/payments", response_model=PaymentResponse)
def create_payment(payment: PaymentRequest):
    """
    Process a new payment.
    Simulates payment processing with random success/failure.
    In production this would call a real payment gateway.
    """
    # Generate unique payment ID
    payment_id = f"PAY-{str(uuid.uuid4())[:8].upper()}"

    # Simulate payment processing
    # 90% success rate, 10% failure
    success = random.random() > 0.1

    status = "completed" if success else "failed"
    message = (
        "Payment processed successfully"
        if success
        else "Payment failed: Gateway timeout"
    )

    # Store payment
    payment_data = {
        "payment_id": payment_id,
        "status": status,
        "amount": payment.amount,
        "currency": payment.currency,
        "merchant": payment.merchant,
        "customer_id": payment.customer_id,
        "description": payment.description,
        "created_at": datetime.utcnow().isoformat(),
        "message": message
    }
    PAYMENTS[payment_id] = payment_data

    return payment_data


@app.post("/analyze", response_model=AnalyzeResponse)
def analyze_content(request: AnalyzeRequest):
    """
    GenAI-powered analysis endpoint.
    Takes any log, alert, terraform plan, or CI/CD failure
    and returns structured AI diagnosis.
    This is what makes this service unique.
    """
    prompt = f"""
You are a senior SRE engineer.
Analyze this {request.content_type} and return ONLY valid JSON:
{{
  "content_type": "{request.content_type}",
  "severity": "P1, P2 or P3",
  "summary": "one sentence summary",
  "root_cause": "one sentence root cause",
  "recommended_action": "most important action to take"
}}

Content to analyze:
{request.content}
"""
    try:
        response = groq_client.chat.completions.create(
            model="llama-3.3-70b-versatile",
            messages=[
                {
                    "role": "system",
                    "content": "You are a senior SRE engineer. Return valid JSON only."
                },
                {"role": "user", "content": prompt}
            ],
            temperature=0,
        )
        raw = response.choices[0].message.content.strip()
        raw = raw.replace("```json", "").replace("```", "").strip()
        result = json.loads(raw)
        return result
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Analysis failed: {str(e)}"
        )


@app.get("/payments")
def list_payments():
    """
    List all payments.
    In production this would be paginated.
    """
    return {
        "total": len(PAYMENTS),
        "payments": list(PAYMENTS.values())
    }
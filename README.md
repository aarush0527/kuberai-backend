# KuberAI Backend

A FastAPI backend for a conversational digital gold platform.

Instead of navigating through menus, users interact with the system using natural language. The application understands investment queries, executes one-time gold purchases, manages recurring SIPs, and maintains a complete transaction and audit history. A hybrid intent engine combines deterministic pattern matching with an LLM so that financial operations remain deterministic while conversations stay natural.

---

# Features

## Conversational Interface

Users can interact using natural language instead of structured API calls.

Examples:

```
Buy gold worth 500 rupees

Should I buy gold or put money in an FD?

Create a SIP of ₹1000 every month.

Pause my SIP.

Resume my SIP.

Cancel my SIP.
```

Simple, deterministic requests are handled without an LLM whenever possible. More open-ended questions are delegated to an LLM that returns structured intents instead of directly performing financial operations.

---

## One-time Gold Purchases

Supports purchasing digital gold using an amount in Indian Rupees.

Features include:

* Exact decimal arithmetic
* Dynamic gold pricing
* Automatic gold quantity calculation
* Transaction ledger
* Audit logging
* Duplicate purchase protection

---

## SIP Management

Supports recurring purchases through Systematic Investment Plans.

Supported operations:

* Create
* Pause
* Resume
* Cancel
* Automatic installment execution

The scheduler periodically checks for due SIPs and executes installments using the same purchase engine used for manual purchases.

---

## Hybrid Intent Resolution

The backend intentionally uses two layers of intent detection.

### Pattern Layer

Handles requests such as

```
Buy ₹500 worth of gold

Pause my SIP

Resume SIP

Create a monthly SIP of ₹1000
```

without invoking the LLM.

This makes common requests:

* faster
* deterministic
* cheaper
* easier to test

### LLM Layer

Handles conversational requests such as

```
Should I buy gold or invest in an FD?

Is gold a good hedge against inflation?

My parents say gold is always safe.
```

The LLM does **not** execute financial operations.

It only proposes a structured action that is validated and executed by backend services.

---

## Idempotent Purchases

Duplicate purchase requests are prevented through idempotency keys.

This protects against situations such as:

* client retries
* network failures
* accidental duplicate submissions

The protection exists at both the application layer and the database layer.

---

## Exact Money Handling

Financial calculations use Python's `Decimal` instead of floating-point arithmetic.

Money values are stored with two decimal places.

Gold quantities and prices are stored with four decimal places.

This guarantees deterministic financial calculations.

---

## Audit Trail

Every important action creates an audit event.

Examples include:

* incoming message
* purchase requested
* purchase completed
* SIP created
* SIP paused
* reply generated

Correlation IDs make it possible to reconstruct the complete journey of a request across the system.

---

# Architecture

```

                User

                  │

                  ▼

            POST /chat

                  │

                  ▼

          Intent Resolution

          ┌──────────────┐
          │              │
          ▼              ▼

   Pattern Layer       LLM

          │              │

          └──────┬───────┘

                 ▼

         Proposed Action

                 │

                 ▼

       Business Services

      ┌─────────┬──────────┐
      │         │          │
      ▼         ▼          ▼

 Purchase     SIP      Information

      │

      ▼

 Price Provider

      │

      ▼

 Money Utilities

      │

      ▼

 SQLAlchemy Models

      │

      ▼

 SQLite Database

```

The important architectural decision is that the LLM never performs financial operations directly.

Every purchase, SIP operation, and calculation passes through deterministic backend logic before anything is written to the database.

---

# Repository Structure

```
app/
│
├── llm/
│   ├── pattern_layer.py
│   ├── groq_client.py
│   ├── tools.py
│   ├── schemas.py
│   └── system_prompt.py
│
├── routers/
│   ├── chat.py
│   ├── purchase.py
│   ├── sip.py
│   ├── price.py
│   ├── users.py
│   ├── debug.py
│   └── health.py
│
├── services/
│   ├── chat_service.py
│   ├── purchase_service.py
│   └── sip_service.py
│
├── config.py
├── db.py
├── models.py
├── money.py
├── scheduler.py
├── price_provider.py
└── main.py

tests/

Dockerfile

docker-compose.yml

requirements.txt
```

---

# Getting Started

## Prerequisites

* Python 3.12+
* Docker Desktop (optional)
* Groq API Key (optional)

The application works without a Groq API key.

Without one, conversational requests that require an LLM fall back gracefully while deterministic functionality such as purchases and SIP management continues to work.

---

# Running Locally

Clone the repository.

```bash
git clone <repository-url>

cd kuberai-backend
```

Create a virtual environment.

```bash
python -m venv .venv
```

Activate it.

macOS / Linux

```bash
source .venv/bin/activate
```

Windows

```cmd
.venv\Scripts\activate
```

Install dependencies.

```bash
pip install -r requirements.txt
```

Create a `.env` file.

```
GROQ_API_KEY=your_api_key_here
```

If no API key is supplied the backend will automatically use its fallback client.

Start the application.

```bash
uvicorn app.main:app --reload
```

The API will be available at

```
http://localhost:8000
```

Swagger UI

```
http://localhost:8000/docs
```

Health endpoint

```
http://localhost:8000/health
```

# Running with Docker

Build and start the application.

```bash
docker compose up
```

The first build downloads the base Python image and installs project dependencies, so it may take a few minutes.

Once the container starts successfully, the API will be available at:

```
http://localhost:8000
```

Swagger UI:

```
http://localhost:8000/docs
```

Health endpoint:

```
http://localhost:8000/health
```

To stop the application:

```bash
Ctrl + C
```

or

```bash
docker compose down
```

---

# Environment Variables

| Variable | Required | Description |
|-----------|----------|-------------|
| `GROQ_API_KEY` | No | Enables LLM-powered conversational responses. Pattern-based functionality continues to work without it. |

---

# API Overview

## Health

```
GET /health
```

Returns the current application status.

Example response:

```json
{
  "status": "ok"
}
```

---

## Chat

```
POST /chat
```

Primary conversational endpoint.

Example request:

```json
{
  "user_id": "aarush",
  "message": "Buy gold worth 500 rupees"
}
```

Possible response:

```json
{
  "reply": "Done — bought ₹500.00 of gold at ₹14550.5424/g, that's 0.0344g.",
  "kind": "purchase",
  "resolved_by": "pattern"
}
```

Example investment question:

```json
{
  "user_id": "aarush",
  "message": "Should I buy gold or invest in an FD?"
}
```

Example response:

```json
{
  "reply": "Are you looking for a low-risk investment with a fixed return or an investment that can potentially hedge against inflation?",
  "kind": "clarify",
  "resolved_by": "llm"
}
```

---

## Purchase

```
POST /purchase
```

Creates a one-time gold purchase.

Request:

```json
{
  "user_id": "aarush",
  "amount": "500.00"
}
```

Successful response:

```json
{
  "success": true,
  "deduped": false,
  "transaction": {
    "id": "txn_xxxxxxxxxxxx",
    "rupee_amount": "500.00",
    "gold_quantity": "0.0344",
    "status": "completed"
  }
}
```

---

## Gold Price

```
GET /price
```

Returns the current gold price used by the backend.

---

## SIP

Create a recurring investment.

```
POST /sip
```

Example:

```json
{
  "user_id": "aarush",
  "amount": "1000",
  "frequency": "monthly"
}
```

Supported frequencies:

* daily
* weekly
* monthly

---

Pause an existing SIP.

```
POST /sip/pause
```

Resume a paused SIP.

```
POST /sip/resume
```

Cancel a SIP.

```
POST /sip/cancel
```

---

## User Journey

```
GET /users/{user_id}/journey
```

Returns the recorded audit trail for a user, allowing requests and actions to be reconstructed chronologically.

---

# Background Scheduler

The scheduler runs continuously after application startup.

Its responsibilities are:

* Find SIPs that are due
* Execute recurring purchases
* Advance the next due date
* Record transaction history
* Record audit events

The scheduler reuses the same purchase engine as manual purchases. This avoids duplicated business logic and ensures identical validation rules regardless of how a purchase is initiated.

---

# Testing

Run the complete test suite.

```bash
pytest
```

Run with verbose output.

```bash
pytest -v
```

The test suite covers:

* Purchase flow
* Money precision
* Price provider
* Pattern routing
* Chat orchestration
* SIP lifecycle
* Scheduler execution
* Duplicate request protection

---

# Design Principles

## The LLM is not trusted with financial operations

The language model is responsible for understanding the user's intent.

The backend is responsible for executing financial operations.

This separation ensures that purchases remain deterministic and fully validated even when conversational input is flexible.

---

## Deterministic before Intelligent

Pattern matching is attempted before invoking the LLM.

This reduces latency, eliminates unnecessary model calls for common requests, improves reproducibility, and makes critical paths easier to test.

---

## Precision over Convenience

Financial calculations use `Decimal` throughout the application.

Floating-point arithmetic is intentionally avoided to eliminate rounding inconsistencies.

---

## Shared Business Logic

Manual purchases and SIP installments use the same purchase engine.

This guarantees identical validation, pricing, transaction recording, and audit behavior across both flows.

---

## Auditability

Every significant operation records structured events with correlation identifiers.

This makes it possible to reconstruct an entire interaction from the initial message through the final database transaction.

---

## Failure Isolation

External dependencies such as the price provider and LLM are isolated behind interfaces.

A failure in one component should not bring down the API.

The scheduler also isolates failures so that one unsuccessful execution does not terminate the background task.

---

# Known Limitations

This project intentionally focuses on backend architecture rather than production infrastructure.

Current limitations include:

* Simulated gold pricing rather than a live market feed.
* SQLite instead of a production database.
* Single-process scheduler.
* No authentication or authorization layer.
* No persistent conversation history beyond audit events.
* No real payment gateway integration.

These tradeoffs keep the implementation focused on correctness, architecture, and maintainability while remaining easy to run locally.

---

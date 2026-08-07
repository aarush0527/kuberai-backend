# Decision Log

This document records the architectural and implementation decisions made during development.

The goal is not to argue that every decision is objectively correct. Instead, it captures the alternatives that were considered, why they were rejected, and the tradeoffs that led to the final implementation.

Many of these decisions were not made upfront. Several only appeared after implementing an initial version, encountering edge cases, or discovering bugs during testing. Those are often the most valuable decisions because they reflect how the design evolved rather than how it was originally imagined.

---

## Table of Contents

1. FastAPI + Pydantic over Flask
2. SQLite over PostgreSQL
3. Simulated Price Feed
4. `ROUND_HALF_UP` Instead of Banker's Rounding
5. Reject Over-Precision Rupee Amounts
6. Two-Layer Idempotency
7. SIP Deduplication Strategy
8. Persisting `anchor_day`
9. Failed SIP Installments Do Not Advance
10. Cache Invalidation During Forced Outages
11. Two-Tier Intent Resolution
12. Deterministic Date Arithmetic
13. Template-Based Money Confirmations
14. Clarification Instead of Guessing
15. Running Without an LLM

---

# 1. FastAPI + Pydantic over Flask

## Decision

Use **FastAPI** with **Pydantic** instead of Flask.

## Alternatives Considered

Use Flask and implement validation manually.

## Why I Rejected It

Pydantic provides strict, typed validation on money fields almost for free. Several invalid-input cases such as incorrect precision or invalid types are rejected before the request even reaches the business layer.

Using Flask would have meant rebuilding functionality that FastAPI already provides natively, without any meaningful advantage for this project.

## Tradeoffs

FastAPI introduces more framework conventions than Flask, but the built-in validation, automatic OpenAPI documentation, and type safety significantly reduced boilerplate while making the API easier to maintain.

---

# 2. SQLite over PostgreSQL

## Decision

Use SQLite as the default database.

## Alternatives Considered

Use PostgreSQL from the beginning.

## Why I Rejected It

The priority was ensuring that the project can be cloned and running in a matter of minutes.

Adding a second database container increases setup complexity and introduces another dependency that can fail independently during local development.

SQLAlchemy is used throughout the project, so migrating to PostgreSQL later would primarily be a connection-string change rather than an architectural rewrite.

## Tradeoffs

SQLite is not intended for production workloads with high write concurrency.

For local development, testing, and demonstration purposes, the simpler setup outweighed the limitations.

---

# 3. Simulated Price Feed over a Live Third-Party API

## Decision

Implement a simulated gold price provider instead of relying on a real external pricing API.

## Alternatives Considered

Integrate a live market data provider.

## Why I Rejected It

A live API introduces an external dependency that is outside the project's control.

Network failures, API outages, authentication changes, or rate limits could all affect the application's behavior despite having nothing to do with the backend itself.

The simulated provider begins from a realistic INR-per-gram value and performs a bounded random walk, allowing the application to exercise the same caching and failure-handling logic that would be used with a real provider.

Because pricing is accessed through an abstraction, replacing the simulated provider with an HTTP-based implementation later would not require changes to the purchase logic.

## Tradeoffs

The prices are not real market prices.

However, the surrounding infrastructure—including caching, stale-data handling, and provider abstraction—matches what would be required in a production integration.

---

# 4. `ROUND_HALF_UP` Instead of Banker's Rounding

## Decision

Use `ROUND_HALF_UP` when quantizing gold quantities.

## Alternatives Considered

Use Python's default banker's rounding (`ROUND_HALF_EVEN`).

## Why I Rejected It

This was one of the few implementation decisions where neither option was obviously better.

Banker's rounding is statistically fair when performing large numbers of calculations, but it can produce results that feel unintuitive for an individual transaction.

For example, values exactly halfway between two representable numbers may round down instead of up, which is mathematically valid but often surprising in a customer-facing financial application.

Using `ROUND_HALF_UP` makes receipts easier to reason about because the behavior matches what most users expect when they think about rounding.

The behavior is also protected by dedicated tests to ensure it cannot silently change in the future.

## Tradeoffs

Banker's rounding reduces long-term statistical bias across extremely large datasets.

This project prioritizes predictable, human-friendly behavior for individual financial transactions.

---

# 5. Reject Over-Precision Rupee Amounts Instead of Silently Rounding

## Decision

Reject rupee amounts that contain more than two decimal places.

## Alternatives Considered

Automatically round the value before processing the purchase.

## Why I Rejected It

A user-provided payment amount should not be silently modified by the system.

If someone enters `333.335`, automatically changing that value changes what the user intended to spend without making that decision explicit.

Returning a validation error is slightly less convenient, but it ensures the backend never interprets or modifies a customer's financial input.

Gold quantity is treated differently because it is calculated internally rather than entered by the user.

Rounding derived values is expected.

Rounding user input is not.

## Tradeoffs

Clients must resubmit the request with a valid amount.

The additional validation avoids unexpected financial behavior and keeps ownership of monetary values with the user rather than the backend.

---

# 6. Two-Layer Idempotency Instead of a Single Check

## Decision

Protect purchases using both application-level duplicate detection and a database uniqueness constraint.

## Alternatives Considered

Use only an application-level lookup before creating a transaction.

Use only a database uniqueness constraint.

## Why I Rejected It

An application-level lookup improves user experience but cannot completely prevent race conditions.

Two concurrent requests can both pass the duplicate check before either transaction commits.

A database uniqueness constraint correctly prevents duplicates even under concurrency, but relying on it alone would expose users to raw integrity errors instead of a clean response.

The implementation combines both approaches.

The application checks for duplicates first in the common case.

The database constraint remains the final guarantee when true concurrent requests occur.

## Tradeoffs

Handling integrity exceptions adds another execution path.

In return, duplicate protection remains correct even under concurrent requests while still returning meaningful responses to clients.

---

# 7. Different Deduplication Rules for SIP Creation and Purchases

## Decision

Use different duplicate detection strategies for one-time purchases and SIP creation.

One-time purchases use a short time-based idempotency window.

SIP creation checks whether an identical active SIP already exists.

## Alternatives Considered

Use the same deduplication logic for both operations.

## Why I Rejected It

Although both features involve recurring purchases of gold, they represent different user intentions.

Creating an identical active SIP is almost never intentional. If a user already has an active ₹500 monthly SIP, creating another one with the same configuration is much more likely to be accidental than deliberate.

One-time purchases are different.

A user may legitimately buy ₹500 of gold multiple times during the same day. The backend only needs to protect against accidental duplicate submissions caused by retries or double-clicks.

For that reason, purchases use a short idempotency window while SIP creation simply checks whether an equivalent active SIP already exists.

## Tradeoffs

The application now has two different deduplication strategies instead of one.

However, each strategy more accurately reflects the user's intent for that particular operation instead of forcing unrelated workflows into the same rule.

---

# 8. Persisting `anchor_day` Separately from `next_due_date`

## Decision

Store the original requested day of the month separately from the calculated next execution date.

## Alternatives Considered

Use the previous execution date to calculate the next one.

## Why I Rejected It

This decision came directly from thinking through month-end edge cases.

Suppose a user creates a monthly SIP on the 31st.

February has no 31st, so the scheduler correctly executes on February 28th.

If future due dates are calculated from February 28th instead of the original request, March would also execute on the 28th.

The SIP would permanently drift away from the user's intended schedule.

Persisting the original `anchor_day` allows every future calculation to be based on what the user originally requested instead of whatever happened during the previous month.

That means a SIP created on the 31st correctly runs:

```
January   → 31
February  → 28
March     → 31
April     → 30
May       → 31
```

instead of becoming permanently fixed to the 28th.

## Tradeoffs

The model stores one additional field and the scheduling logic becomes slightly more complex.

The benefit is that monthly schedules remain stable over time instead of drifting after the first short month.

---

# 9. Failed SIP Installments Should Not Advance the Schedule

## Decision

Only advance `next_due_date` after a successful installment.

## Alternatives Considered

Advance the schedule regardless of whether the purchase succeeded.

## Why I Rejected It

A temporary infrastructure issue should not permanently skip a user's investment.

For example, if the price provider becomes unavailable for a few minutes, marking the installment as completed and advancing to the following month would silently lose that month's purchase.

Instead, failed installments leave `next_due_date` unchanged.

The scheduler naturally retries during its next execution cycle.

The due date is only consumed once the purchase has actually completed successfully.

## Tradeoffs

A failed installment may be retried several times until the underlying issue is resolved.

This behavior is preferable to silently skipping scheduled investments.

---

# 10. Clearing the Cache When Simulating Provider Failures

## Decision

Forcing the price provider into a failure state also invalidates the cached price.

## Alternatives Considered

Only enable the failure flag and wait for the cache to expire naturally.

## Why I Rejected It

This decision came from discovering a real implementation issue.

Initially, enabling the simulated outage did not appear to break anything because recent prices were still being served from cache.

As a result, purchases continued succeeding until the cache eventually expired.

That meant the failure mode could not actually be demonstrated immediately.

The fix was to invalidate the cache whenever the provider is forced into a failed state.

Doing so makes the simulated outage observable immediately and keeps the debug functionality predictable.

## Tradeoffs

The debug path now contains one additional operation.

In return, failure testing behaves consistently instead of depending on cache timing.

---

# 11. Pattern Matching Before the LLM

## Decision

Attempt deterministic pattern matching before sending a request to the language model.

## Alternatives Considered

Route every user message directly through the LLM.

## Why I Rejected It

Three reasons ultimately drove this decision.

First, latency.

Pattern matching executes almost instantly while an LLM request involves network latency and inference time.

Second, cost.

Reducing unnecessary model calls keeps operating costs lower and avoids dependence on API rate limits.

Third, and most importantly, testability.

Every intent handled by the pattern layer can be tested without requiring network access or an API key.

Only genuinely conversational or ambiguous requests depend on the language model.

Both approaches produce the same internal `ProposedAction`, allowing the remainder of the backend to remain completely unaware of how the intent was generated.

## Tradeoffs

Maintaining the pattern layer requires adding new rules as supported commands grow.

The reduced latency, deterministic behavior, and easier testing make that maintenance worthwhile.

---

# 12. All Calendar Arithmetic Lives in Backend Code

## Decision

Never allow the language model to calculate dates.

The LLM only identifies scheduling intent.

Python performs every calendar calculation.

## Alternatives Considered

Ask the model to return the final execution date directly.

## Why I Rejected It

Language models are very good at understanding language.

They are much less reliable when performing precise calendar arithmetic involving month lengths, leap years, and edge cases.

By moving all scheduling logic into deterministic backend code, every date calculation becomes fully testable and independent of model behavior.

The model supplies only the information needed to perform the calculation.

The backend determines the actual schedule.

## Tradeoffs

The conversational layer becomes slightly thinner while the scheduling service becomes more responsible.

This separation keeps calendar logic deterministic and significantly easier to verify.

---

# 13. Confirmation Messages Come From Backend Data

## Decision

Confirmation messages are generated directly from backend state rather than by making a second LLM call.

## Alternatives Considered

Ask the language model to generate the final user-facing confirmation after each completed operation.

## Why I Rejected It

Once money has moved, every value shown to the user should come directly from the transaction that was written to the database.

Allowing a second model call introduces unnecessary latency while creating opportunities for values to be paraphrased or reformatted inconsistently.

Simple string templates guarantee that the confirmation exactly matches the recorded transaction.

## Tradeoffs

The responses are slightly less conversational.

In exchange, every confirmation remains deterministic, inexpensive, and fully aligned with the stored transaction data.

---

# 14. Ask for Clarification Instead of Guessing

## Decision

Require explicit clarification whenever multiple interpretations are equally reasonable.

## Alternatives Considered

Select the most likely interpretation automatically.

## Why I Rejected It

Financial software should avoid making assumptions about user intent.

For example, a request such as:

> "I want to invest ₹5000."

does not indicate whether the user wants a one-time purchase or a recurring SIP.

Automatically choosing one could create an unintended financial action.

Instead, the system asks a follow-up question before creating anything.

## Tradeoffs

Users occasionally answer one extra question.

The backend avoids making irreversible decisions based on ambiguous instructions.

---

# 15. The Application Runs Without an LLM

## Decision

The backend starts successfully even when no Groq API key has been configured.

## Alternatives Considered

Fail application startup whenever an LLM provider is unavailable.

## Why I Rejected It

Only conversational understanding depends on an external language model.

The remainder of the system, including purchases, SIP management, pricing, and transaction history, remains fully functional without one.

A missing API key should not prevent developers from running, testing, or exploring the backend.

Instead, the application falls back to a lightweight placeholder client that clearly communicates when conversational functionality is unavailable.

## Tradeoffs

Some chat functionality becomes unavailable until an API key is configured.

The rest of the backend continues operating normally, making local development and onboarding considerably simpler.



# What's Unfinished

This project implements the complete backend required for a conversational digital gold platform, including conversational routing, purchase execution, SIP management, background scheduling, and audit logging.

That said, several areas could be improved before considering the system production-ready. They are listed here intentionally rather than being treated as hidden limitations.

---

# 1. Live Gold Price Integration

The application currently uses a simulated price provider backed by a bounded random walk and a caching layer.

This was sufficient for exercising pricing logic, caching behavior, failure handling, and purchase execution without introducing an external dependency.

For a production deployment, I would replace the simulated provider with a real market data API while keeping the existing `PriceProvider` abstraction. Since the purchase service already depends on the abstraction rather than a specific implementation, this change would be largely isolated to the provider layer.

---

# 2. Authentication and Authorization

The current implementation identifies users using a supplied `user_id`.

This keeps the API simple for local development and testing but is not appropriate for a real application.

A production version would introduce an authentication layer, such as JWT-based authentication or OAuth, and derive the user identity from the authenticated session rather than trusting client input.

---

# 3. Persistent Conversation History

The backend records audit events for every interaction, but it does not maintain full conversational history for context-aware conversations.

Adding persistent conversation history would allow future versions to:

* reference previous messages naturally
* support longer multi-turn conversations
* personalize responses over time
* provide better clarification handling

I intentionally kept the conversational state lightweight so that financial operations remained deterministic and independent of long-running chat history.

---

# 4. Production Database

SQLite keeps the project easy to run locally and requires virtually no setup.

For production use, I would migrate to PostgreSQL while retaining SQLAlchemy as the ORM.

The current data access layer was written with this migration in mind, so most business logic would remain unchanged.

---

# 5. Scheduler Scalability

The scheduler currently runs as an in-process background task.

This works well for a single application instance but becomes problematic if multiple application instances are running simultaneously.

A production deployment would move scheduled execution into a dedicated worker process using a distributed scheduling mechanism or a task queue to avoid duplicate execution and improve reliability.

---

# 6. External Payment Integration

Purchases currently assume that payment has already succeeded.

The backend focuses on recording transactions rather than processing payments.

A complete production system would integrate with a payment gateway, validate payment status before creating transactions, and handle asynchronous payment callbacks and failures.

---

# 7. Observability

The project includes structured audit events that make debugging individual requests straightforward.

However, a production deployment would also benefit from:

* centralized structured logging
* metrics collection
* request tracing
* monitoring dashboards
* automated alerting

These additions would improve operational visibility without changing the application's core business logic.

---

# 8. Expanded Test Coverage

The existing test suite focuses on the critical business logic:

* purchases
* SIP lifecycle
* scheduler execution
* money calculations
* intent routing
* duplicate protection

If given more time, I would expand testing to include:

* higher-volume concurrency scenarios
* long-running scheduler behavior
* property-based testing for money calculations
* end-to-end API tests against a running server
* performance benchmarking under sustained load

---

# Final Thoughts

The remaining work is largely focused on production readiness rather than core functionality.

The underlying architecture was intentionally designed so that components such as the price provider, authentication mechanism, database, and scheduler can evolve independently without requiring major changes to the business logic.

That separation of responsibilities was one of the primary design goals throughout the project and makes future extensions significantly easier.

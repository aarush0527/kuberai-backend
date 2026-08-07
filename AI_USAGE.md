# AI Usage

AI tools were used throughout development to accelerate implementation, explore alternative designs, and debug issues. They were treated as engineering assistants rather than sources of truth.

Every design decision, architectural tradeoff, and final implementation remained my responsibility. AI-generated code was reviewed, modified where necessary, and integrated only after verifying that it matched the intended behavior.

---

# Tools Used

| Tool | Primary Usage |
|------|---------------|
| GitHub Copilot | Code completion, boilerplate generation, and repetitive implementation while coding in VS Code. |
| ChatGPT | Debugging, discussing architectural ideas, understanding framework behavior, validating approaches, and troubleshooting implementation issues. |
| Claude | Implementing larger components, exploring alternative implementations, reviewing architecture, and improving documentation. |

Each tool served a different purpose.

GitHub Copilot primarily accelerated repetitive coding by generating boilerplate and completing common implementation patterns while writing code.

ChatGPT was used as an interactive engineering assistant for debugging, validating implementation approaches, discussing architecture, and understanding framework behavior.

Claude was mainly used for larger implementation tasks, architectural discussions, reviewing implementation decisions, and refining documentation.

---

# How AI Was Used

AI was most helpful during tasks that were repetitive or required exploring multiple implementation options.

Examples include:

* generating initial boilerplate
* discussing API design
* validating SQLAlchemy patterns
* debugging Docker configuration
* reviewing scheduler logic
* improving project documentation
* brainstorming edge cases for testing

In every case, generated code was reviewed before being incorporated into the project.

---

# A Concrete Example

The debug endpoint for forcing the simulated price source into a failure state (`POST /debug/price-source/fail`) was originally implemented like this:

```python
@router.post("/price-source/fail")
def toggle_price_failure(enabled: bool = True, provider=Depends(get_price_provider)):
    provider.force_fail = enabled
    return {"force_fail": provider.force_fail}
```

At first glance, this implementation looked correct. It set the provider's failure flag exactly as intended and even passed code review by inspection.

The problem only became apparent by running the application end to end.

After priming the price cache with an earlier purchase, enabling `force_fail=true`, and immediately attempting another purchase, the request still succeeded.

The reason was that `CachingPriceService.get_price()` first serves values from its in-memory cache. As long as the cached value remained valid, the underlying provider was never called, meaning the newly enabled failure flag wasn't checked until the cache expired.

The fix was to invalidate the cache whenever a forced outage is enabled:

```python
@router.post("/price-source/fail")
def toggle_price_failure(
    enabled: bool = True,
    provider=Depends(get_price_provider),
    price_service=Depends(get_price_service),
):
    provider.force_fail = enabled
    price_service.clear_cache()
    return {"force_fail": provider.force_fail}
```

The important lesson wasn't that the original implementation contained incorrect code. It was locally correct.

The mistake was failing to account for the larger system. The debug endpoint modified the provider, but requests were actually reading from the caching layer sitting in front of it.

This interaction only became visible by exercising the application the same way a user would rather than reviewing the code in isolation.

After fixing the issue, a dedicated regression test (`test_clear_cache_makes_forced_outage_immediately_observable`) was added so the behavior cannot silently regress.

---

# Additional Examples

## Clarification Resolution Selected the Wrong SIP

After a request such as:

> Pause my SIP.

the application correctly detected that multiple SIPs existed and asked the user which one should be paused.

However, replying:

> the 500 one

incorrectly paused the ₹100 SIP.

The clarification resolver checked ordinal words ("first", "second", "one", "two") before checking for an explicit amount, so the word "one" inside "500 one" was incorrectly interpreted as referring to the first SIP.

The resolver was updated to prioritize explicit monetary values before ordinal references, and ambiguous words such as "one", "two", and "three" were removed from the ordinal matching logic because they frequently appear in unrelated contexts.

An end-to-end regression test was added that verifies the correct SIP is paused, rather than simply checking that *some* SIP changed state.

---

## Incorrect Ordinal Suffixes

The SIP confirmation template originally appended `"th"` to every anchor day.

This produced confirmations such as:

```
31th
```

instead of:

```
31st
```

The bug was not apparent from reading the template because nothing looked obviously incorrect in isolation.

It only became visible by reading the generated confirmation message.

The implementation was updated to generate proper ordinal suffixes (`st`, `nd`, `rd`, `th`), and regression tests were added to ensure incorrect suffixes cannot reappear.

---

## Verification Script Wasn't Safe to Re-run

The original verification script assumed it would always be executed against a fresh application instance.

Running the script twice against an already populated database produced apparent failures.

The backend itself was behaving correctly.

The failures occurred because duplicate requests triggered the application's idempotency guarantees, causing the verification script to interpret successful duplicate protection as failed behavior.

The solution was to generate a unique user identifier for each verification run.

Besides making the script idempotent, this also better reflected how different users would interact with the application in practice.

---

# Final Thoughts

AI significantly accelerated development by reducing the time spent writing repetitive code and providing a useful sounding board during debugging and design discussions.

At the same time, the project reinforced that generated code is only one part of building reliable software. The more challenging work involved understanding how different components interacted, identifying edge cases through testing, and recognizing when an implementation that appeared correct in isolation behaved incorrectly within the broader system.

Throughout development, AI was treated as a productivity tool rather than an authority. Every significant implementation was reviewed, tested, and adapted before becoming part of the final project.

# Contributing

Install with `pip install -e ".[dev]"`. Run `pytest` and `ruff check .` before submitting.

Keep orchestration logic independent from LLM SDKs and web frameworks. Validate all generated plans before scheduling. Do not enable host side effects implicitly. Add regression tests for graph integrity, dependency ordering, concurrency, retries, failures and persistence. Update docs and sample configuration for every new setting.

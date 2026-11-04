# Contributing

## Setup

```bash
python -m pip install -e ".[dev,api,openai]"
```

## Quality gates

```bash
pytest
ruff check .
```

## Expectations

- Keep runtime contracts independent from provider SDKs and API frameworks.
- Do not invent AgentForge fields: integrate against the published 1.1.0 catalog and package API.
- Validate every generated plan before dispatch.
- Keep provider tools disabled unless a separately reviewed executor and permission model exist.
- Add regression coverage for dependency ordering, concurrency, retries, failure propagation, registry compatibility and API authorization.
- Update README, docs, roadmap and .env.example when behavior or configuration changes.
- Never commit API keys, personal data, provider secrets or customer project context.

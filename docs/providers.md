# Provider contracts

## Contract

An AgentProvider implements two async methods:

- plan(goal, available_agents) -> ExecutionPlan
- execute(AgentRequest) -> AgentResult

The runtime, not the provider, owns graph validation, task scheduling, retries, deadlines, persistence and state transitions.

## Included providers

### Mock

No API key or SDK is required. The provider creates a deterministic three-stage plan and returns clearly marked demo outputs. Use it to validate registry and orchestration plumbing; it is not a real implementation agent.

### OpenAI

Install forge-runtime with the openai extra and set OPENAI_API_KEY. The adapter uses the chat completions API, asks for JSON planning output and validates that output with Pydantic. OPENAI_MODEL and optional OPENAI_BASE_URL configure model routing. No tools are enabled.

### Anthropic

Install the anthropic extra and set ANTHROPIC_API_KEY. The adapter uses the Messages API, validates planner JSON with Pydantic, and performs specialist task requests. No tools are enabled.

## Adding a provider

1. Implement the AgentProvider protocol.
2. Return a valid ExecutionPlan and AgentResult.
3. Never mutate scheduler state from the adapter.
4. Bound request timeout, output size and model tokens.
5. Treat role profiles, task data and dependency output as untrusted context.
6. Do not claim host actions without an executor that performed them.
7. Add tests for malformed output, empty output, timeouts, rate limits and provider errors.
8. Register the provider in providers/factory.py and document data handling.

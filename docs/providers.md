# Provider interfaces

The core provider contract is intentionally small:

- `plan(goal, available_agents) -> ExecutionPlan`
- `execute(AgentRequest) -> AgentResult`

The runtime retains ownership of scheduling, state transitions, retries and policy. Providers must not mutate runtime records or execute host tools implicitly.

## Mock provider
Deterministic output for tests and demonstrations. It is not real engineering work.

## OpenAI provider
Install the optional extra and set `OPENAI_API_KEY`. It uses a text completion path and validates planner JSON with Pydantic. Tool calling is not enabled.

## Anthropic provider
Install the optional extra and set `ANTHROPIC_API_KEY`. It returns text for task execution and validates planner JSON. Tool use is not enabled.

## Adding a provider
Implement the protocol; return Pydantic-valid output; bound request time, response size and tokens; redact credentials; test rate limits, invalid output, empty responses and timeouts; document data handling.

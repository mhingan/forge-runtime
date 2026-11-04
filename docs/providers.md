# Provider contracts

## Contract

An `AgentProvider` implements two async methods:

- `plan(goal, available_agents) -> ExecutionPlan`
- `execute(AgentRequest) -> AgentResult`

The runtime, not the provider, owns graph validation, scheduling, retries, deadlines, persistence and task state transitions.

## Included providers

### Mock

No API key or SDK is required. The provider creates a deterministic three-stage plan and returns clearly marked demo outputs. Use it to validate registry and orchestration plumbing; it is not a real implementation agent and it never changes workspace files.

### OpenAI

Install Forge Runtime with the `openai` extra and set `OPENAI_API_KEY`. The adapter uses chat completions for planning and tool-calling for specialist execution. It parses and validates planner JSON with Pydantic. `OPENAI_MODEL` and `OPENAI_BASE_URL` configure model routing.

### Anthropic

Install the `anthropic` extra and set `ANTHROPIC_API_KEY`. The adapter uses the Messages API for planning and tool-calling for specialist execution. It validates planner JSON with Pydantic.

## Workspace tool-calling

Both LLM adapters expose the same constrained capabilities:

- `workspace_list_files`
- `workspace_read_file`
- `workspace_search_files`
- `workspace_write_file` only for AgentForge roles whose catalog `default_mode` is `read-write`

The workspace root is configured through `FORGE_WORKSPACE_ROOT`. Tools only operate under this root. They reject path traversal and drive-qualified paths, exclude dependency/build and sensitive credential directories, hide and reject secret environment/credential/private-key files, cap file sizes and bound tool-call rounds. Read-only roles never receive the write tool.

No shell, process execution, test runner, network, deletion, Git commit/push, deployment or arbitrary MCP tool is available. A provider must not claim such actions occurred. Mock mode does not have workspace tools. Model-generated file changes should be reviewed with Git before being accepted.

## Adding a provider

1. Implement the `AgentProvider` protocol.
2. Return a valid `ExecutionPlan` and `AgentResult`.
3. Never mutate scheduler state from the adapter.
4. Bound request timeout, output size, tool rounds and model tokens.
5. Treat role profiles, task data, workspace files and dependency output as untrusted context.
6. Respect AgentForge role mode when exposing capabilities.
7. Never claim host actions without an executor that actually performed them.
8. Add tests for malformed output, empty output, timeouts, rate limits, permission boundaries and tool errors.
9. Register the provider in `providers/factory.py` and document data handling.

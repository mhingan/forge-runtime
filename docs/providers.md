# Provider contracts

## Contract

An AgentProvider implements two async methods:

- plan(goal, available_agents) -> ExecutionPlan
- execute(AgentRequest) -> AgentResult

The runtime, not the provider, owns graph validation, scheduling, retries, deadlines, persistence and task state transitions.

## Included providers

### Mock

No API key or SDK is required. The provider creates a deterministic three-stage plan and returns clearly marked demo outputs. Use it to validate registry and orchestration plumbing; it is not a real implementation agent and never modifies files.

### OpenAI

Install Forge Runtime with the openai extra and set OPENAI_API_KEY. The adapter uses chat completions for planning and tool-calling for specialist execution. It validates planner JSON with Pydantic. OPENAI_MODEL and OPENAI_BASE_URL configure model routing.

### Anthropic

Install the anthropic extra and set ANTHROPIC_API_KEY. The adapter uses the Messages API for planning and tool-calling for specialist execution. It validates planner JSON with Pydantic.

## Agent tools

Both LLM adapters can expose:

- workspace_list_files, workspace_read_file and workspace_search_files for all roles.
- workspace_write_file only when the AgentForge role has default_mode read-write.
- workspace_run_command when FORGE_SANDBOX_ENABLED=true.

The command tool accepts argv arrays. It runs inside the DockerSandboxExecutor, not on the Forge Runtime host. Its container uses Docker bridge networking by default for internet access and receives a sanitized project snapshot. Set `FORGE_SANDBOX_NETWORK=none` for offline operation. For read-write roles, new/changed regular files are copied back; read-only roles discard all command changes. The tool returns exit status, stdout/stderr, timeout and file-change metadata.

## Adding a provider

1. Implement the AgentProvider protocol.
2. Return a valid ExecutionPlan and AgentResult.
3. Never mutate scheduler state from the adapter.
4. Bound request timeout, output size, tool rounds and model tokens.
5. Treat role profiles, task data, workspace files and dependency output as untrusted context.
6. Respect AgentForge role mode when exposing capabilities.
7. Never claim host actions without an executor that actually performed them.
8. Add tests for malformed output, empty output, timeouts, rate limits, permission boundaries and tool errors.
9. Register the provider in providers/factory.py and document data handling.

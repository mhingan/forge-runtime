# Local PyPI release

Forge packages are uploaded locally by the maintainer using a PyPI API token. GitHub Actions validates pull requests but does not publish distributions.

## Release order

Publish the dependencies before publishing Forge Runtime:

1. agentforge-toolkit at version 1.2.1 or newer in the 1.x line.
2. forge-mcp-registry at version 0.2.0 or newer in the 0.x line.
3. forge-agent-runtime at version 0.2.0 or newer.

Runtime declares both packages as dependencies. Uploading Runtime before the two dependency versions are available will make a fresh installation fail dependency resolution.

## Build and verify

Run each package's own validation and build from a clean checkout:

    python -m pip install --upgrade build twine
    python -m pytest -q
    python -m build
    python -m twine check dist/*

For AgentForge, also run:

    python scripts/format_json.py --check
    python scripts/sync_package_data.py --check
    python -m agentforge validate --strict
    python -m unittest discover -s tests -v

For Forge MCP, also run:

    python -m ruff check src/forge_mcp tests

For Forge Runtime, also run:

    ruff check src tests

## Upload locally

Create a PyPI API token for the specific project being uploaded. Then run:

    python -m twine upload dist/*

When prompted, use __token__ as the username and paste the API token as the password. Twine hides the password input. Do not put the token in source files, shell scripts, GitHub files, or committed environment files.

## Versioning

PyPI releases are immutable. Increase the package version, remove old dist/ contents, rebuild, verify metadata, and upload the newly created files. Do not reuse a version that has already been uploaded.

## Install

After the three packages are published:

    python -m pip install "forge-agent-runtime[openai]"

For Anthropic:

    python -m pip install "forge-agent-runtime[anthropic]"

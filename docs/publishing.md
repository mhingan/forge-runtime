# Publishing forge-agent-runtime to PyPI

The distribution name is `forge-agent-runtime`. The import package is `forge_runtime`, and the installed CLI command is `forge`.

## One-time PyPI setup

The repository is configured to publish through PyPI Trusted Publishing. This uses GitHub Actions OIDC and does not require a long-lived PyPI API token in GitHub Secrets.

1. Sign in to PyPI with the account that should own the project.
2. Open **Account settings → Publishing** and add a **pending publisher** for a new project.
3. Enter these exact values:

   | Field | Value |
   |---|---|
   | PyPI project name | `forge-agent-runtime` |
   | Owner | `mhingan` |
   | Repository | `forge-runtime` |
   | Workflow filename | `.github/workflows/publish.yml` |
   | Environment | `pypi` |

4. In GitHub, open **mhingan/forge-runtime → Settings → Environments** and create an environment named `pypi`. Optionally add required reviewers to approve releases before publishing.

A pending publisher is the supported PyPI flow for creating a new project through Trusted Publishing. The name is not reserved until the first successful publication, so complete the setup and release promptly after confirming availability.

Official PyPI instructions:
- [Create a project with a pending Trusted Publisher](https://docs.pypi.org/trusted-publishers/creating-a-project-through-oidc/)
- [Publish with a Trusted Publisher](https://docs.pypi.org/trusted-publishers/using-a-publisher/)

## First release

The project version is maintained in `pyproject.toml` and mirrored in `forge_runtime.__version__`.

For the initial release:

1. Make sure the latest `main` branch has a green CI run.
2. Create a GitHub Release from the `main` branch with the tag `v0.1.0`.
3. Publish the GitHub Release.

The `.github/workflows/publish.yml` workflow then:

- Checks out the tagged source and confirms the tag matches the package version.
- Checks that the initial PyPI project name is still available.
- Builds a wheel and source distribution.
- Validates metadata with `twine check`.
- Verifies the bundled sandbox Dockerfile is present in both distributions.
- Publishes using PyPI Trusted Publishing.

Do not upload the same version manually before the workflow runs. PyPI does not allow an existing version to be overwritten.

## Install after publication

Open the package page at [pypi.org/project/forge-agent-runtime](https://pypi.org/project/forge-agent-runtime/).

Install the OpenAI extra:

```bash
python -m pip install "forge-agent-runtime[openai]"
forge setup
forge run "Inspect this project, implement the requested feature and run tests"
```

For Anthropic:

```bash
python -m pip install "forge-agent-runtime[anthropic]"
forge setup --provider anthropic
```

For the API extra, use `forge-agent-runtime[api]`; to install all optional integrations for development, install `forge-agent-runtime[openai,anthropic,api,dev]`.

## Future releases

Update both `[project].version` in `pyproject.toml` and `__version__` in `src/forge_runtime/__init__.py` to the same new version. Push the change, wait for CI to pass, then create and publish a GitHub Release with the matching `vX.Y.Z` tag.

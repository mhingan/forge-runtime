FROM python:3.12-slim

ENV DEBIAN_FRONTEND=noninteractive \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        bash \
        build-essential \
        ca-certificates \
        git \
        make \
        nodejs \
        npm \
    && rm -rf /var/lib/apt/lists/*

RUN python -m pip install --no-cache-dir \
    pytest \
    ruff \
    mypy \
    coverage \
    uv \
    pydantic \
    pydantic-settings \
    httpx \
    typer \
    rich \
    fastapi \
    uvicorn \
    agentforge-toolkit==1.1.0

ENV HOME=/tmp \
    TMPDIR=/tmp \
    PATH=/usr/local/bin:/usr/bin:/bin

WORKDIR /workspace

# The runtime overrides UID/GID, drops Linux capabilities, disables networking,
# mounts the root filesystem read-only and only bind-mounts a sanitized project copy.
CMD ["python", "--version"]

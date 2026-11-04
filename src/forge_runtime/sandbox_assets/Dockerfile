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
        coreutils \
        curl \
        git \
        make \
        nodejs \
        npm \
        tar \
        wget \
    && rm -rf /var/lib/apt/lists/*

# Keep the in-container toolchain aligned with the supported project ranges.
RUN python -m pip install --no-cache-dir \
    "pytest>=8,<9" \
    "pytest-asyncio>=0.23,<2" \
    "pytest-cov>=5,<8" \
    "ruff>=0.5" \
    "mypy>=1.10" \
    "coverage>=7,<8" \
    "uv" \
    "pydantic>=2.7,<3" \
    "pydantic-settings>=2.2,<3" \
    "httpx>=0.27,<1" \
    "typer>=0.12,<1" \
    "rich>=13.7,<15" \
    "fastapi>=0.115,<1" \
    "uvicorn[standard]>=0.30,<1" \
    "agentforge-toolkit>=1.2.1,<2"

ENV HOME=/tmp \
    TMPDIR=/tmp \
    PATH=/usr/local/bin:/usr/bin:/bin

RUN mkdir -p /opt/forge-node_modules

WORKDIR /workspace

# The runtime overrides UID/GID and drops Linux capabilities; Docker controls bridge/offline networking,
# and transfers a sanitized snapshot to bounded tmpfs (not a host project bind mount).
CMD ["python", "--version"]

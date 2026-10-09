# Keep in step with apps/api/Dockerfile.api, which names the uv version that apps/api/pyproject.toml requires.
FROM ghcr.io/astral-sh/uv:0.12.21@sha256:a7aed3216253ee804de3e2d8afa5073baa1a177335345d43845cd4165e43b711 AS uv

FROM python:3.12.12-slim-bookworm
ENV PYTHONUNBUFFERED=1 PYTHONDONTWRITEBYTECODE=1 PIP_DISABLE_PIP_VERSION_CHECK=1
# uv installs the locked dependencies into the image's own Python, as apps/api/Dockerfile.api does.
ENV UV_PROJECT_ENVIRONMENT=/usr/local UV_PYTHON_DOWNLOADS=never UV_NO_CACHE=1
RUN apt-get update && apt-get install -y --no-install-recommends libpq-dev gcc g++ libxml2-dev libxslt1-dev libxmlsec1-dev pkg-config && rm -rf /var/lib/apt/lists/*
WORKDIR /code
COPY apps/api/pyproject.toml apps/api/uv.lock ./
RUN --mount=from=uv,source=/uv,target=/bin/uv uv sync --locked --inexact --no-default-groups --group production
# The base image ships the standard library without bytecode, and PYTHONDONTWRITEBYTECODE keeps a
# container from writing it, so each Python process would compile those modules again at start.
RUN python -m compileall -q /usr/local/lib/python3.12
COPY apps/api /code
RUN python -m compileall -q /code
RUN mkdir -p /code/plane/logs /code/static-assets/collected-static
ENV DJANGO_SETTINGS_MODULE=plane.settings.production
RUN DATABASE_URL=postgresql://plane:build@127.0.0.1/plane REDIS_URL=redis://127.0.0.1:6379/0 SECRET_KEY=local-build-collectstatic python manage.py collectstatic --noinput

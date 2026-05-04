FROM python:3.11-slim AS builder

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    PIP_DEFAULT_TIMEOUT=300 \
    PIP_RETRIES=12

WORKDIR /build

ARG PIP_INDEX_URL=https://pypi.org/simple
ARG PIP_TRUSTED_HOST=

COPY pyproject.toml README.md ./
COPY requirements.lock ./
COPY app ./app
RUN --mount=type=cache,target=/root/.cache/pip \
    pip install --prefix=/install \
        --index-url "${PIP_INDEX_URL}" \
        ${PIP_TRUSTED_HOST:+--trusted-host "${PIP_TRUSTED_HOST}"} \
        -r requirements.lock

FROM python:3.11-slim AS runtime

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    TZ=Asia/Shanghai \
    PATH=/install/bin:$PATH \
    PYTHONPATH=/app:/install/lib/python3.11/site-packages

RUN groupadd -r app && useradd -r -g app app

WORKDIR /app

COPY --from=builder /install /install
COPY --chown=app:app app ./app
COPY --chown=app:app alembic ./alembic
COPY --chown=app:app alembic.ini ./
COPY --chown=app:app pyproject.toml ./

USER app

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=5s --start-period=20s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8000/readyz', timeout=2)" || exit 1

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]

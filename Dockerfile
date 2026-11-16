FROM python:3.12-slim

COPY --from=ghcr.io/astral-sh/uv:0.8.22 /uv /usr/local/bin/uv

WORKDIR /app
ENV UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    PYTHONUNBUFFERED=1

# Dependencies first so they are cached independently of source changes.
COPY pyproject.toml uv.lock README.md ./
RUN uv sync --locked --no-dev --extra dashboard --no-install-project

COPY src ./src
COPY dashboard ./dashboard
COPY evals ./evals
RUN uv sync --locked --no-dev --extra dashboard

ENV PATH="/app/.venv/bin:$PATH"
EXPOSE 8501

# Default: the dashboard. For the CLI: docker run --rm -it --env-file .env skill-agent skill-agent chat
CMD ["streamlit", "run", "dashboard/app.py", "--server.address=0.0.0.0", "--server.port=8501", "--server.headless=true"]

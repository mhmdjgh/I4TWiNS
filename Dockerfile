FROM python:3.12-slim

COPY --from=ghcr.io/astral-sh/uv:0.13.8 /uv /usr/local/bin/uv

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
COPY .streamlit ./.streamlit
RUN uv sync --locked --no-dev --extra dashboard

RUN useradd --create-home --uid 1000 app && chown -R app /app
USER app

ENV PATH="/app/.venv/bin:$PATH"
EXPOSE 8501
HEALTHCHECK --interval=30s --timeout=5s --start-period=20s \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8501/_stcore/health')"

# Default: the dashboard. For the CLI: docker run --rm -it --env-file .env skill-agent skill-agent chat
CMD ["streamlit", "run", "dashboard/app.py", "--server.address=0.0.0.0", "--server.port=8501", "--server.headless=true"]

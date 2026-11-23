FROM python:3.13-slim AS build
COPY --from=ghcr.io/astral-sh/uv:0.11.8 /uv /bin/uv
WORKDIR /app
ENV UV_COMPILE_BYTECODE=1 UV_LINK_MODE=copy UV_PYTHON_DOWNLOADS=never
COPY pyproject.toml uv.lock .python-version ./
RUN uv sync --locked --no-dev

FROM python:3.13-slim
LABEL org.opencontainers.image.source="https://github.com/umairedu/kube-right-sizer" \
      org.opencontainers.image.description="Right-size Kubernetes requests and limits from Prometheus usage history"
# pip is not needed at runtime and its vendored packages show up in scans
RUN useradd --uid 10001 --no-create-home app && python -m pip uninstall -y -q pip
WORKDIR /app
COPY --from=build /app/.venv /app/.venv
COPY rightsizer/ rightsizer/
ENV PATH=/app/.venv/bin:$PATH PYTHONUNBUFFERED=1 PYTHONDONTWRITEBYTECODE=1
USER 10001
CMD ["python", "-m", "rightsizer"]

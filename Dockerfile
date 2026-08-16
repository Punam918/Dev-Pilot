# Set PYTHON_IMAGE to a reviewed sha256 digest for a release build.
ARG PYTHON_IMAGE=python:3.12-slim-bookworm
FROM ${PYTHON_IMAGE} AS build
ENV PIP_NO_CACHE_DIR=1 PIP_DISABLE_PIP_VERSION_CHECK=1
WORKDIR /build
COPY requirements/runtime.txt /build/requirements.txt
RUN pip wheel --wheel-dir /wheels -r /build/requirements.txt
COPY pyproject.toml README.md LICENSE /build/
COPY devpilot /build/devpilot
RUN pip wheel --no-deps --wheel-dir /wheels .

FROM ${PYTHON_IMAGE} AS runtime
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 PIP_NO_CACHE_DIR=1 HOME=/tmp
RUN apt-get update && apt-get install -y --no-install-recommends git ca-certificates \
    && rm -rf /var/lib/apt/lists/* \
    && useradd --uid 10001 --create-home devpilot
COPY --from=build /wheels /wheels
RUN pip install --no-index /wheels/*.whl && rm -rf /wheels \
    && mkdir -p /data /workspace /app \
    && chown 10001:10001 /data /workspace /app
WORKDIR /app
USER 10001:10001
EXPOSE 8080
STOPSIGNAL SIGTERM
HEALTHCHECK --interval=15s --timeout=3s --start-period=30s --retries=3 \
  CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8080/livez',timeout=2)"
CMD ["python", "-m", "devpilot", "serve", "--seed"]

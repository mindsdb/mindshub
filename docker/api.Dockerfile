FROM python:3.12-slim AS builder

RUN pip install uv --no-cache-dir

WORKDIR /src
COPY backend/core_agent/ ./core_agent/
COPY backend/core_api/ ./core_api/

RUN python -m venv /opt/venv && \
    /opt/venv/bin/pip install uv --no-cache-dir && \
    /opt/venv/bin/uv pip install ./core_agent ./core_api

FROM python:3.12-slim AS runtime

LABEL org.opencontainers.image.title="cowork-api"
LABEL org.opencontainers.image.source="https://github.com/mindsdb/minds-platform"

RUN apt-get update && apt-get install -y --no-install-recommends ca-certificates \
    && rm -rf /var/lib/apt/lists/* \
    && useradd -m -u 1000 -s /bin/bash cowork

COPY --from=builder /opt/venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH" \
    PYTHONUNBUFFERED=1 \
    COWORK_SERVER_HOST=0.0.0.0 \
    COWORK_SERVER_PORT=26866

RUN mkdir -p /home/cowork/.cowork && chown cowork:cowork /home/cowork/.cowork

USER cowork

EXPOSE 26866

HEALTHCHECK --interval=30s --timeout=5s --start-period=20s --retries=3 \
    CMD python -c "import urllib.request,sys; \
sys.exit(0 if urllib.request.urlopen('http://127.0.0.1:26866/health',timeout=3).status==200 else 1)"

CMD ["cowork-server"]

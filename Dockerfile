# N-Ways Addressing for Guinea: the registry server.
#   docker compose up            (or: docker build -t gn-addresses . && docker run -p 8080:8080 -v gn-data:/data gn-addresses)
# On first start the bundled registry is imported into /data/addresses.sqlite (about two minutes,
# about 2 GB); later starts serve at once.
FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    ADDRESSES_DB=/data/addresses.sqlite \
    REGISTRY_DIR=/app/registry \
    PORT=8080

RUN groupadd --system --gid 10001 addresses \
 && useradd --system --uid 10001 --gid addresses --home-dir /app --shell /usr/sbin/nologin addresses \
 && mkdir -p /data && chown addresses:addresses /data

WORKDIR /app
COPY engine/data engine/data
COPY engine/reference/gn_codes.py engine/reference/plate_names.py engine/reference/
COPY registry registry
COPY server server
COPY LICENSE LICENSE-DATA NOTICE ./

USER addresses
VOLUME ["/data"]
EXPOSE 8080

HEALTHCHECK --interval=30s --timeout=5s --start-period=300s --retries=3 \
  CMD ["python3", "-c", "import os, urllib.request; urllib.request.urlopen('http://127.0.0.1:%s/v1/health' % os.environ.get('PORT', '8080'), timeout=4)"]

CMD ["python3", "-m", "server", "start"]

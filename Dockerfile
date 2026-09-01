# syntax=docker/dockerfile:1

# --- frontend build ---------------------------------------------------
# VITE_API_BASE=/api is the whole trick: Caddy strips /api before
# proxying to uvicorn (see Caddyfile's handle_path), so every fetch the
# built JS makes lands on the same origin the page was served from.
# CORS never enters the picture in this image.
FROM node:20-alpine AS frontend-builder
WORKDIR /app/frontend
COPY frontend/package.json frontend/package-lock.json* ./
RUN npm ci
COPY frontend/ ./
ENV VITE_API_BASE=/api
RUN npm run build

# --- bitcoind + caddy fetch ---------------------------------------------
# Both are pulled as pinned, checksummed binary releases rather than
# apt/distro packages, so the exact version this project was built and
# tested against (bitcoind v31.1 -- the commit sources.py's citations are
# pinned to; caddy 2.11.4 -- what the Caddyfile above was verified
# against) is what actually ships, not "whatever's in the repo today."
FROM debian:bookworm-slim AS fetcher
RUN apt-get update && apt-get install -y --no-install-recommends curl ca-certificates && rm -rf /var/lib/apt/lists/*
ARG TARGETARCH
ARG BITCOIN_VERSION=31.1
ARG CADDY_VERSION=2.11.4
WORKDIR /fetch

RUN set -eux; \
    case "$TARGETARCH" in \
      amd64) BITCOIN_ARCH="x86_64-linux-gnu"; CADDY_ARCH="amd64" ;; \
      arm64) BITCOIN_ARCH="aarch64-linux-gnu"; CADDY_ARCH="arm64" ;; \
      *) echo "unsupported TARGETARCH: $TARGETARCH" >&2; exit 1 ;; \
    esac; \
    BITCOIN_TARBALL="bitcoin-${BITCOIN_VERSION}-${BITCOIN_ARCH}.tar.gz"; \
    curl -fsSLO "https://bitcoincore.org/bin/bitcoin-core-${BITCOIN_VERSION}/${BITCOIN_TARBALL}"; \
    curl -fsSL -o SHA256SUMS "https://bitcoincore.org/bin/bitcoin-core-${BITCOIN_VERSION}/SHA256SUMS"; \
    grep " ${BITCOIN_TARBALL}\$" SHA256SUMS | sha256sum -c -; \
    tar -xzf "$BITCOIN_TARBALL"; \
    mkdir -p /out/bin; \
    cp "bitcoin-${BITCOIN_VERSION}/bin/bitcoind" "bitcoin-${BITCOIN_VERSION}/bin/bitcoin-cli" /out/bin/; \
    curl -fsSL -o caddy.tar.gz "https://github.com/caddyserver/caddy/releases/download/v${CADDY_VERSION}/caddy_${CADDY_VERSION}_linux_${CADDY_ARCH}.tar.gz"; \
    tar -xzf caddy.tar.gz -C /out/bin caddy

# --- final image ---------------------------------------------------------
FROM python:3.12-slim-bookworm
RUN apt-get update && apt-get install -y --no-install-recommends curl && rm -rf /var/lib/apt/lists/*

COPY --from=fetcher /out/bin/bitcoind /out/bin/bitcoin-cli /out/bin/caddy /usr/local/bin/

WORKDIR /app
COPY backend/requirements.txt backend/requirements.txt
RUN pip install --no-cache-dir -r backend/requirements.txt

# vendored test_framework, mutation/scenario/source catalogs, RPC glue --
# fixtures.json is excluded by .dockerignore, so it's never baked in.
COPY backend/ backend/
COPY regtest.conf ./
COPY Caddyfile ./
COPY entrypoint.sh ./
RUN chmod +x entrypoint.sh

COPY --from=frontend-builder /app/frontend/dist /srv/frontend

# Deliberately no VOLUME for the bitcoin datadir: it lives in the
# container's own writable layer and disappears on every restart, which
# is exactly what makes FORCE_SETUP's re-mine-on-boot correct rather than
# just theoretical. See setup_chain.py and entrypoint.sh.
ENV FORCE_SETUP=1

EXPOSE 8080
ENV PORT=8080
HEALTHCHECK --interval=30s --timeout=5s --start-period=90s --retries=3 \
    CMD curl -fsS "http://127.0.0.1:${PORT}/api/health" || exit 1

ENTRYPOINT ["./entrypoint.sh"]

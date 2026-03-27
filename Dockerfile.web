FROM python:3.13.7-alpine3.22

# Install system dependencies: Node.js, Chromium, xvfb, supervisor
RUN apk add --update --no-cache \
    nodejs npm \
    chromium chromium-chromedriver \
    xvfb xauth \
    supervisor

ENV AUTO_SOUTHWEST_CHECK_IN_DOCKER=1

WORKDIR /app

# --- Python dependencies ---
COPY worker/requirements.txt /app/worker/requirements.txt
RUN pip3 install --upgrade pip && \
    pip3 install --no-cache-dir -r /app/worker/requirements.txt

# --- Node dependencies ---
COPY frontend/package.json frontend/package-lock.json /app/frontend/
RUN cd /app/frontend && npm ci

# --- Copy application code ---
COPY frontend/ /app/frontend/
COPY worker/ /app/worker/
COPY supervisord.conf /app/supervisord.conf
COPY init-db.sql /app/init-db.sql

# --- Build Next.js (standalone output) ---
RUN cd /app/frontend && npm run build

# Next.js standalone needs the static files copied alongside it
RUN cp -r /app/frontend/.next/static /app/frontend/.next/standalone/.next/static
# Copy public dir if it exists
RUN if [ -d /app/frontend/public ]; then cp -r /app/frontend/public /app/frontend/.next/standalone/public; fi
# Copy better-sqlite3 native module into standalone node_modules
RUN cp -r /app/frontend/node_modules/better-sqlite3 /app/frontend/.next/standalone/node_modules/better-sqlite3 2>/dev/null || true
RUN cp -r /app/frontend/node_modules/bindings /app/frontend/.next/standalone/node_modules/bindings 2>/dev/null || true
RUN cp -r /app/frontend/node_modules/prebuild-install /app/frontend/.next/standalone/node_modules/prebuild-install 2>/dev/null || true
RUN cp -r /app/frontend/node_modules/file-uri-to-path /app/frontend/.next/standalone/node_modules/file-uri-to-path 2>/dev/null || true

# --- Create data directory for SQLite ---
RUN mkdir -p /app/data

EXPOSE 3000

CMD ["supervisord", "-c", "/app/supervisord.conf"]

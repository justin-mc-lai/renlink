FROM h4ckf0r0day/obscura:latest AS obscura

FROM node:20-bookworm-slim AS node

FROM python:3.11-slim-bookworm

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

# f2 uses pyexecjs, which needs a real Node runtime.
COPY --from=node /usr/local/bin/node /usr/local/bin/node
COPY --from=node /usr/local/lib/node_modules /usr/local/lib/node_modules
RUN ln -sf /usr/local/lib/node_modules/npm/bin/npm-cli.js /usr/local/bin/npm

# Optional renderer binary: copied in, never started unless ENABLE_OBSCURA=1.
# It is a single static Rust binary (no Chromium, no system browser stack).
COPY --from=obscura /obscura /usr/local/bin/obscura
RUN chmod +x /usr/local/bin/obscura

WORKDIR /app

COPY container/requirements.txt ./requirements.txt
RUN pip install --no-cache-dir -r requirements.txt \
    && node --version \
    && python -c "import logging; logging.getLogger('f2').addHandler(logging.NullHandler()); import f2, curl_cffi; print('f2 import ok', getattr(f2, '__version__', 'unknown'), '| curl_cffi', curl_cffi.__version__)"

# Douyin's main path is a signed HTTP call (chg_42d5d41158ba); rendering is
# only the optional Obscura server. The image downloads no browser at all:
# no Chromium, no Playwright browser binaries.
RUN pip install --no-cache-dir playwright==1.64.1 \
    && python -c "from playwright.sync_api import sync_playwright; print('playwright CDP client ok')" \
    && test ! -d /ms-playwright

COPY container/app ./app
COPY contract ./contract
COPY container/entrypoint.sh /usr/local/bin/renlink-entrypoint
RUN chmod +x /usr/local/bin/renlink-entrypoint

EXPOSE 8080

HEALTHCHECK --interval=30s --timeout=3s --start-period=40s --retries=3 \
  CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8080/health', timeout=2)"

ENTRYPOINT ["/usr/local/bin/renlink-entrypoint"]
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8080"]

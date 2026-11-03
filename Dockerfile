FROM python:3.12-slim AS builder
WORKDIR /build

COPY requirements.txt pyproject.toml README.md LICENSE ./
COPY src/ ./src/
# The local development requirement (-e .) becomes a regular wheel, so the
# runtime does not depend on an editable install's path in this build stage.
RUN python -c "from pathlib import Path; Path('/tmp/runtime-requirements.txt').write_text('\n'.join(line for line in Path('requirements.txt').read_text().splitlines() if line.strip() != '-e .') + '\n')" \
    && python -m pip wheel --no-cache-dir --only-binary=:all: \
        --wheel-dir=/wheels -r /tmp/runtime-requirements.txt \
    && python -m pip wheel --no-cache-dir --no-deps --wheel-dir=/wheels . \
    && python -m venv /opt/venv \
    && /opt/venv/bin/python -m pip install --no-cache-dir --no-index \
        --find-links=/wheels python-price-drop-alerts

FROM python:3.12-slim AS runtime
ENV PATH="/opt/venv/bin:$PATH" \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

RUN groupadd --gid 10001 app \
    && useradd --uid 10001 --gid app --home-dir /workspace --no-create-home app \
    && mkdir -p /workspace/data \
    && chown -R app:app /workspace
COPY --from=builder /opt/venv /opt/venv
COPY LICENSE /usr/share/licenses/python-price-drop-alerts/LICENSE
WORKDIR /workspace
COPY --chown=app:app watchlist.yaml ./watchlist.yaml

USER 10001:10001
EXPOSE 8765
HEALTHCHECK --interval=30s --timeout=5s --start-period=5s --retries=3 \
    CMD ["python", "-c", "import urllib.request; response = urllib.request.urlopen('http://127.0.0.1:8765/', timeout=3); response.close(); raise SystemExit(response.status != 200)"]
STOPSIGNAL SIGINT
ENTRYPOINT ["python", "-m", "price_alerts"]
CMD ["ui", "--host", "0.0.0.0"]

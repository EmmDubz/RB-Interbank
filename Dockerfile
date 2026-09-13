FROM python:3.12-slim

WORKDIR /app

COPY pyproject.toml README.md ./
COPY src ./src
COPY website ./website

RUN pip install --no-cache-dir "aiohttp>=3.9"

ENV PYTHONPATH=/app/src
ENV RB_BIND=0.0.0.0
ENV RB_PORT=8787

EXPOSE 8787

CMD ["python", "-u", "-m", "rb_interbank.service"]

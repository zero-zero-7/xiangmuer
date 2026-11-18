FROM python:3.11-slim

ENV PYTHONUNBUFFERED=1 \
    TZ=Asia/Shanghai \
    DATABASE_URL=sqlite:///./local.db \
    SQLITE_PATH=/app/data/local.db

WORKDIR /app

COPY server/requirements.txt /app/server/requirements.txt
RUN pip install --no-cache-dir -r /app/server/requirements.txt

COPY server /app/server
COPY ["四序颐养.html", "/app/四序颐养.html"]

RUN mkdir -p /app/data
WORKDIR /app/server

EXPOSE 80
CMD ["sh", "-c", "python -m uvicorn app:app --host 0.0.0.0 --port ${PORT:-80}"]

FROM python:3.12-slim

WORKDIR /app

# Системные зависимости для asyncpg (компиляция C-расширений)
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

# Порт задаётся платформой через переменную окружения PORT (Render/Railway)
ENV PORT=8000
EXPOSE 8000

# Миграции применяются отдельным шагом при деплое (см. README), не в CMD,
# чтобы избежать гонки при нескольких инстансах и дать контроль над откатами.
CMD ["sh", "-c", "uvicorn app.main:app --host 0.0.0.0 --port ${PORT}"]

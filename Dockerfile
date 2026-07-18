FROM python:3.12-slim

WORKDIR /app

# Системные зависимости для asyncpg (компиляция C-расширений)
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .
RUN chmod +x start.sh

# Порт задаётся платформой через переменную окружения PORT (Render/Railway)
ENV PORT=8000
EXPOSE 8000

# Миграции применяются автоматически при старте через start.sh — это
# осознанный выбор для single-instance деплоя (бесплатный тариф Render без
# Shell-доступа). См. комментарий в start.sh про риски при масштабировании
# на несколько инстансов.
CMD ["./start.sh"]

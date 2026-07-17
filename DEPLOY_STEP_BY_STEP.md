# Деплой «Твой Голос» с нуля — пошаговый гайд

Рассчитан на то, что ничего ещё не создано. Если аккаунт уже есть — просто пропусти соответствующий шаг.

Время: ~30-40 минут на первый деплой.

---

## Шаг 0. Что понадобится

- Аккаунт GitHub (github.com) — бесплатно
- Аккаунт Render (render.com) — бесплатно, вход можно через GitHub
- Аккаунт Vercel (vercel.com) — бесплатно, вход можно через GitHub
- Ключ Anthropic API (console.anthropic.com) — если хочешь LLM-генерацию, а не только fallback-шаблоны. Без ключа тоже работает — на статических шаблонах и rule-based классификаторе.

---

## Шаг 1. GitHub — создать два репозитория

1. Зайти на github.com → New repository
2. Создать `tvoy-golos-frontend` (Public или Private — не важно)
3. Создать `tvoy-golos-backend`

### Залить код (на своей машине, не здесь)

```bash
# Распаковать архивы, которые я прислал
tar -xzf tvoy-golos-deploy-ready-frontend.tar.gz
tar -xzf tvoy-golos-deploy-ready-backend.tar.gz

# Frontend
cd tvoy-golos
git init
git add .
git commit -m "Initial commit: Модули 1-3"
git remote add origin https://github.com/ТВОЙ_ЛОГИН/tvoy-golos-frontend.git
git branch -M main
git push -u origin main

# Backend (в соседней папке)
cd ../tvoy-golos-backend
git init
git add .
git commit -m "Initial commit: Модули 1-3 backend"
git remote add origin https://github.com/ТВОЙ_ЛОГИН/tvoy-golos-backend.git
git branch -M main
git push -u origin main
```

Если Git не установлен или незнаком — на github.com есть кнопка "uploading an existing file", можно перетащить файлы через браузер.

---

## Шаг 2. Render — backend + база данных

1. Зайти на render.com → Sign up (можно через GitHub)
2. New → Blueprint
3. Подключить репозиторий `tvoy-golos-backend`
4. Render найдёт `render.yaml` и предложит создать:
   - Web Service `tvoy-golos-api`
   - PostgreSQL `tvoy-golos-db`
5. Нажать Apply

### После создания — задать секретные переменные вручную

Render Dashboard → tvoy-golos-api → Environment:
- `ANTHROPIC_API_KEY` = твой ключ (или оставить пустым — сработает fallback)
- Если ключа нет — дополнительно поставить `LLM_PROVIDER=none`, чтобы не тратить время на бесполезные попытки подключения

`FRONTEND_ORIGIN` пока оставить как есть — обновим после шага 3.

### Применить миграции

Render Dashboard → tvoy-golos-api → Shell (вкладка сверху):

```bash
alembic upgrade head
```

Подождать пока появится "Deploy live" — обычно 2-5 минут на первый деплой (сборка Docker-образа).

### Проверить

Скопировать URL сервиса (что-то вроде `https://tvoy-golos-api.onrender.com`) и открыть:
```
https://tvoy-golos-api.onrender.com/api/health
```
Должно вернуть `{"status":"ok","db":true,...}`.

Если не отвечает сразу — на бесплатном тарифе Render сервис "засыпает" после 15 минут простоя и просыпается ~30-50 секунд на первый запрос. Это нормально, не баг.

---

## Шаг 3. Vercel — frontend

1. Зайти на vercel.com → Sign up (через GitHub)
2. Add New → Project
3. Импортировать `tvoy-golos-frontend`
4. Framework Preset: Vite (Vercel определит автоматически)
5. Environment Variables (важно, до деплоя):
   - `VITE_API_URL` = `https://tvoy-golos-api.onrender.com/api` (URL из шага 2, с `/api` на конце)
6. Deploy

Через 1-2 минуты появится ссылка вида `https://tvoy-golos-frontend.vercel.app`.

---

## Шаг 4. Связать backend с реальным frontend-доменом

Вернуться в Render Dashboard → tvoy-golos-api → Environment:
- `FRONTEND_ORIGIN` = `https://tvoy-golos-frontend.vercel.app` (без слэша на конце)

Сохранить — Render автоматически передеплоит сервис с новой переменной (около минуты).

**Это критический шаг** — без него браузер заблокирует все запросы с прод-фронтенда как CORS-ошибку, хотя локально всё работало на `localhost`.

---

## Шаг 5. Финальная проверка

1. Открыть `https://tvoy-golos-frontend.vercel.app`
2. Открыть DevTools (F12) → вкладка Network
3. Пройти цикл: регион → категория → льготы
4. В Network не должно быть красных запросов с ошибкой CORS

Если видишь ошибку `has been blocked by CORS policy` — значит `FRONTEND_ORIGIN` в Render не совпадает точно с доменом Vercel (проверить протокол https, отсутствие слэша на конце).

---

## Частые проблемы (реальные, а не гипотетические)

**«Application failed to respond» на Render сразу после деплоя**
Обычно значит что миграции не применены (`alembic upgrade head` не выполнен) и приложение падает при первом обращении к БД. Проверить в Render Dashboard → Logs.

**Fetch failed / Network Error во frontend**
Проверить что `VITE_API_URL` задан ДО билда, а не после — Vite встраивает переменные окружения на этапе сборки, не в рантайме. Если добавил переменную после первого деплоя — нужен redeploy (Vercel → Deployments → Redeploy).

**Render бесплатный тариф "спит"**
Подтверждено официальной документацией Render (на момент проверки): бесплатный web service засыпает после 15 минут без запросов, первый запрос после сна занимает 30-60 секунд. Это ограничение платформы, не баг проекта. Для продакшена — платный тариф от $7/мес убирает засыпание.

**⚠️ Критично: бесплатная PostgreSQL на Render удаляется через 30 дней**
Это не гипотетическая проблема — подтверждено несколькими независимыми источниками на момент проверки (июль 2026). Free-тариф Postgres на Render автоматически удаляется через 30 дней после создания, вместе со всеми данными.

Для нашего проекта это особенно важно: `responses_library` — то есть накопленные обезличенные ответы чиновников — это главная долгосрочная ценность системы согласно ТЗ. Если база на free-тарифе исчезнет через месяц, весь накопленный корпус пропадёт без предупреждения.

**Что делать:**
- Для реального запуска (не просто демо на пару недель) — сразу брать платный Postgres-тариф на Render (обычно от нескольких $/мес за самый простой инстанс)
- Либо настроить регулярный `pg_dump` бэкап на внешнее хранилище пока на free-тарифе
- Либо изначально выбрать другого провайдера для базы (Supabase, Neon — у них тоже есть free-тарифы, но с другими условиями истечения — стоит проверить актуальные условия на момент реального деплоя, так как политики платформ меняются)

**LLM не генерирует, всегда fallback-шаблоны**
Проверить что `ANTHROPIC_API_KEY` реально задан в Render Environment и `LLM_PROVIDER=anthropic`. Без ключа система работает штатно на статических шаблонах — это осознанный fallback, не поломка.

---

## Что делать, если что-то не работает

Пришли мне:
1. Точный текст ошибки из консоли браузера (F12 → Console) или Render Logs
2. Какой именно шаг гайда выполнялся

Я не могу зайти в твои аккаунты, но могу разобрать любую конкретную ошибку по тексту.

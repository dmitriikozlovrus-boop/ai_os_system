# Conductor / Дирижер MVP

Минимальный сервис для Telegram-бота "Люба": принимает текст или голос, классифицирует поток на задачи и вопросы на изучение, записывает результат в Notion, а Todoist держит как следующий подключаемый слой.

## Что уже поддержано

- Telegram webhook: `POST /telegram/webhook`
- Проверка здоровья: `GET /healthz`
- Текстовые сообщения
- Голосовые/аудио сообщения через Telegram file API + OpenAI transcription
- AI-классификация на задачи и вопросы на изучение
- Уточнения в Telegram, если не хватает проекта, срока или уверенность ниже порога
- Создание задач в Notion `Tasks`
- Создание записей в Notion `Study / На изучение`
- Локальное хранение ожидающих уточнений в `data/pending.json`
- Todoist-клиент и синк задач, выключенный по умолчанию

## Быстрый старт

1. Создай `.env` из примера:

```bash
cp .env.example .env
```

2. Заполни токены:

- `TELEGRAM_BOT_TOKEN`
- `OPENAI_API_KEY`
- `NOTION_TOKEN`

3. Запусти локально:

```bash
python3 -m conductor.app
```

4. Для локального теста без Telegram:

```bash
python3 -m conductor.cli "Завтра напомни написать Марко по алюминию. И изучить доступные логистические пути в Веракрус"
```

## Notion базы

Текущие ID уже проставлены в `.env.example`:

- `Tasks`: `be9d26fe652b474696cd5de0118b1210`
- `Study / На изучение`: `4e27e10ca2bf44a08b4c8f86c7a125bd`
- `Projects / Приоритеты`: `bbb501a6933941b4837afff250479f0e`

## Важная логика MVP

- Если срок не указан, Дирижер спрашивает срок.
- Если проект не найден или уверенность ниже `CONFIDENCE_THRESHOLD`, Дирижер спрашивает уточнение.
- Если в сообщении есть и задачи, и вопросы на изучение, создаются обе сущности.
- Исходный RAW отдельно не сохраняется.
- Todoist включается переменной `TODOIST_ENABLED=true`.

## Telegram webhook

Для публичного запуска нужен HTTPS URL. После деплоя выстави webhook:

```bash
curl "https://api.telegram.org/bot$TELEGRAM_BOT_TOKEN/setWebhook?url=https://YOUR_DOMAIN/telegram/webhook"
```

Или через скрипт:

```bash
TELEGRAM_BOT_TOKEN=... PUBLIC_BASE_URL=https://YOUR_DOMAIN sh deploy/set_webhook.sh
```

## Онлайн-запуск

Проект подготовлен для Render через `Dockerfile` и `render.yaml`.

Нужные переменные окружения на хостинге:

- `TELEGRAM_BOT_TOKEN`
- `TELEGRAM_WEBHOOK_SECRET` — любая длинная случайная строка, опционально, но желательно
- `OPENAI_API_KEY`
- `NOTION_TOKEN`
- `NOTION_TASKS_DATABASE_ID`
- `NOTION_STUDY_DATABASE_ID`
- `NOTION_PROJECTS_DATABASE_ID`
- `TODOIST_ENABLED=false` на первом этапе
- `TODOIST_API_TOKEN` позже

После деплоя надо вызвать Telegram `setWebhook` на публичный URL сервиса.

## Следующие доработки

- Кнопки "Изменить" и пошаговое редактирование параметров.
- Двусторонняя синхронизация Todoist -> Notion.
- OCR для фото и документов.
- Поддержка испанского и английского.

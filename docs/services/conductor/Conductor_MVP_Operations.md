# Conductor MVP Operations

## Назначение документа

Этот документ содержит операционное описание текущего `Conductor / Дирижёр MVP`.

Документ фиксирует практическую информацию по запуску, webhook, переменным окружения, Notion, Todoist, OpenAI transcription, командам и эксплуатации MVP.

Сервисное описание роли и границ `Conductor` хранится отдельно:

```text
docs/services/conductor/Conductor_Service_Description.md
```

Краткое описание папки сервиса хранится отдельно:

```text
docs/services/conductor/README.md
```

## Текущий статус MVP

`Conductor / Дирижёр MVP` — сервис для Telegram-бота `Lyuba` и двусторонней синхронизации задач `Notion ↔ Todoist`.

Текущая рабочая логика:

- `Todoist` используется как основной рабочий интерфейс задач;
- `Notion` используется как общая база задач для `Lyuba` и будущих агентов;
- `Conductor` принимает входящие сообщения, классифицирует их, создает записи и синхронизирует задачи.

На текущем этапе код сервиса находится в корневой папке:

```text
conductor/
```

Целевой перенос в `apps/conductor/` не выполняется без отдельной миграционной задачи.

## Что поддержано

Текущий MVP поддерживает:

- Telegram webhook: `POST /telegram/webhook`;
- проверку здоровья: `GET /healthz`;
- текстовые сообщения;
- голосовые и аудиосообщения через Telegram file API и OpenAI transcription;
- AI-классификацию на задачи и вопросы на изучение;
- AI-классификацию на товары;
- уточнения в Telegram, если не хватает проекта, срока или уверенность ниже порога;
- создание задач в Notion `Tasks`;
- создание записей в Notion `Study / На изучение`;
- создание записей в Notion `GOODS`;
- локальное хранение ожидающих уточнений в `data/pending.json`;
- формирование черновика технического задания из `IMPROVEMENTS` при отдельном feature flag;
- нормализацию пользовательского feedback в backlog при отдельном feature flag;
- AI-assisted triage накопленного backlog при отдельном feature flag;
- полную двустороннюю синхронизацию базы `TASKS` и Todoist.

## Быстрый старт

### 1. Создать `.env`

```bash
cp .env.example .env
```

### 2. Заполнить обязательные токены

Минимальный набор:

```text
TELEGRAM_BOT_TOKEN
OPENAI_API_KEY
NOTION_TOKEN
```

Для синхронизации с Todoist также нужны:

```text
TODOIST_API_TOKEN
TODOIST_WEBHOOK_SECRET
TASK_SYNC_SECRET
```

### 3. Запустить локально

```bash
python3 -m conductor.app
```

### 4. Локальный тест без Telegram

```bash
python3 -m conductor.cli "Завтра напомни написать Марко по алюминию. И изучить доступные логистические пути в Веракрус"
```

## Notion базы

Текущие ID баз указаны в `.env.example`.

Текущие базы:

| База | ID |
|---|---|
| `Tasks` | `be9d26fe652b474696cd5de0118b1210` |
| `Study / На изучение` | `4e27e10ca2bf44a08b4c8f86c7a125bd` |
| `GOODS` | `e327cd54181f44ba883bb5a012dfd3d7` |
| `SYSTEM ISSUES` | `268ecbc58ba44b1787de101e49af1c73` |
| `IMPROVEMENTS` | `59332d8093464758baa4a86e077cbe59` |
| `Projects / Приоритеты` | `bbb501a6933941b4837afff250479f0e` |

## Важная логика MVP

Текущие правила MVP:

- если срок не указан, `Conductor` спрашивает срок;
- если проект не найден или уверенность ниже `CONFIDENCE_THRESHOLD`, `Conductor` спрашивает уточнение;
- если в сообщении есть и задачи, и вопросы на изучение, создаются обе сущности;
- если в сообщении есть задачи, вопросы на изучение и товары, создаются соответствующие сущности;
- исходный `RAW` отдельно не сохраняется;
- Todoist включается при наличии `TODOIST_API_TOKEN`;
- аварийная пауза Todoist sync управляется только переменной `TODOIST_SYNC_PAUSED`.
- генерация технического задания из Improvement выключена по умолчанию и управляется `TECHNICAL_SPEC_GENERATION_ENABLED`.
- накопительный backlog feedback выключен по умолчанию и управляется `FEEDBACK_BACKLOG_ENABLED`.
- AI triage backlog выключен по умолчанию и управляется `BACKLOG_AI_TRIAGE_ENABLED`.
- production write для feedback/backlog hardening заблокирован dry-run флагом `BACKLOG_PRODUCTION_DRY_RUN=true`.

## Improvement → Codex Task

Сценарий подготовки технического задания описан отдельно:

```text
docs/product/use_cases/UC_004_Improvement_To_Codex_Task.md
```

Операционные правила:

- `TECHNICAL_SPEC_GENERATION_ENABLED=false` — значение по умолчанию;
- Conductor не запускает Codex, не создает GitHub issue, branch, commit или PR;
- Improvement context выбирается из текущего Telegram chat, reply на сообщение о созданном Improvement или явной Notion URL;
- связанные ошибки читаются через relation `IMPROVEMENTS.Какие ошибки исправляет`;
- локальный repository context read-only и ограничен 8 файлами, 120 KB и 300 строками на файл;
- preview не сохраняется в Notion;
- полное ТЗ показывается после подтверждения пользователя;
- сохранение в Improvement выполняется только после отдельного подтверждения пользователя;
- при отсутствии OpenAI Improvement не изменяется.

Feature flag:

```bash
TECHNICAL_SPEC_GENERATION_ENABLED=false
```

## Telegram Feedback → Backlog

Сценарий нормализации feedback описан отдельно:

```text
docs/product/use_cases/UC_005_Telegram_Feedback_To_Backlog.md
```

Операционные правила:

- `FEEDBACK_BACKLOG_ENABLED=false` — значение по умолчанию;
- correction flow, System Issues, existing Improvement flow и Technical Spec flow продолжают работать при выключенном флаге;
- Conductor сохраняет исходный feedback и отдельно формирует нейтральное описание;
- конкретная ошибка может создать `SYSTEM ISSUES`;
- общая проблема или идея может попасть в `IMPROVEMENTS` без конкретного interaction;
- сначала ищется существующий открытый Improvement, затем предлагается новый;
- связь с существующим Improvement и создание нового Improvement требуют пользовательского подтверждения, кроме явной команды `Добавь в backlog`;
- summary обновляется только в managed section `CONDUCTOR_FEEDBACK_SUMMARY_START/END`;
- изменение приоритета или статуса Improvement требует отдельного подтверждения;
- runtime не запускает Codex и не создает GitHub branch, commit, push или PR.

Feature flag:

```bash
FEEDBACK_BACKLOG_ENABLED=false
```

## Backlog AI Triage

Сценарий управляемого разбора backlog описан отдельно:

```text
docs/product/use_cases/UC_006_Backlog_AI_Triage.md
```

Операционные правила:

- `BACKLOG_AI_TRIAGE_ENABLED=false` — значение по умолчанию;
- при выключенном флаге feedback backlog работает детерминированно, а AI triage команды возвращают controlled unavailable message;
- AI enrichment запускается только после deterministic normalization и не является источником обязательной логики;
- semantic matching не связывает Improvement автоматически без подтверждения пользователя;
- merge не удаляет вторичный Improvement, а переводит его в `Отложено`;
- split доступен только как preview;
- переход в Technical Spec flow возможен только по явному выбору пользователя и при достаточной readiness.
- перед handoff создается snapshot выбранного Improvement и проверяется stale-состояние.
- diagnostics не создает и не изменяет Notion records.

Feature flag:

```bash
BACKLOG_AI_TRIAGE_ENABLED=false
BACKLOG_PRODUCTION_DRY_RUN=true
```

Сценарий перехода из backlog в технический анализ:

```text
docs/product/use_cases/UC_007_Backlog_To_Technical_Analysis.md
```

## TASKS ↔ Todoist

### Общая модель

Текущая модель маршрутизации:

- `STREAMS` соответствует родительскому проекту Todoist;
- `PROJECTS` соответствует дочернему проекту Todoist;
- расположение задачи в Todoist определяет `TASKS.Проект`;
- `TASKS.Stream` определяется через связь `Project → Stream`;
- раздел Todoist записывается прямо в `TASKS.Раздел` и `TASKS.Todoist Section ID`;
- разделы создаются и редактируются в Todoist;
- отдельной базы Sections нет;
- проектные метки больше не используются для маршрутизации.

### Обязательные поля Notion `TASKS`

Обязательные поля базы Notion:

```text
Task
Описание
Статус
Deadline
Срок выполнения
Strategic Impact
Source
Проект
Stream
Раздел
Todoist Section ID
Метки Todoist
Todoist ID
Sync status
Sync error
Sync Notion hash
Sync Todoist hash
```

### Сопоставление полей

| Notion `TASKS` | Todoist / назначение |
|---|---|
| `Task` | название задачи |
| `Описание` | описание задачи |
| `Статус: Done` | задача завершена |
| `Статус: Cancelled` | задача завершена с сохранением истории |
| `Срок выполнения` | due date |
| `Deadline` | deadline |
| `Strategic Impact` | priority |
| `Проект` | проект, в котором находится задача |
| `Stream` | группа проекта; определяется через `Project → Stream` |
| `Раздел` | название раздела внутри проекта |
| `Todoist Section ID` | стабильная связь с разделом |
| `Метки Todoist` | только разрешенные операционные метки |
| `Todoist ID` | стабильная связь записей |
| `Sync status` | техническое состояние синхронизации |
| `Sync error` | последняя причина ошибки; очищается после успешной сверки |
| `Sync Notion hash` | технический отпечаток последней синхронизированной версии Notion |
| `Sync Todoist hash` | технический отпечаток последней синхронизированной версии Todoist |

### Разрешенные управляемые метки

Разрешенные управляемые метки:

```text
встреча
звонок
письмо
сообщение
документ
анализ
исследование
планирование
низкая_энергия
средняя_энергия
высокая_энергия
пятиминутное_дело
```

Служебная метка:

```text
проверить_завершение
```

Назначение служебной метки: показать задачи, которые `Lyuba`, агент или пользователь завершили в Notion и которые нужно подтвердить закрытием в Todoist.

Все остальные метки сохраняются без изменений.

## Режимы Todoist sync

### `todoist-primary`

Рабочий режим `todoist-primary` использует Todoist как первоначальный источник.

Правила:

- первая сверка новой версии переносит текущие версии связанных задач Todoist в Notion;
- webhook переносит изменения Todoist почти сразу, включая задачи во входящих;
- периодическая сверка каждые 5 минут восстанавливает пропущенные события;
- новые активные задачи из Notion создаются в Todoist: в назначенном проекте или во входящих;
- последующие конфликты решаются по времени изменения;
- удаление Todoist переводит запись Notion в `Cancelled`;
- `Done` или `Cancelled` из Notion не закрывает Todoist без второго ключа;
- при `Done` или `Cancelled` из Notion задача остается активной с меткой `проверить_завершение`.

### `observe`

Режим `observe` остается доступен для инвентаризации без удаленных записей.

## Переменные окружения для Todoist sync

Базовые переменные:

```bash
TODOIST_SYNC_PAUSED=false
TODOIST_SYNC_MODE=observe
TODOIST_API_TOKEN=...
TODOIST_WEBHOOK_SECRET=...
TASK_SYNC_SECRET=...
```

Защитные разрешения для поэтапного canary-запуска:

```bash
TODOIST_ALLOW_PROJECT_CREATE=false
TODOIST_ALLOW_TASK_CREATE=false
TODOIST_ALLOW_TASK_MOVE=false
TODOIST_ALLOW_LABEL_WRITE=false
TODOIST_ALLOW_STATUS_WRITE=false
TODOIST_ALLOW_MISSING_CANCEL=false
TODOIST_MAX_TASK_MOVES=10
```

Аварийная пауза без удаления токенов:

```bash
TODOIST_SYNC_PAUSED=true
```

## Ручной reconciliation

Ручной запуск сверки:

```bash
curl -X POST \
  -H "X-Conductor-Sync-Secret: $TASK_SYNC_SECRET" \
  https://YOUR_DOMAIN/tasks/sync
```

## Todoist webhook

Для мгновенного обновления `Todoist → Notion` нужно зарегистрировать webhook приложения Todoist:

```text
https://YOUR_DOMAIN/todoist/webhook
```

В `TODOIST_WEBHOOK_SECRET` указывается `Client Secret` приложения Todoist.

Если webhook не настроен, периодический reconciliation продолжает синхронизировать активные задачи и завершения.

Удаления определяются периодической сверкой после успешной загрузки истории завершенных задач.

С webhook изменения попадают в Notion почти сразу.

## Telegram webhook

Для публичного запуска нужен HTTPS URL.

После деплоя выставить webhook:

```bash
curl "https://api.telegram.org/bot$TELEGRAM_BOT_TOKEN/setWebhook?url=https://YOUR_DOMAIN/telegram/webhook"
```

Или через скрипт:

```bash
TELEGRAM_BOT_TOKEN=... PUBLIC_BASE_URL=https://YOUR_DOMAIN sh deploy/set_webhook.sh
```

## Онлайн-запуск

Проект подготовлен для Render через:

```text
Dockerfile
render.yaml
```

Нужные переменные окружения на хостинге:

```text
TELEGRAM_BOT_TOKEN
TELEGRAM_WEBHOOK_SECRET
OPENAI_API_KEY
NOTION_TOKEN
NOTION_TASKS_DATABASE_ID
NOTION_STUDY_DATABASE_ID
NOTION_GOODS_DATABASE_ID
NOTION_SYSTEM_ISSUES_DATABASE_ID
NOTION_IMPROVEMENTS_DATABASE_ID
NOTION_PROJECTS_DATABASE_ID
SYSTEM_IMPROVEMENTS_ENABLED
TECHNICAL_SPEC_GENERATION_ENABLED
FEEDBACK_BACKLOG_ENABLED
BACKLOG_AI_TRIAGE_ENABLED
BACKLOG_PRODUCTION_DRY_RUN
TODOIST_API_TOKEN
TODOIST_WEBHOOK_SECRET
TASK_SYNC_SECRET
```

`TELEGRAM_WEBHOOK_SECRET` — любая длинная случайная строка. Переменная опциональна, но желательна.

После деплоя нужно вызвать Telegram `setWebhook` на публичный URL сервиса.

## OpenAI transcription

MVP поддерживает голосовые и аудиосообщения через связку:

```text
Telegram file API
OpenAI transcription
```

Для работы нужен:

```text
OPENAI_API_KEY
```

Транскрибированный текст дальше передается в общую логику классификации входящего сообщения.

## Команды и endpoints

| Назначение | Команда / endpoint |
|---|---|
| Локальный запуск | `python3 -m conductor.app` |
| CLI-тест без Telegram | `python3 -m conductor.cli "текст сообщения"` |
| Telegram webhook | `POST /telegram/webhook` |
| Health check | `GET /healthz` |
| Ручной sync | `POST /tasks/sync` |
| Todoist webhook | `POST /todoist/webhook` |

## Эксплуатационные правила

### Перед запуском

Проверить:

- заполнен `.env`;
- есть `TELEGRAM_BOT_TOKEN`;
- есть `OPENAI_API_KEY`;
- есть `NOTION_TOKEN`;
- указаны ID Notion-баз;
- при включении Todoist sync есть `TODOIST_API_TOKEN`;
- при включении ручного sync есть `TASK_SYNC_SECRET`;
- при webhook Todoist есть `TODOIST_WEBHOOK_SECRET`.

### При проблемах с Telegram

Проверить:

- публичный HTTPS URL;
- корректность Telegram webhook;
- переменную `TELEGRAM_BOT_TOKEN`;
- endpoint `POST /telegram/webhook`;
- доступность `GET /healthz`.

### При проблемах с Notion

Проверить:

- `NOTION_TOKEN`;
- ID баз Notion;
- доступ интеграции Notion к базам;
- обязательные поля базы `TASKS`;
- корректность названий полей;
- ошибки в логах Conductor.

### При проблемах с Todoist sync

Проверить:

- `TODOIST_API_TOKEN`;
- `TODOIST_SYNC_PAUSED`;
- `TODOIST_SYNC_MODE`;
- `TASK_SYNC_SECRET`;
- `TODOIST_WEBHOOK_SECRET`;
- защитные переменные canary-запуска;
- последние значения `Sync status`;
- поле `Sync error`;
- значения `Sync Notion hash` и `Sync Todoist hash`.

### При проблемах с OpenAI transcription

Проверить:

- `OPENAI_API_KEY`;
- доступность Telegram file API;
- тип входящего сообщения;
- ошибки загрузки аудиофайла;
- ошибки транскрибации.

## Обратная связь и исправление ошибок

Conductor поддерживает пользовательскую обратную связь через Telegram до обработки Pending и до новой классификации.

Поддерживаемые явные сигналы:

- `Неправильно`;
- `Неверно`;
- `Ошибка`;
- `Не так`;
- `/wrong`;
- `/error`.

Также поддерживаются естественные исправления при наличии контекста или Telegram Reply:

- `Нет, это задача`;
- `Это не товар, это исследование`;
- `Дата неверная, встреча завтра`;
- `Поставь время 15:00`;
- `Это для проекта Мексика`;
- `Правильно будет: купить покрышку 26x2 для велосипеда`;
- `Ничего создавать не нужно, это просто комментарий`.

Порядок маршрутизации:

1. активный feedback state;
2. Telegram Reply на сообщение результата бота;
3. явная feedback-команда или конструкция исправления;
4. Pending;
5. обычная классификация нового сообщения.

Выбор исправляемого взаимодействия:

1. Reply на сообщение результата бота;
2. последнее завершенное interaction в том же чате;
3. если контекст не найден, бот просит прислать описание ошибки и правильный вариант одним сообщением.

В `SYSTEM ISSUES` сохраняются:

- исходный ввод;
- фактический результат классификации, созданных записей, Pending и ошибок;
- обратная связь пользователя;
- ожидаемый правильный результат;
- предполагаемая причина;
- решение для ручного исправления.

После регистрации ошибки бот предлагает исправить запись сейчас. Автоматическое исправление выполняется только при явном подтверждении пользователя и только если можно безопасно заново создать правильную запись через существующий Conductor flow. Исходные записи не удаляются автоматически.

Если OpenAI недоступен, используется fallback-классификация ошибки. Если `SYSTEM ISSUES` недоступна, пользователь получает явный отказ; ошибка регистрации не запускает рекурсивную регистрацию новой ошибки.

## Выявление повторяющихся ошибок и Improvements

После успешного сохранения пользовательского System Issue Conductor может искать похожие ошибки и предложить системное улучшение.

Источник конкретных ошибок — Notion `SYSTEM ISSUES`.
Источник предложений — Notion `IMPROVEMENTS`.
Устойчивые правила и код остаются в GitHub и не меняются автоматически.

Для поиска повторяемости Conductor:

1. запрашивает не более 30 System Issues за последние 90 дней;
2. фильтрует кандидатов по `Тип ошибки` и `База данных`;
3. сравнивает новую ошибку с кандидатами через отдельный OpenAI Structured Output;
4. при недоступности OpenAI использует детерминированную группировку по типу, базе и направлению исправления.

Improvement предлагается, если:

- найдены минимум две предыдущие похожие ошибки;
- найдена одна похожая ошибка и новая ошибка имеет высокую критичность;
- пользователь явно просит системное исправление или новое правило.

Improvement создается только после подтверждения пользователя. При создании используется статус `Идея`, а поле `Какие ошибки исправляет` связывает Improvement с выбранными System Issues.

Перед созданием Conductor проверяет открытые Improvements. Если похожая открытая запись уже есть, бот предлагает связать с ней новую ошибку вместо создания дубликата.

Нужная переменная окружения:

```text
NOTION_IMPROVEMENTS_DATABASE_ID
SYSTEM_IMPROVEMENTS_ENABLED=false
```

`SYSTEM_IMPROVEMENTS_ENABLED=false` — безопасный режим по умолчанию. В нем System Issues и correction flow продолжают работать, но recurrence analysis и создание Improvements не запускаются и пользователь не получает предложение, которое нельзя выполнить.

`SYSTEM_IMPROVEMENTS_ENABLED=true` включает поиск повторяемости, предложение Improvement и создание записи после подтверждения пользователя. Если `NOTION_IMPROVEMENTS_DATABASE_ID` не задан, flow завершается контролируемо и пишет технический лог без блокировки сохранения System Issue.

`FEEDBACK_BACKLOG_ENABLED=false` — безопасный режим по умолчанию. В нем normalization, накопительная summary и browsing backlog через Telegram не запускаются.

`FEEDBACK_BACKLOG_ENABLED=true` включает fallback-нормализацию feedback, поиск существующего Improvement, предложение backlog item, managed summary и Telegram-команды просмотра backlog.

`BACKLOG_AI_TRIAGE_ENABLED=false` — безопасный режим по умолчанию. В нем AI enrichment, semantic matching, triage, duplicate merge proposals и implementation candidates не запускаются.

`BACKLOG_AI_TRIAGE_ENABLED=true` включает optional AI enrichment после deterministic normalization, semantic matching открытых Improvements, readiness-разбор backlog, clarification questions, merge preview/confirmation и безопасный handoff в existing Technical Spec flow.

`BACKLOG_PRODUCTION_DRY_RUN=true` — безопасный режим по умолчанию. В нем разрешены чтение, diagnostics, OpenAI preview и readiness, но заблокированы Notion writes для System Issues, Improvements, relations, priority/status, feedback summary и Technical Spec.

Безопасные smoke-команды:

```bash
python3 -m conductor.feedback_backlog_smoke --validate-only
python3 -m conductor.feedback_backlog_smoke --dry-run
```

## Feedback Backlog MVP Release Runbook

Release document:

```text
docs/releases/Feedback_Backlog_MVP_Release.md
```

Before enabling production writes:

1. Run `python3 -m conductor.feedback_backlog_smoke --validate-only`.
2. Confirm Notion `SYSTEM ISSUES` and `IMPROVEMENTS` schemas.
3. Confirm OpenAI structured output contracts on `[SMOKE TEST]` data.
4. Run `python3 -m conductor.feedback_backlog_smoke --dry-run` and verify `writes completed: 0`.
5. Enable `BACKLOG_PRODUCTION_DRY_RUN=false` and `SMOKE_TEST_WRITES_ENABLED=true` only for controlled write smoke.
6. Disable `SMOKE_TEST_WRITES_ENABLED` immediately after write smoke.
7. Run Telegram pilot in a test chat before broad production use.

Rollback does not delete data. Set `BACKLOG_PRODUCTION_DRY_RUN=true` or disable `FEEDBACK_BACKLOG_ENABLED`, `BACKLOG_AI_TRIAGE_ENABLED` and `TECHNICAL_SPEC_GENERATION_ENABLED`.

Ограничения MVP:

- нет автоматического удаления или архивирования ошибочных исходных записей;
- нет самообучения правил;
- одинаковые backlog signals дедуплицируются по тексту в течение 7 дней;
- технические ошибки дедуплицируются по fingerprint в течение 7 дней;
- feedback state живет 24 часа.

## Что не должно храниться в этом документе

Этот документ не должен содержать:

- архитектурную карту всей AI OS;
- roadmap;
- планы будущих агентов;
- детальное описание Data Ownership;
- подробные use cases;
- новые архитектурные решения;
- секретные токены и реальные значения ключей.

Для этих целей используются отдельные документы.

## Связанные документы

| Документ | Назначение |
|---|---|
| `docs/services/conductor/README.md` | краткое описание папки сервиса |
| `docs/services/conductor/Conductor_Service_Description.md` | роль, ответственность и границы Conductor |
| `docs/services/conductor/Conductor_MVP_Operations.md` | текущий операционный документ |
| `docs/architecture/System_Map.md` | верхнеуровневая карта AI OS |
| `docs/architecture/System_Component_Registry.md` | компоненты по слоям |
| `docs/data/Data_Ownership_Map.md` | источники истины |
| `docs/product/use_cases/` | пользовательские сценарии |
| `.env.example` | пример переменных окружения |
| `README.md` | корневое описание репозитория |

## Следующие доработки, зафиксированные в текущем README

В текущем README указаны следующие будущие доработки:

- кнопки `Изменить` и пошаговое редактирование параметров;
- OCR для фото и документов;
- поддержка испанского и английского.

Эти пункты не являются задачами в рамках данного операционного документа.

Если они переводятся в работу, их нужно оформить отдельно в `docs/roadmap/` или в конкретных `docs/product/use_cases/`.

## Текущий статус

Статус документа: базовая версия.

Документ создан как перенос операционной информации Conductor MVP из корневого README в сервисную документацию.

При изменении запуска, webhook, переменных окружения, Notion, Todoist, OpenAI transcription или команд этот документ должен обновляться.

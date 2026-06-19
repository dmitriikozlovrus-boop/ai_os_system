# System Component Registry

## Назначение

Этот документ содержит перечень конкретных компонентов, сервисов и инструментов AI OS по архитектурным слоям.

Документ не описывает общую архитектуру. Общая архитектура описана в `docs/architecture/System_Map.md`.

Документ не является roadmap и не фиксирует порядок реализации.

## Главное правило

Один компонент может относиться к нескольким слоям.

Пример:

```text
Gmail = Source + Input Interface + Execution Layer + Output Interface
Todoist = Source + Execution Layer + Output Interface
Notion = Input Interface + Data Layer + Execution Layer + Output Interface
Lyuba = Input Interface + Output Interface
OpenAI = Intelligence Layer
```

В таких случаях компонент указывается во всех релевантных слоях, но с разной ролью.

## Статусы

```text
Active — уже используется
Candidate — предполагается к использованию
Future — возможно позже
Deprecated — больше не использовать
```

## 1. User / External Sources

| Компонент | Статус | Роль | Комментарий |
|---|---|---|---|
| User | Active | основной источник команд и информации | ручной ввод |
| Telegram | Active | источник сообщений | через Lyuba |
| Gmail | Candidate | источник входящих писем | digest, follow-up, задачи |
| Google Calendar | Candidate | источник событий | event processing |
| Todoist | Candidate | источник задач | ручные задачи пользователя |
| Notion | Active | источник ручных обновлений | также Data Layer |
| Google Drive | Candidate | источник документов | research outputs, файлы |
| External websites | Candidate | источник данных | research и digest |
| API triggers | Future | автоматические сигналы | позже |

## 2. Input Interface Layer

| Интерфейс | Статус | Назначение | Комментарий |
|---|---|---|---|
| Lyuba / Telegram bot | Active | быстрый пользовательский ввод | основной conversational interface |
| ChatGPT | Active | ручной аналитический интерфейс | проектирование, тексты, анализ |
| Notion UI | Active | ручной интерфейс управления БД | не должен содержать всю логику |
| Todoist UI | Candidate | интерфейс задач | может быть входом и выходом |
| Gmail UI | Candidate | интерфейс коммуникаций | письма и ответы |
| Google Calendar UI | Candidate | интерфейс времени | события и расписание |
| Web interface | Future | будущая панель управления | не MVP |
| API interface | Future | машинный вход | не MVP |

## 3. Conductor

| Компонент | Статус | Назначение | Комментарий |
|---|---|---|---|
| Conductor | Active / Design | центральная маршрутизация | логический центр AI OS |

## 4. Core Logic

| Блок | Статус | Назначение | Комментарий |
|---|---|---|---|
| Task Logic | Candidate | обработка задач | классификация, поля, статусы |
| Event Logic | Candidate | обработка событий | календарь, время, follow-up |
| Study Logic | Candidate | обработка исследований | вопросы, outputs |
| Problem Logic | Candidate | обработка проблем | проблемные сущности |
| Idea Logic | Candidate | обработка идей | capture и дальнейшая конверсия |
| Digest Logic | Candidate | подготовка дайджестов | research / monitoring |
| Error Logic | Candidate | обработка ошибок | error log и rule improvement |
| Validation Logic | Candidate | проверка записей | качество данных |

## 5. Intelligence Layer

| Компонент | Статус | Назначение | Комментарий |
|---|---|---|---|
| OpenAI / GPT | Active | reasoning, классификация, генерация | основной LLM-движок |
| Research Agent | Candidate | исследования и digest | описывается в Agent Registry |
| Task Agent | Candidate | работа с задачами | роль уточняется |
| Calendar Agent | Candidate | работа с календарем | позже |
| Error Agent | Candidate | анализ ошибок | позже |
| Classifiers | Candidate | классификация входов | могут быть LLM-based |
| Extractors | Candidate | извлечение полей | даты, имена, сущности |

## 6. Integration Layer

| Интеграция | Статус | Назначение | Комментарий |
|---|---|---|---|
| Telegram Bot API | Active | связь с Lyuba | input/output |
| Notion API | Active / Candidate | работа с БД | MVP backend |
| Todoist API | Candidate | задачи | execution + output |
| Google Calendar API | Candidate | события | execution + source |
| Gmail API | Candidate | письма | source + execution |
| Google Drive API | Candidate | документы | storage |
| GitHub API | Candidate | файлы и архитектура | technical truth |
| OpenAI API | Active / Candidate | LLM processing | intelligence |
| Supabase API | Future | будущий backend | не MVP |
| PostgreSQL connection | Future | структурная БД | не MVP |
| Make / n8n / Zapier | Candidate | автоматизация сценариев | при необходимости |

## 7. Data Layer

| Хранилище | Статус | Назначение | Комментарий |
|---|---|---|---|
| Notion | Active | операционные БД | MVP backend |
| GitHub | Active | архитектурная и техническая правда | docs, rules, code |
| Google Drive | Active / Candidate | документы и outputs | исследования, файлы |
| Knowledge | Active | правила и стабильные инструкции | не операционная БД |
| Error Log | Candidate | ошибки системы | важно спроектировать рано |
| Supabase / PostgreSQL | Future | основной backend | позже |
| Vector DB | Future | смысловой поиск | позже |

## 8. Execution Layer

| Инструмент | Статус | Что выполняет | Комментарий |
|---|---|---|---|
| Todoist | Candidate | создание и обновление задач | task execution |
| Google Calendar | Candidate | создание и обновление событий | event execution |
| Gmail | Candidate | drafts, replies, forwarding | communication execution |
| Notion | Active / Candidate | создание и обновление записей | operational DB |
| GitHub | Active / Candidate | создание и изменение файлов | через Codex или API |
| Google Drive | Candidate | сохранение документов | research outputs |
| Telegram | Active | уведомления и ответы | через Lyuba |
| Codex | Active | технические изменения | code/document execution |

## 9. Output Interface Layer

| Интерфейс | Статус | Что показывает | Комментарий |
|---|---|---|---|
| Lyuba / Telegram bot | Active | ответы, подтверждения, уточнения | основной быстрый output |
| ChatGPT | Active | проектирование, тексты, анализ | ручной output |
| Todoist UI | Candidate | задачи | task output |
| Google Calendar UI | Candidate | события | calendar output |
| Notion UI | Active | записи и базы | admin output |
| Gmail UI | Candidate | письма | communication output |
| Google Drive | Candidate | документы | output storage |
| Dashboard | Future | сводная панель | не MVP |

## 10. Control & Improvement Layer

| Компонент | Статус | Назначение | Комментарий |
|---|---|---|---|
| Error Log | Candidate | фиксация ошибок | ключевой элемент |
| Error Types | Candidate | классификация ошибок | справочник |
| Quality Rules | Candidate | правила качества | validation |
| Audit Log | Future | история действий | позже |
| Knowledge Updates | Candidate | улучшение правил | ручное или автоматическое |
| Architecture Decisions | Candidate | фиксация решений | `docs/decisions/` |

## Usage by Codex

Codex should use this file as a reference when a task involves:

- adding or changing integrations;
- changing interfaces;
- connecting external services;
- modifying execution flows;
- deciding where a component belongs in the architecture;
- updating documentation about tools, APIs, sources, systems of record, or action systems.

Codex should not treat this file as a roadmap.

Codex should not add future tools unless explicitly requested.

Codex should not move components between layers without updating the relevant architecture documentation.

## Связанные документы

| Документ | Назначение |
|---|---|
| `docs/architecture/System_Map.md` | верхнеуровневая логическая карта системы |
| `docs/architecture/System_Component_Registry.md` | перечень компонентов по слоям |
| `docs/architecture/Document_Placement_Rules.md` | правила размещения документов |
| `knowledge/agents/Agent_Registry.md` | роли агентов |
| `docs/data/Data_Ownership_Map.md` | источники истины и владение данными |
| `docs/services/` | подробные описания отдельных сервисов |
| `docs/use_cases/` | конкретные маршруты обработки |

## Текущий статус

Статус документа: базовая версия.

Документ является living registry и может обновляться по мере появления новых инструментов, интерфейсов, интеграций и хранилищ.

Изменения в этом документе не должны подменять изменения в `System_Map.md`.

`System_Map.md` фиксирует архитектурную схему.

`System_Component_Registry.md` фиксирует конкретные реализации по слоям.

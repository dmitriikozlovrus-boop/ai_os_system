# Repository Structure Target

Версия: 1.0  
Статус: целевая архитектура  
Целевой путь: `docs/architecture/Repository_Structure_Target.md`

---

## 1. Назначение документа

Документ фиксирует целевую файловую архитектуру репозитория `ai_os_system`.

Это не план миграции и не описание текущего состояния.

Документ отвечает только на один вопрос:

> Как должен быть устроен репозиторий AI OS в целевом состоянии?

---

## 2. Главный принцип

Репозиторий `ai_os_system` должен быть устроен как монорепозиторий персональной AI OS, а не как репозиторий одного сервиса.

Структура должна быть system-first.

Главная логика:

```text
apps/          = через что система работает
core/          = как система думает
integrations/  = с чем система соединяется
agents/        = кто выполняет роли
workflows/     = какие процессы выполняются
prompts/       = как инструктируются модели
knowledge/     = что система знает и по каким правилам живет
docs/          = как система спроектирована
data/          = как устроены данные
tests/         = как проверяется работа
deploy/        = как система запускается
```

---

## 3. Целевая верхнеуровневая структура

```text
ai_os_system/
├── apps/
├── core/
├── integrations/
├── agents/
├── workflows/
├── prompts/
├── knowledge/
├── docs/
├── data/
├── tests/
├── deploy/
│
├── README.md
├── AGENTS.md
├── .env.example
├── .gitignore
├── Dockerfile
└── render.yaml
```

---

## 4. `apps/`

`apps/` содержит запускаемые приложения, интерфейсы и точки входа в систему.

Примеры:

```text
apps/
├── conductor/
├── lyuba_bot/
├── scheduler/
├── admin_panel/
└── api/
```

Правила:

- приложения принимают запросы;
- приложения вызывают `core/`;
- приложения используют `integrations/`;
- приложения возвращают результат пользователю, агенту или внешней системе;
- основная доменная логика не должна жить в `apps/`.

---

## 5. `core/`

`core/` содержит независимое ядро логики AI OS.

Примеры:

```text
core/
├── input_processing/
├── entity_extraction/
├── classification/
├── routing/
├── record_management/
├── data_enrichment/
├── relationship_management/
├── command_execution/
├── quality_control/
├── result_reporting/
└── error_driven_refinement/
```

Правила:

- `core/` не зависит от Telegram, Notion, Todoist, Gmail, Google Calendar или конкретного интерфейса;
- `core/` получает нормализованные входные данные;
- `core/` принимает решения;
- `core/` возвращает структурированный результат;
- физические действия во внешних сервисах выполняются через `integrations/`.

---

## 6. `integrations/`

`integrations/` содержит код подключения к внешним сервисам.

Примеры:

```text
integrations/
├── notion/
├── todoist/
├── telegram/
├── openai/
├── gmail/
├── google_calendar/
├── google_drive/
├── whatsapp/
├── linkedin/
├── facebook/
└── supabase/
```

Правила:

- интеграции являются адаптерами;
- интеграции не принимают доменные решения;
- интеграции не классифицируют сущности;
- интеграции не управляют бизнес-логикой;
- интеграции выполняют физическое чтение, запись, отправку или синхронизацию.

---

## 7. `agents/`

`agents/` содержит конкретные AI-агенты и их рабочие пакеты.

Целевая структура:

```text
agents/
├── shared/
├── work/
├── business/
├── personal_development/
└── family_life/
```

Пример структуры одного агента:

```text
agents/work/business_environment_analyst/
├── README.md
├── Agent_Brief.md
├── Agent_Rules.md
├── Data_Requirements.md
├── Tools.md
├── Workflows.md
├── Prompts.md
└── Backlog.md
```

Правила:

- `agents/` содержит конкретные роли;
- один агент может использовать несколько workflows;
- один агент может использовать несколько tools;
- общие стандарты проектирования агентов лежат в `knowledge/agents/`;
- конкретные рабочие описания агентов лежат в `agents/`.

---

## 8. `workflows/`

`workflows/` содержит процессы, которые могут использоваться разными агентами, приложениями и сервисами.

Примеры:

```text
workflows/
├── inbox_processing/
├── task_lifecycle/
├── research_pipeline/
├── digest_generation/
├── error_handling/
├── agent_feedback_loop/
├── meeting_follow_up/
└── todoist_notion_sync/
```

Правила:

- агент — это роль;
- workflow — это процесс;
- один workflow может использоваться несколькими агентами;
- workflow должен описывать последовательность действий, вход, выход и критерий завершения.

---

## 9. `prompts/`

`prompts/` содержит промпты, системные инструкции и reusable prompt templates.

Примеры:

```text
prompts/
├── shared/
├── conductor/
├── lyuba/
├── classification/
├── extraction/
├── research/
├── writing/
├── digest/
└── agents/
```

Правила:

- повторно используемые промпты должны храниться отдельными файлами;
- промпты не должны быть размазаны по случайным README;
- общие промпты лежат в `prompts/shared/`;
- агентные промпты лежат в `prompts/agents/` или внутри пакета конкретного агента, если используются только им.

---

## 10. `knowledge/`

`knowledge/` содержит устойчивые знания системы.

Целевая структура:

```text
knowledge/
├── vision/
├── architecture/
├── entities/
├── classification/
├── development/
├── agents/
├── tools/
├── principles/
└── memory/
```

Правила:

- `knowledge/` хранит устойчивые принципы, определения, стандарты и правила;
- `knowledge/` не хранит временные roadmap-документы;
- `knowledge/` не хранит код;
- `knowledge/` не хранит реальные пользовательские данные.

---

## 11. `docs/`

`docs/` содержит проектную, техническую и сервисную документацию.

Целевая структура:

```text
docs/
├── architecture/
├── data/
├── services/
├── decisions/
├── roadmap/
├── product/
└── general/
```

Правила:

- `docs/architecture/` — архитектура реализации;
- `docs/data/` — модели данных, схемы БД, Notion, Supabase;
- `docs/services/` — документация сервисов;
- `docs/decisions/` — принятые архитектурные решения;
- `docs/roadmap/` — планы развития и функциональные карты;
- `docs/product/` — продуктовые сценарии и требования;
- `docs/general/` — общая документация.

---

## 12. `data/`

`data/` содержит схемы, контракты, миграции и примеры структур данных.

Примеры:

```text
data/
├── schemas/
├── notion/
├── supabase/
├── seed/
└── examples/
```

Правила:

- реальные личные данные не хранить;
- медицинские данные не хранить;
- переписки не хранить;
- финансы не хранить;
- токены, ключи и секреты не хранить;
- хранить только схемы, шаблоны, контракты и обезличенные примеры.

---

## 13. `tests/`

`tests/` содержит тесты проекта.

Правила:

- при изменении логики должны обновляться тесты;
- тесты должны проверять `core/`, `apps/` и `integrations/`;
- тесты не должны зависеть от реальных секретов и личных данных.

---

## 14. `deploy/`

`deploy/` содержит скрипты и файлы деплоя.

Примеры:

```text
deploy/
├── README.md
└── set_webhook.sh
```

Правила:

- не хранить секреты;
- не хранить токены;
- не хранить пароли;
- переменные окружения описывать через `.env.example`.

---

## 15. Базовые различия между слоями

### `apps/` vs `core/`

```text
apps/ = точки входа и интерфейсы
core/ = доменная логика
```

### `core/` vs `integrations/`

```text
core/ = решение
integrations/ = физическое действие во внешней системе
```

### `agents/` vs `workflows/`

```text
agents/ = кто выполняет роль
workflows/ = какой процесс выполняется
```

### `knowledge/` vs `docs/`

```text
knowledge/ = устойчивые правила и знания системы
docs/ = проектные и реализационные документы
```

---

## 16. README-политика

README должен отвечать на три вопроса:

1. Что лежит в папке.
2. Зачем это нужно.
3. Какие правила действуют внутри папки.

README не должен вручную перечислять все файлы, если список может часто меняться.

---

## 17. Итоговое целевое дерево

```text
ai_os_system/
├── apps/
│   ├── conductor/
│   ├── lyuba_bot/
│   ├── scheduler/
│   └── admin_panel/
│
├── core/
│   ├── input_processing/
│   ├── entity_extraction/
│   ├── classification/
│   ├── routing/
│   ├── record_management/
│   ├── data_enrichment/
│   ├── relationship_management/
│   ├── command_execution/
│   ├── quality_control/
│   ├── result_reporting/
│   └── error_driven_refinement/
│
├── integrations/
│   ├── notion/
│   ├── todoist/
│   ├── telegram/
│   ├── openai/
│   ├── gmail/
│   ├── google_calendar/
│   ├── google_drive/
│   └── supabase/
│
├── agents/
│   ├── shared/
│   ├── work/
│   ├── business/
│   ├── personal_development/
│   └── family_life/
│
├── workflows/
│   ├── inbox_processing/
│   ├── task_lifecycle/
│   ├── research_pipeline/
│   ├── digest_generation/
│   ├── error_handling/
│   └── agent_feedback_loop/
│
├── prompts/
│   ├── shared/
│   ├── conductor/
│   ├── lyuba/
│   ├── classification/
│   ├── extraction/
│   ├── research/
│   └── agents/
│
├── knowledge/
│   ├── vision/
│   ├── architecture/
│   ├── entities/
│   ├── classification/
│   ├── development/
│   ├── agents/
│   ├── tools/
│   ├── principles/
│   └── memory/
│
├── docs/
│   ├── architecture/
│   ├── data/
│   ├── services/
│   ├── decisions/
│   ├── roadmap/
│   ├── product/
│   └── general/
│
├── data/
│   ├── schemas/
│   ├── notion/
│   ├── supabase/
│   ├── seed/
│   └── examples/
│
├── tests/
├── deploy/
│
├── README.md
├── AGENTS.md
├── .env.example
├── .gitignore
├── Dockerfile
└── render.yaml
```

# Repository Structure Target

Версия: 1.1  
Статус: целевая архитектура  
Целевой путь: `docs/architecture/Repository_Structure_Target.md`

---

## 1. Назначение документа

Документ фиксирует целевую файловую архитектуру репозитория `ai_os_system`.

Это не план немедленной миграции и не описание текущего состояния.

Документ отвечает на вопрос:

> Как должен быть устроен репозиторий AI OS в целевом состоянии?

---

## 2. Важное уточнение по текущему этапу

На текущем этапе рабочий код сервиса может оставаться в корневой папке `conductor/`.

Физически переносить `conductor/` в `apps/conductor/` следует только тогда, когда будет подготовлена отдельная миграционная задача с проверкой:

- импортов;
- тестов;
- Dockerfile;
- Render-конфигурации;
- команд запуска;
- внутренних ссылок документации.

До этого `apps/`, `core/`, `integrations/`, `agents/`, `workflows/`, `prompts/` и `data/` могут существовать только как целевая архитектура в документации.

Не нужно создавать пустые папки без реального содержимого.

---

## 3. Главный принцип

Репозиторий `ai_os_system` должен развиваться как монорепозиторий персональной AI OS, а не как репозиторий одного сервиса.

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

## 4. Целевая верхнеуровневая структура

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

## 5. `apps/`

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

## 6. `core/`

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

## 7. `integrations/`

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

## 8. `agents/`

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

## 9. `workflows/`

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

## 10. `prompts/`

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

## 11. `knowledge/`

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
- `knowledge/` не хранит реализационные архитектурные решения по структуре репозитория;
- `knowledge/` не хранит реальные пользовательские данные.

Примеры:

```text
knowledge/vision/System_Vision.md
knowledge/architecture/Core_Capabilities.md
knowledge/architecture/Entity_Description_Standard.md
knowledge/entities/Task_Entity.md
knowledge/classification/Classification_Rules.md
knowledge/development/Codex_Module_Development_Standard.md
knowledge/agents/Agent_Registry.md
```

---

## 12. `docs/`

`docs/` содержит проектную, техническую, сервисную и продуктовую документацию.

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

- `docs/architecture/` — архитектура реализации и структура репозитория;
- `docs/data/` — модели данных, схемы БД, Notion, Supabase;
- `docs/services/` — документация сервисов;
- `docs/decisions/` — принятые архитектурные решения;
- `docs/roadmap/` — планы развития и функциональные карты;
- `docs/product/` — продуктовые сценарии, требования и use cases;
- `docs/general/` — общая документация.

Примеры:

```text
docs/architecture/Repository_Structure_Target.md
docs/architecture/Document_Placement_Rules.md
docs/architecture/System_Map.md
docs/data/Data_Ownership_Map.md
docs/product/use_cases/Use_Case_Template.md
docs/services/conductor/Conductor_Service_Description.md
docs/services/conductor/Conductor_MVP_Operations.md
```

---

## 13. `docs/product/use_cases/`

`docs/product/use_cases/` содержит продуктовые use cases.

Use case описывает пользовательский сценарий до передачи задачи в разработку.

Правила:

- use case не должен быть кодовой задачей;
- use case должен описывать цель, вход, выход, данные, сущности, агентов, сервисы, правила и критерии готовности;
- после утверждения use case из него может быть подготовлен `Codex Task`;
- шаблон use case хранится в `docs/product/use_cases/Use_Case_Template.md`.

Не использовать отдельную верхнеуровневую папку `docs/use_cases/`, чтобы не разрывать продуктовую документацию.

---

## 14. `data/`

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

## 15. `tests/`

`tests/` содержит тесты проекта.

Правила:

- при изменении логики должны обновляться тесты;
- тесты должны проверять `core/`, `apps/` и `integrations/`;
- тесты не должны зависеть от реальных секретов и личных данных.

---

## 16. `deploy/`

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

## 17. Базовые различия между слоями

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
docs/ = проектные, реализационные и продуктовые документы
```

### `docs/product/use_cases/` vs `docs/architecture/`

```text
docs/product/use_cases/ = что должен уметь пользовательский сценарий
docs/architecture/ = как устроена система и ее реализация
```

---

## 18. README-политика

README должен отвечать на три вопроса:

1. Что лежит в папке.
2. Зачем это нужно.
3. Какие правила действуют внутри папки.

README не должен вручную перечислять все файлы, если список может часто меняться.

---

## 19. Политика миграции

Миграция структуры должна выполняться поэтапно.

Запрещено одним изменением:

- переносить код;
- менять импорты;
- менять деплой;
- менять тесты;
- менять структуру документации;
- менять бизнес-логику.

Правильный порядок:

1. Зафиксировать целевую структуру в документации.
2. Создать недостающие README и правила размещения документов.
3. Перенести документацию.
4. Проверить markdown-ссылки.
5. Только затем планировать перенос кода.
6. Перенос кода выполнять отдельной задачей с тестами.

---

## 20. Итоговое целевое дерево

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
│   │   └── use_cases/
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

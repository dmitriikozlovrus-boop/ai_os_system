# Repository Transition Plan

Версия: 1.0  
Статус: план перехода  
Целевой путь: `docs/architecture/Repository_Transition_Plan.md`

---

## 1. Назначение документа

Документ описывает плавный переход от текущей структуры репозитория к целевой архитектуре AI OS.

Целевая архитектура зафиксирована в отдельном документе:

```text
docs/architecture/Repository_Structure_Target.md
```

Этот документ отвечает на вопросы:

- чем текущая структура отличается от целевой;
- какие шаги перехода нужно выполнить;
- что переносить сейчас;
- что переносить позже;
- какие изменения требуют отдельной задачи;
- как не сломать работающий MVP.

---

## 2. Главный принцип перехода

Переход должен быть поэтапным.

Не переносить код вместе с документацией.

Не менять deployment вместе с файловым укладом.

Не рефакторить бизнес-логику в задачах на структуру.

Правильный порядок:

```text
1. Зафиксировать целевую архитектуру
2. Разложить knowledge
3. Разложить docs
4. Создать roadmap агентов
5. Создать каркас будущих слоев
6. Только потом переносить код
```

---

## 3. Текущее состояние

Текущий репозиторий начинался как MVP сервиса Conductor / Дирижёр.

Упрощенно текущая структура выглядит так:

```text
ai_os_system/
├── conductor/
├── deploy/
├── docs/
├── knowledge/
├── tests/
│
├── README.md
├── AGENTS.md
├── .env.example
├── .gitignore
├── Dockerfile
└── render.yaml
```

Сейчас `conductor/` находится в корне и фактически является главным работающим сервисом.

Это допустимо для MVP, но не является целевой архитектурой AI OS.

---

## 4. Целевое состояние

Целевая структура:

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

Ключевое изменение:

```text
conductor/
```

должен перестать быть смысловым центром репозитория.

В целевой структуре он становится одним из приложений:

```text
apps/conductor/
```

---

## 5. Что можно сделать сразу

### 5.1. Зафиксировать целевую архитектуру

Создать:

```text
docs/architecture/Repository_Structure_Target.md
```

Без переноса кода.

---

### 5.2. Разложить knowledge-документы

Переместить:

```text
System_Vision.md
→ knowledge/vision/System_Vision.md

Core_Capabilities.md
→ knowledge/architecture/Core_Capabilities.md

Entity_Description_Standard.md
→ knowledge/architecture/Entity_Description_Standard.md

Codex_Module_Development_Standard.md
→ knowledge/development/Codex_Module_Development_Standard.md

*_Entity.md
→ knowledge/entities/

Classification_Rules.md
→ knowledge/classification/Classification_Rules.md
```

Ограничения:

- не переписывать содержимое;
- не менять смысл;
- не объединять документы;
- не создавать новые сущности.

---

### 5.3. Обновить README в `knowledge/`

README должен кратко объяснять:

```text
vision/          = зачем существует система
architecture/    = принципы и стандарты системы
entities/        = определения сущностей
classification/  = правила выбора между сущностями
development/     = стандарты разработки
```

README не должен вручную перечислять все файлы, если список может часто меняться.

---

### 5.4. Создать папки в `docs/`

Создать:

```text
docs/architecture/
docs/data/
docs/services/
docs/decisions/
docs/roadmap/
docs/product/
```

Если папка уже существует — не трогать.

---

## 6. Что делать вторым этапом

### 6.1. Перенести накидку будущих агентов

Текущая функциональная карта по направлениям:

```text
Работа
Бизнес
Личное развитие
Семья и повседневная жизнь
```

должна лечь в:

```text
docs/roadmap/Agent_Directions_Roadmap.md
```

Это roadmap, а не финальная спецификация агентов.

---

### 6.2. Описать сервисы

Создать:

```text
docs/services/conductor/
docs/services/lyuba/
docs/services/scheduler/
```

Примеры документов:

```text
docs/services/conductor/Conductor_Service_Description.md
docs/services/conductor/Conductor_Module_Architecture.md

docs/services/lyuba/Lyuba_Interface_Description.md

docs/services/scheduler/Scheduler_Service_Description.md
```

---

### 6.3. Описать данные

Создать:

```text
docs/data/notion/
docs/data/supabase/
docs/data/schemas/
```

Примеры документов:

```text
docs/data/Data_Model.md
docs/data/Entity_Relationships.md
docs/data/notion/Notion_Database_Schema.md
docs/data/supabase/Supabase_Migration_Plan.md
```

---

## 7. Что делать третьим этапом

Создать каркас будущих слоев без переноса кода:

```text
apps/
core/
integrations/
agents/
workflows/
prompts/
data/
```

На этом этапе можно создать только README.md в каждой папке.

Не переносить работающий код.

---

## 8. Что делать четвертым этапом

Разложить проектирование агентов.

Создать:

```text
agents/
├── shared/
├── work/
├── business/
├── personal_development/
└── family_life/
```

Для каждого конкретного агента создавать отдельный пакет только после принятия решения о его разработке.

Пример:

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

---

## 9. Что делать пятым этапом

Перенести текущий код:

```text
conductor/
→ apps/conductor/
```

Это отдельная техническая задача.

Она должна включать обновление:

- импортов;
- команд запуска;
- Dockerfile;
- render.yaml;
- тестов;
- README;
- deployment-инструкций.

Не делать этот перенос вместе с переносом документации.

---

## 10. Что не делать в ближайших задачах

Не переносить `conductor/` в `apps/conductor/` без отдельной задачи.

Не создавать микросервисы.

Не дробить каждый модуль Conductor в отдельный сервис.

Не менять Python-код в задачах на документацию.

Не менять deployment в задачах на knowledge.

Не смешивать agent roadmap и agent implementation.

Не хранить реальные пользовательские данные в репозитории.

Не хранить секреты.

---

## 11. Рекомендуемая последовательность задач для Codex

### Task 1. Create target architecture document

Создать:

```text
docs/architecture/Repository_Structure_Target.md
```

Код не трогать.

---

### Task 2. Move knowledge documents

Разложить существующие knowledge-документы по папкам.

Код не трогать.

---

### Task 3. Create docs structure

Создать целевые папки внутри `docs/`.

Код не трогать.

---

### Task 4. Create agent roadmap

Создать:

```text
docs/roadmap/Agent_Directions_Roadmap.md
```

Код не трогать.

---

### Task 5. Create future layer placeholders

Создать README-only папки:

```text
apps/
core/
integrations/
agents/
workflows/
prompts/
data/
```

Код не трогать.

---

### Task 6. Move Conductor code

Перенести:

```text
conductor/
→ apps/conductor/
```

Это отдельная задача с обновлением импортов, тестов и deployment.

---

## 12. Контрольные правила

Перед каждой задачей Codex должен определить:

1. Нужно ли читать код?
2. Нужно ли менять код?
3. Какие файлы разрешено менять?
4. Какие файлы запрещено менять?
5. Какой минимальный результат нужен?

Если задача про документацию — код не читать.

Если задача про структуру — содержимое длинных документов не переписывать.

Если задача про перенос кода — заранее ограничить список файлов.

---

## 13. Итоговая логика перехода

Текущий репозиторий:

```text
Conductor MVP
```

Целевой репозиторий:

```text
AI OS monorepo
```

Переход:

```text
Документы
→ Knowledge
→ Roadmap
→ Каркас слоев
→ Сервисы
→ Код
```

Главный принцип:

```text
Сначала зафиксировать решение.
Потом переносить файлы.
Потом менять код.
```

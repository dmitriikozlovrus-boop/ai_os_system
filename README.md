# AI OS System

## Что это

AI OS System — персональная ИИ-инфраструктура.

Система предназначена для приема входящей информации, классификации сущностей, работы с задачами, событиями, исследованиями, идеями, проблемами, документами и будущими агентами.

Репозиторий содержит код текущего MVP, устойчивые знания системы и проектную документацию.

## Текущий рабочий MVP

Текущий рабочий MVP — `Conductor / Дирижёр`.

`Conductor` принимает входящую информацию, классифицирует ее, создает и обновляет записи, синхронизирует задачи и возвращает результат обработки.

На текущем этапе код сервиса находится в корневой папке:

```text
conductor/
```

Целевая архитектура может предусматривать будущий перенос в:

```text
apps/conductor/
```

Такой перенос не выполняется без отдельной миграционной задачи.

Операционное описание Conductor MVP вынесено в:

```text
docs/services/conductor/Conductor_MVP_Operations.md
```

## Структура

```text
conductor/  — текущий рабочий код Conductor MVP
knowledge/  — устойчивые знания системы
docs/       — проектная, техническая, сервисная и продуктовая документация
tests/      — тесты
deploy/     — деплой
```

## Где искать

| Раздел | Путь |
|---|---|
| Видение | `knowledge/vision/` |
| Сущности | `knowledge/entities/` |
| Классификация | `knowledge/classification/` |
| Архитектура репозитория | `docs/architecture/` |
| Данные | `docs/data/` |
| Сервисы | `docs/services/` |
| Use cases | `docs/product/use_cases/` |
| Агенты и роли | `knowledge/agents/` |

## Ключевые документы

| Документ | Назначение |
|---|---|
| `docs/architecture/System_Map.md` | верхнеуровневая логическая карта AI OS |
| `docs/architecture/System_Component_Registry.md` | перечень компонентов по архитектурным слоям |
| `docs/architecture/Document_Placement_Rules.md` | правила размещения документов |
| `knowledge/agents/Agent_Registry.md` | роли агентов и сервисов |
| `docs/product/use_cases/Use_Case_Template.md` | шаблон описания пользовательских сценариев |
| `docs/services/conductor/README.md` | краткое описание Conductor service docs |
| `docs/services/conductor/Conductor_Service_Description.md` | роль, ответственность и границы Conductor |
| `docs/services/conductor/Conductor_MVP_Operations.md` | запуск, webhook, переменные окружения, Notion, Todoist, OpenAI transcription и эксплуатация MVP |

## Правило работы с README

Корневой `README.md` должен оставаться короткой входной дверью в AI OS System.

Подробное операционное описание конкретных сервисов не должно храниться в корневом README.

Если информация относится к запуску, webhook, переменным окружения, Notion, Todoist, OpenAI transcription, командам или эксплуатации Conductor MVP, она должна храниться в:

```text
docs/services/conductor/Conductor_MVP_Operations.md
```

Если информация относится к архитектуре, данным, агентам, use cases или roadmap, она должна храниться в соответствующем разделе `docs/` или `knowledge/`.

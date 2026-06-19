# Conductor

Conductor / Дирижёр — текущий рабочий MVP-сервис AI OS.

Он принимает входящую информацию, классифицирует ее, создает и обновляет записи, синхронизирует задачи и возвращает результат обработки.

На текущем этапе код сервиса находится в корневой папке:

```text
conductor/
```

Целевая архитектура может предусматривать будущий перенос в:

```text
apps/conductor/
```

Такой перенос не выполняется без отдельной миграционной задачи.

## Роль в AI OS

Conductor является текущей реализацией оркестрационного слоя AI OS.

Он связан с логической ролью `Conductor`, описанной в архитектурных документах, но этот README описывает именно текущий MVP-сервис и его место в репозитории.

Conductor не является:

- пользовательским интерфейсом;
- агентом узкой специализации;
- базой данных;
- единственным местом всей бизнес-логики;
- roadmap будущей архитектуры.

## Текущие направления ответственности

На уровне MVP Conductor может участвовать в следующих процессах:

- прием входящих сообщений;
- классификация входящей информации;
- создание и обновление записей;
- работа с Notion;
- работа с Todoist;
- синхронизация задач;
- обработка Telegram webhook;
- использование OpenAI transcription для голосовых и аудиосообщений;
- возврат результата пользователю;
- обработка ошибок и спорных случаев в рамках текущей реализации.

Подробные операционные детали должны быть описаны отдельно в:

```text
docs/services/conductor/Conductor_MVP_Operations.md
```

## Связь с Lyuba

Lyuba — это Telegram-бот и один из интерфейсов взаимодействия с AI OS.

Conductor не является Lyuba.

Типовой маршрут:

```text
User
 ↓
Lyuba / Telegram
 ↓
Conductor
 ↓
Core Logic / Integrations
 ↓
Notion / Todoist / OpenAI
 ↓
Result
 ↓
Lyuba / Telegram
 ↓
User
```

## Связанные документы

Перед изменением логики Conductor необходимо учитывать:

```text
docs/architecture/System_Map.md
docs/architecture/System_Component_Registry.md
docs/architecture/Document_Placement_Rules.md
knowledge/agents/Agent_Registry.md
docs/data/Data_Ownership_Map.md
docs/product/use_cases/Use_Case_Template.md
```

При работе с конкретным пользовательским сценарием также нужно читать соответствующий use case в:

```text
docs/product/use_cases/
```

## Правило изменений

Этот README не должен содержать подробные инструкции по запуску, webhook, переменным окружения, Notion, Todoist, OpenAI transcription или эксплуатации MVP.

Такая информация должна храниться в:

```text
docs/services/conductor/Conductor_MVP_Operations.md
```

Этот README должен оставаться кратким навигационным описанием сервиса.

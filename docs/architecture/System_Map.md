# System Map
## Назначение
Этот документ описывает верхнеуровневую логическую карту AI OS.
Документ показывает не физическую структуру кода, а основные слои системы, их роли и типовые направления движения информации.
`System_Map.md` не фиксирует один обязательный бизнес-процесс. Разные сценарии могут использовать разные входы, интеграции, хранилища, инструменты исполнения и каналы результата.
Документ нужен для выравнивания понимания архитектуры между пользователем, ИИ-ассистентами, Codex и будущими агентами.
## Главное правило
AI OS строится не вокруг одного интерфейса, одного бота, одной базы данных или одной языковой модели.
Центральный логический узел системы — `Conductor`.
`Lyuba` — это Telegram-бот и один из интерфейсов взаимодействия с системой. Она может быть входом и выходом для части процессов, но не является обязательным маршрутом для всех бизнес-процессов.
## Логическая карта AI OS
```text
User / External Sources
        ↓
Input Interface Layer
        ↓
Conductor
        ↓
Core Logic
        ↓
Intelligence Layer
        ↓
Integration Layer
        ↓
Data Layer / Execution Layer
        ↓
Result / Feedback
        ↓
Output Interface Layer
        ↓
User / External Recipient
```
Эта схема является логической, а не жесткой технической последовательностью. В реальных сценариях некоторые слои могут вызываться повторно, параллельно или в другом порядке.
## Основные слои системы
| Слой | Назначение | Примеры |
|---|---|---|
| User / External Sources | Источники входящей информации, команд, сигналов или событий | пользователь, Telegram, Gmail, Calendar, Todoist, Notion, API, файлы, сайты, триггеры |
| Input Interface Layer | Интерфейсы, через которые информация попадает в AI OS | Lyuba, ChatGPT, Telegram-бот, Gmail, Calendar, Todoist, Notion, web, API |
| Conductor | Центральный координатор и маршрутизатор | классификация, выбор сценария, выбор сущности, вызов логики, возврат результата |
| Core Logic | Правила, процедуры и бизнес-логика обработки | Task Logic, Event Logic, Study Logic, Problem Logic, Idea Logic, Digest Logic, Error Logic |
| Intelligence Layer | Языковые модели, агенты и интеллектуальная обработка | OpenAI / GPT, другие LLM, Research Agent, Task Agent, Calendar Agent, Error Agent |
| Integration Layer | Подключение к внешним системам и API | Notion API, Todoist API, Google Calendar API, Gmail API, Telegram Bot API, OpenAI API |
| Data Layer | Хранение данных, документов, правил, истории и источников истины | Notion, PostgreSQL / Supabase, Google Drive, GitHub, Knowledge, Error Log |
| Execution Layer | Совершение действий во внешних системах | создать задачу, событие, письмо, запись, документ, follow-up, ошибку |
| Result / Feedback | Итог обработки входящего сигнала | задача, событие, digest, исследование, ошибка, уточнение, отклонение шума |
| Output Interface Layer | Интерфейсы, через которые пользователь видит результат | Lyuba, ChatGPT, Todoist UI, Calendar UI, Notion UI, Gmail, dashboard, отчет |
| Control & Improvement Layer | Контроль качества, ошибки, аудит и улучшение системы | Error Log, Error Types, Quality Rules, Audit Log, Rule Updates, Knowledge Updates |
## Ключевые определения
### Sources
`User / External Sources` — места, где возникает информация.
Источник сам по себе не является интерфейсом, оркестратором или базой данных.
Один и тот же сервис может выполнять разные роли в разных сценариях.
Пример:
```text
Gmail как Source = входящее письмо
Gmail как Execution = отправка письма
Gmail как Output Interface = пользователь видит письмо
```
### Interface Layer
`Input Interface Layer` принимает вход в AI OS.
`Output Interface Layer` показывает результат пользователю или внешнему получателю.
Интерфейс не обязан содержать бизнес-логику. Его задача — принять вход, передать его дальше, сохранить технический контекст и показать результат.
### Conductor
`Conductor` — центральный логический координатор AI OS.
Его задачи:
- принять входящий сигнал;
- определить тип входа;
- классифицировать информацию;
- определить целевую сущность;
- выбрать сценарий обработки;
- вызвать нужный блок `Core Logic`;
- при необходимости вызвать `Intelligence Layer`;
- инициировать запись, обновление, проверку или действие;
- вернуть результат в подходящий канал;
- зафиксировать ошибку или спорный случай.
`Conductor` не должен быть привязан только к Telegram или `Lyuba`.
`Conductor` не является пользовательским интерфейсом, базой данных, языковой моделью или агентом узкой специализации.
### Core Logic
`Core Logic` — слой правил, процедур и бизнес-логики системы.
На этом уровне находятся правила классификации, определения сущностей, маршрутизации, заполнения полей, валидации, дедупликации, обновления записей, работы с ошибками и обработки конкретных сценариев.
На текущем этапе `core/` может быть описан концептуально. Физическая структура кода может быть определена позже.
### Intelligence Layer
`Intelligence Layer` — слой языковых моделей, агентов и интеллектуальной обработки.
Его задачи: понимать естественный язык, классифицировать входящие сигналы, извлекать сущности и поля, определять даты, имена, организации, темы и связи, резюмировать информацию, генерировать ответы, готовить аналитические материалы, выявлять ошибки и противоречия.
Важно: LLM сама по себе не является агентом.
```text
Agent = Role + Instructions + Tools + Responsibility
```
`Intelligence Layer` не является источником истины. Он помогает обрабатывать информацию, но не должен заменять `Data Layer`.
### Integration Layer
`Integration Layer` — слой подключения к внешним системам, API и техническим сервисам.
Его задача — изолировать бизнес-логику от конкретных API и технических деталей интеграций.
`Core Logic` должен говорить: “создать задачу”, “обновить событие”, “получить письмо”, “записать исследование”.
`Integration Layer` должен решать, как именно это сделать технически.
### Data Layer
`Data Layer` — слой хранения данных, документов, правил, истории и источников истины.
Примеры хранилищ: Notion, PostgreSQL / Supabase, Google Drive, GitHub, Knowledge, Error Log, Research outputs, Action logs.
Примеры сущностей: Tasks, Events, Projects, Problems, Study, Ideas, Contacts, Streams, Topics, Agents, Error Types.
Важно: разные сущности могут иметь разные источники истины. Это должно быть отдельно описано в `docs/data/`.
### Execution Layer
`Execution Layer` — слой совершения действий во внешних системах.
Execution — это не интерфейс вывода. Execution означает, что система что-то реально сделала.
Примеры действий: создать задачу в Todoist, создать событие в Google Calendar, отправить письмо через Gmail, обновить запись в Notion, сохранить документ в Google Drive, изменить файл в GitHub, создать follow-up, зафиксировать ошибку.
### Result / Feedback
`Result / Feedback` — итог обработки входящего сигнала.
Примеры: создана задача, обновлена запись, создано календарное событие, подготовлен digest, создан исследовательский вывод, отправлен ответ пользователю, создана ошибка в журнале, информация отклонена как шум, задан уточняющий вопрос.
Результат не обязан возвращаться через тот же интерфейс, через который пришел вход.
### Control & Improvement Layer
`Control & Improvement Layer` — слой контроля качества, ошибок, аудита и улучшения системы.
Его задачи: фиксировать ошибки, классифицировать ошибки, определять повторяемость ошибок, выявлять пробелы в правилах и архитектуре, проверять качество данных, проводить аудит действий, обновлять правила, предлагать улучшения.
Базовая логика:
```text
Ошибка → классификация → причина → повторяемость → исправление → изменение правила
```
## Роль Lyuba
`Lyuba` — это Telegram-бот и единое удобное окно для части пользовательских взаимодействий.
Типовая роль `Lyuba`:
```text
User
 ↓
Lyuba / Telegram
 ↓
Conductor
 ↓
Core Logic
 ↓
Intelligence Layer
 ↓
Integration Layer
 ↓
Data Layer / Execution Layer
 ↓
Result
 ↓
Lyuba / Telegram
 ↓
User
```
Эта схема является частным use case, а не универсальной архитектурой всей AI OS.
`Lyuba` может использоваться для быстрого ввода задач, голосового или текстового capture, уточнений, уведомлений, возврата результата, ручной коррекции ошибки, фиксации идеи и передачи команды в систему.
`Lyuba` не должна подменять `Conductor`.
Правильная фиксация:
```text
Lyuba = Interface Layer
Conductor = Orchestration Layer
```
## Роль Conductor
`Conductor` — центральный оркестрационный слой AI OS.
Типовая логика `Conductor`:
```text
Получить вход
 ↓
Определить тип сигнала
 ↓
Определить целевую сущность
 ↓
Выбрать сценарий обработки
 ↓
Вызвать нужную Core Logic
 ↓
При необходимости вызвать Intelligence Layer
 ↓
Через Integration Layer обратиться к нужным системам
 ↓
Записать данные или выполнить действие
 ↓
Вернуть результат
 ↓
Зафиксировать ошибку или обратную связь при необходимости
```
`Conductor` не должен содержать всю бизнес-логику внутри себя. Он должен координировать специализированные блоки логики.
## Примеры логических маршрутов
### Telegram → Task
```text
User → Lyuba / Telegram → Conductor → Task Core Logic → Intelligence Layer → Integration Layer → Notion Tasks DB / Todoist → Result → Lyuba → User
```
### Gmail → Digest
```text
Gmail → Conductor → Digest Core Logic → Intelligence Layer → Integration Layer → Research Output / Notion / Google Drive → Digest Result → Output Interface → User
```
### Google Calendar → Event Processing
```text
Google Calendar → Conductor → Event Core Logic → Calendar Rules / Events DB → Conflict Check / Follow-up / Update → Result → User
```
### Manual Notion Update → Validation
```text
Manual Notion Update → Conductor → Validation Logic → Entity Rules / Data Rules → Correction / Error Log / Confirmation
```
### Error Logging → System Improvement
```text
Detected Error → Conductor → Error Core Logic → Error Classification → Error Log → Error Type / Rule Gap / Architecture Gap → Manual or Automated Correction → Knowledge / Rule Update
```
### Research Request → Research Output
```text
User / External Request → Input Interface → Conductor → Study / Research Core Logic → Research Agent / Intelligence Layer → Integration Layer → Sources / Documents / Web / Files → Research Output → Google Drive / Notion / Knowledge → Output Interface → User
```
## Что этот документ фиксирует
Этот документ фиксирует:
- AI OS имеет слоистую логическую архитектуру;
- архитектура строится вокруг функций, а не вокруг конкретных сервисов;
- `Conductor` является центральным координатором;
- `Lyuba` является интерфейсом, а не всей системой;
- `LLM` является частью `Intelligence Layer`, а не источником истины;
- агенты являются специализированными ролями, а не всей системой;
- разные бизнес-процессы могут иметь разные маршруты;
- `Core Logic` и `Integration Layer` могут быть сначала концептуальными;
- `Data Layer` и `Execution Layer` должны различаться;
- `Input Interface` и `Output Interface` должны различаться;
- карта системы не равна структуре папок, структуре backend-кода или roadmap.
## Что этот документ не фиксирует
Этот документ не фиксирует физическую структуру backend-кода, финальную структуру папок `core/` и `integrations/`, конкретные API-контракты, детальные схемы баз данных, полный список use cases, порядок реализации, roadmap, финальный состав агентов, финальную модель данных, prompts и системные инструкции для каждого агента.
Эти вопросы должны описываться в отдельных документах.
## Где описывать связанные документы
| Тип документа | Где хранить |
|---|---|
| Верхнеуровневая карта системы | `docs/architecture/System_Map.md` |
| Устойчивые архитектурные принципы | `knowledge/architecture/` |
| Архитектура реализации | `docs/architecture/` |
| Источники истины и модель данных | `docs/data/` |
| Описание сервисов | `docs/services/` |
| Описание Conductor | `docs/conductor/` |
| Конкретные use cases | `docs/use_cases/` |
| Архитектурные решения | `docs/decisions/` |
| Roadmap и планы развития | `docs/roadmap/` |
| Реестр агентов | `knowledge/agents/Agent_Registry.md` |
| Правила размещения документов | `docs/architecture/Document_Placement_Rules.md` |
## Базовый принцип развития карты
Сначала фиксируется логическая карта слоев.
Затем отдельно описываются конкретные маршруты: Telegram input → Task, Telegram input → Event, Gmail → Digest, Calendar → Event Processing, Notion update → Validation, Error log → Rule improvement, Research request → Research output, Idea capture → Idea DB, Problem capture → Problem DB, Document upload → Document processing, Contact signal → Contact update, Task completion → Follow-up generation.
Каждый такой маршрут должен оформляться как отдельный use case в `docs/use_cases/`.
## Правила разделения
### 1. Не смешивать архитектурный слой и конкретную реализацию
```text
Lyuba ≠ architecture
Lyuba = implementation of Interface Layer
```
### 2. Не смешивать интерфейс и оркестратор
```text
Interface = принимает и показывает
Conductor = выбирает маршрут
```
### 3. Не смешивать LLM и агента
```text
LLM = Intelligence Engine
Agent = Role + Instructions + Tools + Responsibility
```
### 4. Не смешивать Data Layer и Execution Layer
```text
Data Layer = хранит
Execution Layer = выполняет действия
```
### 5. Не смешивать Knowledge и операционные БД
```text
Knowledge = правила и стабильные инструкции
Operational DB = живые рабочие записи
```
### 6. Не смешивать Output и Execution
```text
Execution = действие совершено
Output = результат показан
```
### 7. Не привязывать бизнес-логику к одному интерфейсу
Логика обработки задачи должна работать независимо от того, откуда пришел вход: `Lyuba`, ChatGPT, Gmail, Todoist, Notion, API или ручной ввод.
Интерфейс может меняться. Логика должна сохраняться.
## Минимальная терминология
| Термин | Значение |
|---|---|
| Source | Откуда пришла информация |
| Input Interface | Через что информация вошла в систему |
| Conductor | Центральный координатор и маршрутизатор |
| Core Logic | Правила и процедуры обработки |
| Intelligence Layer | LLM, агенты, классификация, анализ, генерация |
| Integration Layer | Подключение к API и внешним системам |
| Data Layer | Хранение данных, документов, правил и истории |
| Execution Layer | Выполнение действий во внешних системах |
| Result / Feedback | Итог обработки и обратная связь |
| Output Interface | Где пользователь видит результат |
| Control & Improvement | Ошибки, аудит, улучшение правил |
## Текущий статус
Статус документа: базовая версия.
На текущем этапе документ нужен для выравнивания понимания архитектуры между пользователем, ИИ-ассистентами, Codex и будущими агентами.
Документ может уточняться по мере появления новых интерфейсов, сервисов, агентов, баз данных и сценариев.
Изменения в этом документе должны вноситься только при изменении верхнеуровневой логики AI OS.
Частные изменения в агентах, БД, prompts, инструментах, интеграциях и use cases должны описываться в отдельных документах.

# Use Case: Improvement To Codex Task

## 1. Цель

Сценарий формирует из подтвержденного `IMPROVEMENT` готовое техническое задание для ручной передачи в Codex.

Conductor не запускает Codex автоматически, не создает GitHub issue, branch, commit или PR, не меняет код, правила, промпты и статус Improvement.

## 2. Актор

Основной актор — пользователь Telegram-бота Lyuba.

Conductor выбирает конкретный Improvement, собирает ограниченный read-only контекст репозитория, просит OpenAI подготовить `TechnicalChangeProposal`, показывает preview и ждет отдельные подтверждения на показ полного ТЗ и сохранение в Notion.

## 3. Предусловия

- Есть запись `IMPROVEMENT` со статусом `Идея`, `В работе` или другим текущим статусом.
- `IMPROVEMENTS.Какие ошибки исправляет` содержит relation на связанные `SYSTEM ISSUES`, если они есть.
- `NOTION_IMPROVEMENTS_DATABASE_ID` и `NOTION_SYSTEM_ISSUES_DATABASE_ID` настроены.
- `TECHNICAL_SPEC_GENERATION_ENABLED=true` включает сценарий.
- `OPENAI_API_KEY` доступен для генерации полного предложения.
- Локальный checkout репозитория доступен Conductor только для чтения.

## 4. Основной сценарий

1. Пользователь пишет: `Сформируй ТЗ`, `Подготовь задачу для Кодекса` или похожий запрос.
2. Conductor определяет Improvement context в безопасном порядке:
   - активный state;
   - reply на сообщение бота о созданном Improvement;
   - последний созданный или подтвержденный Improvement в текущем Telegram chat;
   - явная Notion URL в сообщении.
3. Conductor читает Improvement из Notion.
4. Conductor берет связанные System Issues только из forward relation `IMPROVEMENTS.Какие ошибки исправляет`.
5. `RepositoryContextProvider` выбирает до 8 файлов-кандидатов из локального checkout.
6. Conductor читает до 120 KB суммарно и до 300 строк на файл.
7. OpenAI формирует `TechnicalChangeProposal`.
8. Conductor валидирует, что proposal ссылается только на прочитанные файлы, содержит regression tests и acceptance criteria.
9. Пользователь получает preview и вопрос: `Показать полное ТЗ?`
10. После ответа `Да` Conductor отправляет полный markdown-блок и спрашивает: `Сохранить это ТЗ в Improvement?`
11. Только после второго подтверждения Conductor сохраняет ТЗ в Improvement.

## 5. Notion Update

Сохранение добавляет или заменяет только управляемую секцию страницы Improvement:

```markdown
## Техническое задание для Codex
Статус проекта ТЗ: Черновик
Дата формирования: <date>
...
<!-- CONDUCTOR_TECH_SPEC_END -->
```

Если секция уже есть, Conductor архивирует только блоки от заголовка `Техническое задание для Codex` до маркера `CONDUCTOR_TECH_SPEC_END`, затем добавляет новую версию секции.

Пользовательский текст вне управляемой секции не изменяется.

## 6. Ограничения Repository Context

Разрешенные расширения:

```text
.py
.md
.yaml
.yml
.json
.toml
```

Ограничения:

- максимум 8 файлов;
- максимум 120 KB суммарно;
- максимум 300 строк на файл;
- без `.git`, virtualenv, `node_modules`, runtime state и секретов;
- без `.env`, `data/interactions.json`, `pending.json`, `recent.json`.

Context provider не сканирует весь репозиторий семантически и не создает индекс.

## 7. Feature Flag

Флаг:

```bash
TECHNICAL_SPEC_GENERATION_ENABLED=false
```

По умолчанию сценарий выключен.

При выключенном флаге Conductor отвечает, что подготовка ТЗ сейчас выключена, и не вызывает Notion/OpenAI для этого сценария.

## 8. OpenAI Unavailable

Если OpenAI недоступен или `OPENAI_API_KEY` отсутствует, Conductor не формирует полный proposal и отвечает:

```text
Не удалось автоматически подготовить техническое задание, поскольку AI-анализ недоступен.

Improvement сохранен и не изменен.
```

Improvement не обновляется.

## 9. Logs

События:

- `TECH_SPEC_REQUESTED`;
- `TECH_SPEC_CONTEXT_COLLECTED`;
- `TECH_SPEC_GENERATED`;
- `TECH_SPEC_VALIDATION_FAILED`;
- `TECH_SPEC_SHOWN`;
- `TECH_SPEC_SAVE_REQUESTED`;
- `TECH_SPEC_SAVED`;
- `TECH_SPEC_SAVE_ERROR`.

Логи не должны содержать полный текст ТЗ, пользовательский ввод, секреты или содержимое файлов.

## 10. Out Of Scope

- Автоматический запуск Codex.
- Автоматическое создание GitHub issue.
- Автоматическое создание branch, commit или PR.
- Автоматическое изменение кода, правил или prompts.
- Автоматическая смена статуса Improvement на `В работе`.
- Векторная база или agent.
- Сканирование всего репозитория.

## 11. Критерии успеха

- Improvement выбирается только из безопасного контекста пользователя.
- System Issues читаются через `IMPROVEMENTS.Какие ошибки исправляет`.
- Preview не сохраняет ТЗ.
- Полное ТЗ показывается только после подтверждения.
- Сохранение в Notion выполняется только после отдельного подтверждения.
- Повторное сохранение заменяет только управляемую секцию.
- Внешние вызовы в тестах замоканы.
- Существующий Task, Study, Goods и feedback-flow продолжают работать.

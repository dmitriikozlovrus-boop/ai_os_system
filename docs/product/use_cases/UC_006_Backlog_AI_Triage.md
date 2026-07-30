# Use Case: Backlog AI Triage

## 1. Цель

Conductor помогает разобрать накопленный backlog Improvements через Telegram: обогащает feedback, находит похожие Improvements, показывает готовность записей к доработке и предлагает безопасные действия без автоматического запуска Codex.

## 2. Feature Flag

Флаг:

```bash
BACKLOG_AI_TRIAGE_ENABLED=false
```

По умолчанию выключен.

При выключенном флаге существующий feedback backlog продолжает работать детерминированно. Команды AI triage возвращают controlled unavailable message и не меняют Notion.

## 3. AI Enrichment

Перед AI всегда выполняется детерминированная нормализация feedback.

OpenAI используется только как optional enrichment:

- уточняет `feedback_kind`;
- нормализует title/description;
- предлагает actual/expected behavior;
- оценивает severity и confidence;
- сохраняет original user wording separately.

Если OpenAI недоступен, вернул невалидный JSON или недопустимые значения, Conductor использует детерминированный результат.

`NOT_FEEDBACK` не создает действий. `CORRECTION` остается в correction flow и не попадает в backlog.

## 4. Guardrails

AI enrichment не может:

- добавить неизвестную database;
- заменить feedback kind на неподдержанный;
- придумывать expected behavior без evidence;
- повышать confidence выше допустимого диапазона;
- превратить neutral Reply вроде `Спасибо` в ошибку.

При противоречии между deterministic context и AI output применяется fallback.

## 5. Semantic Matching

Conductor формирует deterministic shortlist не больше 10 открытых Improvements.

AI сравнивает новый feedback с shortlist и возвращает candidates:

- `SAME_PROBLEM`;
- `RELATED_PROBLEM`;
- `DIFFERENT_PROBLEM`.

Решение:

- score `<60` — предложить новый Improvement;
- score `60-84` — показать варианты пользователю;
- score `85+` и `SAME_PROBLEM` — предложить привязку к существующему Improvement, но только после подтверждения.

Совпадение только по базе или компоненту не считается достаточным.

## 6. Backlog Readiness

Для Improvement рассчитывается readiness:

- `NEEDS_SIGNALS`;
- `NEEDS_CLARIFICATION`;
- `READY_FOR_REVIEW`;
- `READY_FOR_IMPLEMENTATION_SELECTION`.

Учитываются:

- описание проблемы;
- фактическое поведение;
- ожидаемое поведение;
- связанные System Issues;
- конфликтующие ожидания.

Если не хватает actual или expected behavior, запись требует уточнения.

## 7. Telegram Commands

Поддержанные группы команд:

- разобрать backlog;
- открыть первый/второй элемент из последнего triage list;
- показать возможные дубли;
- предложить split;
- показать кандидатов для реализации;
- выбрать элемент для существующего Technical Spec flow.

Triage list хранится локально по chat id и не пересекается между чатами.

## 8. Clarification

Если Improvement требует уточнения, Conductor задает до трех простых вопросов и сохраняет state:

```text
awaiting_backlog_clarification_answer
```

Ответ пользователя обновляет существующий Improvement summary. Новый Improvement и System Issue при этом не создаются.

## 9. Merge

Conductor может предложить объединение похожих Improvements.

Merge выполняется только после подтверждения пользователя:

- primary Improvement получает deduped relations;
- feedback summary primary обновляется;
- secondary Improvement переводится в статус `Отложено`;
- secondary не удаляется.

При частичном сбое пользователь получает сообщение о partial success.

## 10. Split

Split работает только как preview.

Conductor показывает возможное разделение одной записи на два Improvements, но не создает страницы и не меняет Notion без отдельной будущей задачи.

## 11. Technical Spec Handoff

Conductor не запускает Codex автоматически.

Переход в существующий Technical Spec flow возможен только после явного выбора пользователя и только если readiness достаточный.

## 12. Out Of Scope

- автоматический запуск Codex;
- GitHub branch/commit/push/PR из runtime;
- автоматическое изменение кода;
- автоматическое удаление Improvements;
- создание новой Notion database;
- полноценный split execution;
- самообучение правил.

## 13. Прогресс

Текущая оценка после сценария: 90%.

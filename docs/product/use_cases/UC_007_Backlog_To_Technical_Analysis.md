# Use Case: Backlog To Technical Analysis

## 1. Цель

Пользователь выбирает Improvement из backlog, Conductor проверяет готовность данных, создает immutable snapshot выбора и только после подтверждения передает запись в существующий Technical Spec flow.

## 2. Feature Flags

Требуются:

- `FEEDBACK_BACKLOG_ENABLED=true`;
- `TECHNICAL_SPEC_GENERATION_ENABLED=true`.

`BACKLOG_AI_TRIAGE_ENABLED=true` требует `FEEDBACK_BACKLOG_ENABLED=true`; иначе AI triage считается выключенным.

Production-safe default:

```bash
BACKLOG_PRODUCTION_DRY_RUN=true
```

## 3. Dry-run

Dry-run разрешает чтение Notion, normalization, OpenAI enrichment, semantic matching, readiness, preview и diagnostics.

Dry-run блокирует:

- создание System Issue;
- создание Improvement;
- обновление relation;
- изменение priority/status;
- сохранение feedback summary;
- сохранение Technical Spec.

Telegram показывает: `Режим проверки: данные не будут записаны в Notion.`

## 4. Context Resolution

Improvement выбирается только из текущего chat:

1. active state;
2. reply;
3. номер из triage list текущего chat;
4. номер из backlog list текущего chat;
5. явная Notion URL;
6. latest Improvement текущего chat только для явно разрешенных команд.

Глобальный latest и другой chat не используются.

## 5. Readiness Gate

`READY_FOR_IMPLEMENTATION_SELECTION` переходит к confirmation preview.

`READY_FOR_REVIEW` показывает предупреждение, что данных может быть недостаточно, и требует подтверждения.

`NEEDS_CLARIFICATION` и `NEEDS_SIGNALS` не запускают Technical Spec flow; Conductor предлагает clarification flow.

Readiness отображается как `Оценка готовности системы: N/100`.

## 6. Snapshot

При выборе сохраняется state-only snapshot:

- Improvement ID;
- title;
- last edited time;
- related System Issue IDs;
- feedback summary hash;
- readiness status/score;
- selected_at;
- chat_id.

Snapshot не записывается в Notion.

## 7. Stale Protection

Перед генерацией Technical Spec Conductor повторно читает Improvement и сверяет snapshot.

Если changed last edited time, relations или feedback summary hash, генерация не запускается. Пользователь получает обновленную readiness preview.

## 8. Technical Spec Handoff

Conductor переиспользует существующий Technical Spec flow:

```text
RepositoryContextProvider
→ OpenAI TechnicalChangeProposal
→ preview
→ full view confirmation
→ save confirmation
```

Новый generator не создается.

## 9. Diagnostics

Telegram-команды:

- `Проверь систему обратной связи`;
- `Диагностика backlog`;
- `Проверь интеграции`.

Команда проверяет flags, Notion schema и OpenAI contracts без write.

## 10. Smoke CLI

Команды:

```bash
python3 -m conductor.feedback_backlog_smoke --validate-only
python3 -m conductor.feedback_backlog_smoke --dry-run
```

`--write-smoke` заблокирован, если одновременно не заданы:

- CLI argument `--write-smoke`;
- `BACKLOG_PRODUCTION_DRY_RUN=false`;
- `SMOKE_TEST_WRITES_ENABLED=true`.

## 11. Managed Sections

Feedback summary и Technical Spec обновляются через managed markers.

Conductor сначала читает все блоки с pagination, валидирует START/END и только потом архивирует старую managed section.

Пользовательские блоки до и после секции сохраняются.

## 12. Partial Failures

Сообщения разделяются по типу:

- Notion read error;
- schema mismatch;
- OpenAI unavailable;
- invalid response;
- managed section corrupted;
- stale Improvement;
- feature disabled;
- dry-run blocked write;
- Technical Spec generation/save failed.

## 13. State Transitions

```text
backlog list
→ triage item
→ readiness preview
→ technical analysis confirmation
→ improvement snapshot
→ technical spec preview
→ save confirmation
```

Отказ очищает state. Stale snapshot возвращает пользователя к updated readiness preview.

## 14. Rollback

Runtime не меняет код, GitHub, Notion schema и не удаляет Improvements.

Если write заблокирован dry-run или schema mismatch, данные остаются неизменными.

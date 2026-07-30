# Feedback Backlog MVP Release

## 1. Цель релиза

Завершить приемку Feedback Backlog MVP для маршрута `Telegram -> Notion -> Backlog -> Technical Spec` без runtime-запуска Codex, GitHub writes или автоматического deploy.

## 2. Пользовательский flow

Поддержан маршрут:

1. Telegram feedback.
2. Поиск Reply/current chat context или controlled no-context path.
3. Deterministic normalization и optional AI enrichment.
4. System Issue для конкретной ошибки.
5. Link к существующему Improvement или proposal нового Improvement.
6. Feedback summary в managed section.
7. Backlog triage и readiness.
8. Выбор Improvement пользователем.
9. Snapshot и stale protection.
10. Existing Technical Spec flow.
11. Save confirmation в managed Technical Spec section.

## 3. Архитектурные компоненты

- `conductor/feedback_backlog.py` — deterministic normalization и summary payload.
- `conductor/backlog_context.py` — единый current-chat Improvement resolver.
- `conductor/backlog_triage.py` — AI enrichment, semantic matching, readiness, snapshot, duplicate assessment.
- `conductor/integration_validation.py` — Notion schema и OpenAI contract diagnostics.
- `conductor/write_guard.py` — centralized dry-run write guard.
- `conductor/feedback_backlog_smoke.py` — validate/dry-run/write-smoke CLI.
- `conductor/service.py` — routing, state machine и dependency wiring.

## 4. Notion dependencies

Required databases:

- `SYSTEM ISSUES`;
- `IMPROVEMENTS`.

Forward relation `IMPROVEMENTS -> Какие ошибки исправляет` остается source of truth. Reverse relation не обязательна.

## 5. OpenAI dependencies

Structured outputs:

- `FeedbackEnrichment`;
- `ImprovementMatchCandidate`;
- `ImprovementPairAssessment`;
- `TechnicalChangeProposal`.

Diagnostics use only `[SMOKE TEST]` synthetic data.

## 6. Telegram commands

- `Покажи backlog`;
- `Разбери backlog`;
- `Покажи возможные дубли`;
- `Что лучше доработать следующим?`;
- `Подготовь ТЗ по этому улучшению`;
- `Проверь систему обратной связи`;
- `Диагностика backlog`;
- `Проверь интеграции`.

## 7. Feature flags

Safe defaults:

```text
FEEDBACK_BACKLOG_ENABLED=false
BACKLOG_AI_TRIAGE_ENABLED=false
TECHNICAL_SPEC_GENERATION_ENABLED=false
SYSTEM_IMPROVEMENTS_ENABLED=false
BACKLOG_PRODUCTION_DRY_RUN=true
SMOKE_TEST_WRITES_ENABLED=false
```

`BACKLOG_AI_TRIAGE_ENABLED=true` requires `FEEDBACK_BACKLOG_ENABLED=true`.

## 8. Dry-run запуск

```bash
python3 -m conductor.feedback_backlog_smoke --dry-run
```

Expected:

```text
writes attempted: 4
writes blocked: 4
writes completed: 0
```

## 9. Validate-only запуск

```bash
python3 -m conductor.feedback_backlog_smoke --validate-only
```

In this Codex run, credentials were not configured, so Notion schema and OpenAI contracts were not live-confirmed.

## 10. Write-smoke запуск

Allowed only when all conditions are true:

```text
--write-smoke
BACKLOG_PRODUCTION_DRY_RUN=false
SMOKE_TEST_WRITES_ENABLED=true
```

Use only `[SMOKE TEST YYYY-MM-DD HH:MM]` records. Do not delete automatically.

## 11. Production activation

Stage 1 diagnostics:

```text
FEEDBACK_BACKLOG_ENABLED=false
BACKLOG_AI_TRIAGE_ENABLED=false
TECHNICAL_SPEC_GENERATION_ENABLED=false
BACKLOG_PRODUCTION_DRY_RUN=true
```

Stage 2 read-only pilot:

```text
FEEDBACK_BACKLOG_ENABLED=true
BACKLOG_AI_TRIAGE_ENABLED=true
TECHNICAL_SPEC_GENERATION_ENABLED=true
BACKLOG_PRODUCTION_DRY_RUN=true
```

Stage 3 controlled write pilot:

```text
BACKLOG_PRODUCTION_DRY_RUN=false
SMOKE_TEST_WRITES_ENABLED=true
```

After smoke:

```text
SMOKE_TEST_WRITES_ENABLED=false
```

Stage 4 production MVP:

```text
FEEDBACK_BACKLOG_ENABLED=true
BACKLOG_AI_TRIAGE_ENABLED=true
TECHNICAL_SPEC_GENERATION_ENABLED=true
BACKLOG_PRODUCTION_DRY_RUN=false
SMOKE_TEST_WRITES_ENABLED=false
```

## 12. Rollback

Immediate safe rollback:

```text
BACKLOG_PRODUCTION_DRY_RUN=true
```

Full disable:

```text
FEEDBACK_BACKLOG_ENABLED=false
BACKLOG_AI_TRIAGE_ENABLED=false
TECHNICAL_SPEC_GENERATION_ENABLED=false
```

Do not delete created System Issues, Improvements or Technical Specs during rollback.

## 13. Known limitations

- Live Notion schema validation requires credentials.
- Live OpenAI contract validation requires `OPENAI_API_KEY`.
- Telegram pilot requires a test chat.
- Write smoke was not run in this Codex session.

## 14. Smoke record URLs

Not run. No smoke System Issue or Improvement URLs are available.

## 15. Acceptance results

- Unit/mock tests: passed locally.
- Acceptance corpus: 30 cases.
- Dry-run smoke: passed.
- Validate-only: completed with clear missing-credentials diagnostics.
- Write smoke: not run.
- Telegram pilot: not run.

Production ready: no, live validation blockers remain.

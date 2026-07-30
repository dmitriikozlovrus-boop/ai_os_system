from __future__ import annotations

import argparse
import os
from tempfile import TemporaryDirectory
from unittest.mock import Mock

from .backlog_triage import calculate_readiness, normalize_with_ai, semantic_match_improvements
from .config import get_settings
from .integration_validation import validate_feedback_backlog_schema, validate_openai_contracts
from .models import ImprovementSummary
from .notion_client import NotionClient
from .openai_client import OpenAIClient
from .write_guard import ProductionWriteBlocked, ProductionWriteGuard


def main() -> int:
    parser = argparse.ArgumentParser(description="Feedback backlog production smoke checks.")
    parser.add_argument("--validate-only", action="store_true")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--write-smoke", action="store_true")
    args = parser.parse_args()
    if not (args.validate_only or args.dry_run or args.write_smoke):
        parser.error("choose --validate-only, --dry-run or --write-smoke")

    settings = get_settings()
    print("LIVE_SMOKE_STARTED")
    if args.write_smoke:
        if settings.backlog_production_dry_run or not settings.smoke_test_writes_enabled:
            print("LIVE_SMOKE_FAILED write smoke is blocked: require --write-smoke, BACKLOG_PRODUCTION_DRY_RUN=false and SMOKE_TEST_WRITES_ENABLED=true")
            return 2

    notion = NotionClient(
        token=settings.notion_token,
        tasks_db=settings.notion_tasks_database_id,
        study_db=settings.notion_study_database_id,
        projects_db=settings.notion_projects_database_id,
        goods_db=settings.notion_goods_database_id,
        system_issues_db=settings.notion_system_issues_database_id,
        improvements_db=settings.notion_improvements_database_id,
    )
    openai = OpenAIClient(settings.openai_api_key, settings.openai_model, settings.openai_transcribe_model, settings.openai_transcribe_fallback_model)

    if args.validate_only:
        _print_results(validate_feedback_backlog_schema(notion))
        if settings.openai_api_key:
            _print_results(validate_openai_contracts(openai))
        else:
            print("OpenAI contracts: not_checked (OPENAI_API_KEY is not configured)")

    if args.dry_run:
        guard = ProductionWriteGuard(dry_run=True)
        fake_openai = Mock()
        feedback = normalize_with_ai(openai=fake_openai, raw_text="[SMOKE TEST] Ты часто теряешь даты", interaction=None, enabled=False)
        improvement = ImprovementSummary(
            page_id="00000000-0000-0000-0000-000000000001",
            url="https://www.notion.so/00000000000000000000000000000001",
            title="[SMOKE TEST] Даты теряются",
            status="Идея",
            improvement_type="Правило",
            change_location="Правила Дирижёра",
            related_issue_urls=["00000000-0000-0000-0000-000000000002"],
            priority="Средний",
            description="Сейчас дата иногда теряется.",
            suggested_change="Система должна сохранять дату.",
        )
        matches = semantic_match_improvements(openai=fake_openai, feedback=feedback, shortlist=[improvement], enabled=False)
        readiness = calculate_readiness(improvement, [])
        with TemporaryDirectory():
            pass
        for operation in ("create_system_issue", "create_improvement", "update_feedback_summary", "save_technical_spec"):
            try:
                guard.assert_write_allowed(operation)
            except ProductionWriteBlocked:
                pass
        print(f"dry-run feedback={feedback.feedback_kind} matches={len(matches)} readiness={readiness.status}:{readiness.score}")
        print("Режим проверки: данные не будут записаны в Notion.")
        summary = guard.summary()
        print(f"writes attempted: {summary['writes_attempted']}")
        print(f"writes blocked: {summary['writes_blocked']}")
        print(f"writes completed: {summary['writes_completed']}")

    if args.write_smoke:
        if not (settings.notion_token and settings.notion_system_issues_database_id and settings.notion_improvements_database_id):
            print("LIVE_SMOKE_FAILED write smoke is blocked: Notion credentials/databases are not configured")
            return 2
        print("LIVE_SMOKE_FAILED write smoke requires a live Telegram/Notion pilot step and is not run automatically")
        return 2

    print("LIVE_SMOKE_COMPLETED")
    return 0


def _print_results(results: list[object]) -> None:
    for item in results:
        print(f"{item.integration}: {'OK' if item.valid else 'ERROR'}")
        for error in item.errors:
            print(f"- {error}")
        for warning in item.warnings:
            print(f"- warning: {warning}")


if __name__ == "__main__":
    raise SystemExit(main())

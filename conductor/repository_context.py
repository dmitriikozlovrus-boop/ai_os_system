from __future__ import annotations

from pathlib import Path

from .models import ImprovementSummary, SystemIssueSummary


ALLOWED_SUFFIXES = {".py", ".md", ".yaml", ".yml", ".json", ".toml"}
EXCLUDED_DIRS = {".git", "venv", ".venv", "node_modules", "__pycache__", "data"}
EXCLUDED_NAMES = {".env", ".env.example.local", "interactions.json", "pending.json", "recent.json"}
MAX_FILES = 8
MAX_BYTES = 120 * 1024
MAX_LINES_PER_FILE = 300


class RepositoryContextProvider:
    def __init__(self, root: str | Path = "."):
        self.root = Path(root).resolve()

    def get_repository_map(self) -> list[str]:
        paths = []
        for path in self.root.rglob("*"):
            if not path.is_file() or not _allowed_path(path, self.root):
                continue
            paths.append(path.relative_to(self.root).as_posix())
            if len(paths) >= 400:
                break
        return sorted(paths)

    def find_relevant_files(
        self,
        *,
        improvement: ImprovementSummary,
        issues: list[SystemIssueSummary],
    ) -> list[str]:
        repo_map = set(self.get_repository_map())
        candidates = []
        candidates.extend(_seed_paths_for_improvement(improvement))
        text = " ".join(
            [
                improvement.title,
                improvement.improvement_type,
                improvement.change_location,
                *(issue.title for issue in issues),
                *(issue.database for issue in issues),
                *(issue.issue_type for issue in issues),
            ]
        ).casefold()
        if "goods" in text or "buy" in text or "товар" in text or "покуп" in text:
            candidates.extend(["conductor/openai_client.py", "conductor/models.py", "tests/test_models.py"])
        if "notion" in text or "баз" in text or improvement.change_location == "Notion":
            candidates.extend(["conductor/notion_client.py", "tests/test_notion_client.py"])
        if "telegram" in text:
            candidates.extend(["conductor/service.py", "conductor/telegram.py"])

        result = []
        for path in candidates:
            if path in repo_map and path not in result:
                result.append(path)
            if len(result) >= MAX_FILES:
                break
        return result

    def read_candidate_files(self, paths: list[str], *, max_files: int = MAX_FILES) -> dict[str, str]:
        result: dict[str, str] = {}
        total = 0
        for relative in paths:
            if len(result) >= max_files:
                break
            path = (self.root / relative).resolve()
            if not _allowed_path(path, self.root) or not path.exists() or not path.is_file():
                continue
            data = path.read_bytes()
            if total + len(data) > MAX_BYTES:
                data = data[: max(0, MAX_BYTES - total)]
            text = data.decode("utf-8", errors="replace")
            lines = text.splitlines()[:MAX_LINES_PER_FILE]
            content = "\n".join(lines)
            result[relative] = content
            total += len(content.encode("utf-8"))
            if total >= MAX_BYTES:
                break
        return result


def _seed_paths_for_improvement(improvement: ImprovementSummary) -> list[str]:
    if improvement.improvement_type == "Правило":
        return ["knowledge", "docs", "conductor/openai_client.py", "conductor/models.py", "tests/test_models.py"]
    if improvement.improvement_type == "Промпт":
        return ["conductor/openai_client.py", "knowledge", "tests/test_models.py"]
    if improvement.improvement_type == "Архитектура":
        return ["conductor/service.py", "conductor/models.py", "docs/architecture", "docs/product/use_cases"]
    if improvement.improvement_type == "Поля базы":
        return ["conductor/notion_client.py", "conductor/models.py", "tests/test_notion_client.py", "docs/services/conductor"]
    if improvement.improvement_type == "Интеграция":
        return ["conductor/notion_client.py", "conductor/config.py", "conductor/service.py", "render.yaml", ".env.example", "tests/test_notion_client.py"]
    if improvement.improvement_type == "Автоматизация":
        return ["conductor/service.py", "conductor/interactions.py", "conductor/config.py", "docs/services/conductor", "tests"]
    return ["conductor/service.py", "conductor/models.py", "tests"]


def _allowed_path(path: Path, root: Path) -> bool:
    try:
        relative = path.resolve().relative_to(root)
    except ValueError:
        return False
    if any(part in EXCLUDED_DIRS for part in relative.parts):
        return False
    if path.name in EXCLUDED_NAMES:
        return False
    if path.suffix not in ALLOWED_SUFFIXES:
        return False
    if path.suffix == ".json" and any(part in {"data", "tmp"} for part in relative.parts):
        return False
    return True

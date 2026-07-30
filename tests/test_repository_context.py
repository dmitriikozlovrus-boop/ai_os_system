import os
import unittest
from tempfile import TemporaryDirectory

from conductor.models import ImprovementSummary, SystemIssueSummary
from conductor.repository_context import RepositoryContextProvider


class RepositoryContextProviderTest(unittest.TestCase):
    def _write(self, root, path, content="x"):
        full = os.path.join(root, path)
        directory = os.path.dirname(full)
        if directory:
            os.makedirs(directory, exist_ok=True)
        with open(full, "w", encoding="utf-8") as file:
            file.write(content)

    def _improvement(self, improvement_type="Правило", change_location="Правила Дирижёра"):
        return ImprovementSummary(
            page_id="imp",
            url="imp-url",
            title="Уточнить Goods",
            status="Идея",
            improvement_type=improvement_type,
            change_location=change_location,
            related_issue_urls=[],
        )

    def _issue(self):
        return SystemIssueSummary(
            page_id="issue",
            url="issue-url",
            title="Покрышка попала в Study",
            issue_type="Неверная классификация",
            severity="Средняя",
            database="BUY",
            input_data="Купить покрышку",
            description="Фактический результат Study, ожидаемый Goods",
            solution="Исправить правило",
            detected_date="2026-07-30",
        )

    def test_repository_map_excludes_secrets_runtime_and_heavy_dirs(self):
        with TemporaryDirectory() as tmp:
            self._write(tmp, "conductor/service.py")
            self._write(tmp, ".env", "SECRET=1")
            self._write(tmp, "data/interactions.json", "{}")
            self._write(tmp, "node_modules/pkg/index.js", "x")

            repo = RepositoryContextProvider(tmp)

            self.assertEqual(repo.get_repository_map(), ["conductor/service.py"])

    def test_find_relevant_files_returns_existing_candidates_only(self):
        with TemporaryDirectory() as tmp:
            self._write(tmp, "conductor/openai_client.py")
            self._write(tmp, "conductor/models.py")
            self._write(tmp, "tests/test_models.py")
            repo = RepositoryContextProvider(tmp)

            files = repo.find_relevant_files(improvement=self._improvement(), issues=[self._issue()])

            self.assertEqual(files, ["conductor/openai_client.py", "conductor/models.py", "tests/test_models.py"])

    def test_read_candidate_files_respects_file_count_and_line_limit(self):
        with TemporaryDirectory() as tmp:
            for index in range(10):
                self._write(tmp, f"f{index}.py", "\n".join(str(i) for i in range(400)))
            repo = RepositoryContextProvider(tmp)

            content = repo.read_candidate_files([f"f{index}.py" for index in range(10)], max_files=8)

            self.assertEqual(len(content), 8)
            self.assertLessEqual(max(len(value.splitlines()) for value in content.values()), 300)

    def test_nonexistent_candidate_files_are_not_read(self):
        with TemporaryDirectory() as tmp:
            self._write(tmp, "conductor/service.py")
            repo = RepositoryContextProvider(tmp)

            content = repo.read_candidate_files(["missing.py", "conductor/service.py"])

            self.assertEqual(set(content), {"conductor/service.py"})


if __name__ == "__main__":
    unittest.main()

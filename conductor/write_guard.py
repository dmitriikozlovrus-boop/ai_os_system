from __future__ import annotations


class ProductionWriteBlocked(RuntimeError):
    def __init__(self, operation: str):
        super().__init__(f"Dry-run blocks Notion write: {operation}")
        self.operation = operation


class ProductionWriteGuard:
    def __init__(self, *, dry_run: bool):
        self.dry_run = dry_run
        self.writes_attempted = 0
        self.writes_blocked = 0
        self.writes_completed = 0

    def assert_write_allowed(self, operation: str) -> None:
        self.writes_attempted += 1
        if self.dry_run:
            self.writes_blocked += 1
            print(f"BACKLOG_DRY_RUN_WRITE_BLOCKED operation={operation}", flush=True)
            raise ProductionWriteBlocked(operation)

    def record_completed(self) -> None:
        self.writes_completed += 1

    def summary(self) -> dict[str, int]:
        return {
            "writes_attempted": self.writes_attempted,
            "writes_blocked": self.writes_blocked,
            "writes_completed": self.writes_completed,
        }

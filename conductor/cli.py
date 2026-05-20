from __future__ import annotations

import json
import sys

from .config import get_settings
from .service import ConductorService


def main() -> None:
    text = " ".join(sys.argv[1:]).strip()
    if not text:
        print("Usage: python3 -m conductor.cli '<message>'")
        raise SystemExit(2)
    service = ConductorService(get_settings())
    result = service.process_text(text, chat_id=None, source="CLI")
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()

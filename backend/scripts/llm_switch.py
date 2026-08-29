"""Toggle all LLM features globally.

    docker compose -f docker-compose.prod.yml exec backend \\
        python -m scripts.llm_switch off
    ... python -m scripts.llm_switch on
    ... python -m scripts.llm_switch status
"""

import sys

from app.database import SessionLocal
from app.llm.switch import llm_features_enabled, set_llm_features_enabled


def _main() -> None:
    cmd = sys.argv[1] if len(sys.argv) > 1 else "status"
    db = SessionLocal()
    try:
        if cmd == "on":
            set_llm_features_enabled(db, True)
        elif cmd == "off":
            set_llm_features_enabled(db, False)
        elif cmd != "status":
            print("usage: python -m scripts.llm_switch {on|off|status}")
            return
        print("LLM features:", "ON" if llm_features_enabled(db) else "OFF")
    finally:
        db.close()


if __name__ == "__main__":
    _main()

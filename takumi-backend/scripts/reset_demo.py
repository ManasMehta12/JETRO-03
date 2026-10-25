import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from sqlalchemy.orm import Session  # noqa: E402

from app.config import get_settings  # noqa: E402
from app.database import build_engine, init_db  # noqa: E402
from app.services import media_service  # noqa: E402
from app.services.seed_service import reset_demo  # noqa: E402


def main():
    parser = argparse.ArgumentParser(description="Replace only illustrative task_001 data.")
    parser.add_argument("--state", choices=["fresh", "approved_baseline"], default="fresh")
    parser.add_argument("--yes", action="store_true")
    args = parser.parse_args()
    if not args.yes:
        parser.error("--yes is required to reset demo data")
    settings = get_settings()
    if settings.app_env == "production" or not settings.demo_mode:
        parser.error("reset requires DEMO_MODE=true outside production")
    engine = build_engine(settings)
    try:
        init_db(engine)
        with Session(engine) as session, session.begin():
            storage_keys = reset_demo(session, args.state)
        media_service.remove_stored_files(settings, storage_keys)
        print(f"reset to {args.state}")
    finally:
        engine.dispose()


if __name__ == "__main__":
    main()

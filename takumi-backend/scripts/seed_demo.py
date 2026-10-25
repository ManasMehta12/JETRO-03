import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from sqlalchemy.orm import Session  # noqa: E402

from app.config import get_settings  # noqa: E402
from app.database import build_engine, init_db  # noqa: E402
from app.services.seed_service import seed_demo  # noqa: E402


def main():
    parser = argparse.ArgumentParser(description="Seed illustrative demo without replacing edits.")
    parser.add_argument(
        "--state", choices=["fresh", "approved_baseline"], default="approved_baseline"
    )
    args = parser.parse_args()
    engine = build_engine(get_settings())
    try:
        init_db(engine)
        with Session(engine) as session, session.begin():
            created = seed_demo(session, args.state)
        print("seeded" if created else "already present; nothing changed")
    finally:
        engine.dispose()


if __name__ == "__main__":
    main()

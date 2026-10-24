import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.config import get_settings  # noqa: E402
from app.services.processing_worker import run_forever  # noqa: E402


def main():
    sys.exit(run_forever(get_settings()))


if __name__ == "__main__":
    main()

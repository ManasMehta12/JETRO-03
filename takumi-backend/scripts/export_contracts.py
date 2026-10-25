import json
import sys
from pathlib import Path
from tempfile import TemporaryDirectory

BACKEND = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND))

from fastapi.testclient import TestClient  # noqa: E402

from app.config import Settings  # noqa: E402
from app.main import create_app  # noqa: E402
from app.models.schemas import (  # noqa: E402
    ClarificationOut,
    JobOut,
    KnowledgeUnit,
    MediaOut,
    ReleaseOut,
    TrainingPack,
)
from scripts.demo_flow import run_flow  # noqa: E402


def redact(value):
    if isinstance(value, dict):
        return {
            key: "<token>" if key == "access_token" else redact(item) for key, item in value.items()
        }
    if isinstance(value, list):
        return [redact(item) for item in value]
    return value


def main():
    contracts = BACKEND / "contracts"
    examples = contracts / "api-examples"
    examples.mkdir(parents=True, exist_ok=True)

    def save(path, value):
        path.write_text(json.dumps(redact(value), indent=2) + "\n")

    count = 0

    def record(name, method, path, body, status, response):
        nonlocal count
        count += 1
        save(
            examples / f"{count:02}-{name}.json",
            {
                "request": {"method": method, "path": path, "body": body},
                "response": {"status": status, "body": response},
            },
        )

    with TemporaryDirectory() as directory:
        app = create_app(
            Settings(
                _env_file=None,
                database_url=f"sqlite:///{directory}/contracts.db",
                demo_signing_secret="contract-export",
            )
        )
        save(contracts / "openapi.json", app.openapi())
        for name, model in (
            ("knowledge-unit", KnowledgeUnit),
            ("clarification", ClarificationOut),
            ("release", ReleaseOut),
            ("training-pack", TrainingPack),
            ("media", MediaOut),
            ("processing-job", JobOut),
        ):
            save(contracts / f"{name}.json", model.model_json_schema())
        with TestClient(app) as client:
            run_flow(client, record)
    assert count == 16
    print("Exported OpenAPI, six schemas and 16 API examples.")


if __name__ == "__main__":
    main()

import threading

from app.core.errors import AppError
from app.services import knowledge_service


def test_concurrent_draft_writes_yield_one_success_and_one_revision_conflict(client):
    sessionmaker = client.app.state.sessionmaker
    both_started = threading.Barrier(2, timeout=5)
    outcomes = []

    def writer(actor):
        try:
            with sessionmaker() as session, session.begin():
                both_started.wait()
                draft = knowledge_service.get_draft(session, "task_001")
                threading.Event().wait(0.2)  # overlap the read and the write of both writers
                knowledge_service.bump_draft(session, draft, 1, draft.knowledge_units, actor, "t")
            outcomes.append("ok")
        except AppError as exc:
            outcomes.append(exc.code)
        except Exception as exc:
            outcomes.append(type(exc).__name__)

    threads = [threading.Thread(target=writer, args=(actor,)) for actor in ("a", "b")]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()

    assert sorted(outcomes) == ["REVISION_CONFLICT", "ok"]

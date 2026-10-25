import argparse
import json
import sys
import time
from pathlib import Path
from uuid import uuid4

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import httpx  # noqa: E402


def run_flow(
    client,
    video: Path,
    mode: str,
    timeout: float,
    answer: str | None = None,
    question: str | None = None,
) -> None:
    headers = {}

    def request(method, path, **kwargs):
        response = client.request(method, f"/api/v1{path}", headers=headers, **kwargs)
        response.raise_for_status()
        return response

    login = request("POST", "/auth/demo-login", json={"demo_user": "expert"}).json()
    headers["Authorization"] = f"Bearer {login['access_token']}"
    task = request(
        "POST",
        "/tasks",
        json={"title": video.stem, "equipment": "Demonstration bench", "language": "en"},
    ).json()
    task_id = task["id"]
    with video.open("rb") as source:
        media = request(
            "POST", f"/tasks/{task_id}/media", files={"file": (video.name, source, "video/mp4")}
        ).json()
    media_id = media["media_id"]
    print(f"media_id={media_id}", flush=True)
    media = request("GET", f"/media/{media_id}").json()
    print(f"duration_ms={media['duration_ms']}", flush=True)
    response = client.get(media["playback_url"], headers={"Range": "bytes=0-1023"})
    response.raise_for_status()
    assert response.status_code == 206, (response.status_code, response.text)
    print("range=206", flush=True)
    print(f"playback={client.base_url.join(media['playback_url'])}", flush=True)
    job = request(
        "POST",
        f"/tasks/{task_id}/process",
        json={"media_id": media_id, "mode": mode, "request_id": f"video_flow_{uuid4().hex[:8]}"},
    ).json()
    print(f"job_id={job['job_id']}", flush=True)
    started = time.monotonic()
    deadline = started + timeout
    previous = None
    while True:
        state = (job["stage"], job["status"])
        if state != previous:
            print(
                f"t={time.monotonic() - started:.0f}s stage={state[0]} status={state[1]}",
                flush=True,
            )
            previous = state
        if job["status"] == "failed":
            raise RuntimeError(json.dumps(job["error"]))
        if job["status"] == "completed":
            break
        remaining = deadline - time.monotonic()
        if remaining <= 0:
            raise TimeoutError(f"Timed out waiting for job {job['job_id']}")
        time.sleep(min(2, remaining))
        job = request("GET", f"/jobs/{job['job_id']}").json()
    draft = request("GET", f"/tasks/{task_id}/draft").json()
    print(f"knowledge_units={len(draft['knowledge_units'])}")
    evidence_items = {}
    for unit in draft["knowledge_units"]:
        intervals = []
        for evidence_id in unit["evidence_ids"]:
            evidence = request("GET", f"/evidence/{evidence_id}").json()
            evidence_items[evidence_id] = evidence
            if evidence["type"] == "video_segment":
                intervals.append(f"{evidence['start_ms']}-{evidence['end_ms']} ms")
        print(f"{unit['id']}: {unit['action']} | evidence: {', '.join(intervals) or 'none'}")
    if answer is None:
        return

    response = client.get(media["playback_url"])
    response.raise_for_status()
    assert response.status_code == 200, (response.status_code, response.text)
    print("playback=200", flush=True)
    for evidence in evidence_items.values():
        if evidence["type"] == "video_segment":
            assert evidence["media_id"] == media_id, evidence
            assert 0 <= evidence["start_ms"] < evidence["end_ms"] <= media["duration_ms"], evidence
    print(f"warnings={json.dumps(job['warnings'])}", flush=True)
    unsupported = sum(not unit["evidence_ids"] for unit in draft["knowledge_units"])
    print(f"units_without_evidence={unsupported} (flagged for review)", flush=True)
    for gap in draft["clarifications"]:
        print(f"{gap['id']} {gap['gap_type']} {gap['question']}", flush=True)
    pending = [gap for gap in draft["clarifications"] if gap["status"] == "pending"]
    if not pending:
        raise RuntimeError("No pending clarification to answer during acceptance run")
    clarification = pending[0]
    unit = next(
        unit
        for unit in draft["knowledge_units"]
        if unit["id"] == clarification["knowledge_unit_id"]
    )
    result = request(
        "POST",
        f"/clarifications/{clarification['id']}/respond",
        json={
            "expected_draft_revision": draft["revision"],
            "disposition": "answered",
            "answer": answer,
            "knowledge_update": {
                "knowledge_unit_id": unit["id"],
                "fields": {"interpretation": answer},
            },
        },
    ).json()
    expert_evidence_id = result["evidence_id"]
    evidence = request("GET", f"/evidence/{expert_evidence_id}").json()
    assert evidence["type"] == "expert_response", evidence
    print(f"expert_response={expert_evidence_id}", flush=True)
    revision = result["draft_revision"]
    for gap in pending[1:]:
        result = request(
            "POST",
            f"/clarifications/{gap['id']}/respond",
            json={
                "expected_draft_revision": revision,
                "disposition": "deferred",
                "answer": "Deferred during acceptance run.",
            },
        ).json()
        revision = result["draft_revision"]
    evaluation = request(
        "POST",
        f"/studio/tasks/{task_id}/evaluate",
        json={"expected_revision": revision},
    ).json()
    if not evaluation["passed"]:
        print(f"evaluation_issues={json.dumps(evaluation['issues'])}", flush=True)
        raise RuntimeError("Evaluation failed: review flagged units before publishing")
    login = request("POST", "/auth/demo-login", json={"demo_user": "reviewer"}).json()
    headers["Authorization"] = f"Bearer {login['access_token']}"
    response = request(
        "POST",
        f"/tasks/{task_id}/publish",
        json={
            "expected_revision": revision,
            "approval_note": "Reviewed during V2 acceptance run.",
        },
    )
    assert response.status_code == 201, (response.status_code, response.text)
    release_id = response.json()["release_id"]
    release = request("GET", f"/releases/{release_id}").json()
    assert release["id"] == release_id, release
    pack = request("GET", f"/releases/{release_id}/training-pack").json()
    assert expert_evidence_id in {item["id"] for item in pack["evidence_items"]}, pack
    login = request("POST", "/auth/demo-login", json={"demo_user": "apprentice"}).json()
    headers["Authorization"] = f"Bearer {login['access_token']}"
    action = unit["action"]
    supported = request(
        "POST",
        f"/tasks/{task_id}/ask",
        json={"question": question or f"Why do you {action[0].lower()}{action[1:]}?"},
    ).json()
    assert supported["status"] == "answered", supported
    assert any(expert_evidence_id in claim["evidence_ids"] for claim in supported["claims"]), (
        supported
    )
    print(f"supported_question={supported['status']}", flush=True)
    unsupported_answer = request(
        "POST",
        f"/tasks/{task_id}/ask",
        json={"question": "What is the torque specification for this task?"},
    ).json()
    assert unsupported_answer["status"] == "insufficient_evidence", unsupported_answer
    print(f"unsupported_question={unsupported_answer['status']}", flush=True)
    print(f"release_id={release_id}", flush=True)
    print("acceptance=ok", flush=True)


def main() -> int:
    parser = argparse.ArgumentParser(description="Upload a recording and poll its extraction job.")
    parser.add_argument("--base-url", default="http://localhost:8000")
    parser.add_argument("--video", type=Path, required=True)
    parser.add_argument("--mode", choices=("live", "demo"), default="live")
    parser.add_argument("--answer", help="Expert answer; continue through full acceptance flow.")
    parser.add_argument("--question", help="Supported apprentice question for the acceptance flow.")
    parser.add_argument(
        "--timeout", type=float, default=600, help="Job polling timeout in seconds."
    )
    args = parser.parse_args()
    if args.timeout <= 0:
        parser.error("--timeout must be positive")
    try:
        with httpx.Client(base_url=args.base_url, timeout=30) as client:
            run_flow(client, args.video, args.mode, args.timeout, args.answer, args.question)
    except httpx.HTTPStatusError as error:
        print(f"HTTP {error.response.status_code}: {error.response.text}", file=sys.stderr)
        return 1
    except (httpx.RequestError, OSError, RuntimeError, AssertionError) as error:
        print(str(error), file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())

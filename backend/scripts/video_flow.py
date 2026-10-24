import argparse
import json
import sys
import time
from pathlib import Path
from uuid import uuid4

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import httpx  # noqa: E402


def run_flow(client, video: Path, mode: str, timeout: float) -> None:
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
    job = request(
        "POST",
        f"/tasks/{task_id}/process",
        json={"media_id": media_id, "mode": mode, "request_id": f"video_flow_{uuid4().hex[:8]}"},
    ).json()
    print(f"job_id={job['job_id']}", flush=True)
    deadline = time.monotonic() + timeout
    previous = None
    while True:
        state = (job["stage"], job["status"])
        if state != previous:
            print(f"stage={state[0]} status={state[1]}", flush=True)
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
    for unit in draft["knowledge_units"]:
        intervals = []
        for evidence_id in unit["evidence_ids"]:
            evidence = request("GET", f"/evidence/{evidence_id}").json()
            if evidence["type"] == "video_segment":
                intervals.append(f"{evidence['start_ms']}-{evidence['end_ms']} ms")
        print(f"{unit['id']}: {unit['action']} | evidence: {', '.join(intervals) or 'none'}")


def main() -> int:
    parser = argparse.ArgumentParser(description="Upload a recording and poll its extraction job.")
    parser.add_argument("--base-url", default="http://localhost:8000")
    parser.add_argument("--video", type=Path, required=True)
    parser.add_argument("--mode", choices=("live", "demo"), default="live")
    parser.add_argument(
        "--timeout", type=float, default=600, help="Job polling timeout in seconds."
    )
    args = parser.parse_args()
    if args.timeout <= 0:
        parser.error("--timeout must be positive")
    try:
        with httpx.Client(base_url=args.base_url, timeout=30) as client:
            run_flow(client, args.video, args.mode, args.timeout)
    except httpx.HTTPStatusError as error:
        print(f"HTTP {error.response.status_code}: {error.response.text}", file=sys.stderr)
        return 1
    except (httpx.RequestError, OSError, RuntimeError, AssertionError) as error:
        print(str(error), file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())

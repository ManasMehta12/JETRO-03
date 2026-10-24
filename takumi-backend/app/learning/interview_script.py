"""Build an auditable interview from an immutable, approved release only."""

import hashlib
import json

from app.core.errors import AppError


def build_script(release):
    evidence = {item["id"] for item in release.evidence_snapshot}
    units = release.knowledge_snapshot
    if not units:
        raise AppError("COURSE_RELEASE_UNAVAILABLE", "The release has no training knowledge.", 409)

    def statements(fields):
        return "\n".join(
            f"{unit['id']} — {field}: {unit[field]}"
            for unit in units
            for field in fields
            if unit.get(field)
        )

    # Include every published field in the source brief. A tutor correction therefore
    # changes both the generated script and its hash before any interview begins.
    brief = statements(("action", "cue", "interpretation", "decision", "exception"))
    references = sorted({ref for unit in units for ref in unit.get("evidence_ids", [])} & evidence)

    # Cover every published unit in the visible answer choices. In particular a
    # correction to a later unit must affect what the apprentice is assessed on.
    def summarize(fields):
        return " ".join(
            f"{unit['id']}: " + "; ".join(str(unit[field]) for field in fields if unit.get(field))
            for unit in units
            if any(unit.get(field) for field in fields)
        )

    correct = (
        summarize(("action",)) + " Record the observation for each check.",
        summarize(("cue", "interpretation", "decision"))
        or "Seek clarification; no observation or decision is specified.",
        (summarize(("exception",)) or "Seek review where the release is silent.")
        + " Training choices do not certify a physical assembly.",
    )
    templates = (
        ("explain-check", "How should you perform and record the checks across this release?", "b"),
        (
            "changed-condition",
            "Across the reviewed checks, how should observations affect your next decisions?",
            "b",
        ),
        ("evidence-limits", "Which exceptions and limits must you recognize?", "c"),
    )
    bank = []
    for index, (identifier, prompt, answer) in enumerate(templates):
        options = []
        for choice in ("a", "b", "c"):
            approved = choice == answer
            options.append(
                {
                    "id": choice,
                    "label": correct[index]
                    if approved
                    else (
                        "Proceed using appearance alone without consulting the published checks."
                        if choice == "a"
                        else "Assume missing information is verified and continue without review."
                    ),
                    "points": 2 if approved else 0,
                    "recognizes_limits": approved and identifier == "evidence-limits",
                    "feedback": (
                        "Supported by the published release. "
                        if approved
                        else "This choice is unsupported by the published release. "
                    )
                    + correct[index],
                    "evidence_ids": references,
                }
            )
        bank.append(
            {
                "id": identifier,
                "prompt": prompt,
                "source_context": f"Reviewed release v{release.version}:\n{brief}",
                "options": options,
            }
        )
    return {
        "bank": bank,
        "generation_method": "release_grounded_template",
        "rubric_version": 3,
        "source_release_id": release.id,
        "source_content_hash": release.content_hash,
        "bundle_hash": hashlib.sha256(json.dumps(bank, sort_keys=True).encode()).hexdigest(),
    }

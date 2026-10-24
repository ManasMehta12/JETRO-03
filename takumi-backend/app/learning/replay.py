"""Replay the authored TypeScript workshop; these rules are not physics validation."""

from app.core.errors import AppError

PARTS = ["base", "housing", "shaft", "bearing"]
TOOLS = ["alignment-jig", "bearing-sleeve", "hex-key", "handwheel"]
BOLTS = ["A", "C", "B", "D"]


def replay(actions, scenario):
    inspected, answers, placed, bolts = set(), {}, set(), []
    observation = verified = False
    held = tool = terminal = None
    alignment, depth, turns = 2, 0, 0

    def require(condition):
        if not condition:
            raise AppError(
                "INVALID_ATTEMPT", "The action log violates an exercise prerequisite.", 422
            )

    for action in actions:
        require(isinstance(action, str) and terminal is None)
        if action.startswith("inspect-"):
            part = action[8:]
            require(part in PARTS and part not in inspected)
            inspected.add(part)
        elif action == "record-observation":
            require(len(inspected) == 4 and not observation)
            observation = True
        elif action.startswith("answer:"):
            pieces = action.split(":")
            require(len(pieces) == 3)
            _, question, option = pieces
            require(question in ("q1", "q2", "q3") and option in ("a", "b", "c"))
            require(question not in answers)
            answers[question] = option
        elif action.startswith("workshop:"):
            require(observation and not verified)
            step = action[9:]
            if step.startswith("pick:"):
                part = step[5:]
                require(part in PARTS and part not in placed and held != part)
                held = part
            elif step.startswith("tool:"):
                chosen = step[5:]
                require(chosen in TOOLS and chosen != tool)
                tool = chosen
            elif step.startswith("place:"):
                part = step[6:]
                require(part in PARTS and part not in placed and held == part)
                require(all(p in placed for p in PARTS[: PARTS.index(part)]))
                if part == "shaft":
                    require(tool == "alignment-jig" and alignment == 0)
                if part == "bearing":
                    require(tool == "bearing-sleeve")
                placed.add(part)
                held = None
            elif step in ("adjust:left", "adjust:right"):
                require(tool == "alignment-jig" and "housing" in placed and "shaft" not in placed)
                alignment += -1 if step == "adjust:left" else 1
                require(-2 <= alignment <= 2)
            elif step == "press":
                require(tool == "bearing-sleeve" and "bearing" in placed and depth < 3)
                depth += 1
            elif step.startswith("tighten:"):
                require(tool == "hex-key" and depth == 3 and len(bolts) < 4)
                require(step[8:] == BOLTS[len(bolts)])
                bolts.append(step[8:])
            elif step == "turn":
                require(tool == "handwheel" and len(bolts) == 4 and turns < 3)
                turns += 1
            elif step == "verify":
                require(len(placed) == 4 and alignment == 0 and depth == 3)
                require(bolts == BOLTS and turns == 3)
                verified = True
            else:
                require(False)
        elif action in ("continue", "escalate"):
            require(verified and len(answers) == 3)
            terminal = action
        else:
            require(False)
    require(terminal is not None)
    critical = terminal == "continue" and scenario == "uncertain"
    judgment = 100 if terminal == ("continue" if scenario == "standard" else "escalate") else 60
    if critical:
        judgment = 0
    outcome = (
        "Unsupported release: unresolved fit evidence required escalation."
        if critical
        else "Supported release: all authored checks were recorded."
        if terminal == "continue"
        else "Supported escalation: unresolved evidence was preserved for review."
        if scenario == "uncertain"
        else "Conservative escalation: the authored evidence supported release."
    )
    correct = {"q1": "b", "q2": "b", "q3": "c"}
    return {
        "scores": {
            "procedure": 100,
            "judgment": judgment,
            "knowledge": round(100 * sum(answers[q] == correct[q] for q in correct) / 3),
        },
        "critical_error": critical,
        "outcome": outcome,
    }

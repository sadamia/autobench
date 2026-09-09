#!/usr/bin/env python3
"""Mine real invocation windows for a skill from Claude Code session transcripts.

An invocation window is: the user ask that preceded the invocation, the
invocation turn itself, and the turns that followed -- because that trailing
region is where user corrections live, and a correction is the gold signal.

Usage:
    python3 mine_invocations.py <skill-name> [options]

    --projects DIR   transcript root (default: ~/.claude/projects)
    --after N        turns to keep after the invocation (default: 4)
    --before N       turns to keep before the invocation (default: 2)
    --json           emit raw JSON windows instead of the human report
    --triggers "a,b" extra phrases that also count as an invocation signal

Exit codes:
    0  windows found
    3  no windows found (fail-closed: caller must emit a no-history report)
    4  transcript root does not exist
"""

import argparse
import json
import os
import re
import sys
from pathlib import Path

# Phrases a user reaches for when the previous turn got it wrong. Presence in a
# post-invocation user turn promotes that window to a correction (gold signal).
CORRECTION_MARKERS = [
    "no,", "nope", "that's not", "thats not", "not what i", "wrong",
    "actually,", "instead", "i said", "i asked for", "don't", "dont ",
    "stop", "revert", "undo", "you missed", "you forgot", "again,",
    "incorrect", "isn't right", "isnt right", "not right", "fix that",
    "try again", "redo", "why did you", "i wanted",
]


def iter_transcripts(root: Path):
    """Yield (project_slug, jsonl_path) for every session transcript."""
    for path in sorted(root.glob("*/*.jsonl")):
        yield path.parent.name, path


def load_turns(path: Path):
    """Flatten one transcript into ordered conversational turns.

    Returns a list of dicts: {i, role, text, tools, uuid, timestamp}.
    Non-conversational record types (bridge-session, queue-operation,
    attachment, snapshots) are skipped -- they carry no usage evidence.
    """
    turns = []
    with path.open("r", encoding="utf-8", errors="replace") as fh:
        for line in fh:
            line = line.strip()
            if not line:
                continue
            try:
                rec = json.loads(line)
            except json.JSONDecodeError:
                continue
            if rec.get("type") not in ("user", "assistant"):
                continue
            msg = rec.get("message") or {}
            content = msg.get("content")
            text_parts, tools = [], []
            if isinstance(content, str):
                text_parts.append(content)
            elif isinstance(content, list):
                for block in content:
                    if not isinstance(block, dict):
                        continue
                    btype = block.get("type")
                    if btype == "text":
                        text_parts.append(block.get("text", ""))
                    elif btype == "tool_use":
                        tools.append({
                            "name": block.get("name", ""),
                            "input": block.get("input", {}),
                        })
                    elif btype == "tool_result":
                        # Tool results are echoed context, not user intent.
                        continue
            turns.append({
                "i": len(turns),
                "role": rec.get("type"),
                "text": "\n".join(p for p in text_parts if p).strip(),
                "tools": tools,
                "uuid": rec.get("uuid"),
                "timestamp": rec.get("timestamp"),
            })
    return turns


def invocation_signal(turn, skill, triggers):
    """Classify how strongly this turn indicates the skill actually ran.

    Returns (strength, how) or None. Strength "strong" means the harness
    recorded an invocation; "weak" means the name merely appeared in prose and
    the window needs human confirmation before it grounds a case.
    """
    for tool in turn["tools"]:
        if tool["name"] == "Skill":
            invoked = str(tool["input"].get("skill", ""))
            # Plugin skills are addressed as "plugin:skill".
            if invoked == skill or invoked.endswith(":" + skill):
                return "strong", f"Skill tool -> {invoked}"
        if tool["name"] == "Task":
            sub = str(tool["input"].get("subagent_type", ""))
            if sub == skill:
                return "strong", f"Agent tool -> {sub}"

    text = turn["text"]
    if not text:
        return None
    low = text.lower()

    # Slash-command invocations are recorded as a <command-name> envelope.
    m = re.search(r"<command-name>\s*/?([\w:-]+)\s*</command-name>", text)
    if m and (m.group(1) == skill or m.group(1).endswith(":" + skill)):
        return "strong", "slash command"

    if re.search(r"(?<![\w/])/" + re.escape(skill) + r"(?![\w-])", text):
        return "strong", "slash command (inline)"

    for phrase in triggers:
        if phrase and phrase.lower() in low:
            return "weak", f"trigger phrase: {phrase!r}"

    if re.search(r"(?<![\w-])" + re.escape(skill) + r"(?![\w-])", low):
        return "weak", "skill name mentioned"

    return None


def is_correction(turn):
    if turn["role"] != "user" or not turn["text"]:
        return False
    low = turn["text"].lower()
    return any(marker in low for marker in CORRECTION_MARKERS)


def build_window(turns, idx, before, after, project, path, strength, how):
    lo = max(0, idx - before)
    hi = min(len(turns), idx + after + 1)
    slice_ = turns[lo:hi]

    ask = None
    for t in reversed(turns[lo:idx]):
        if t["role"] == "user" and t["text"]:
            ask = t["text"]
            break

    corrections = [t["text"] for t in turns[idx + 1:hi] if is_correction(t)]

    return {
        "project": project,
        "session": path.stem,
        "turn_index": idx,
        "timestamp": turns[idx].get("timestamp"),
        "signal": strength,
        "matched_by": how,
        "preceding_ask": ask,
        "corrections": corrections,
        "is_gold": bool(corrections),
        "turns": [
            {"role": t["role"], "text": t["text"][:2000],
             "tools": [x["name"] for x in t["tools"]]}
            for t in slice_
        ],
    }


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("skill")
    ap.add_argument("--projects", default=os.path.expanduser("~/.claude/projects"))
    ap.add_argument("--before", type=int, default=2)
    ap.add_argument("--after", type=int, default=4)
    ap.add_argument("--json", action="store_true")
    ap.add_argument("--triggers", default="")
    args = ap.parse_args()

    root = Path(args.projects).expanduser()
    if not root.is_dir():
        print(f"transcript root not found: {root}", file=sys.stderr)
        return 4

    triggers = [t.strip() for t in args.triggers.split(",") if t.strip()]

    windows, scanned_files, scanned_turns = [], 0, 0
    for project, path in iter_transcripts(root):
        scanned_files += 1
        turns = load_turns(path)
        scanned_turns += len(turns)
        for turn in turns:
            sig = invocation_signal(turn, args.skill, triggers)
            if sig:
                windows.append(build_window(turns, turn["i"], args.before,
                                            args.after, project, path, *sig))

    substrate = {
        "transcript_root": str(root),
        "transcript_files": scanned_files,
        "turns_scanned": scanned_turns,
        "windows": len(windows),
        "strong_windows": sum(1 for w in windows if w["signal"] == "strong"),
        "corrections": sum(1 for w in windows if w["is_gold"]),
    }

    if args.json:
        print(json.dumps({"substrate": substrate, "windows": windows}, indent=2))
    else:
        print(f"substrate: {json.dumps(substrate)}")
        if not windows:
            print(f"\nNO HISTORY for skill {args.skill!r}.")
            print("Emit an honest no-history report. Do NOT invent invocations.")
        for w in windows:
            gold = "  [GOLD: correction follows]" if w["is_gold"] else ""
            print(f"\n--- {w['project']}/{w['session']} turn {w['turn_index']} "
                  f"({w['signal']}: {w['matched_by']}){gold}")
            if w["preceding_ask"]:
                print(f"  ask: {w['preceding_ask'][:300]}")
            for c in w["corrections"]:
                print(f"  correction: {c[:300]}")

    return 0 if windows else 3


if __name__ == "__main__":
    sys.exit(main())

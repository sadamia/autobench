#!/usr/bin/env python3
"""Assert that a multi-model judging panel was actually a panel.

The silent failure: a model-id normalizer strips provider prefixes, every
"different model" call lands on the same host, and a "3-frontier consensus"
turns out to be one model's opinion in a trench coat. The aggregate score
looks fine. It is worthless.

This is pure assertion logic over a result object that already exists. It
never calls a model: no network, no cost.

Usage:
    python3 check_panel_integrity.py <receipt.json>
    cat receipt.json | python3 check_panel_integrity.py -

Input: JSON with a list of panel slots under "panel", "judges", "models" or
"responses" (or a bare top-level list). Each slot may carry:
    model / model_id / name      -- the model the slot claims to be
    provider / endpoint / base_url / host  -- where it actually went
    response / output / text / content     -- what came back

Exit codes:
    0  panel integrity holds
    1  integrity violated -- do not trust the aggregate
    2  malformed input (treated as INCONCLUSIVE, never as a pass)
"""

import hashlib
import json
import sys

SLOT_KEYS = ("panel", "judges", "models", "responses", "slots", "results")
MODEL_KEYS = ("model", "model_id", "modelId", "name", "id")
PROVIDER_KEYS = ("provider", "endpoint", "base_url", "baseUrl", "host", "api_base")
OUTPUT_KEYS = ("response", "output", "text", "content", "completion", "answer")


def first(d, keys):
    for k in keys:
        if k in d and d[k] not in (None, ""):
            return d[k]
    return None


def extract_slots(doc):
    if isinstance(doc, list):
        return doc
    if isinstance(doc, dict):
        for key in SLOT_KEYS:
            val = doc.get(key)
            if isinstance(val, list):
                return val
            if isinstance(val, dict):
                # {"gpt-x": {...}, "claude-y": {...}}
                out = []
                for name, slot in val.items():
                    if isinstance(slot, dict):
                        slot = dict(slot)
                        slot.setdefault("model", name)
                        out.append(slot)
                return out
    return None


def norm_output(value):
    """Collapse a slot's output to comparable bytes."""
    if value is None:
        return None
    if not isinstance(value, str):
        value = json.dumps(value, sort_keys=True)
    return value.strip()


def check(doc):
    violations, notes = [], []
    slots = extract_slots(doc)
    if not slots:
        return None, ["could not locate panel slots in the receipt"]

    seen_providers, seen_hashes, names = {}, {}, []

    for idx, slot in enumerate(slots):
        if not isinstance(slot, dict):
            violations.append(f"slot {idx}: not an object")
            continue
        name = str(first(slot, MODEL_KEYS) or f"<unnamed slot {idx}>")
        names.append(name)

        # 1. Every named model must have actually returned something.
        out = norm_output(first(slot, OUTPUT_KEYS))
        if not out:
            violations.append(f"{name}: empty or missing response -- slot did not return")
            continue

        # 2. Slots must have hit distinct provider endpoints.
        provider = first(slot, PROVIDER_KEYS)
        if provider is None:
            notes.append(f"{name}: no provider/endpoint recorded -- "
                         "distinct-endpoint check cannot run for this slot")
        else:
            provider = str(provider)
            if provider in seen_providers and seen_providers[provider] != name:
                violations.append(
                    f"{name} and {seen_providers[provider]} share provider "
                    f"{provider!r} -- panel collapsed to one host")
            seen_providers.setdefault(provider, name)

        # 3. Two differently-named models returning identical bytes are one
        #    model. This catches a collapse even when provider metadata is
        #    missing or faked -- which is exactly when you need it most.
        digest = hashlib.sha256(out.encode("utf-8")).hexdigest()
        if digest in seen_hashes and seen_hashes[digest] != name:
            violations.append(
                f"{name} returned byte-identical output to "
                f"{seen_hashes[digest]} -- same model behind two names")
        seen_hashes.setdefault(digest, name)

    if len(slots) < 2:
        violations.append(f"panel has {len(slots)} slot(s); a panel needs at least 2")
    if len(set(names)) < len(names):
        violations.append("duplicate model names in the panel")

    return violations, notes


def main():
    src = sys.argv[1] if len(sys.argv) > 1 else "-"
    try:
        raw = sys.stdin.read() if src == "-" else open(src, encoding="utf-8").read()
        doc = json.loads(raw)
    except (OSError, json.JSONDecodeError) as exc:
        print(f"INCONCLUSIVE: cannot read receipt: {exc}")
        return 2

    violations, notes = check(doc)
    if violations is None:
        print("INCONCLUSIVE: " + "; ".join(notes))
        return 2

    for note in notes:
        print(f"NOTE: {note}")
    if violations:
        print("PANEL INTEGRITY VIOLATED -- do not trust the aggregate score")
        for v in violations:
            print(f"  - {v}")
        return 1

    print("PANEL OK: every slot returned, endpoints distinct, no identical outputs")
    return 0


if __name__ == "__main__":
    sys.exit(main())

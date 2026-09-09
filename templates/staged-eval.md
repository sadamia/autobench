---
skill: <name>
status: PENDING-HUMAN-APPROVAL
generated: <YYYY-MM-DD>
substrate:
  transcript_files: 0
  turns_scanned: 0
  windows: 0
  strong_windows: 0
  corrections: 0
---

# Autobench: <name> — <YYYY-MM-DD>

## Grounding

<!-- One paragraph. How much REAL history backs this eval? How many windows
     were strong vs weak? How many carried corrections? If history is thin or
     never exercised the core path, open with:
     **GROUNDING WARNING:** only N windows found, none exercised <path>. -->

## Proposed eval contract

**Goal:** <what a good run of this skill achieves, in one sentence>

**Dimensions**

| # | Dimension | Label | Evidence |
|---|-----------|-------|----------|
| 1 | <what is being measured> | HISTORY-IMPLIED | proj-slug/session/turn-N |
| 2 | <what is being measured> | SPEC-DERIVED | SKILL.md §<section> |

**Hard fails** — any one of these makes the run a failure regardless of score.

- <observed correction, generalized into a rule> (HISTORY-IMPLIED: turn-N)

## Cases

<!-- 4-8. Every case names the failure mode it exists to catch. A case that
     catches no named failure is decoration -- cut it. Entities MUST be
     placeholders: alice-example, acme-example, /path/to/project. -->

### case-01 [HISTORY-IMPLIED — proj-slug/session/turn-N]

- **input:** <the realistic ask, scrubbed onto placeholders>
- **expected_behavior:** <checkable, not vibes>
- **failure_mode_to_catch:** <the named thing that actually went wrong>

### case-02 [SPEC-DERIVED]

- **input:**
- **expected_behavior:**
- **failure_mode_to_catch:**

## Spec-vs-usage gaps

<!-- Often the most valuable section: invisible from inside the spec. -->

- Spec says <X>; users consistently ask for <Y>. (windows: ...)

## Fail-improve classification

| Case | Class | Durable fix |
|------|-------|-------------|
| case-01 | DETERMINISTIC-CODIFIABLE | <the code + permanent test that replaces the fallback> |
| case-02 | PROMPT-FIXABLE | <eval case, then optimizer run> |
| case-03 | SPEC-GAP | <decision for the human> |
| case-04 | ROUTING-MISS | <routing-eval case, not a benchmark case> |

## Human review

- [ ] Grounding claims match the cited windows
- [ ] No SPEC-DERIVED item is labeled HISTORY-IMPLIED
- [ ] All real names, companies, and paths replaced with placeholders
- [ ] Hard fails are genuinely fatal, not merely undesirable
- [ ] Approved for merge into SKILL.md by: <name>, <date>

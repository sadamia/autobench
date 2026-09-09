---
name: autobench
description: Author an eval for an existing skill from its REAL usage history instead of its spec. Mines Claude Code session transcripts for actual invocations, treats a user correction after an invocation as the gold signal, then synthesizes an eval contract plus 4-8 replayable cases, each labeled HISTORY-IMPLIED or SPEC-DERIVED, staged for human approval. Never rewrites SKILL.md. Also ships a panel-integrity check for multi-model judging. Use for "autobench <skill>", "write the eval from usage history", "synthesize an eval for this skill", "mine how this skill is actually used", "build a benchmark from my corrections", "verify the eval panel", "did all providers actually return".
---

# autobench — write the eval from lived usage

A self-improving skill needs three legs: an **eval**, a **variant generator**,
and a **replay + judge harness**. Generators and judges are everywhere. The
leg that is persistently missing is the **eval author** — someone has to
actually WRITE the eval, and a spec-derived benchmark only tests what the
skill promised, never what users actually asked for or what actually went
wrong.

This skill writes the eval from reality instead of imagination.

The core asymmetry: **a user correction following an invocation is worth more
than the entire spec.** The spec is a claim about intent. A correction is an
observed, dated, reproducible failure. Mine the corrections and the eval
writes itself.

## Pipeline

### 1. MINE — extract real invocation windows

An **invocation window** is the user ask before the invocation, the invocation
turn, and the turns after — because that trailing region is where corrections
live.

```bash
python3 scripts/mine_invocations.py <skill-name>
python3 scripts/mine_invocations.py <skill-name> --json > /tmp/windows.json
python3 scripts/mine_invocations.py <skill-name> --triggers "phrase one,phrase two"
```

The miner reads `~/.claude/projects/<project-slug>/<session>.jsonl`, the
per-project session transcripts Claude Code writes locally. Override the root
with `--projects` for another harness's store; absent stores are skipped, not
faked.

It separates two signal strengths, and the distinction is load-bearing:

- **strong** — the harness recorded an actual invocation (a `Skill` tool call,
  an agent dispatch, a slash command). This grounds a case.
- **weak** — the skill's name merely appeared in prose. This is a lead, not
  evidence. Confirm it by reading the window before letting it ground
  anything. A naive grep would call these invocations; they usually aren't.

Windows whose trailing turns contain a correction are flagged `GOLD`. Start
there. Each one converts directly into a `hard_fail` plus a replayable case.

Exit code `3` means zero windows.

**FAIL-CLOSED.** If no substrate yields a single real invocation, emit an
honest no-history report — substrates checked, queries run, turns scanned,
zero matches — and **stop**. Do not invent "typical" invocations. A skill with
no history needs a spec-derived bootstrap that is *labeled* spec-derived, not
a fabricated usage benchmark wearing history's clothes.

Before declaring no history, widen once: try the skill's trigger phrases via
`--triggers`, and its former names if it was renamed. "No history" should
mean you looked, not that you ran one query.

### 2. SYNTH — turn windows into a proposed eval

From the mined windows plus the current `SKILL.md`, produce:

- **A proposed eval contract** — goal, dimensions, hard_fails. Dimensions come
  from observed asks. Hard_fails encode observed corrections.
- **4-8 replayable cases**, each `{input, expected_behavior,
  failure_mode_to_catch}` — a realistic input, a checkable expected behavior,
  and the named failure mode the case exists to catch. A case that catches no
  named failure is decoration; cut it.
- **Spec-vs-usage gaps** — "the spec says X, users consistently ask for Y."
  These are often the most valuable output of the whole run, because they are
  invisible from inside the spec.

**HONESTY LABELS ARE MANDATORY.** Every dimension and every case carries one:

- `HISTORY-IMPLIED` — a real mined window backs it. Cite which one
  (project/session/turn).
- `SPEC-DERIVED` — inferred from SKILL.md only. No usage evidence.

Never blur them. If history is thin or off-target, say so at the very top of
the staged file — `GROUNDING WARNING: only 2 windows found, neither exercised
the core path` — rather than padding the eval with invented evidence.
Presenting spec-derived dimensions as history-grounded is the cardinal sin of
this skill: it launders a guess into a measurement.

**Privacy scrub before staging.** Staged evals live in a skill repo and get
distributed. Mined windows contain real names, companies, paths, and deals.
Rewrite every case onto placeholder slugs (`alice-example`, `acme-example`,
`/path/to/project`) before writing the file. A history-grounded case keeps its
shape and its failure mode, never its real entities.

### 3. STAGE — human gate, always

Write `<skill-dir>/eval/autobench-<YYYY-MM-DD>.md` with frontmatter
`status: PENDING-HUMAN-APPROVAL`. See `templates/staged-eval.md`.

**This skill NEVER rewrites SKILL.md** — not the eval contract, not the body,
not the description, not the triggers. Merging is the human's decision. This
is a workflow contract you honor, not a gate anything enforces for you.

## The loop (after approval)

1. The human reviews, edits, and approves the staged eval; the approved
   contract is merged into the skill explicitly, by them.
2. Approved cases become benchmark lines — one JSON object per case — for
   whatever optimizer or replay harness the project uses. This is the point:
   a history-grounded benchmark replacing a spec-derived bootstrap.
3. Judge the outputs. If judging uses a multi-model panel, run the panel
   integrity check below over the receipt **before** believing any verdict.
4. Re-run autobench once more usage accumulates, and diff against the prior
   staged baseline. Drift in the gaps section is the signal worth watching.

## Panel integrity — trust no aggregate

Multi-model judging is only as good as the panel being real. The silent
failure class: a model-id normalizer strips provider prefixes, every
"different model" call lands on the same host, and a "3-frontier consensus"
is one model's opinion in a trench coat. The score looks fine. It means
nothing.

```bash
python3 scripts/check_panel_integrity.py receipt.json
```

Three assertions over the result object:

1. **Every named model returned a non-empty response.** An empty slot is the
   first tell of a collapse.
2. **Slots hit distinct provider endpoints.** Three "different models"
   reporting one provider is one host.
3. **No two differently-named models returned byte-identical output.** This
   catches a collapse even when provider metadata is missing or faked —
   which is precisely when you need it.

Exit `0` OK, `1` violated, `2` inconclusive. Inconclusive is never a pass.

The check is pure assertion logic over a result that already exists. It never
calls a model: no network, no cost. Anything that calls a model to verify a
panel has misunderstood the problem.

## Fail-improve taxonomy — what mined failures become

Classify every mined correction by its cheapest durable fix. The direction of
travel matters: each fixed failure becomes a permanent test, the
deterministic share rises, the LLM-fallback share falls.

| Class | Signal in history | Durable fix |
|---|---|---|
| **DETERMINISTIC-CODIFIABLE** | An LLM fallback repeatedly handles the same input shape — regex, parsing, slugs, dates | Convert to deterministic code plus a permanent test. The LLM was never the solution; it was the training-data generator for the code that replaces it. |
| **PROMPT-FIXABLE** | The correction targets tone, format, or an omission the SKILL.md could have specified | An eval case, then an optimizer run |
| **SPEC-GAP** | Users consistently ask for something the spec never promised | A spec-vs-usage gap for the human to rule on |
| **ROUTING-MISS** | The skill fired on the wrong ask, or failed to fire on the right one | A routing-eval case, not a benchmark case — these test dispatch, not behavior |

Log and improve. Never silently drop a mined failure.

## Contract

- **Input:** the name of a skill that already exists.
- **Substrate:** Claude Code session transcripts under `~/.claude/projects/`
  (local-only by design), plus any store passed via `--projects`. No usable
  substrate → honest no-history report, never fabricated evidence.
- **Output:** exactly one staged file at
  `<skill-dir>/eval/autobench-<date>.md` with
  `status: PENDING-HUMAN-APPROVAL` — or the no-history report. Never an edit
  to SKILL.md, the description, or any routing surface.
- **Cost posture:** mining is free — it is local file parsing, no model calls.
  Synthesis runs cheap. A multi-model judging pass is an explicit opt-in.
- **Honesty:** every dimension and case labeled SPEC-DERIVED or
  HISTORY-IMPLIED; thin history flagged at the top, not papered over.
- **Privacy:** mined cases rewritten onto placeholder entities before staging.

## Output format

```markdown
---
skill: <name>
status: PENDING-HUMAN-APPROVAL
generated: <YYYY-MM-DD>
substrate: { transcript_files: N, turns_scanned: T, windows: K, strong: S, corrections: C }
---

# Autobench: <name> — <date>

## Grounding
<one paragraph: how much real history backs this eval.
 GROUNDING WARNING at the top if thin.>

## Proposed eval contract
goal / dimensions (each HISTORY-IMPLIED|SPEC-DERIVED) / hard_fails

## Cases (4-8)
### case-01 [HISTORY-IMPLIED — proj-slug/session/turn-14]
input: ...
expected_behavior: ...
failure_mode_to_catch: ...

## Spec-vs-usage gaps
- spec says X; users ask Y (windows: ...)

## Fail-improve classification
- case-03 → DETERMINISTIC-CODIFIABLE (same date-format fallback, 4 windows)
```

## Anti-patterns

- ❌ Auto-merging a synthesized eval into SKILL.md. The human gate is the
  contract, and it is the whole reason this is safe to run.
- ❌ Presenting SPEC-DERIVED dimensions as history-grounded. Fabricating usage
  evidence is the cardinal sin.
- ❌ Mining nothing and emitting a confident eval anyway. Fail loudly or label
  honestly.
- ❌ Treating a weak signal (name mentioned in prose) as a real invocation.
- ❌ Declaring "no history" after one query, without trying trigger phrases or
  former names.
- ❌ Trusting "3 models scored it 8/10" without checking that three providers
  actually returned distinct, non-identical responses.
- ❌ Calling a model inside the panel-integrity check. It is assertion logic
  over a result object.
- ❌ Staging cases with real people, companies, or filesystem paths in them.
  Placeholders only.

## Boundaries

- **Skill optimizers** improve a skill's body against an *existing* benchmark;
  their bootstrap modes derive tasks from the spec. This skill *authors* the
  benchmark from lived usage and hands it over. It extends an optimizer's
  surface; it never duplicates it. With no history at all, use the optimizer's
  spec-derived bootstrap — and let it be labeled as such.
- **skill-creator / skillify** create skills from descriptions. They don't
  mine usage.
- **Judging harnesses / cross-modal review** *run* panels. They don't author
  evals. The integrity assertions here verify their panels were real.
- **Conformance checkers** audit skill structure — frontmatter, references,
  duplicate triggers. This audits behavior quality.
- **Routing evals** test dispatch: does the right skill fire? Autobench tests
  behavior after dispatch. ROUTING-MISS findings route there.

# autobench — a Claude Code skill

**Write a skill's eval from its real usage history, not its spec.**

A spec-derived benchmark tests what a skill *promised*. It cannot test what
users actually asked for, and it definitely cannot test what went wrong. This
skill mines your Claude Code session transcripts for real invocations of a
skill, treats **a user correction following an invocation as the gold signal**
— a dated, reproducible, observed failure — and synthesizes an eval from those.

Everything it produces is staged for human approval. It never rewrites
`SKILL.md`.

## Install

```bash
git clone https://github.com/sadamia/autobench.git ~/.claude/skills/autobench
```

Requires Python 3 (standard library only — no dependencies).

## Use

> autobench the media-ingest skill

> synthesize an eval for this skill based on how I've actually used it

> verify the eval panel — did all three providers actually return?

## What it does

**1. Mine.** Reads `~/.claude/projects/*/*.jsonl` and extracts *invocation
windows*: the ask before, the invocation, and the turns after (where
corrections live).

```bash
python3 scripts/mine_invocations.py media-ingest
python3 scripts/mine_invocations.py media-ingest --json > windows.json
```

It distinguishes **strong** signals (a `Skill` tool call, agent dispatch, or
slash command the harness actually recorded) from **weak** ones (the skill's
name merely appearing in prose). That distinction matters: a naive grep calls
both an invocation, and mostly it's wrong. Windows followed by a correction
are flagged `GOLD`.

Exit code `3` means zero windows — **fail-closed**. The skill then emits an
honest no-history report instead of inventing "typical" invocations.

**2. Synthesize.** An eval contract plus 4–8 replayable cases
(`input` / `expected_behavior` / `failure_mode_to_catch`), each labeled
`HISTORY-IMPLIED` (with a cited window) or `SPEC-DERIVED` (no usage evidence).
Blurring those two is the failure mode the whole design exists to prevent —
it launders a guess into a measurement. Real names, companies, and paths are
scrubbed to placeholders before anything is written.

**3. Stage.** Writes `<skill-dir>/eval/autobench-<date>.md` with
`status: PENDING-HUMAN-APPROVAL`. Merging is your call, always.

## Panel integrity

A bundled, dependency-free assertion check for multi-model judging:

```bash
python3 scripts/check_panel_integrity.py receipt.json
```

The silent failure it catches: a model-id normalizer strips provider prefixes,
every "different model" call lands on the same host, and your "3-frontier
consensus" is one model's opinion in a trench coat. Three assertions — every
slot returned, endpoints are distinct, and no two differently-named models
returned byte-identical output. That last one catches a collapse even when
provider metadata is missing or faked, which is exactly when you need it.

Exit `0` OK, `1` violated, `2` inconclusive. Inconclusive never counts as a pass.
It never calls a model: no network, no cost.

## Fail-improve taxonomy

Each mined failure is classified by its cheapest durable fix —
`DETERMINISTIC-CODIFIABLE`, `PROMPT-FIXABLE`, `SPEC-GAP`, or `ROUTING-MISS`.
The point is direction of travel: every fixed failure becomes a permanent
test, the deterministic share rises, and the LLM-fallback share falls. An LLM
repeatedly handling the same input shape isn't a solution — it's the
training-data generator for the code that should replace it.

## Layout

```
SKILL.md                          the skill
scripts/mine_invocations.py       transcript miner (stdlib only)
scripts/check_panel_integrity.py  panel assertions (stdlib only)
templates/staged-eval.md          the PENDING-HUMAN-APPROVAL output shape
routing-eval.jsonl                dispatch cases for this skill
```

## Credit

Extracted and generalized from the `skill-autobench` skill in
[garrytan/gbrain](https://github.com/garrytan/gbrain)
(`skills/skill-autobench/SKILL.md`, v1.0.0), MIT licensed, © 2026 Garry Tan.

**Changes in this standalone version.** The original mined a gbrain "brain"
conversation archive via `gbrain search` / `gbrain query` / `gbrain transcripts`,
and handed off to `gbrain skillopt` and `gbrain eval cross-modal` — none of
which exist outside that repo, which left the pipeline's central step
unexecutable. Here the substrate is the Claude Code transcript store, and the
mining is a working script written against its actual schema rather than a
described procedure. The panel-integrity assertions and the fail-improve
taxonomy, both prose-only in the original, are now an executable check and a
staged-output section. Dangling `conventions/` links, gbrain-internal frontmatter
(`requires`, `upstream`, `writes_to`), and gbrain-specific dedup targets were
removed or generalized; the frontmatter was rewritten for standard Claude Code
skill loading.

## License

MIT — see [LICENSE](LICENSE).

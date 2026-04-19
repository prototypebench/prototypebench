<p align="right">
  <b>English</b> · <a href="README.ko.md">한국어</a>
</p>

# PrototypeBench

> **Can your agent ship a full-stack AI-native prototype?**

![status](https://img.shields.io/badge/status-phase%201%20(curation)-yellow)
![license](https://img.shields.io/badge/license-MIT-blue)
![stack](https://img.shields.io/badge/stack-React%20%2B%20Vite%20%2B%20Tailwind%20%7C%20FastAPI%20%2B%20SQLModel-black)

PrototypeBench is an open benchmark for evaluating the **full-stack product-shipping ability** of AI coding agents. Where SWE-Bench measures bug-fixing in mature Python libraries, PrototypeBench measures **"can the agent ship a full-stack feature on a modern AI-native stack?"**

- **Task source**: merged PRs from [`fastapi/full-stack-fastapi-template`](https://github.com/fastapi/full-stack-fastapi-template) (MIT, 42.7k★).
- **Scoring**: all `FAIL_TO_PASS` pass + all `PASS_TO_PASS` don't regress = 1 point (binary). Dual runner (pytest + Playwright).
- **Format**: extends the SWE-Bench `instances.jsonl` schema — existing tooling is re-usable with minimal glue.

## Why this stack?

Each component is #1 in its category per 2024 industry surveys.

| | Share | Source |
|---|---|---|
| **React** | 82% (undisputed #1) | State of JS 2024 |
| **Vite** | 78.1% (overtook Webpack) | State of JS 2024 |
| **Tailwind CSS** | 62% (first time over Bootstrap) | State of CSS 2024 |
| **FastAPI** | 38% (first time over Django/Flask), 42% of ML engineers | JetBrains Python Survey 2024 |

16,209 open "fastapi react" jobs on Indeed (2025). We evaluate AI agents on the stack that actual AI product teams ship on.

## What's in a task

Each task is a JSON object derived from one real merged PR. It extends the SWE-Bench format with **dual-test (backend + frontend)** fields.

```jsonc
{
  "instance_id": "fastapi__full-stack-fastapi-template-1234",
  "repo": "fastapi/full-stack-fastapi-template",
  "base_commit": "0123...",
  "head_commit": "abcd...",
  "problem_statement": "Users should be able to archive an item without deleting it ...",
  "patch": "diff --git a/backend/app/api/routes/items.py ...",
  "test_patch": "diff --git a/... test files only ...",
  "fail_to_pass": {
    "backend":  ["backend/app/tests/.../test_archive_item_success"],
    "frontend": ["frontend/tests/items.spec.ts:42:3 › archive button toggles"]
  },
  "pass_to_pass": { "backend": [...], "frontend": [...] },
  "stack_domain": "fullstack",
  "environment": { "python_version": "3.11", "node_version": "20", "uv_lock_sha": "...", "bun_lock_sha": "..." },
  "contamination_tier": "held_out"
}
```

Full schema: [`schemas/task_instance.schema.json`](schemas/task_instance.schema.json) · [`docs/task-schema.md`](docs/task-schema.md).

## Status

| Phase | Status |
|---|---|
| 1 · Task curation pipeline | 🚧 In progress |
| 2 · Evaluation harness (pytest + Playwright) | ⏳ |
| 3 · Internal beta (model shootout) | ⏳ |
| 4 · Public leaderboard | ⏳ |
| 5 · Continuous task refresh | ⏳ |

Leaderboard submissions open in Phase 4. Design principles and the full roadmap live in [`PLAN.md`](PLAN.md).

## Fairness & contamination

Two invariants carry the benchmark's credibility:

1. **Fairness** — tasks on which the operating organization's agent performs *poorly* are required. The benchmark name carries no vendor branding.
2. **Contamination defense** — the source repo is MIT-public, so frontier models likely saw its PR diffs during training.
   Tasks are partitioned into `public` / `held_out` / `internal_only` tiers by merge date vs. model cutoff. Held-out tiers rotate per leaderboard season.
   Submitters must disclose model cutoff dates.

## Quick start (curator / contributor)

This repo is currently the **task-curation pipeline**. The evaluation harness that runs your agent against tasks lands in Phase 2.

### Prerequisites

- Python 3.11+, [`uv`](https://docs.astral.sh/uv/)
- [`gh` CLI](https://cli.github.com/) (authenticated)

### Install

```bash
git clone https://github.com/prototypebench/prototypebench.git
cd prototypebench
uv sync
```

### Pipeline

```bash
# 1. Crawl merged PRs from the source repo → raw/prs.jsonl
uv run pbench crawl

# 2. Filter + score → raw/candidates.jsonl (+ rejected.jsonl)
uv run pbench filter

# 3. Inspect candidate distribution
uv run pbench stats
uv run pbench top --n 20

# 4. Draft N instances (with <<TODO:...>> markers) from the top candidates
uv run pbench draft --top 10

# 5. Curator fills in TODOs, then validates against the schema
uv run pbench validate -p tasks/instances.jsonl
```

Full CLI help: `uv run pbench --help`.

### Seed curation workflow

The initial 10-task manual pass exists to validate the pipeline end-to-end, not as a finished task set. Checkout, test execution, FAIL/PASS extraction, and `problem_statement` authoring steps are in [`docs/seed-curation.md`](docs/seed-curation.md).

## Repo layout

```
prototypebench/
├── PLAN.md                      # Project charter (principles · competitive map · roadmap)
├── schemas/
│   └── task_instance.schema.json
├── docs/
│   ├── task-schema.md           # Field-by-field schema explainer
│   └── seed-curation.md         # Manual curation checklist
├── scripts/                     # `pbench` CLI
│   ├── cli.py
│   ├── crawl_prs.py
│   ├── filter_prs.py
│   ├── build_instance.py
│   └── validate.py
├── tasks/
│   └── instances.jsonl          # Final task bundle (curation output)
└── raw/                         # Crawler scratch (gitignored)
```

## Contributing

In Phase 1, **task quality is benchmark credibility**. Welcome contributions:

- Improvements to the [`docs/seed-curation.md`](docs/seed-curation.md) checklist
- Schema v0.2 proposals (see last section of [`docs/task-schema.md`](docs/task-schema.md))
- Filter-heuristic tuning (`scripts/filter_prs.py`)
- New seed-task proposals (link to a specific base-repo PR + a `notes` draft)

Please open an Issue before a PR while the process is still hardening.

## References

- [SWE-Bench](https://www.swebench.com/) · [Terminal-Bench](https://www.tbench.ai/) · [FullStackBench (arxiv 2412.00535)](https://arxiv.org/abs/2412.00535) · [LiveBench](https://livebench.ai/)
- [State of JS 2024](https://2024.stateofjs.com/) · [State of CSS 2024](https://2024.stateofcss.com/) · [JetBrains Python Survey 2024](https://lp.jetbrains.com/python-developers-survey-2024/)

## License

MIT. The base repo `fastapi/full-stack-fastapi-template` is also MIT.

## Cite

Citation format will be fixed at the Phase 4 public launch.

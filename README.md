# PrototypeBench

> **Can your agent ship a full-stack AI-native prototype?**

![status](https://img.shields.io/badge/status-phase%201%20(curation)-yellow)
![license](https://img.shields.io/badge/license-MIT-blue)
![stack](https://img.shields.io/badge/stack-React%20%2B%20Vite%20%2B%20Tailwind%20%7C%20FastAPI%20%2B%20SQLModel-black)

PrototypeBench는 AI 코딩 에이전트의 **풀스택 제품 개발 능력**을 평가하는 공개 벤치마크입니다. SWE-Bench가 "성숙한 Python 라이브러리에서의 버그픽스"를 측정한다면, PrototypeBench는 **"현대적 AI-native 스택에서 풀스택 기능을 ship 할 수 있는가"** 를 측정합니다.

- **태스크 소스**: [`fastapi/full-stack-fastapi-template`](https://github.com/fastapi/full-stack-fastapi-template) (MIT, 42.7k★) 의 merged PR.
- **스코어링**: `FAIL_TO_PASS` 전체 통과 + `PASS_TO_PASS` 미회귀 = 1점 (이진). pytest + Playwright 이중 러너.
- **포맷**: SWE-Bench `instances.jsonl` 과 호환되는 확장 스키마 — 기존 툴체인 재사용 가능.

## Why this stack?

각 컴포넌트는 2024 업계 서베이 기준 자기 카테고리 1위입니다.

| | Share | Source |
|---|---|---|
| **React** | 82% (독보적 1위) | State of JS 2024 |
| **Vite** | 78.1% (Webpack 추월) | State of JS 2024 |
| **Tailwind CSS** | 62% (Bootstrap 첫 추월) | State of CSS 2024 |
| **FastAPI** | 38% (Django/Flask 첫 추월), ML 엔지니어 42% | JetBrains Python Survey 2024 |

Indeed "fastapi react" 직무 공고 16,209건 (2025). AI 제품을 만드는 사람들의 스택에서 AI 에이전트를 평가한다는 서사.

## What's in a task

각 태스크는 하나의 실제 merged PR에서 도출된 JSON 객체입니다. SWE-Bench 포맷에 **풀스택 이중 테스트** 확장이 더해졌습니다.

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

전체 스키마: [`schemas/task_instance.schema.json`](schemas/task_instance.schema.json) · [`docs/task-schema.md`](docs/task-schema.md).

## Status

| Phase | Status |
|---|---|
| 1 · Task curation pipeline | 🚧 In progress |
| 2 · Evaluation harness (pytest + Playwright) | ⏳ |
| 3 · Internal beta (model shootout) | ⏳ |
| 4 · Public leaderboard | ⏳ |
| 5 · Continuous task refresh | ⏳ |

Phase 4 공개 론칭 전까지 리더보드 제출은 열리지 않습니다. 설계 원칙과 전체 로드맵은 [`PLAN.md`](PLAN.md).

## Fairness & contamination

공개 벤치마크의 신뢰는 두 축에 달려있습니다:

1. **공정성** — 운영 조직의 에이전트에게 불리한 태스크도 필수 포함. 벤치 이름에 벤더 이름 배제.
2. **오염 방어** — 베이스 repo가 MIT 공개라 프런티어 모델이 학습 데이터로 접했을 가능성이 높습니다.
   태스크를 cutoff 기준으로 `public` / `held_out` / `internal_only` 티어로 분리 운영. held-out 셋은 시즌 단위 로테이션.
   리더보드 제출 시 모델 cutoff 공개가 요구됩니다.

## Quick start (curator / contributor)

현재 레포는 **태스크 큐레이션 파이프라인** 단계입니다. 에이전트를 직접 돌리는 하네스는 Phase 2에서 공개됩니다.

### Prerequisites

- Python 3.11+, [`uv`](https://docs.astral.sh/uv/)
- [`gh` CLI](https://cli.github.com/) (GitHub 인증 필요)

### Install

```bash
git clone https://github.com/prototypebench/prototypebench.git
cd prototypebench
uv sync
```

### Pipeline

```bash
# 1. 소스 repo의 merged PR을 raw/prs.jsonl 로 크롤
uv run pbench crawl

# 2. 필터링 + 스코어링 → raw/candidates.jsonl (+ rejected.jsonl)
uv run pbench filter

# 3. 태스크 후보 분포 확인
uv run pbench stats
uv run pbench top --n 20

# 4. 상위 N개에서 instance 초안 (<<TODO:...>> 포함) 생성
uv run pbench draft --top 10

# 5. 큐레이터가 초안의 TODO 채운 뒤 스키마 검증
uv run pbench validate -p tasks/instances.jsonl
```

CLI 도움말: `uv run pbench --help`.

### Seed curation workflow

10개 수동 큐레이션은 파이프라인 end-to-end 검증이 목적입니다. 체크아웃 · 테스트 실행 · FAIL/PASS 추출 · `problem_statement` 작성 절차는 [`docs/seed-curation.md`](docs/seed-curation.md) 참조.

## Repo layout

```
prototypebench/
├── PLAN.md                      # 프로젝트 헌장 (원칙 · 경쟁 지도 · 로드맵)
├── schemas/
│   └── task_instance.schema.json
├── docs/
│   ├── task-schema.md           # 스키마 필드별 해설
│   └── seed-curation.md         # 수동 큐레이션 체크리스트
├── scripts/                     # `pbench` CLI 구현
│   ├── cli.py
│   ├── crawl_prs.py
│   ├── filter_prs.py
│   ├── build_instance.py
│   └── validate.py
├── tasks/
│   └── instances.jsonl          # 최종 태스크 번들 (큐레이션 산출물)
└── raw/                         # 크롤러 중간 산출물 (gitignored)
```

## Contributing

Phase 1에서는 **태스크 품질**이 곧 벤치마크 신뢰도입니다. 환영하는 기여:

- `docs/seed-curation.md` 체크리스트 개선 제안
- 태스크 스키마 v0.2 의견 ([`docs/task-schema.md`](docs/task-schema.md) 마지막 섹션)
- 필터 휴리스틱 튜닝 (`scripts/filter_prs.py`)
- 새로운 seed 태스크 제안 (베이스 repo의 특정 PR 링크 + `notes` 초안)

프로세스 성숙 전까지는 Issue로 논의를 시작해주세요.

## References

- [SWE-Bench](https://www.swebench.com/) · [Terminal-Bench](https://www.tbench.ai/) · [FullStackBench (arxiv 2412.00535)](https://arxiv.org/abs/2412.00535) · [LiveBench](https://livebench.ai/)
- [State of JS 2024](https://2024.stateofjs.com/) · [State of CSS 2024](https://2024.stateofcss.com/) · [JetBrains Python Survey 2024](https://lp.jetbrains.com/python-developers-survey-2024/)

## License

MIT. 베이스 repo인 `fastapi/full-stack-fastapi-template` 또한 MIT.

## Cite

Phase 4 공개 론칭 시 인용 형식이 확정됩니다.

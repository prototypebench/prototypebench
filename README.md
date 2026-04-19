# PrototypeBench

> **Can your agent ship a full-stack AI-native prototype?**

AI-native 풀스택 에이전트 벤치마크. 타깃 스택은 **React + Vite + Tailwind + shadcn/ui (프런트)** × **FastAPI + SQLModel + Postgres (백)** — 각 카테고리 2024 업계 1위.

태스크 소스: [`fastapi/full-stack-fastapi-template`](https://github.com/fastapi/full-stack-fastapi-template) (MIT, 42.7k★) 의 merged PR 40~60개.

## Status

Phase 1 진행 중 — 태스크 큐레이션 파이프라인.

| Phase | 상태 |
|---|---|
| 1. 태스크 큐레이션 | 🚧 in progress |
| 2. 하네스 (runner) | ⏳ |
| 3. 내부 베타 | ⏳ |
| 4. 공개 베타 | ⏳ |

전체 맥락 · 설계 원칙 · 경쟁 지도는 [PLAN.md](PLAN.md).

## Repo 구조

```
prototypebench/
├── PLAN.md                 # 프로젝트 헌장 (§1–§11)
├── docs/
│   └── task-schema.md      # 태스크 스키마 설계 문서
├── schemas/
│   └── task_instance.schema.json
├── scripts/                # 파이프라인 도구
│   ├── cli.py              # pbench 엔트리포인트
│   └── crawl_prs.py        # full-stack-fastapi-template PR 크롤러
├── tasks/
│   └── instances.jsonl     # 최종 태스크 번들 (산출물)
└── raw/                    # PR 원시 덤프 (gitignored)
```

## Dev setup

```bash
uv sync
source .env
uv run pbench --help
```

## 원칙 (요약)

1. **공정성 우선** — 내부 에이전트에 불리한 태스크도 포함.
2. **오염 방어** — cutoff 이후 PR 을 held-out 셋으로 분리.
3. **투명성** — SWE-Bench/Terminal-Bench 수준 방법론 문서.
4. **내부 먼저** — 리더보드는 부산물. 내부 버전 간 시그널이 1차 목적.

전체는 [PLAN.md §5](PLAN.md).

## License

MIT.

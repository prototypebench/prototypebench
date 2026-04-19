# Harness Architecture — v0.1

> Phase 2 하네스의 설계 문서. 목적: (a) `FAIL_TO_PASS` 자동 추출로 Phase 1 수동 큐레이션을 해제하고, (b) 에이전트 패치의 자동 채점 기반을 구축한다.

## Design decisions (2026-04-20)

| # | 결정 | 대안 | 사유 |
|---|---|---|---|
| D1 | **컨테이너 기반 실행** (docker compose) | 로컬 venv + host postgres | 베이스 repo 가 compose 로 DB/백/프런트 오케스트레이션. 재현성과 격리. |
| D2 | **에이전트 인터페이스 v1 = patch submission** | tool-use agent loop | SWE-Bench 호환. tool-use(v2) 를 스코어링 없이 빌드하면 튜닝 기준이 없음. |
| D3 | **첫 이정표 = FAIL_TO_PASS 추출기** | 에이전트 end-to-end 먼저 | 추출기는 Phase 1 블로커 해제 + v1 스코어링 코어와 완전 공유. |
| D4 | **이미지 캐시 키 = `uv_lock_sha` / `bun_lock_sha`** | 커밋 해시 | lock 변하지 않으면 deps 레이어 재사용. 이미지 수 ≈ lock 변동 수 ≪ PR 수. |
| D5 | **에이전트 패치는 *non-test* 파일만 수정** | 테스트 수정 허용 | 정답 테스트 우회 방지. `test_patch` 는 하네스가 주입. |

## Extraction pipeline (single PR)

FAIL_TO_PASS / PASS_TO_PASS 추출은 하네스의 가장 작은 유닛이다.

```
 Input:  PR merged commit (head) + computed base (merge-base)
 Output: FAIL_TO_PASS, PASS_TO_PASS, base/head test results
```

### Steps

```
1. clone base repo → /tmp/pb-<instance_id>/repo
2. git checkout <base_commit>
3. git apply <test_patch>                  (only test files)
4. build/reuse image prototypebench/backend:<uv_lock_sha>
5. compose up -d db
6. docker run backend pytest --junitxml → base_tests.xml
7. git reset --hard <base_commit>
8. git checkout <head_commit>              (or: apply patch + test_patch on top of base)
9. docker run backend pytest --junitxml → head_tests.xml
10. parse: FAIL_TO_PASS = { t | t.fails(base) AND t.passes(head) }
           PASS_TO_PASS = { t | t.passes(base) AND t.passes(head) } \ FAIL_TO_PASS
11. (frontend) same pattern with `bun run test:e2e --reporter=json`
12. compose down -v
13. write raw/extract/<instance_id>/{base.xml, head.xml, frontend.json, summary.json}
```

### Variant: agent-patch evaluation (same machinery)

에이전트 평가 시 step 8 만 다르다:
```
8'. git checkout <base_commit>
    git apply <test_patch>
    git apply <agent_patch>        ← 에이전트가 제출한 diff
    docker run backend pytest      → agent_tests.xml
score = 1 if FAIL_TO_PASS ⊆ passing(agent_tests)
             AND PASS_TO_PASS ⊆ passing(agent_tests)
        else 0
```

즉 추출기와 스코어러는 **동일 실행 코어**, 다른 입력 세트.

## Container topology

태스크 1건 실행 시 띄우는 compose 스택:

```
┌──────────────────────────────────────────────────────┐
│ compose project: pbench-<instance_id>                │
│                                                      │
│  db              ← postgres:17 (ephemeral volume)    │
│  backend-tests   ← prototypebench/backend:<lock_sha> │
│                    mount: repo-snapshot              │
│                    cmd:   uv run pytest --junitxml   │
│  backend-serve   ← 같은 이미지, 다른 command         │
│                    cmd:   uvicorn app.main:app       │
│                   (frontend e2e 단계에서만 기동)     │
│  frontend-tests  ← prototypebench/frontend:<bun_sha> │
│                    depends_on: backend-serve         │
│                    cmd: bun run test:e2e --reporter=json│
└──────────────────────────────────────────────────────┘
```

- `db` 는 task-scoped volume 사용 → 오염 없음.
- `backend-tests` 는 db 없이도 대부분 돌지만 integration 테스트는 db 필요. 항상 기동.
- 프런트 e2e 는 `backend-serve` 에 의존. 백 테스트와 분리된 컨테이너라 상태 격리.

## Images

### `prototypebench/backend:<uv_lock_sha>`
```
FROM python:3.11-slim
RUN pip install --no-cache-dir uv
WORKDIR /app
COPY backend/pyproject.toml backend/uv.lock ./
RUN uv sync --frozen --no-install-project
```
- lock 가 변하지 않으면 이 레이어가 그대로 재사용 → 태스크당 deps 설치 비용 0.
- 프로젝트 코드는 런타임 bind mount 로 주입.

### `prototypebench/frontend:<bun_lock_sha>`
```
FROM mcr.microsoft.com/playwright:v1.50-jammy
RUN curl -fsSL https://bun.sh/install | bash
WORKDIR /app
COPY frontend/package.json frontend/bun.lockb ./
RUN bun install --frozen-lockfile
```
- Playwright 공식 이미지로 브라우저 바이너리 번들. 별도 설치 없이 바로 E2E.

## Output layout

```
raw/extract/
  fastapi__full-stack-fastapi-template-1543/
    base.junit.xml
    head.junit.xml
    frontend.base.json
    frontend.head.json
    summary.json          ← FAIL_TO_PASS, PASS_TO_PASS, 소요시간, 환경 해시
    logs/
      backend-base.log
      backend-head.log
      frontend-base.log
      frontend-head.log
```

`summary.json` 을 읽어 `tasks/instances.jsonl` 의 해당 인스턴스를 완성.

## Local-only mode (dev fast path)

Docker 이미지 빌드는 무겁다. 반복 작업 시 로컬 모드 옵션:
- backend: host 의 `uv` 로 tmp repo 에서 바로 `uv run pytest`
- db: 로컬 postgres (compose 로만 기동)
- frontend: host 의 `bun` + `bunx playwright`

정확한 재현성은 Docker 모드가 정답이지만, 큐레이터 iteration 에서는 로컬 모드가 ×10 빠르다. CLI 플래그로 전환: `--mode docker | local` (기본: docker).

## Not in v0.1 (flagged for later)

- **병렬 실행 스케줄러** — 여러 태스크 동시 돌리기. 초기엔 직렬.
- **GPU / 모델 inference 컨테이너** — 에이전트 패치 생성은 외부에서. 하네스는 패치만 받음.
- **Flaky test 재시도** — 첫 실행만. 재시도 정책은 Phase 3 튜닝 이후.
- **결과 캐싱** — 같은 (base, patch) 조합 재실행 생략. 구현 쉽지만 yagni 상 보류.

## Observed failure modes (validated 2026-04-20 on PRs 1543, 1396, 2104, 1270, 2146)

| Mode | Root cause | Current behavior | Fix |
|---|---|---|---|
| **Pre-uv-era base_commit** | base predates PR #2090 (2026-01-20) which introduced the uv workspace layout. The harness assumes `uv.lock` at repo root. | Extractor checks for `uv.lock` after base checkout and aborts with an actionable error. `filter_prs.py` drops PRs with `mergedAt < 2026-01-20` from the candidate pool. | Poetry-era runner is v2+ scope. |
| **Collection-error on base** (e.g. PR #2104) | `test_patch` imports symbols the base commit doesn't have yet (e.g. `argon2` in a fresh-feature PR). pytest fails at collection, emitting file-level errors instead of test-nodeid errors. | F2P = 0, P2P = 0 (intersection is empty because base reports no nodeids). | **v2**: fall back to parsing `+def test_*` from `test_patch` and intersecting with head's passing set. |
| **Flaky on first-cold-cache Docker run** | Not yet observed | — | Monitor; add retries in Phase 3 if it shows up. |

## Failure modes to explicitly log

- git apply 실패 (base/head 충돌) → `patch_apply_failed`
- 이미지 빌드 실패 (lock 변경 등) → `image_build_failed`
- 테스트 시작 실패 (import error, db 연결 불가) → `test_collection_failed`
- 테스트 타임아웃 (태스크당 상한 15분) → `timeout`
- 모든 실패 시에도 `summary.json` 에 원인을 structured 로 기록 — triage 품질이 태스크 품질을 결정한다.

## 첫 구현 범위 (Sprint A)

- [x] 이 문서
- [ ] `harness/` 패키지 스캐폴드
- [ ] `harness/extract.py` — **backend-only, local mode** 단일 PR 추출기
  - git clone/checkout/apply
  - host uv 로 pytest 실행 (Docker 나중)
  - junit xml → FAIL_TO_PASS/PASS_TO_PASS
- [ ] `pbench extract --pr <N>` CLI
- [ ] 후보 1개로 실증 실행

이것이 동작하면 Sprint B 에서 Docker 화 + Playwright 를 추가한다.

# Seed Curation Guide — 10 PR × end-to-end

> Phase 1 step 4. 10개 수동 큐레이션은 **파이프라인 end-to-end 검증**이 목적이지, 완성된 태스크 셋이 아니다.
> 이 단계에서 발견되는 스키마/프로세스 허점은 스키마 v0.2 로 반영.

## 선정 원칙 (10개 구성)

| 카테고리 | 개수 | 이유 |
|---|---|---|
| `stack_domain=backend_only` | 3 | 가장 자동화 쉬움 (pytest 단독). 파이프라인 baseline. |
| `stack_domain=frontend_only` | 2 | Playwright runner 조기 점검. |
| `stack_domain=fullstack` | 4 | 핵심 카테고리. 난이도 spectrum (easy 1 / medium 2 / hard 1). |
| `contamination_tier=held_out` | 1+ | cutoff 이후 PR 1개 이상 포함해 held-out 로직 검증. |

## 큐레이션 체크리스트 (per PR)

각 후보 PR 에 대해 다음을 순서대로 수행. 체크 실패 시 교체 후보로 rotate.

### 1. 선정 프리필터
- [ ] `raw/candidates.jsonl` 상위에서 선정 (수동 픽도 OK)
- [ ] PR diff 육안 검사: 정답이 자명하지 않고, 스펙이 충분히 제약적
- [ ] 제외 조건: 단순 typo / 의존성 업데이트 / 리팩토링 (기능 변화 없음) / docs-only

### 2. 체크아웃 & 재현성
```bash
git clone https://github.com/fastapi/full-stack-fastapi-template.git /tmp/src
cd /tmp/src
git checkout <base_commit>
```
- [ ] `docker compose up -d db` → Postgres 기동
- [ ] `cd backend && uv sync && uv run pytest` → 모든 base-line 테스트 통과 확인 (없는 파일 추가되기 전)
- [ ] `cd frontend && bun install && bun run build` → 빌드 성공

### 3. 테스트 delta 추출
```bash
git checkout <head_commit>
git diff <base_commit> <head_commit> -- '*test*' '*spec.ts' > /tmp/test.diff
git diff <base_commit> <head_commit> -- . ':!*test*' ':!*spec.ts' > /tmp/patch.diff
```
- [ ] `test_patch` / `test_patch_backend` / `test_patch_frontend` 생성
- [ ] `patch` (정답) 에 테스트 diff 가 **절대 섞이지 않도록** 검토

### 4. FAIL_TO_PASS / PASS_TO_PASS 추출

**backend**:
```bash
git checkout <base_commit>
git apply /tmp/test.diff                 # 테스트만 주입
cd backend && uv run pytest --tb=no -q > /tmp/base_tests.txt  # 실패 리스트
git apply /tmp/patch.diff                 # 정답 주입
uv run pytest --tb=no -q > /tmp/head_tests.txt
```
- [ ] `fail_to_pass.backend` = base 에서 FAIL → head 에서 PASS
- [ ] `pass_to_pass.backend` = base 에서 PASS → head 에서도 PASS (현실적으로 샘플링 OK — 전체 suite 넣으면 maintenance cost 높음)

**frontend**:
```bash
cd frontend && bun run test:e2e -- --list > /tmp/e2e.txt
# FAIL→PASS 목록은 실제 실행 비교로 도출 (헤드리스 Playwright)
```
- [ ] `fail_to_pass.frontend` 동일 방식
- [ ] Playwright test ID 포맷 통일: `frontend/tests/<file>.spec.ts:<line>:<col> › <title>`

### 5. `problem_statement` 작성
우선순위:
1. 이 PR 의 closing issue body 가 자명한 스펙이면 그대로
2. 그 외: PR description 을 베이스로 에이전트 관점에서 재작성 (해결 방법 힌트 제거)
3. 둘 다 부적절: 수동 작성 (`notes` 에 근거 기록)

검토 포인트:
- [ ] 구현 선택지를 강요하지 않음 (예: "X 테이블에 `archived_at` 컬럼 추가" ❌ → "아이템을 archive 할 수 있어야 한다" ✅)
- [ ] 테스트가 검증하는 제약이 모두 스펙에 드러남

### 6. 환경 해시
```bash
git show <base_commit>:backend/uv.lock | shasum -a 256 | cut -d' ' -f1
git show <base_commit>:frontend/bun.lockb | shasum -a 256 | cut -d' ' -f1
git show <base_commit>:docker-compose.yml | shasum -a 256 | cut -d' ' -f1
```

### 7. 스키마 검증
```bash
uv run pbench validate -p tasks/instances.jsonl
```
- [ ] 에러 없음

### 8. 오염 티어 지정
- `created_at < 2026-01-01` (Claude Opus 4.7 cutoff) → `public`
- `created_at >= 2026-01-01` → `held_out`
- 예외적으로 유명 이슈(GitHub trending, blog 다뤄짐) → `internal_only`

## 산출물

각 PR 당 1 JSON object 를 `tasks/instances.jsonl` 에 append.
큐레이터 근거는 `notes` 필드에 필수 기록 (왜 이 PR 인가, 주의사항).

## 자동화 가능 지점 (v2)

- [4] FAIL/PASS 추출 → 하네스에서 자동. 하네스 완성 전엔 수동.
- [5] `problem_statement` 재작성 → LLM 보조 (근거 기록 조건).
- [6] 환경 해시 → 빌더 스크립트에 포함.

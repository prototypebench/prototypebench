# Task Instance Schema — v0.1

> JSON Schema 원본: [`schemas/task_instance.schema.json`](../schemas/task_instance.schema.json)
> 버전: **0.1** (2026-04-20 초안)

## 설계 원칙

1. **SWE-bench 호환성 베이스** — `instance_id`, `repo`, `base_commit`, `problem_statement`, `patch`, `test_patch` 등 상위 필드명은 SWE-bench `instances.jsonl` 과 동일. 기존 SWE-bench 계열 툴체인(시각화, diff viewer, 등)에서 최소 수정으로 호환.
2. **풀스택 이중 테스트 분리** — `FAIL_TO_PASS` / `PASS_TO_PASS` 을 `{backend, frontend}` 객체로 확장. pytest 노드 ID 와 Playwright 테스트 ID 를 구분 저장.
3. **오염(contamination) 티어 필드 내장** — `contamination_tier` 로 public/held-out/internal-only 분리. PR `created_at` 과 평가 대상 모델의 cutoff 비교로 자동 계산.
4. **환경 재현성** — `environment.uv_lock_sha`, `bun_lock_sha`, `docker_compose_sha` 로 빌드 재현 검증. 값은 lock 파일 내용 해시.

## SWE-bench 대비 변경점 요약

| 필드 | SWE-bench | PrototypeBench | 변경 사유 |
|---|---|---|---|
| `FAIL_TO_PASS` / `PASS_TO_PASS` | `list[str]` | `{backend, frontend}` 객체 | pytest + Playwright 이중 러너 |
| `test_patch` | 단일 diff | 단일 + `test_patch_backend/frontend` 분리 옵션 | 프런트/백 독립 실행 |
| `environment_setup_commit` | 단일 commit | `environment` 객체 (python/node 버전 + lock SHA) | 멀티 런타임 |
| `pr_number` / `pr_url` / `pr_labels` | 없음 | 있음 | PR 기반이라 원본 링크 중요 |
| `stack_domain` | 없음 | `backend_only` / `frontend_only` / `fullstack` | 부분 점수 분석 |
| `contamination_tier` | 없음 | 있음 | 공정성 설계 핵심 |
| `schema_version` | 없음 | `"0.1"` | 스키마 진화 관리 |

## 필드 상세

### 식별자

- **`instance_id`** — `<owner>__<repo>-<pr_number>`. 예: `fastapi__full-stack-fastapi-template-1234`.
  SWE-bench 컨벤션(`__` 구분)을 그대로 따름. 파일명 안전 문자만 허용.
- **`repo`** — `owner/name` 형식. 하네스가 git clone 대상 결정.
- **`pr_number`** — 머지된 PR 번호. `base_commit` / `head_commit` 추출 근거.

### 커밋

- **`base_commit`** — 에이전트 시작 상태. PR 의 머지 베이스 (=`pull/N/base.sha`).
- **`head_commit`** — 참조 솔루션 상태. PR 의 머지 커밋. `patch` = `diff(base_commit, head_commit)` - test files.

### 태스크 본문

- **`problem_statement`** — 에이전트에게 전달되는 NL 기술서.
  우선순위: (a) closing issue body → (b) PR description 전체. 둘 다 없으면 큐레이션 시 수동 작성.
- **`hints_text`** — 해결 힌트를 흘릴 수 있는 텍스트 (리뷰 코멘트, 커밋 메시지 등). 기본 평가 시 노출 금지.

### 패치

- **`patch`** — 정답 diff. **테스트 파일 제외**. 에이전트가 생성해야 할 코드 변경의 참조.
- **`test_patch`** — 테스트 파일 diff 전체. 하네스가 태스크 주입 시 적용.
- **`test_patch_backend` / `test_patch_frontend`** — 옵션. `backend/` 와 `frontend/` 경로로 분리한 diff. 프런트만/백만 테스트 재실행 같은 세분화된 스코어링에 사용.

### 테스트 분류

- **`fail_to_pass`** — 통과 = 태스크 완수. `backend` 와 `frontend` 모두 명시 (빈 배열 OK, 둘 다 비면 태스크 무효).
- **`pass_to_pass`** — 리그레션 가드. `base_commit` 에서도 통과하던 테스트 집합.

### 스코어링 규약 (v1)

```
score(instance) =
  1  if all(fail_to_pass.backend ∪ frontend pass on agent_patch)
     and all(pass_to_pass.backend ∪ frontend still pass)
  0  otherwise
```

부분 점수(frontend만 성공) 는 `stack_domain` 필드 활용해 **분석 단계**에서만 도출 — 공식 스코어는 이진 (SWE-bench 호환).

### 환경

- **`environment.python_version`** / **`node_version`** — 하네스 컨테이너 베이스 이미지 태그 결정.
- **`uv_lock_sha`** / **`bun_lock_sha`** / **`docker_compose_sha`** — `base_commit` 시점 lock 파일 콘텐츠 해시. 하네스가 의존성 캐시 키로 활용.
- **`setup_commit`** — 옵션. 의존성 설치 시점 commit 이 `base_commit` 과 달라야 할 때만 지정.

### 오염 방어

- **`contamination_tier`**:
  - `public` — `created_at` 이 모든 대상 모델 cutoff 이전. 공개 리더보드에 포함.
  - `held_out` — 어떤 대상 모델의 cutoff 이후. 시즌 단위 로테이션.
  - `internal_only` — 공개 시 leak 위험이 큰 태스크 (예: 아주 유명한 이슈). 내부 dev loop 전용.

분류 기준 상세는 PLAN.md §5.2.

### 메타

- **`difficulty`** — 큐레이션 후 수동 라벨. `easy` / `medium` / `hard`.
- **`notes`** — 큐레이터 메모. "이 PR 은 원래 multi-commit 이었는데 squashed-only", "test flake 가능성" 등.

## 예시 (가상)

```jsonc
{
  "instance_id": "fastapi__full-stack-fastapi-template-1234",
  "repo": "fastapi/full-stack-fastapi-template",
  "pr_number": 1234,
  "pr_url": "https://github.com/fastapi/full-stack-fastapi-template/pull/1234",
  "pr_title": "Add item archive endpoint",
  "pr_author": "exampleuser",
  "pr_labels": ["feature"],
  "base_commit": "0123456789abcdef0123456789abcdef01234567",
  "head_commit": "abcdef0123456789abcdef0123456789abcdef01",
  "problem_statement": "Users should be able to archive an item without deleting it. Add POST /api/v1/items/{id}/archive ...",
  "patch": "diff --git a/backend/app/api/routes/items.py ...",
  "test_patch": "diff --git a/backend/app/tests/api/routes/test_items.py ...",
  "test_patch_backend": "diff --git a/backend/app/tests/api/routes/test_items.py ...",
  "test_patch_frontend": "diff --git a/frontend/tests/items.spec.ts ...",
  "fail_to_pass": {
    "backend": [
      "backend/app/tests/api/routes/test_items.py::test_archive_item_success",
      "backend/app/tests/api/routes/test_items.py::test_archive_item_idempotent"
    ],
    "frontend": [
      "frontend/tests/items.spec.ts:42:3 › Items › archive button toggles state"
    ]
  },
  "pass_to_pass": {
    "backend": ["backend/app/tests/api/routes/test_items.py::test_create_item"],
    "frontend": []
  },
  "stack_domain": "fullstack",
  "environment": {
    "python_version": "3.11",
    "node_version": "20",
    "uv_lock_sha": "sha256:...",
    "bun_lock_sha": "sha256:...",
    "docker_compose_sha": "sha256:..."
  },
  "created_at": "2026-02-14T08:31:00Z",
  "contamination_tier": "held_out",
  "difficulty": "medium",
  "notes": "Closing issue linked via 'Closes #1230'. PR includes minor refactor in items.py that is unrelated but kept to preserve patch atomicity.",
  "schema_version": "0.1"
}
```

## v0.2 로 옮길 후보 (미확정)

- Partial credit 스코어링 공식화 (현재 v1 은 이진).
- `required_files_readonly` — 에이전트가 편집하면 안 되는 파일 화이트리스트.
- `dependency_delta` — 의존성 추가/제거 선언적 표기 (uv.lock diff 보다 가독성 목적).
- `tool_budget` — 태스크별 에이전트 turn/time 예산 권장값.

# 코드 되돌리기(revert) 리허설 — 2026-10-23 (P1-2)

목적: 운영 배포 뒤 문제가 생겼을 때 **코드만** `git revert` 로 되돌리는 절차가 실제로 막힘없이 되는지, 시간이 얼마나 드는지 한 번 재현해 둔다. 로컬에서만 수행, push 없음.

## 결과 요약

| 항목 | 값 |
|---|---|
| revert 대상 | `b251d8d` 수주 상태 정리 r4 (정정 루틴 fail-closed D18·부분 취소 차단 D19, 마이그레이션 없음, 4파일 189+/25-) |
| 기준 HEAD | `e94e7f8` (복구 커밋, 2026-10-23) |
| 작업 위치 | 별도 worktree + 브랜치 `rehearsal/revert` (주 작업 트리 불변) |
| `git revert --no-edit b251d8d` | 충돌 없음 → `b36bb9b`, 즉시 |
| 전체 pytest | **472 passed**, 1 warning, 42분 13초 (14:41:15 → 15:23:29) |
| 뒷정리 | worktree 제거·브랜치 삭제 (push 안 함) |

revert 뒤 테스트 수가 478 → 472 인 것은 b251d8d 가 넣은 r4 테스트 6건이 함께 되돌아갔기 때문이다(코드와 테스트가 같은 커밋이므로 정상).

## 절차 (재현용)

```bash
git worktree add -b rehearsal/revert <임시경로> <기준 HEAD>
cd <임시경로>
git revert --no-edit <되돌릴 SHA>        # 충돌 나면 해결 후 git revert --continue
python -m pytest tests -q -p no:cacheprovider
# 운영에 적용할 때만: main 에서 같은 revert 를 만들고 push (CI → Cloud 자동 배포)
cd - && git worktree remove <임시경로> && git branch -D rehearsal/revert
```

## 교훈·주의

- **마이그레이션이 섞인 커밋은 revert 로 복구되지 않는다.** `git revert` 는 코드·파일만 되돌리고 운영 DB 스키마·데이터는 그대로다. 그런 커밋은 DB 되돌리기 절차(`docs/db-migration-guide.md` §3 롤백, 유형별 08 §2)를 **따로** 먼저 정하고, 코드 revert 는 그 다음이다. 되돌릴 커밋에 `supabase/migrations/` 변경이 있는지 `git show --stat <SHA>` 로 먼저 본다.
- 되돌릴 커밋이 HEAD 가 아니면(사이에 다른 커밋이 있으면) 충돌 가능성이 있다. 이번에는 사이 커밋 4개(778e199·2e03092·e94e7f8 등)가 다른 파일만 건드려 충돌이 없었다.
- 전체 pytest 가 42분이라 "되돌리기 결정 → 배포" 최단 소요는 약 50분(테스트 포함). 긴급 시 회귀 묶음(`tests/test_so_close*.py` 등 관련 파일만, 약 10분)으로 먼저 push 하고 전체는 뒤따라 돌리는 선택지를 열어 둔다 — 그 판단은 기획·검토 세션 승인.
- worktree 는 `.streamlit/secrets.toml` 을 갖지 않는다. 테스트는 conftest 가짜 secrets 로 돌아 문제없지만, 앱을 실제로 띄우려면 복사해야 한다(운영 DB 를 가리키므로 띄우지 않는 편이 안전).

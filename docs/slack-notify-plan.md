# 슬랙 알림 구현 계획 (2026-08-12 사용자 합의)

앱의 업무 분기점마다 슬랙 채널로 알림을 보낸다. 이 문서는 다른 세션에서
작업을 이어받기 위한 스펙이다. 구현 전 반드시 repo 루트 CLAUDE.md 참고.

## 합의된 방식

- **Incoming Webhook 1개** (채널 단위, 관리자가 생성) — 직원별 슬랙 연동 없음
- 메시지는 봇 명의로 게시, **처리자는 앱 로그인 실명을 본문에 표기**
  (`current_user_name()` — 원장 created_by와 같은 값)
- 전송 실패가 업무 처리를 막으면 안 됨: 백그라운드 스레드 + 짧은 타임아웃
  + 실패 무시(로그만). st.rerun() 전에 발사(fire-and-forget)
- webhook_url은 `st.secrets["slack"]["webhook_url"]` (secrets.toml.example에
  자리 있음). 로컬/클라우드 secrets 양쪽에 넣어야 함. **미설정 시 조용히 스킵**
  (테스트·로컬 환경에서 에러 금지)

## 알림 지점 (6종으로 시작)

| 이벤트 | 코드 위치 힌트 (streamlit_app.py) |
|---|---|
| 발주 (발주서 발송/상태 SENT) | 발주/입고 페이지, PO 상태 변경·새 발주서 작성 |
| 소재 입고 | 발주/입고 > 입고 처리 탭 (txn_type=RECEIPT, W-LOT 발행) |
| 작업 투입 | 공정 관리 투입 등록 (wo_events INPUT insert 지점) |
| 작업 완료(인수) | `_wo_apply()` event RECEIVE |
| 외주 투입 | `_wo_apply()` event OUT_SEND |
| 외주 완료(회수) | `_wo_apply()` event OUT_RETURN |

공정 4종은 전부 `_wo_apply()` 한 함수를 지나므로 그 안에서 event_type을 보고
분기하면 된다. 라우팅(product_routing) 기능이 먼저 들어가면 외주 알림에
공정명(예: "에이징 출고 → ○○열처리")을 포함할 것.

## 메시지 포맷 예

```
[투입] HDVN-03 500 EA · 소재 W2608-012 — 김준오
[외주 출고] MRG6-07 480 EA · 에이징 → 성보정밀 — 황민혁
[입고] W2608-015 · S45C Ø45 300kg — 명진메탈 (염정원)
```

- 채널 구성(단일 vs 분리)과 웹훅 URL은 사용자가 슬랙 셋업 후 제공 예정
- 이벤트별 on/off 설정(app_settings)은 2차 — 처음엔 6종 고정으로 시작

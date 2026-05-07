# 🏭 우성정밀 업무관리 시스템

부산 우성정밀의 발주·재고·생산·매출을 통합 관리하는 사내용 웹앱.

## 🎯 목표

수기/엑셀/슬랙으로 분산된 업무를 단일 시스템으로:
- 발주서 자동 생성·송부 (월간 루틴 자동화)
- BOM 기반 자재 필요량 산출 + 부족 알림
- 생산 일정·실적 통합 (현장 모바일 입력)
- 매출/매입 자동 대조 + 미수금 관리
- 사급↔도급 전환 자동 탐지 + 마진 분석

## 📐 아키텍처

```
[구글시트 raw 입력]      [Supabase PostgreSQL]      [Streamlit Cloud 웹]
매출전표 ──매시간 sync──→  sales_ledger        ←──→  발주·재고·생산 화면
매입내역 ──매시간 sync──→  purchase_ledger     ←──→  마스터 관리
생산일정/일일보고 ──sync→  production_*        ←──→  현장 모바일 입력

마스터 (앱이 권위):
  product_master / vendors / materials / bom / drawings

매일 자정 → Google Drive 자동 백업
```

## 🛠 기술 스택

- **앱**: Streamlit (Python 3.11)
- **DB**: Supabase (PostgreSQL, 무료 500MB)
- **호스팅**: Streamlit Community Cloud (무료)
- **인증**: streamlit-authenticator (1차) → Google OAuth (추후)
- **백업**: Google Drive API (서비스 어카운트)
- **외부 연동**: gspread (구글시트), Slack Webhook

## 📊 마스터 데이터 현황 (2026-05 기준)

| 마스터 | 건수 | 상태 |
|---|---|---|
| 제품 | 834건 | alias 166 / 조달유형 시점 분기 / 도면품번·BOM 매핑 |
| 자재 | 308건 | 재질·규격 정규화, 주공급사 매핑 |
| BOM | ~310건 | 활성 매출 97% 커버 |
| 거래처 | 201건 | 카테고리 자동 태깅 |
| 도면 | 2,778건 | 고객사·리비전 추적 |

## 🚧 개발 단계

- [x] Stage 0: 환경 구축 (현재 진행 중)
- [ ] Stage 1: 마스터 import + PMLib 포팅
- [ ] Stage 2: Phase 1 발주 모듈 MVP
- [ ] Stage 3: 시범 운영
- [ ] Stage 4: Phase 2 입출고·생산 통합
- [ ] Stage 5: Phase 3 매출 대조
- [ ] Stage 6: Phase 4 대시보드

## 📞 운영

- 운영 책임: 김민수 (PO 담당)
- 시스템 관리: 클로드 (코드 작성·배포 전담)
- 사용자: 김민수, 염정원, 김준오, 황민혁 (단계별 합류)

-- 064: 발주 발송 기록 (2026-09-16)
-- [발송 완료 처리] / 앱 메일 발송 시 받는 주소와 메시지 ID 를 남긴다.
-- 메일 발송 기능은 secrets [mail].enabled 로 켤 때까지 UI 에 나타나지 않는다.
alter table public.purchase_orders
  add column if not exists sent_to text,
  add column if not exists mail_message_id text;

comment on column public.purchase_orders.sent_to is
  '발송 시 받는 주소 목록(앱 메일 발송). 수동 [발송 완료 처리]는 null';
comment on column public.purchase_orders.mail_message_id is
  '앱 메일 발송의 Message-ID (수동 발송 완료는 null)';

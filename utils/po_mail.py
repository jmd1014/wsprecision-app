"""발주서 메일 발송 (2026-09-16) — 회사 메일 계정(SMTP)으로 PDF 를 첨부해 보낸다.

기능은 만들어 두되 secrets ``[mail].enabled = true`` 로 켜기 전까지는 앱에
버튼이 나타나지 않는다 (사용자 결정: 발송은 사용 안정화 이후 적용, 그때까지
작성 → 수동 메일 → [발송 완료 처리]).

secrets.toml::

    [mail]
    enabled = false            # true 로 바꾸면 [메일로 발송] 버튼이 생긴다
    smtp_host = "smtp.naver.com"
    smtp_port = 465            # 465 = SSL, 587 = STARTTLS
    use_ssl = true
    user = "order@example.com" # 발신 계정 (로그인 ID)
    password = "앱 비밀번호"
    sender_name = "우성정밀 구매"
    reply_to = ""              # 비우면 발신 계정으로 회신
    cc = ""                    # 콤마 구분 — 담당자 참조
    test_to = ""               # 값이 있으면 모든 메일을 이 주소로만 보낸다(테스트 모드)

네트워크가 필요한 부분(send_message)과 메시지 조립(build_message)을 분리해
조립은 테스트한다.
"""
from __future__ import annotations

import smtplib
import ssl
from email.message import EmailMessage
from email.utils import formataddr, make_msgid

_KEYS = ("smtp_host", "smtp_port", "use_ssl", "user", "password",
         "sender_name", "reply_to", "cc", "test_to")


def _split(v) -> list:
    if not v:
        return []
    if isinstance(v, (list, tuple)):
        return [str(x).strip() for x in v if str(x).strip()]
    return [x.strip() for x in str(v).replace(";", ",").split(",")
            if x.strip()]


def mail_cfg(secrets) -> dict | None:
    """secrets 에서 [mail] 설정을 읽는다. 꺼져 있거나 필수값이 없으면 None."""
    try:
        m = secrets["mail"]
    except Exception:
        return None
    try:
        enabled = bool(m.get("enabled", False))
    except Exception:
        return None
    if not enabled:
        return None
    cfg = {k: m.get(k) for k in _KEYS}
    if not (cfg.get("smtp_host") and cfg.get("user") and cfg.get("password")):
        return None
    cfg["use_ssl"] = bool(cfg.get("use_ssl", True))
    try:
        cfg["smtp_port"] = int(cfg.get("smtp_port") or (465 if cfg["use_ssl"] else 587))
    except (TypeError, ValueError):
        cfg["smtp_port"] = 465 if cfg["use_ssl"] else 587
    cfg["cc"] = _split(cfg.get("cc"))
    cfg["test_to"] = (str(cfg.get("test_to") or "").strip() or None)
    cfg["reply_to"] = (str(cfg.get("reply_to") or "").strip() or None)
    cfg["sender_name"] = (str(cfg.get("sender_name") or "").strip()
                          or str(cfg["user"]))
    return cfg


def po_subject(company: str, po_no: str) -> str:
    return f"[{company}] 발주서 {po_no}"


def po_body(company: str, po_no: str, vendor: str, po_date, delivery,
            n_items: int, total, contact: str | None = None) -> str:
    lines = [
        f"{vendor} 담당자님,",
        "",
        f"{company} 발주서를 보내드립니다. 첨부 PDF 를 확인 부탁드립니다.",
        "",
        f"  발주 번호 : {po_no}",
        f"  발주일    : {po_date or '-'}",
        f"  납기      : {delivery or '-'}",
        f"  품목      : {n_items}건 · 합계 {float(total or 0):,.0f}원 (VAT 별도)",
    ]
    if contact:
        lines += ["", f"  담당 : {contact}"]
    lines += ["", "감사합니다.", company]
    return "\n".join(lines)


def build_message(cfg: dict, *, to, subject: str, body: str,
                  pdf_bytes: bytes, filename: str, cc=None,
                  reply_to: str | None = None) -> EmailMessage:
    """받는 사람·참조·제목·본문·PDF 첨부로 메시지를 조립한다.

    발신은 항상 회사 계정(cfg.user) 하나이고, 담당자 구분은 reply_to(로그인
    사용자 이메일)로 한다 — 계정별로 SMTP 비밀번호를 받지 않아도 거래처
    답장이 담당자에게 간다 (2026-09-16 사용자 질문). cc 는 설정값에 담당자
    이메일을 더한 것.
    test_to 가 설정돼 있으면 받는 사람을 그 주소 하나로 바꾸고 참조는 뺀다
    (실제 발송 전 확인용). 원래 받는 사람은 X-PO-Original-To 헤더에 남긴다.
    """
    to = _split(to)
    cc = _split(cc) if cc is not None else list(cfg.get("cc") or [])
    msg = EmailMessage()
    msg["From"] = formataddr((cfg["sender_name"], cfg["user"]))
    if cfg.get("test_to"):
        msg["X-PO-Original-To"] = ", ".join(to + cc)
        to, cc = [cfg["test_to"]], []
    if not to:
        raise ValueError("받는 사람 이메일이 없습니다")
    msg["To"] = ", ".join(to)
    if cc:
        msg["Cc"] = ", ".join(cc)
    _rt = (reply_to or "").strip() or cfg.get("reply_to")
    if _rt:
        msg["Reply-To"] = _rt
    msg["Subject"] = subject
    msg["Message-ID"] = make_msgid()
    msg.set_content(body)
    msg.add_attachment(pdf_bytes, maintype="application", subtype="pdf",
                       filename=filename)
    return msg


def recipients(msg: EmailMessage) -> list:
    out = []
    for h in ("To", "Cc"):
        out += _split(msg.get(h))
    return out


def send_message(cfg: dict, msg: EmailMessage, timeout: float = 20.0) -> str:
    """SMTP 로 보낸다. 성공하면 Message-ID 를 돌려주고, 실패는 예외로."""
    host, port = cfg["smtp_host"], int(cfg["smtp_port"])
    ctx = ssl.create_default_context()
    if cfg.get("use_ssl", True):
        with smtplib.SMTP_SSL(host, port, context=ctx, timeout=timeout) as s:
            s.login(cfg["user"], cfg["password"])
            s.send_message(msg)
    else:
        with smtplib.SMTP(host, port, timeout=timeout) as s:
            s.ehlo()
            s.starttls(context=ctx)
            s.login(cfg["user"], cfg["password"])
            s.send_message(msg)
    return str(msg["Message-ID"])


def send_po_mail(cfg: dict, *, to, subject: str, body: str, pdf_bytes: bytes,
                 filename: str, cc=None, reply_to: str | None = None
                 ) -> tuple[str, list]:
    """조립 + 발송. (message_id, 실제 받는 주소 목록)"""
    msg = build_message(cfg, to=to, subject=subject, body=body,
                        pdf_bytes=pdf_bytes, filename=filename, cc=cc,
                        reply_to=reply_to)
    mid = send_message(cfg, msg)
    return mid, recipients(msg)

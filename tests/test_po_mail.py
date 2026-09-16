# -*- coding: utf-8 -*-
"""발주서 메일 조립 — 네트워크 없이 검증 (2026-09-16)."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from utils.po_mail import (mail_cfg, build_message, po_subject, po_body,  # noqa: E402
                           recipients)

_BASE = {"enabled": True, "smtp_host": "smtp.example.com", "smtp_port": "465",
         "use_ssl": True, "user": "order@example.com", "password": "x",
         "sender_name": "우성정밀 구매", "cc": "buyer@example.com"}


def test_cfg_disabled_or_missing_returns_none():
    assert mail_cfg({}) is None
    assert mail_cfg({"mail": {**_BASE, "enabled": False}}) is None
    assert mail_cfg({"mail": {**_BASE, "password": ""}}) is None


def test_cfg_parses_port_cc_and_defaults():
    cfg = mail_cfg({"mail": {**_BASE, "smtp_port": "", "use_ssl": False,
                             "cc": "a@x.com; b@x.com", "test_to": " "}})
    assert cfg["smtp_port"] == 587 and cfg["use_ssl"] is False
    assert cfg["cc"] == ["a@x.com", "b@x.com"]
    assert cfg["test_to"] is None and cfg["reply_to"] is None


def test_build_message_headers_and_attachment():
    cfg = mail_cfg({"mail": {**_BASE, "reply_to": "kim@example.com"}})
    msg = build_message(cfg, to="vendor@v.com",
                        subject=po_subject("우성정밀", "PO-202609-004"),
                        body=po_body("우성정밀", "PO-202609-004", "(주)명진메탈",
                                     "2026-09-16", "2026-09-30", 5, 3240000,
                                     "김민수"),
                        pdf_bytes=b"%PDF-1.4 test", filename="PO-202609-004.pdf")
    assert msg["To"] == "vendor@v.com"
    assert msg["Cc"] == "buyer@example.com"
    assert msg["Reply-To"] == "kim@example.com"
    assert "PO-202609-004" in msg["Subject"]
    assert msg["Message-ID"].startswith("<")
    atts = [p for p in msg.iter_attachments()]
    assert len(atts) == 1 and atts[0].get_filename() == "PO-202609-004.pdf"
    assert atts[0].get_content_type() == "application/pdf"
    assert "3,240,000" in msg.get_body(preferencelist=("plain",)).get_content()
    assert recipients(msg) == ["vendor@v.com", "buyer@example.com"]


def test_test_to_overrides_recipients():
    cfg = mail_cfg({"mail": {**_BASE, "test_to": "me@example.com"}})
    msg = build_message(cfg, to=["vendor@v.com"], subject="s", body="b",
                        pdf_bytes=b"x", filename="a.pdf")
    assert msg["To"] == "me@example.com" and msg["Cc"] is None
    assert "vendor@v.com" in msg["X-PO-Original-To"]


def test_missing_recipient_raises():
    cfg = mail_cfg({"mail": {**_BASE, "cc": ""}})
    try:
        build_message(cfg, to="", subject="s", body="b", pdf_bytes=b"x",
                      filename="a.pdf")
    except ValueError:
        return
    raise AssertionError("빈 받는 사람은 예외여야 함")

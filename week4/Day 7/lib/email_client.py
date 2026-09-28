"""
lib/email_client.py — Day 4, Task 4

# STATUS: CODE-COMPLETE | Tested only with --dry-run flag
# RUN ON USER MACHINE (dry run, no network):
#   python -c "import asyncio; from lib.email_client import EmailClient; asyncio.run(EmailClient(dry_run=True).send_confirmation('client@example.com', 'LAH-0004', '2026-09-30 15:00', 'Hajra'))"
# RUN LIVE (after .env has EMAIL_MODE + credentials set):
#   same code with EmailClient(dry_run=False)
# EXPECTED OUTPUT: {'status': 'sent', ...} ONLY if smtplib/Gmail API actually
#   accepted the message. On any failure returns {'status': 'error', ...}.

Two modes, selected by EMAIL_MODE env var:
  - "smtp"      : smtplib + Gmail App Password (simplest)
  - "gmail_api" : Gmail API + OAuth token (same as CalendarClient)

Env loading: this module calls load_dotenv() at import time so that even if
the calling script forgets to load .env, the SMTP/API credentials are
available. override=False means a real environment variable always wins.
"""
from __future__ import annotations

import asyncio
import logging
import os
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from pathlib import Path
from typing import Any, Dict, Optional

# ----- Load .env at import time (defensive) -----
try:
    from dotenv import load_dotenv

    _ENV_PATH = Path(r"D:\Qasim Rajput\Doc\.env")
    if _ENV_PATH.exists():
        load_dotenv(_ENV_PATH, override=False)
except Exception:
    # If dotenv isn't installed or path doesn't exist, fall through.
    # Env vars must then be set by the calling process.
    pass

from lib import rag_lib  # noqa: E402

logger = logging.getLogger("day4.email_client")


class EmailClient:
    def __init__(
        self,
        mode: Optional[str] = None,
        dry_run: bool = False,
        smtp_host: str = "smtp.gmail.com",
        smtp_port: int = 587,
    ) -> None:
        self.mode = mode or os.environ.get("EMAIL_MODE", "smtp")
        self.dry_run = dry_run
        self.smtp_host = smtp_host
        self.smtp_port = smtp_port
        if self.mode not in ("smtp", "gmail_api"):
            raise ValueError(f"EMAIL_MODE must be 'smtp' or 'gmail_api', got {self.mode!r}")

    # ------------------------------------------------------------------ body
    @staticmethod
    def _property_facts(property_id: str) -> Optional[Dict[str, Any]]:
        return rag_lib.get_property(property_id)

    @staticmethod
    def _render_bodies(
        property_id: str,
        visit_time: str,
        agent_name: str,
        prop: Optional[Dict[str, Any]],
    ) -> Dict[str, str]:
        if prop:
            addr = f"{prop['area']}, {prop['city']}"
            price = prop.get("price_formatted") or rag_lib.format_price(prop.get("price_pkr"))
            beds = prop.get("bedrooms")
            beds_line = f"{beds} bedroom, " if beds not in (None, "") else ""
            details_line = f"{beds_line}{prop['property_type']}, {addr} — {price}"
            link = prop.get("source_url") or ""
        else:
            details_line = f"Property {property_id} (details unavailable right now)"
            link = ""

        subject = f"Site Visit Confirmed — {property_id} — {visit_time}"

        text_body = (
            f"Assalam-o-Alaikum,\n\n"
            f"Ji, aap ki site visit confirm ho gayi hai:\n\n"
            f"  Property : {details_line}\n"
            f"  Visit time: {visit_time}\n"
            f"  Agent    : {agent_name}, RealEstate Hub\n\n"
            + (f"  More details: {link}\n\n" if link else "")
            + f"Waqt par pohanch jayen, agent aap ka wahan intezar karenge. "
            f"Agar koi tabdeeli chahiye ho to hamein reply kar dein ya call kar lein.\n\n"
            f"Shukriya,\n{agent_name}\nRealEstate Hub"
        )

        html_body = f"""\
<html><body style="font-family:Arial,sans-serif;font-size:14px;color:#222;">
  <p>Assalam-o-Alaikum,</p>
  <p>Ji, aap ki site visit <strong>confirm</strong> ho gayi hai:</p>
  <table cellpadding="6" style="border-collapse:collapse;">
    <tr><td><strong>Property</strong></td><td>{details_line}</td></tr>
    <tr><td><strong>Visit time</strong></td><td>{visit_time}</td></tr>
    <tr><td><strong>Agent</strong></td><td>{agent_name}, RealEstate Hub</td></tr>
  </table>
  {f'<p><a href="{link}">Property ki tafseelat / more details</a></p>' if link else ''}
  <p>Waqt par pohanch jayen, agent aap ka wahan intezar karenge. Agar koi
  tabdeeli chahiye ho to hamein reply kar dein ya call kar lein.</p>
  <p>Shukriya,<br/>{agent_name}<br/>RealEstate Hub</p>
</body></html>"""

        return {"subject": subject, "text": text_body, "html": html_body}

    # --------------------------------------------------------------- public
    async def send_confirmation(
        self, to: str, property_id: str, visit_time: str, agent_name: str
    ) -> Dict[str, Any]:
        prop = await asyncio.to_thread(self._property_facts, property_id)
        rendered = self._render_bodies(property_id, visit_time, agent_name, prop)

        if self.dry_run:
            print("----- DRY RUN: email NOT sent -----")
            print(f"To     : {to}")
            print(f"Subject: {rendered['subject']}")
            print(rendered["text"])
            print("------------------------------------")
            return {
                "status": "dry_run",
                "to": to,
                "subject": rendered["subject"],
                "mode": self.mode,
                "property_found": prop is not None,
            }

        try:
            if self.mode == "smtp":
                await asyncio.to_thread(self._send_smtp, to, rendered)
            else:
                await asyncio.to_thread(self._send_gmail_api, to, rendered)
            logger.info("email_client.send_confirmation -> sent to=%s mode=%s", to, self.mode)
            return {"status": "sent", "to": to, "subject": rendered["subject"], "mode": self.mode}
        except Exception as e:
            logger.exception("email_client.send_confirmation failed")
            return {"status": "error", "to": to, "mode": self.mode, "error": f"{type(e).__name__}: {e}"}

    # ---------------------------------------------------------------- smtp
    def _send_smtp(self, to: str, rendered: Dict[str, str]) -> None:
        # Read env vars LAZILY (at call time, not import time)
        user = os.environ.get("GMAIL_ADDRESS") or os.environ.get("GMAIL_SENDER") or os.environ.get("SMTP_USER")
        app_password = os.environ.get("GMAIL_APP_PASSWORD")

        if not user or not app_password:
            raise RuntimeError(
                "EMAIL_MODE=smtp requires GMAIL_ADDRESS (or GMAIL_SENDER) and "
                "GMAIL_APP_PASSWORD in .env. "
                f"Current: GMAIL_ADDRESS={bool(user)}, GMAIL_APP_PASSWORD={bool(app_password)}. "
                "See scripts/setup_google_cloud.py for how to create an app password."
            )

        logger.info("smtp_sending from=%s to=%s host=%s port=%d",
                    user, to, self.smtp_host, self.smtp_port)

        msg = MIMEMultipart("alternative")
        msg["Subject"], msg["From"], msg["To"] = rendered["subject"], user, to
        msg.attach(MIMEText(rendered["text"], "plain", "utf-8"))
        msg.attach(MIMEText(rendered["html"], "html", "utf-8"))

        with smtplib.SMTP(self.smtp_host, self.smtp_port, timeout=30) as server:
            server.starttls()
            server.login(user, app_password)
            server.sendmail(user, [to], msg.as_string())

        logger.info("smtp_sent to=%s subject=%s", to, rendered["subject"])

    # ------------------------------------------------------------ gmail_api
    def _send_gmail_api(self, to: str, rendered: Dict[str, str]) -> None:
        import base64

        from googleapiclient.discovery import build

        from lib.google_auth import GoogleAuth

        creds = GoogleAuth().get_credentials()
        service = build("gmail", "v1", credentials=creds, cache_discovery=False)

        msg = MIMEMultipart("alternative")
        msg["Subject"], msg["To"] = rendered["subject"], to
        msg.attach(MIMEText(rendered["text"], "plain", "utf-8"))
        msg.attach(MIMEText(rendered["html"], "html", "utf-8"))
        raw = base64.urlsafe_b64encode(msg.as_bytes()).decode("utf-8")

        service.users().messages().send(userId="me", body={"raw": raw}).execute()
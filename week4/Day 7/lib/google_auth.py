"""
lib/google_auth.py — Day 4, Task 2

# STATUS: CODE-COMPLETE | UNTESTED — requires live OAuth + network
# RUN ON USER MACHINE:
#   python -c "from lib.google_auth import GoogleAuth; GoogleAuth().get_credentials()"
# EXPECTED OUTPUT: a browser window opens asking you to log into the Google
#   account you added as a Test user, approve the Calendar + Gmail scopes, then
#   the console prints "Saved token to <path>" and token.json exists next to
#   credentials.json.
#
# IMPORTANT — Testing-mode expiry: because the OAuth consent screen is left in
# "Testing" publishing status (see scripts/setup_google_cloud.py), Google
# expires the refresh token in token.json after 7 days. When it expires, every
# call in this file will start raising RefreshError; get_credentials() detects
# that and will prompt you to re-run the interactive login instead of silently
# failing. To stop this happening every week, move the OAuth consent screen to
# "In production" in the Cloud Console (no Google review is required for an
# app with only these two scopes if it stays under 100 users).

Install (already listed in the Day 4 prompt's quick reference):
    pip install google-api-python-client google-auth-httplib2 google-auth-oauthlib
"""
from __future__ import annotations

import logging
import os
from typing import List, Optional

logger = logging.getLogger("day4.google_auth")

SCOPES: List[str] = [
    "https://www.googleapis.com/auth/calendar",
    "https://www.googleapis.com/auth/calendar.events",
    "https://www.googleapis.com/auth/gmail.send",
]

DEFAULT_CREDENTIALS_PATH = os.environ.get(
    "GOOGLE_CREDENTIALS_PATH", r"D:/Qasim Rajput/Intership/2026/Geek3/Week 4/Day 4/day4_deliverables/day4/docs/credentials.json"
)


class GoogleAuthError(Exception):
    """Raised when credentials cannot be obtained and the caller must act
    (re-run interactive login, fix a missing file, etc.)."""


class GoogleAuth:
    """Handles first-run OAuth (Desktop flow) and silent token refresh.

    Usage:
        creds = GoogleAuth().get_credentials()
        service = build("calendar", "v3", credentials=creds)
    """

    def __init__(
        self,
        credentials_path: Optional[str] = None,
        token_path: Optional[str] = None,
        scopes: Optional[List[str]] = None,
    ) -> None:
        self.credentials_path = credentials_path or DEFAULT_CREDENTIALS_PATH
        self.token_path = token_path or os.path.join(
            os.path.dirname(self.credentials_path), "token.json"
        )
        self.scopes = scopes or SCOPES

    def get_credentials(self):
        """Returns a google.oauth2.credentials.Credentials object.

        Order of attempts:
          1. Load token.json if present.
          2. If expired but refreshable, refresh it silently.
          3. Otherwise run the interactive browser flow and save a new token.json.

        Raises GoogleAuthError with a clear message on any unrecoverable case
        (missing credentials.json, revoked token that needs a fresh login, etc.)
        — it never fabricates or returns a fake credentials object.
        """
        try:
            from google.auth.transport.requests import Request
            from google.oauth2.credentials import Credentials
            from google_auth_oauthlib.flow import InstalledAppFlow
            from google.auth.exceptions import RefreshError
        except ImportError as e:
            raise GoogleAuthError(
                "google-auth / google-auth-oauthlib is not installed. Run: "
                "pip install google-api-python-client google-auth-httplib2 "
                "google-auth-oauthlib"
            ) from e

        creds = None

        if os.path.exists(self.token_path):
            try:
                creds = Credentials.from_authorized_user_file(self.token_path, self.scopes)
                logger.info("Loaded existing token from %s", self.token_path)
            except (ValueError, OSError) as e:
                logger.warning("token.json exists but is unreadable (%s); re-authenticating", e)
                creds = None

        if creds and creds.valid:
            return creds

        if creds and creds.expired and creds.refresh_token:
            try:
                creds.refresh(Request())
                self._save_token(creds)
                logger.info("Refreshed expired token")
                return creds
            except RefreshError as e:
                logger.warning(
                    "Token refresh failed (%s) — likely revoked or the 7-day "
                    "Testing-mode limit was hit. Falling through to interactive "
                    "re-authentication.",
                    e,
                )
                creds = None

        # First run, or refresh failed: interactive browser flow.
        if not os.path.exists(self.credentials_path):
            raise GoogleAuthError(
                f"credentials.json not found at {self.credentials_path}. Run "
                f"scripts/setup_google_cloud.py first and download it from the "
                f"Cloud Console."
            )

        print(
            "\n[google_auth] Opening a browser window for you to log in and "
            "approve access. If no window opens, copy the URL that is printed "
            "into your browser manually.\n"
        )
        flow = InstalledAppFlow.from_client_secrets_file(self.credentials_path, self.scopes)
        creds = flow.run_local_server(port=0)
        self._save_token(creds)
        logger.info("Completed interactive OAuth login; saved token to %s", self.token_path)
        return creds

    def _save_token(self, creds) -> None:
        with open(self.token_path, "w", encoding="utf-8") as f:
            f.write(creds.to_json())
        print(f"Saved token to {self.token_path}")


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    GoogleAuth().get_credentials()
    print("OAuth check complete — token.json is valid.")

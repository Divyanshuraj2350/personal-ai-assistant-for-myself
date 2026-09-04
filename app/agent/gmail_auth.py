import json
from pathlib import Path

from google_auth_oauthlib.flow import Flow
from google.oauth2.credentials import Credentials
from google.auth.transport.requests import Request


# ---------------------------------------------------------
# Paths
# ---------------------------------------------------------

BASE_DIR = Path(__file__).resolve().parents[2]

CREDENTIALS_FILE = BASE_DIR / "credentials.json"
TOKEN_FILE = BASE_DIR / "token.json"
OAUTH_STATE_FILE = BASE_DIR / ".oauth_state.json"


# ---------------------------------------------------------
# Google OAuth configuration
# ---------------------------------------------------------

REDIRECT_URI = "http://127.0.0.1:8000/gmail/oauth2callback"

SCOPES = [
    "https://www.googleapis.com/auth/gmail.send"
]


# ---------------------------------------------------------
# Create OAuth authorization URL
# ---------------------------------------------------------

def create_authorization_url():

    if not CREDENTIALS_FILE.exists():
        raise FileNotFoundError(
            f"OAuth credentials file not found: {CREDENTIALS_FILE}"
        )

    flow = Flow.from_client_secrets_file(
        str(CREDENTIALS_FILE),
        scopes=SCOPES,
    )

    flow.redirect_uri = REDIRECT_URI

    authorization_url, state = flow.authorization_url(
        access_type="offline",
        prompt="consent",
        include_granted_scopes="true",
    )

    # Google-auth-oauthlib generates a PKCE code verifier.
    # We must save it because the callback uses a new Flow object.
    code_verifier = flow.code_verifier

    OAUTH_STATE_FILE.write_text(
        json.dumps(
            {
                "state": state,
                "code_verifier": code_verifier,
            }
        ),
        encoding="utf-8",
    )

    return authorization_url


# ---------------------------------------------------------
# Handle Google's OAuth callback
# ---------------------------------------------------------

def handle_oauth_callback(authorization_response: str):

    if not OAUTH_STATE_FILE.exists():
        raise RuntimeError(
            "OAuth session expired or was not started. "
            "Start the Gmail connection again."
        )

    try:
        oauth_data = json.loads(
            OAUTH_STATE_FILE.read_text(
                encoding="utf-8"
            )
        )

        state = oauth_data["state"]
        code_verifier = oauth_data["code_verifier"]

    except Exception as exc:

        raise RuntimeError(
            "Invalid OAuth session data. "
            "Start the Gmail connection again."
        ) from exc

    flow = Flow.from_client_secrets_file(
        str(CREDENTIALS_FILE),
        scopes=SCOPES,
        state=state,
        code_verifier=code_verifier,
    )

    flow.redirect_uri = REDIRECT_URI

    flow.fetch_token(
        authorization_response=authorization_response
    )

    credentials = flow.credentials

    save_credentials(credentials)

    # OAuth session is finished.
    try:
        OAUTH_STATE_FILE.unlink()
    except FileNotFoundError:
        pass

    return credentials


# ---------------------------------------------------------
# Save OAuth credentials
# ---------------------------------------------------------

def save_credentials(credentials):

    TOKEN_FILE.write_text(
        credentials.to_json(),
        encoding="utf-8",
    )


# ---------------------------------------------------------
# Load saved OAuth credentials
# ---------------------------------------------------------

def load_credentials():

    if not TOKEN_FILE.exists():
        return None

    try:

        credentials = Credentials.from_authorized_user_file(
            str(TOKEN_FILE),
            SCOPES,
        )

    except Exception:

        return None

    if (
        credentials
        and credentials.expired
        and credentials.refresh_token
    ):

        try:

            credentials.refresh(Request())

            save_credentials(credentials)

        except Exception:

            return None

    if credentials and credentials.valid:

        return credentials

    return None


# ---------------------------------------------------------
# Check whether Gmail is connected
# ---------------------------------------------------------

def is_gmail_connected():

    credentials = load_credentials()

    return credentials is not None

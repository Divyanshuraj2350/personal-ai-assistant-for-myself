import base64
from email.message import EmailMessage

from googleapiclient.discovery import build

from app.agent.gmail_auth import load_credentials


def send_email(recipient, subject, body):

    credentials = load_credentials()

    if not credentials:
        return {
            "status": "error",
            "message": "Gmail is not connected. Please connect Gmail first.",
        }

    try:
        service = build(
            "gmail",
            "v1",
            credentials=credentials,
        )

        message = EmailMessage()

        message["To"] = recipient
        message["Subject"] = subject

        message.set_content(body)

        encoded_message = base64.urlsafe_b64encode(
            message.as_bytes()
        ).decode()

        result = service.users().messages().send(
            userId="me",
            body={
                "raw": encoded_message
            },
        ).execute()

        return {
            "status": "sent",
            "message_id": result.get("id"),
            "recipient": recipient,
            "subject": subject,
        }

    except Exception as exc:

        return {
            "status": "error",
            "message": str(exc),
        }

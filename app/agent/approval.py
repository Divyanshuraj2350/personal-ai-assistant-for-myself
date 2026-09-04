from app.agent.approval_store import (
    save_approval,
    get_approval,
    update_approval,
)

from app.agent.gmail_sender import send_email


def create_approval_request(draft):

    approval_request = {
        "status": "pending_approval",
        "approval_id": draft["approval_id"],
        "recipient": draft["recipient"],
        "subject": draft["subject"],
        "body": draft["body"],
        "approved": False,
    }

    save_approval(approval_request)

    return approval_request


def approve(approval_id):

    approval_request = get_approval(
        approval_id
    )

    if not approval_request:

        return {
            "status": "error",
            "message": "Approval request not found.",
        }

    if approval_request["status"] != "pending_approval":

        return {
            "status": "error",
            "message": "This approval request is no longer pending.",
        }

    # ------------------------------------------------------
    # Mark as approved
    # ------------------------------------------------------

    update_approval(
        approval_id,
        "approved",
    )

    # ------------------------------------------------------
    # Send through Gmail
    # ------------------------------------------------------

    result = send_email(
        recipient=approval_request["recipient"],
        subject=approval_request["subject"],
        body=approval_request["body"],
    )

    # ------------------------------------------------------
    # Sending failed
    # ------------------------------------------------------

    if result["status"] == "error":

        update_approval(
            approval_id,
            "send_failed",
        )

        return {
            "status": "error",
            "approval_id": approval_id,
            "message": "Email was approved but could not be sent.",
            "error": result["message"],
        }

    # ------------------------------------------------------
    # Successfully sent
    # ------------------------------------------------------

    return {
        "status": "sent",
        "approval_id": approval_id,
        "recipient": approval_request["recipient"],
        "subject": approval_request["subject"],
        "message": "Email sent successfully through Gmail.",
        "gmail_message_id": result.get("message_id"),
    }


def reject(approval_id):

    approval_request = get_approval(
        approval_id
    )

    if not approval_request:

        return {
            "status": "error",
            "message": "Approval request not found.",
        }

    if approval_request["status"] != "pending_approval":

        return {
            "status": "error",
            "message": "This approval request is no longer pending.",
        }

    return update_approval(
        approval_id,
        "rejected",
    )

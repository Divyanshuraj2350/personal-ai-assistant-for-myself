import json
from pathlib import Path


STORE_PATH = Path("data/approvals.json")


def _load():
    if not STORE_PATH.exists():
        return {}

    with open(STORE_PATH, "r", encoding="utf-8") as file:
        return json.load(file)


def _save(data):
    STORE_PATH.parent.mkdir(parents=True, exist_ok=True)

    with open(STORE_PATH, "w", encoding="utf-8") as file:
        json.dump(
            data,
            file,
            indent=2,
            ensure_ascii=False,
        )


def save_approval(approval_request):
    data = _load()

    approval_id = approval_request["approval_id"]

    data[approval_id] = approval_request

    _save(data)

    return approval_request


def get_approval(approval_id):
    data = _load()

    return data.get(approval_id)


def update_approval(approval_id, status):
    data = _load()

    if approval_id not in data:
        return None

    data[approval_id]["status"] = status

    if status == "approved":
        data[approval_id]["approved"] = True
    else:
        data[approval_id]["approved"] = False

    _save(data)

    return data[approval_id]


def delete_approval(approval_id):
    data = _load()

    if approval_id not in data:
        return False

    del data[approval_id]

    _save(data)

    return True
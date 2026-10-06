from pathlib import Path
from datetime import datetime, timezone
import sqlite3
import uuid


DB_PATH = Path("data/files/files.sqlite3")


class FileRegistryError(Exception):
    """Raised when a file registry operation fails."""
    pass


def _get_connection():
    """Create a connection to the file registry database."""
    DB_PATH.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    connection = sqlite3.connect(
        DB_PATH
    )

    connection.row_factory = sqlite3.Row

    return connection


def initialize_registry():
    """Create the file registry schema if it does not exist."""

    with _get_connection() as connection:

        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS files (
                file_id TEXT PRIMARY KEY,
                file_name TEXT NOT NULL,
                file_path TEXT NOT NULL,
                file_extension TEXT NOT NULL,
                media_type TEXT NOT NULL,
                file_size INTEGER NOT NULL,
                processing_status TEXT NOT NULL,
                processing_method TEXT,
                rag_document_id TEXT,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            )
            """
        )

        connection.commit()


def create_file_record(
    file_path,
    media_type,
    processing_status="pending",
    processing_method=None,
    rag_document_id=None,
):
    """
    Create a persistent metadata record for a file.
    """

    path = Path(file_path)

    if not path.exists():
        raise FileRegistryError(
            f"File not found: {path}"
        )

    if not path.is_file():
        raise FileRegistryError(
            f"Path is not a file: {path}"
        )

    initialize_registry()

    now = datetime.now(
        timezone.utc
    ).isoformat()

    file_id = str(
        uuid.uuid4()
    )

    record = {
        "file_id": file_id,
        "file_name": path.name,
        "file_path": str(path.resolve()),
        "file_extension": path.suffix.lower(),
        "media_type": media_type,
        "file_size": path.stat().st_size,
        "processing_status": processing_status,
        "processing_method": processing_method,
        "rag_document_id": rag_document_id,
        "created_at": now,
        "updated_at": now,
    }

    with _get_connection() as connection:

        connection.execute(
            """
            INSERT INTO files (
                file_id,
                file_name,
                file_path,
                file_extension,
                media_type,
                file_size,
                processing_status,
                processing_method,
                rag_document_id,
                created_at,
                updated_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                record["file_id"],
                record["file_name"],
                record["file_path"],
                record["file_extension"],
                record["media_type"],
                record["file_size"],
                record["processing_status"],
                record["processing_method"],
                record["rag_document_id"],
                record["created_at"],
                record["updated_at"],
            ),
        )

        connection.commit()

    return record


def get_file_record(file_id):
    """Return one file record by ID."""

    initialize_registry()

    with _get_connection() as connection:

        row = connection.execute(
            """
            SELECT *
            FROM files
            WHERE file_id = ?
            """,
            (file_id,),
        ).fetchone()

    if row is None:
        return None

    return dict(row)

def get_file_record_by_path(file_path):
    """Return a file record by its absolute file path."""

    path = Path(file_path).resolve()

    initialize_registry()

    with _get_connection() as connection:

        row = connection.execute(
            """
            SELECT *
            FROM files
            WHERE file_path = ?
            """,
            (str(path),),
        ).fetchone()

    if row is None:
        return None

    return dict(row)

def update_file_record(
    file_id,
    processing_status=None,
    processing_method=None,
    rag_document_id=None,
):
    """
    Update processing information for an existing file record.
    """

    initialize_registry()

    updates = []
    values = []

    if processing_status is not None:
        updates.append(
            "processing_status = ?"
        )
        values.append(
            processing_status
        )

    if processing_method is not None:
        updates.append(
            "processing_method = ?"
        )
        values.append(
            processing_method
        )

    if rag_document_id is not None:
        updates.append(
            "rag_document_id = ?"
        )
        values.append(
            rag_document_id
        )

    if not updates:
        raise FileRegistryError(
            "No fields provided for update."
        )

    updates.append(
        "updated_at = ?"
    )

    values.append(
        datetime.now(
            timezone.utc
        ).isoformat()
    )

    values.append(file_id)

    with _get_connection() as connection:

        cursor = connection.execute(
            f"""
            UPDATE files
            SET {", ".join(updates)}
            WHERE file_id = ?
            """,
            values,
        )

        connection.commit()

    if cursor.rowcount == 0:
        return None

    return get_file_record(file_id)

def list_file_records():
    """Return all registered files."""

    initialize_registry()

    with _get_connection() as connection:

        rows = connection.execute(
            """
            SELECT *
            FROM files
            ORDER BY created_at DESC
            """
        ).fetchall()

    return [
        dict(row)
        for row in rows
    ]

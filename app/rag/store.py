import hashlib
from datetime import datetime

import chromadb
from sentence_transformers import SentenceTransformer


# ============================================================
# CONFIGURATION
# ============================================================

DB_PATH = "data/chroma"

COLLECTION_NAME = "personal_knowledge"

RELEVANCE_THRESHOLD = 1.25

EMBEDDING_MODEL_NAME = "all-MiniLM-L6-v2"


# ============================================================
# EMBEDDING MODEL
# ============================================================

embedding_model = SentenceTransformer(
    EMBEDDING_MODEL_NAME
)


# ============================================================
# CHROMADB
# ============================================================

client = chromadb.PersistentClient(
    path=DB_PATH
)


collection = client.get_or_create_collection(
    name=COLLECTION_NAME
)


# ============================================================
# HELPERS
# ============================================================

def create_document_id(
    text,
):
    """
    Create a stable ID based on document text.

    The same text will generate the same ID.
    """

    normalized_text = (
        text.strip()
        .lower()
    )

    return hashlib.sha256(
        normalized_text.encode(
            "utf-8"
        )
    ).hexdigest()


def create_chunk_id(
    document_id,
    chunk_index,
):
    """
    Create a unique ID for a chunk.
    """

    return (
        f"{document_id}"
        f"_chunk_"
        f"{chunk_index}"
    )


# ============================================================
# ADD SINGLE DOCUMENT
# ============================================================

def add_document(
    document_id,
    text,
    metadata=None,
):
    """
    Add a single document to the RAG database.

    This function is mainly useful for
    small pieces of knowledge.
    """

    if not isinstance(
        text,
        str,
    ):

        return {
            "status": "error",
            "error": "Document text must be a string.",
        }

    text = text.strip()

    if not text:

        return {
            "status": "error",
            "error": "Document text cannot be empty.",
        }

    if not document_id:

        document_id = create_document_id(
            text
        )

    existing = collection.get(
        ids=[document_id],
    )

    if existing.get(
        "ids"
    ):

        return {
            "status": "exists",
            "document_id": document_id,
        }

    if metadata is None:

        metadata = {}

    metadata = {
        **metadata,
        "created_at": datetime.now().isoformat(),
        "document_id": document_id,
    }

    embedding = embedding_model.encode(
        text
    ).tolist()

    collection.add(
        ids=[document_id],
        documents=[text],
        embeddings=[embedding],
        metadatas=[metadata],
    )

    return {
        "status": "success",
        "document_id": document_id,
    }


# ============================================================
# ADD MULTIPLE CHUNKS
# ============================================================

def add_chunks(
    document_id,
    chunks,
    metadata=None,
):
    """
    Add multiple chunks from one source document.

    Each chunk receives:
    - A unique chunk ID
    - Source document ID
    - Chunk index
    - Creation time
    """

    if not isinstance(
        chunks,
        list,
    ):

        return {
            "status": "error",
            "error": "Chunks must be a list.",
        }

    cleaned_chunks = []

    for chunk in chunks:

        if not isinstance(
            chunk,
            str,
        ):
            continue

        chunk = chunk.strip()

        if chunk:

            cleaned_chunks.append(
                chunk
            )

    if not cleaned_chunks:

        return {
            "status": "error",
            "error": "No valid chunks were provided.",
        }

    if metadata is None:

        metadata = {}

    ids = []
    documents = []
    embeddings = []
    metadatas = []

    for index, chunk in enumerate(
        cleaned_chunks
    ):

        chunk_id = create_chunk_id(
            document_id,
            index,
        )

        existing = collection.get(
            ids=[chunk_id],
        )

        if existing.get(
            "ids"
        ):

            continue

        chunk_metadata = {
            **metadata,
            "document_id": document_id,
            "chunk_index": index,
            "created_at": datetime.now().isoformat(),
        }

        embedding = embedding_model.encode(
            chunk
        ).tolist()

        ids.append(
            chunk_id
        )

        documents.append(
            chunk
        )

        embeddings.append(
            embedding
        )

        metadatas.append(
            chunk_metadata
        )

    if not ids:

        return {
            "status": "exists",
            "document_id": document_id,
            "chunks_added": 0,
        }

    collection.add(
        ids=ids,
        documents=documents,
        embeddings=embeddings,
        metadatas=metadatas,
    )

    return {
        "status": "success",
        "document_id": document_id,
        "chunks_added": len(
            ids
        ),
    }


# ============================================================
# SEARCH DOCUMENTS
# ============================================================

def search_documents(
    query,
    limit=5,
):
    """
    Search the knowledge base for documents
    relevant to the user's query.
    """

    if not isinstance(
        query,
        str,
    ):
        return []

    query = query.strip()

    if not query:
        return []

    query_embedding = embedding_model.encode(
        query
    ).tolist()

    results = collection.query(
        query_embeddings=[
            query_embedding
        ],
        n_results=limit,
        include=[
            "documents",
            "metadatas",
            "distances",
        ],
    )

    documents = results.get(
        "documents",
        [[]],
    )[0]

    metadatas = results.get(
        "metadatas",
        [[]],
    )[0]

    distances = results.get(
        "distances",
        [[]],
    )[0]

    formatted_results = []

    for document, metadata, distance in zip(
        documents,
        metadatas,
        distances,
    ):

        formatted_results.append(
            {
                "content": document,
                "metadata": metadata or {},
                "distance": distance,
            }
        )

    return formatted_results


# ============================================================
# DELETE SOURCE DOCUMENT
# ============================================================

def delete_document(
    document_id,
):
    """
    Delete all chunks belonging to a document.
    """

    try:

        collection.delete(
            where={
                "document_id": document_id
            }
        )

        return {
            "status": "success",
            "document_id": document_id,
        }

    except Exception as error:

        return {
            "status": "error",
            "error": str(
                error
            ),
        }


# ============================================================
# DATABASE STATS
# ============================================================

def get_database_stats():
    """
    Return basic information about
    the RAG knowledge base.
    """

    try:

        count = collection.count()

        return {
            "status": "success",
            "collection": COLLECTION_NAME,
            "documents": count,
            "embedding_model": EMBEDDING_MODEL_NAME,
        }

    except Exception as error:

        return {
            "status": "error",
            "error": str(
                error
            ),
        }

# ============================================================
# DEBUG SEARCH
# ============================================================

def debug_search_documents(
    query,
    limit=10,
):
    """
    Search documents without applying the relevance threshold.

    This function is only for testing and debugging
    the RAG retrieval system.
    """

    if not isinstance(
        query,
        str,
    ):

        return []

    query = query.strip()

    if not query:

        return []

    embedding = embedding_model.encode(
        query
    ).tolist()

    try:

        results = collection.query(
            query_embeddings=[
                embedding
            ],
            n_results=limit,
            include=[
                "documents",
                "distances",
                "metadatas",
            ],
        )

    except Exception as error:

        return {
            "status": "error",
            "error": str(
                error
            ),
        }

    documents = results.get(
        "documents",
        [[]],
    )[0]

    distances = results.get(
        "distances",
        [[]],
    )[0]

    metadatas = results.get(
        "metadatas",
        [[]],
    )[0]

    matches = []

    for document, distance, metadata in zip(
        documents,
        distances,
        metadatas,
    ):

        matches.append(
            {
                "content": document,
                "metadata": metadata or {},
                "distance": distance,
            }
        )

    return matches
def reset_knowledge_base():
    """
    Delete and recreate the RAG knowledge collection.

    Use this only when rebuilding the knowledge base
    from scratch.
    """

    global collection

    try:

        client.delete_collection(
            name=COLLECTION_NAME
        )

    except Exception:

        pass

    collection = client.get_or_create_collection(
        name=COLLECTION_NAME
    )

    return {
        "status": "success",
        "message": "Knowledge base reset successfully.",
        "collection": COLLECTION_NAME,
    }
def get_knowledge_base_stats():
    """
    Return basic information about the RAG collection.
    """

    return {
        "status": "success",
        "collection": COLLECTION_NAME,
        "documents": collection.count(),
        "embedding_model": "all-MiniLM-L6-v2",
    }

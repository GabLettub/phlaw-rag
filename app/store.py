"""Pinecone index, embeddings and vector store helpers."""

from langchain_pinecone import PineconeEmbeddings, PineconeVectorStore
from pinecone import Pinecone, ServerlessSpec

from app.config import get_settings

EMBEDDING_MODEL = "multilingual-e5-large"
# Output size of multilingual-e5-large. The index must match it exactly,
# and it cannot be changed after the index is created.
DIMENSION = 1024
NAMESPACE = "decisions"
CLOUD = "aws"
REGION = "us-east-1"


def ensure_index():
    """Return the Pinecone index, creating it first if it is missing.

    The index is dense, cosine, serverless. Creating it waits until it
    is ready, so the returned handle can be used straight away.
    """
    settings = get_settings()
    client = Pinecone(api_key=settings.pinecone_api_key)
    if not client.has_index(settings.pinecone_index):
        client.create_index(
            name=settings.pinecone_index,
            dimension=DIMENSION,
            metric="cosine",
            spec=ServerlessSpec(cloud=CLOUD, region=REGION),
        )
    return client.Index(settings.pinecone_index)


def get_vector_store():
    """Return a LangChain vector store bound to the decisions namespace."""
    embedding = PineconeEmbeddings(
        model=EMBEDDING_MODEL,
        pinecone_api_key=get_settings().pinecone_api_key,
    )
    return PineconeVectorStore(
        index=ensure_index(),
        embedding=embedding,
        namespace=NAMESPACE,
    )


def delete_case(case_id):
    """Delete every stored chunk of one case and return how many.

    Chunk ids look like "<case_id>-<chunk_index>", so listing by that
    prefix finds them. Running this before re-indexing a case removes
    stale chunks when the new text produces fewer chunks than the old.
    """
    index = ensure_index()
    ids = []
    for page in index.list(prefix=f"{case_id}-", namespace=NAMESPACE):
        ids.extend(page)
    if ids:
        index.delete(ids=ids, namespace=NAMESPACE)
    return len(ids)

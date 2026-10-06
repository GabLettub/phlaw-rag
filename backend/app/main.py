"""FastAPI app: public chat endpoints and token-protected admin ones."""

import logging
import secrets
import threading
from datetime import datetime, timezone
from typing import Literal, Optional

import httpx
from fastapi import Depends, FastAPI, Header, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from groq import RateLimitError as GroqRateLimitError
from pydantic import BaseModel, Field
from slowapi import Limiter
from slowapi.errors import RateLimitExceeded
from slowapi.util import get_remote_address

from app import cases, chains, ingest, store
from app.config import get_settings

logger = logging.getLogger("phlaw")

CHAT_RATE_LIMIT = "10/minute"
LIMIT_MESSAGE = (
    "Demo limit reached. This prototype runs on free tiers; "
    "please try again in a little while."
)
CASE_ID_PATTERN = r"^[a-z0-9][a-z0-9-]{0,63}$"


def client_ip(request):
    """Return the caller's IP, honouring the proxy's X-Forwarded-For.

    Render and similar hosts put every request behind a proxy, so the
    socket address would be the same for everyone. The header can be
    spoofed, which is why the daily cap below backs this limit up.
    """
    forwarded = request.headers.get("x-forwarded-for")
    if forwarded:
        return forwarded.split(",")[0].strip()
    return get_remote_address(request)


class DailyCap:
    """A thread-safe count of requests per UTC day, shared by all users."""

    def __init__(self):
        """Start with an empty count."""
        self._lock = threading.Lock()
        self._day = None
        self._count = 0

    def allow(self, cap):
        """Count one request; return False once cap is exceeded today."""
        today = datetime.now(timezone.utc).date()
        with self._lock:
            if today != self._day:
                self._day = today
                self._count = 0
            self._count += 1
            return self._count <= cap


limiter = Limiter(key_func=client_ip)
daily_cap = DailyCap()
app = FastAPI(title="PHLaw RAG")
app.state.limiter = limiter

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        origin.strip()
        for origin in get_settings().allowed_origins.split(",")
        if origin.strip()
    ],
    allow_methods=["GET", "POST"],
    allow_headers=["Content-Type", "X-Ingest-Token"],
)


class ChatMessage(BaseModel):
    """One earlier message in the conversation."""

    role: Literal["user", "assistant"]
    content: str = Field(max_length=4000)


class ChatRequest(BaseModel):
    """The body of POST /chat."""

    message: str = Field(min_length=1, max_length=1000)
    history: list[ChatMessage] = Field(default_factory=list, max_length=20)
    active_case_id: Optional[str] = Field(default=None, max_length=64)


class Source(BaseModel):
    """An excerpt an answer was based on."""

    case_id: str
    title: str
    gr_no: str
    section: str
    snippet: str
    url: str


class ChatResponse(BaseModel):
    """The body returned by POST /chat."""

    answer: str
    intent: str
    case_id: Optional[str] = None
    sources: list[Source]


class IngestRequest(BaseModel):
    """The body of POST /ingest: one decision to fetch and index."""

    url: str = Field(pattern=r"^https?://")
    case_id: str = Field(pattern=CASE_ID_PATTERN)
    title: str = Field(min_length=1, max_length=300)
    gr_no: str = Field(min_length=1, max_length=100)
    date: str = Field(min_length=1, max_length=20)
    topic: str = Field(default="", max_length=200)


class IngestResponse(BaseModel):
    """The body returned by POST /ingest."""

    case_id: str
    chunks: int


class DigestRequest(BaseModel):
    """The body of POST /digest."""

    case_id: str = Field(pattern=CASE_ID_PATTERN)


class DigestSection(BaseModel):
    """One heading of a digest with its paragraphs."""

    heading: str
    paragraphs: list[str]


class DigestSource(BaseModel):
    """A source excerpt in the shape the Notion workflow expects."""

    section: str
    snippet: str
    url: str


class DigestResponse(BaseModel):
    """The body returned by POST /digest."""

    case_id: str
    title: str
    gr_no: str
    sections: list[DigestSection]
    sources: list[DigestSource]


def require_ingest_token(x_ingest_token: str = Header(default="")):
    """Reject the request unless X-Ingest-Token matches INGEST_TOKEN.

    An unset INGEST_TOKEN locks the admin endpoints instead of leaving
    them open. The comparison is constant-time.
    """
    expected = get_settings().ingest_token
    if not expected or not secrets.compare_digest(x_ingest_token, expected):
        raise HTTPException(status_code=401, detail="Invalid token.")


def enforce_daily_cap():
    """Reject the request once the day's DAILY_REQUEST_CAP is used up."""
    if not daily_cap.allow(get_settings().daily_request_cap):
        raise HTTPException(status_code=429, detail=LIMIT_MESSAGE)


@app.exception_handler(RateLimitExceeded)
def handle_rate_limit(request, exc):
    """Answer a per-IP rate limit with the friendly demo message."""
    return JSONResponse(status_code=429, content={"detail": LIMIT_MESSAGE})


@app.exception_handler(GroqRateLimitError)
def handle_groq_limit(request, exc):
    """Answer a Groq free-tier limit with the same friendly message."""
    logger.warning("Groq rate limit: %s", exc)
    return JSONResponse(status_code=429, content={"detail": LIMIT_MESSAGE})


@app.exception_handler(Exception)
def handle_unexpected(request, exc):
    """Log an unexpected error and return a generic one.

    Details stay in the server log; none are sent to the client.
    """
    logger.exception("Unhandled error")
    return JSONResponse(
        status_code=500,
        content={"detail": "Something went wrong. Please try again."},
    )


@app.post("/chat", response_model=ChatResponse)
@limiter.limit(CHAT_RATE_LIMIT)
def chat(
    request: Request,
    body: ChatRequest,
    _cap: None = Depends(enforce_daily_cap),
):
    """Answer a chat message: route it, run the chain, return sources."""
    return chains.respond(body.message, body.history, body.active_case_id)


@app.get("/cases")
def list_cases():
    """Return the indexed cases with their summary cards."""
    return list(cases.load_cases().values())


@app.get("/health")
def health():
    """Report whether Pinecone is reachable and how many vectors it has."""
    try:
        stats = store.ensure_index().describe_index_stats()
        return {"ok": True, "vectors": stats.total_vector_count}
    except Exception:
        logger.exception("Health check failed")
        return {"ok": False, "vectors": None}


@app.post(
    "/ingest",
    response_model=IngestResponse,
    dependencies=[Depends(require_ingest_token)],
)
def ingest_case(body: IngestRequest):
    """Fetch one decision, chunk it and replace its chunks in Pinecone."""
    try:
        text = ingest.fetch_clean(body.url)
    except httpx.HTTPError as exc:
        logger.warning("Fetch failed for %s: %s", body.url, exc)
        reason = ingest.describe_fetch_error(exc)
        raise HTTPException(
            status_code=502, detail=f"Could not fetch the URL ({reason})."
        )
    case = {
        "id": body.case_id,
        "title": body.title,
        "gr_no": body.gr_no,
        "date": body.date,
        "topic": body.topic,
        "url": body.url,
    }
    chunks = ingest.index_case(case, text)
    chains.clear_digest_cache(body.case_id)
    return {"case_id": body.case_id, "chunks": chunks}


@app.post(
    "/digest",
    response_model=DigestResponse,
    dependencies=[Depends(require_ingest_token)],
)
def digest_case(body: DigestRequest):
    """Return the structured digest for one indexed case."""
    try:
        return chains.build_digest(body.case_id)
    except LookupError:
        raise HTTPException(status_code=404, detail="Case not indexed.")

import secrets
from datetime import date, datetime
from functools import lru_cache
from typing import Annotated, Any, Literal
from uuid import UUID

import psycopg
from fastapi import FastAPI, Header, HTTPException, Query, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.gzip import GZipMiddleware
from fastapi.middleware.trustedhost import TrustedHostMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field

from civicos_api.assistant import (
    AnswerGenerationUnavailableError,
    AnswerStatus,
    AssistantPolicy,
    Confidence,
    GroundedAnswer,
    GroundedAnswerService,
    OpenAICompatibleAnswerClient,
)
from civicos_api.auth import AuthenticationError, Authenticator
from civicos_api.beta import (
    BetaAnalyticsEventName,
    BetaSurface,
    FeedbackCategory,
    PublicBetaRepository,
    PublicBetaUnavailableError,
)
from civicos_api.briefings import (
    BriefingAccessError,
    BriefingNotFoundError,
    BriefingSubscription,
    DailyBriefing,
    PostgresBriefingRepository,
)
from civicos_api.config import get_settings
from civicos_api.founder import (
    FounderBrief,
    FounderIntelligenceAccessError,
    FounderIntelligenceUnavailableError,
    FounderOpportunity,
    FounderSignal,
    FounderWatchlist,
    PostgresFounderIntelligenceRepository,
)
from civicos_api.notebooks import (
    Notebook,
    NotebookEntry,
    NotebookGroundingError,
    NotebookSnapshot,
    PostgresNotebookRepository,
    ResearchAccessError,
    ResearchNotebookService,
    ResearchNotFoundError,
    SavedDocument,
    SavedSearch,
    SourceReference,
)
from civicos_api.observability import (
    AuthenticationMiddleware,
    InMemoryRateLimiter,
    Metrics,
    RequestContextMiddleware,
    configure_logging,
)
from civicos_api.search import (
    HybridSearchService,
    OpenAICompatibleSemanticSearchClient,
    PostgresSearchRepository,
    SearchFilters,
    SearchHit,
    SearchMode,
    SearchUnavailableError,
)
from civicos_api.users import (
    ManagedUser,
    PostgresUserRepository,
    UserManagementAccessError,
    UserManagementError,
    UserManagementNotFoundError,
)

settings = get_settings()
configure_logging(settings.log_level)
metrics = Metrics()

app = FastAPI(
    title="CivicOS API",
    version="0.1.0",
    docs_url=None,
    redoc_url=None,
    openapi_url=None,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[str(origin) for origin in settings.cors_origins],
    allow_credentials=False,
    allow_methods=["GET", "POST", "DELETE"],
    allow_headers=["Authorization", "Content-Type", "X-Request-ID"],
)
app.add_middleware(TrustedHostMiddleware, allowed_hosts=settings.allowed_hosts)
app.add_middleware(GZipMiddleware, minimum_size=1_000)


class SearchResultResponse(BaseModel):
    document_id: UUID
    document_version_id: UUID
    title: str
    document_type: str
    source_name: str | None
    canonical_url: str | None
    department_id: UUID | None
    published_at: date | None
    excerpt: str
    score: float
    match_kind: str


class SearchResponseModel(BaseModel):
    results: list[SearchResultResponse]
    semantic_available: bool


class AssistantQuestionRequest(BaseModel):
    question: Annotated[str, Field(min_length=5, max_length=1_000)]
    start_date: date | None = None
    end_date: date | None = None
    department_ids: list[UUID] = Field(default_factory=list, max_length=50)
    topic_ids: list[UUID] = Field(default_factory=list, max_length=50)
    source_ids: list[UUID] = Field(default_factory=list, max_length=50)


class AssistantClaimResponse(BaseModel):
    text: str
    citation_ids: list[str]


class AssistantCitationResponse(BaseModel):
    citation_id: str
    document_id: UUID
    document_version_id: UUID
    title: str
    source_name: str | None
    source_url: str | None
    published_at: str | None
    excerpt: str


class AssistantConfidenceResponse(BaseModel):
    score: float
    level: str
    rationale: list[str]


class AssistantAnswerResponse(BaseModel):
    status: Literal[AnswerStatus.ANSWERED, AnswerStatus.INSUFFICIENT_EVIDENCE]
    answer: str
    claims: list[AssistantClaimResponse]
    citations: list[AssistantCitationResponse]
    confidence: AssistantConfidenceResponse
    semantic_available: bool


class NotebookResponse(BaseModel):
    id: UUID
    title: str
    description: str | None
    visibility: str
    created_at: datetime
    updated_at: datetime


class NotebookEntryResponse(BaseModel):
    id: UUID
    position: int
    entry_type: str
    title: str | None
    body_markdown: str | None
    structured_content: dict[str, Any]
    created_at: datetime
    updated_at: datetime


class SavedSearchResponse(BaseModel):
    id: UUID
    title: str
    query_text: str
    filters: dict[str, Any]
    created_at: datetime
    updated_at: datetime


class SavedDocumentResponse(BaseModel):
    document_id: UUID
    document_version_id: UUID | None
    title: str
    document_type: str
    source_name: str | None
    source_url: str | None
    published_at: date | None
    note: str | None
    saved_at: datetime


class SourceReferenceResponse(BaseModel):
    citation_id: UUID
    notebook_entry_id: UUID
    document_id: UUID
    document_version_id: UUID
    title: str
    source_name: str | None
    source_url: str | None
    published_at: date | None
    excerpt: str | None
    locator: dict[str, Any]
    note: str | None


class NotebookSnapshotResponse(BaseModel):
    notebook: NotebookResponse
    entries: list[NotebookEntryResponse]
    saved_searches: list[SavedSearchResponse]
    saved_documents: list[SavedDocumentResponse]
    source_references: list[SourceReferenceResponse]


class CreateNotebookRequest(BaseModel):
    title: Annotated[str, Field(min_length=1, max_length=200)]
    description: Annotated[str | None, Field(max_length=2_000)] = None
    visibility: Literal["private", "organization"] = "private"


class SaveSearchRequest(BaseModel):
    title: Annotated[str, Field(min_length=1, max_length=200)]
    query_text: Annotated[str, Field(min_length=2, max_length=500)]
    filters: dict[str, Any] = Field(default_factory=dict)


class SaveDocumentRequest(BaseModel):
    document_id: UUID
    note: Annotated[str | None, Field(max_length=2_000)] = None


class AddNoteRequest(BaseModel):
    title: Annotated[str | None, Field(max_length=200)] = None
    body_markdown: Annotated[str, Field(min_length=1, max_length=20_000)]


class AddHighlightRequest(BaseModel):
    document_version_id: UUID
    excerpt: Annotated[str, Field(min_length=1, max_length=10_000)]
    start_offset: int | None = Field(default=None, ge=0)
    end_offset: int | None = Field(default=None, ge=0)
    note: Annotated[str | None, Field(max_length=2_000)] = None


class GenerateSummaryRequest(BaseModel):
    focus: Annotated[str | None, Field(max_length=500)] = None


class BriefingSubscriptionResponse(BaseModel):
    id: UUID
    delivery_channel: str
    is_active: bool
    created_at: datetime
    updated_at: datetime


class DailyBriefingResponse(BaseModel):
    id: UUID
    briefing_date: date
    content: dict[str, Any]
    generated_at: datetime
    delivery_status: str
    delivered_at: datetime
    read_at: datetime | None


class ManagedUserResponse(BaseModel):
    user_id: UUID
    external_subject: str
    email: str
    display_name: str
    role_key: str
    is_active: bool
    created_at: datetime
    updated_at: datetime


class CurrentUserResponse(BaseModel):
    user_id: UUID
    organization_id: UUID
    role_key: str


class FounderLoginRequest(BaseModel):
    secret: Annotated[str, Field(min_length=32, max_length=1_024)]


class FounderLoginResponse(BaseModel):
    access_token: str
    token_type: Literal["Bearer"]
    expires_in: int


class ProvisionUserRequest(BaseModel):
    external_subject: Annotated[str, Field(min_length=1, max_length=255)]
    email: Annotated[str, Field(min_length=3, max_length=320)]
    display_name: Annotated[str, Field(min_length=1, max_length=200)]
    role_key: Literal["tenant_admin", "researcher", "government_staff"] = "researcher"


class UpdateUserRequest(BaseModel):
    role_key: Literal["tenant_admin", "researcher", "government_staff"]
    is_active: bool


class PublicBetaFeedbackRequest(BaseModel):
    category: FeedbackCategory
    message: Annotated[str, Field(min_length=1, max_length=2_000)]
    contact_email: Annotated[str | None, Field(max_length=320)] = None
    page_path: Annotated[str, Field(min_length=1, max_length=160, pattern=r"^/[A-Za-z0-9/_-]*$")]


class PublicBetaAnalyticsRequest(BaseModel):
    event_name: BetaAnalyticsEventName
    page_path: Annotated[str, Field(min_length=1, max_length=160, pattern=r"^/[A-Za-z0-9/_-]*$")]
    surface: BetaSurface | None = None


class FounderOpportunityResponse(BaseModel):
    id: UUID
    signal_id: UUID
    signal_type: str
    title: str
    what_happened: str
    why_it_matters: str
    where_money_may_be: str
    who_might_pay: list[str]
    action_to_take: str
    urgency: str
    score: int
    evidence: list[dict[str, Any]]
    affected_organizations: list[str]
    source_url: str | None
    document_title: str
    discovered_at: datetime


class FounderSignalResponse(BaseModel):
    id: UUID
    signal_type: str
    title: str
    summary: str
    why_it_matters: str
    commercial_significance: int
    confidence_score: float
    evidence: list[dict[str, Any]]
    affected_organizations: list[str]
    potential_customer_segments: list[str]
    source_url: str | None
    discovered_at: datetime


class FounderWatchlistResponse(BaseModel):
    id: UUID
    watch_type: str
    name: str
    normalized_term: str
    criteria: dict[str, Any]
    is_active: bool
    match_count: int
    latest_match_at: datetime | None
    created_at: datetime


class CreateFounderWatchlistRequest(BaseModel):
    watch_type: Literal[
        "company",
        "industry",
        "property",
        "geographic_area",
        "government_department",
        "project",
        "topic",
    ]
    name: Annotated[str, Field(min_length=1, max_length=200)]
    term: Annotated[str, Field(min_length=1, max_length=200)]
    criteria: dict[str, Any] = Field(default_factory=dict)


class FounderBriefResponse(BaseModel):
    id: UUID
    briefing_date: date
    content: dict[str, Any]
    generated_at: datetime


@lru_cache
def get_search_service() -> HybridSearchService | None:
    if settings.database_url is None:
        return None
    semantic_client = None
    if settings.qdrant_url and settings.embedding_base_url and settings.embedding_model:
        semantic_client = OpenAICompatibleSemanticSearchClient(
            embedding_base_url=settings.embedding_base_url,
            embedding_model=settings.embedding_model,
            embedding_api_key=settings.embedding_api_key,
            qdrant_url=settings.qdrant_url,
            qdrant_collection=settings.qdrant_collection,
            qdrant_api_key=settings.qdrant_api_key,
        )
    return HybridSearchService(
        repository=PostgresSearchRepository(settings.database_url), semantic_client=semantic_client
    )


@lru_cache
def get_assistant_service() -> GroundedAnswerService | None:
    search_service = get_search_service()
    if search_service is None or not settings.llm_base_url or not settings.llm_model:
        return None
    return GroundedAnswerService(
        retriever=search_service,
        answer_client=OpenAICompatibleAnswerClient(
            base_url=settings.llm_base_url,
            model=settings.llm_model,
            api_key=settings.llm_api_key,
            temperature=settings.assistant_temperature,
        ),
        policy=AssistantPolicy(
            retrieval_limit=settings.assistant_retrieval_limit,
            max_claims=settings.assistant_max_claims,
            minimum_citations_per_claim=settings.assistant_min_citations_per_claim,
            target_independent_sources=settings.assistant_target_independent_sources,
            high_confidence_threshold=settings.assistant_high_confidence_threshold,
            medium_confidence_threshold=settings.assistant_medium_confidence_threshold,
        ),
    )


@lru_cache
def get_notebook_repository() -> PostgresNotebookRepository | None:
    if settings.database_url is None:
        return None
    return PostgresNotebookRepository(settings.database_url)


@lru_cache
def get_notebook_service() -> ResearchNotebookService | None:
    repository = get_notebook_repository()
    if repository is None:
        return None
    answer_client = None
    if settings.llm_base_url and settings.llm_model:
        answer_client = OpenAICompatibleAnswerClient(
            base_url=settings.llm_base_url,
            model=settings.llm_model,
            api_key=settings.llm_api_key,
            temperature=settings.assistant_temperature,
        )
    return ResearchNotebookService(
        repository=repository,
        answer_client=answer_client,
        max_claims=settings.assistant_max_claims,
    )


@lru_cache
def get_briefing_repository() -> PostgresBriefingRepository | None:
    if settings.database_url is None:
        return None
    return PostgresBriefingRepository(settings.database_url)


@lru_cache
def get_user_repository() -> PostgresUserRepository | None:
    if settings.database_url is None:
        return None
    return PostgresUserRepository(settings.database_url)


@lru_cache
def get_public_beta_repository() -> PublicBetaRepository | None:
    if settings.database_url is None:
        return None
    return PublicBetaRepository(settings.database_url)


@lru_cache
def get_founder_intelligence_repository() -> PostgresFounderIntelligenceRepository | None:
    if settings.database_url is None:
        return None
    return PostgresFounderIntelligenceRepository(settings.database_url)


authenticator = Authenticator(settings, get_user_repository())

app.add_middleware(
    AuthenticationMiddleware,
    settings=settings,
    authenticator=authenticator,
)
app.add_middleware(
    RequestContextMiddleware,
    metrics=metrics,
    limiter=InMemoryRateLimiter(settings.rate_limit_per_minute),
    settings=settings,
)


@app.exception_handler(ResearchAccessError)
async def research_access_error(_: Request, error: ResearchAccessError) -> JSONResponse:
    return JSONResponse(status_code=403, content={"detail": str(error)})


@app.exception_handler(ResearchNotFoundError)
async def research_not_found_error(_: Request, error: ResearchNotFoundError) -> JSONResponse:
    return JSONResponse(status_code=404, content={"detail": str(error)})


@app.exception_handler(BriefingAccessError)
async def briefing_access_error(_: Request, error: BriefingAccessError) -> JSONResponse:
    return JSONResponse(status_code=403, content={"detail": str(error)})


@app.exception_handler(BriefingNotFoundError)
async def briefing_not_found_error(_: Request, error: BriefingNotFoundError) -> JSONResponse:
    return JSONResponse(status_code=404, content={"detail": str(error)})


@app.exception_handler(UserManagementAccessError)
async def user_management_access_error(
    _: Request, error: UserManagementAccessError
) -> JSONResponse:
    return JSONResponse(status_code=403, content={"detail": str(error)})


@app.exception_handler(UserManagementNotFoundError)
async def user_management_not_found_error(
    _: Request, error: UserManagementNotFoundError
) -> JSONResponse:
    return JSONResponse(status_code=404, content={"detail": str(error)})


@app.exception_handler(UserManagementError)
async def user_management_error(_: Request, error: UserManagementError) -> JSONResponse:
    return JSONResponse(status_code=409, content={"detail": str(error)})


@app.exception_handler(FounderIntelligenceAccessError)
async def founder_intelligence_access_error(
    _: Request, error: FounderIntelligenceAccessError
) -> JSONResponse:
    return JSONResponse(status_code=403, content={"detail": str(error)})


@app.exception_handler(FounderIntelligenceUnavailableError)
async def founder_intelligence_unavailable_error(
    _: Request, error: FounderIntelligenceUnavailableError
) -> JSONResponse:
    return JSONResponse(status_code=503, content={"detail": str(error)})


@app.exception_handler(PublicBetaUnavailableError)
async def public_beta_unavailable_error(
    _: Request, error: PublicBetaUnavailableError
) -> JSONResponse:
    return JSONResponse(status_code=503, content={"detail": str(error)})


@app.get("/healthz", include_in_schema=False)
async def healthcheck() -> dict[str, str]:
    """Container liveness endpoint; it intentionally checks no product dependencies."""

    return {"status": "ok"}


@app.get("/readyz", include_in_schema=False)
async def readiness() -> dict[str, str]:
    """Readiness endpoint checks the authoritative transactional dependency only."""

    if settings.database_url is None:
        raise HTTPException(status_code=503, detail="Database is not configured")
    database_url = settings.database_url.replace("postgresql+psycopg://", "postgresql://", 1)
    try:
        async with await psycopg.AsyncConnection.connect(database_url) as connection:
            await connection.execute("SELECT 1")
    except psycopg.Error as error:
        raise HTTPException(status_code=503, detail="Database is not ready") from error
    return {"status": "ready"}


@app.get("/metrics", include_in_schema=False)
async def prometheus_metrics(request: Request) -> Response:
    if not settings.metrics_token:
        raise HTTPException(status_code=404, detail="Not found")
    authorization = request.headers.get("authorization", "")
    expected = f"Bearer {settings.metrics_token}"
    if not secrets.compare_digest(authorization, expected):
        raise HTTPException(status_code=401, detail="Metrics authentication is required")
    return Response(content=metrics.render_prometheus(), media_type="text/plain; version=0.0.4")


@app.post("/public/beta-feedback", status_code=202)
async def submit_public_beta_feedback(request: PublicBetaFeedbackRequest) -> dict[str, bool]:
    repository = get_public_beta_repository()
    if repository is None:
        raise HTTPException(status_code=503, detail="Feedback storage is not configured")
    await repository.submit_feedback(
        category=request.category,
        message=request.message,
        contact_email=request.contact_email,
        page_path=request.page_path,
    )
    return {"accepted": True}


@app.post("/public/analytics/events", status_code=202)
async def record_public_beta_analytics_event(
    request: PublicBetaAnalyticsRequest,
) -> dict[str, bool]:
    repository = get_public_beta_repository()
    if repository is None:
        raise HTTPException(status_code=503, detail="Analytics storage is not configured")
    await repository.record_event(
        event_name=request.event_name,
        page_path=request.page_path,
        surface=request.surface,
    )
    return {"accepted": True}


@app.post("/auth/founder/login", response_model=FounderLoginResponse)
async def founder_login(request: FounderLoginRequest) -> FounderLoginResponse:
    """Exchange the private Railway-stored founder secret for a short-lived token."""

    try:
        access_token, expires_in = await authenticator.login_founder(request.secret)
    except AuthenticationError as error:
        raise HTTPException(status_code=401, detail="Founder login failed") from error
    return FounderLoginResponse(
        access_token=access_token,
        token_type="Bearer",
        expires_in=expires_in,
    )


@app.get("/v1/me", response_model=CurrentUserResponse)
async def current_user(
    organization_id: Annotated[UUID, Header(alias="X-CivicOS-Organization-ID")],
    user_id: Annotated[UUID, Header(alias="X-CivicOS-User-ID")],
    role_key: Annotated[str, Header(alias="X-CivicOS-Role")],
) -> CurrentUserResponse:
    return CurrentUserResponse(
        user_id=user_id,
        organization_id=organization_id,
        role_key=role_key,
    )


@app.get("/v1/users", response_model=list[ManagedUserResponse])
async def list_users(
    organization_id: Annotated[UUID, Header(alias="X-CivicOS-Organization-ID")],
    user_id: Annotated[UUID, Header(alias="X-CivicOS-User-ID")],
) -> list[ManagedUserResponse]:
    repository = get_user_repository()
    if repository is None:
        raise HTTPException(status_code=503, detail="User storage is not configured")
    return [
        ManagedUserResponse.model_validate(_managed_user_payload(user))
        for user in await repository.list_users(organization_id=organization_id, user_id=user_id)
    ]


@app.post("/v1/users", response_model=ManagedUserResponse, status_code=201)
async def provision_user(
    request: ProvisionUserRequest,
    organization_id: Annotated[UUID, Header(alias="X-CivicOS-Organization-ID")],
    user_id: Annotated[UUID, Header(alias="X-CivicOS-User-ID")],
) -> ManagedUserResponse:
    repository = get_user_repository()
    if repository is None:
        raise HTTPException(status_code=503, detail="User storage is not configured")
    user = await repository.provision_user(
        organization_id=organization_id,
        user_id=user_id,
        external_subject=request.external_subject,
        email=request.email,
        display_name=request.display_name,
        role_key=request.role_key,
    )
    return ManagedUserResponse.model_validate(_managed_user_payload(user))


@app.post("/v1/users/{target_user_id}", response_model=ManagedUserResponse)
async def update_user(
    target_user_id: UUID,
    request: UpdateUserRequest,
    organization_id: Annotated[UUID, Header(alias="X-CivicOS-Organization-ID")],
    user_id: Annotated[UUID, Header(alias="X-CivicOS-User-ID")],
) -> ManagedUserResponse:
    repository = get_user_repository()
    if repository is None:
        raise HTTPException(status_code=503, detail="User storage is not configured")
    user = await repository.update_user(
        organization_id=organization_id,
        user_id=user_id,
        target_user_id=target_user_id,
        role_key=request.role_key,
        is_active=request.is_active,
    )
    return ManagedUserResponse.model_validate(_managed_user_payload(user))


@app.get("/v1/founder/opportunities", response_model=list[FounderOpportunityResponse])
async def list_founder_opportunities(
    organization_id: Annotated[UUID, Header(alias="X-CivicOS-Organization-ID")],
    user_id: Annotated[UUID, Header(alias="X-CivicOS-User-ID")],
    limit: Annotated[int, Query(ge=1, le=100)] = 25,
) -> list[FounderOpportunityResponse]:
    repository = get_founder_intelligence_repository()
    if repository is None:
        raise HTTPException(
            status_code=503, detail="Founder Intelligence storage is not configured"
        )
    return [
        FounderOpportunityResponse.model_validate(_founder_opportunity_payload(opportunity))
        for opportunity in await repository.list_opportunities(
            organization_id=organization_id, user_id=user_id, limit=limit
        )
    ]


@app.get("/v1/founder/signals", response_model=list[FounderSignalResponse])
async def list_founder_signals(
    organization_id: Annotated[UUID, Header(alias="X-CivicOS-Organization-ID")],
    user_id: Annotated[UUID, Header(alias="X-CivicOS-User-ID")],
    limit: Annotated[int, Query(ge=1, le=100)] = 50,
) -> list[FounderSignalResponse]:
    repository = get_founder_intelligence_repository()
    if repository is None:
        raise HTTPException(
            status_code=503, detail="Founder Intelligence storage is not configured"
        )
    return [
        FounderSignalResponse.model_validate(_founder_signal_payload(signal))
        for signal in await repository.list_signals(
            organization_id=organization_id, user_id=user_id, limit=limit
        )
    ]


@app.get("/v1/founder/watchlists", response_model=list[FounderWatchlistResponse])
async def list_founder_watchlists(
    organization_id: Annotated[UUID, Header(alias="X-CivicOS-Organization-ID")],
    user_id: Annotated[UUID, Header(alias="X-CivicOS-User-ID")],
) -> list[FounderWatchlistResponse]:
    repository = get_founder_intelligence_repository()
    if repository is None:
        raise HTTPException(
            status_code=503, detail="Founder Intelligence storage is not configured"
        )
    return [
        FounderWatchlistResponse.model_validate(_founder_watchlist_payload(watchlist))
        for watchlist in await repository.list_watchlists(
            organization_id=organization_id, user_id=user_id
        )
    ]


@app.post("/v1/founder/watchlists", response_model=FounderWatchlistResponse, status_code=201)
async def create_founder_watchlist(
    request: CreateFounderWatchlistRequest,
    organization_id: Annotated[UUID, Header(alias="X-CivicOS-Organization-ID")],
    user_id: Annotated[UUID, Header(alias="X-CivicOS-User-ID")],
) -> FounderWatchlistResponse:
    repository = get_founder_intelligence_repository()
    if repository is None:
        raise HTTPException(
            status_code=503, detail="Founder Intelligence storage is not configured"
        )
    watchlist = await repository.create_watchlist(
        organization_id=organization_id,
        user_id=user_id,
        watch_type=request.watch_type,
        name=request.name,
        term=request.term,
        criteria=request.criteria,
    )
    return FounderWatchlistResponse.model_validate(_founder_watchlist_payload(watchlist))


@app.get("/v1/founder/brief", response_model=FounderBriefResponse)
async def latest_founder_brief(
    organization_id: Annotated[UUID, Header(alias="X-CivicOS-Organization-ID")],
    user_id: Annotated[UUID, Header(alias="X-CivicOS-User-ID")],
) -> FounderBriefResponse:
    repository = get_founder_intelligence_repository()
    if repository is None:
        raise HTTPException(
            status_code=503, detail="Founder Intelligence storage is not configured"
        )
    brief = await repository.latest_brief(organization_id=organization_id, user_id=user_id)
    if brief is None:
        raise HTTPException(status_code=404, detail="No Founder Brief has been generated yet")
    return FounderBriefResponse.model_validate(_founder_brief_payload(brief))


@app.get("/v1/search", response_model=SearchResponseModel)
async def search_documents(
    query: Annotated[str, Query(min_length=2, max_length=500)],
    organization_id: Annotated[UUID, Header(alias="X-CivicOS-Organization-ID")],
    mode: SearchMode = SearchMode.HYBRID,
    limit: Annotated[int, Query(ge=1)] = 20,
    start_date: date | None = None,
    end_date: date | None = None,
    department_id: Annotated[list[UUID] | None, Query()] = None,
    topic_id: Annotated[list[UUID] | None, Query()] = None,
    source_id: Annotated[list[UUID] | None, Query()] = None,
) -> SearchResponseModel:
    """Search one organization; authentication must derive the tenant scope at the edge."""

    if start_date and end_date and start_date > end_date:
        raise HTTPException(status_code=422, detail="start_date must not be after end_date")
    if limit > settings.search_max_limit:
        raise HTTPException(
            status_code=422, detail=f"limit must not exceed {settings.search_max_limit}"
        )
    service = get_search_service()
    if service is None:
        raise HTTPException(status_code=503, detail="Search storage is not configured")
    filters = SearchFilters(
        start_date=start_date,
        end_date=end_date,
        department_ids=tuple(department_id or []),
        topic_ids=tuple(topic_id or []),
        source_ids=tuple(source_id or []),
    )
    try:
        response = await service.search(
            organization_id=organization_id, query=query, filters=filters, mode=mode, limit=limit
        )
    except SearchUnavailableError as error:
        raise HTTPException(status_code=503, detail=str(error)) from error
    return SearchResponseModel(
        results=[
            SearchResultResponse.model_validate(_search_hit_payload(hit))
            for hit in response.results
        ],
        semantic_available=response.semantic_available,
    )


@app.post("/v1/assistant/answers", response_model=AssistantAnswerResponse)
async def answer_question(
    request: AssistantQuestionRequest,
    organization_id: Annotated[UUID, Header(alias="X-CivicOS-Organization-ID")],
) -> AssistantAnswerResponse:
    """Answer from tenant-scoped CivicOS records and return evidence for every displayed claim."""

    if request.start_date and request.end_date and request.start_date > request.end_date:
        raise HTTPException(status_code=422, detail="start_date must not be after end_date")
    service = get_assistant_service()
    if service is None:
        raise HTTPException(status_code=503, detail="Grounded assistant is not configured")
    try:
        answer = await service.answer(
            organization_id=organization_id,
            question=request.question,
            filters=SearchFilters(
                start_date=request.start_date,
                end_date=request.end_date,
                department_ids=tuple(request.department_ids),
                topic_ids=tuple(request.topic_ids),
                source_ids=tuple(request.source_ids),
            ),
        )
    except AnswerGenerationUnavailableError as error:
        raise HTTPException(status_code=503, detail=str(error)) from error
    return AssistantAnswerResponse.model_validate(_grounded_answer_payload(answer))


@app.post(
    "/v1/briefing-subscriptions", response_model=BriefingSubscriptionResponse, status_code=201
)
async def subscribe_to_daily_briefing(
    organization_id: Annotated[UUID, Header(alias="X-CivicOS-Organization-ID")],
    user_id: Annotated[UUID, Header(alias="X-CivicOS-User-ID")],
) -> BriefingSubscriptionResponse:
    repository = get_briefing_repository()
    if repository is None:
        raise HTTPException(status_code=503, detail="Briefing storage is not configured")
    subscription = await repository.subscribe(organization_id=organization_id, user_id=user_id)
    return BriefingSubscriptionResponse.model_validate(_briefing_subscription_payload(subscription))


@app.delete(
    "/v1/briefing-subscriptions/{subscription_id}", response_model=BriefingSubscriptionResponse
)
async def unsubscribe_from_daily_briefing(
    subscription_id: UUID,
    organization_id: Annotated[UUID, Header(alias="X-CivicOS-Organization-ID")],
    user_id: Annotated[UUID, Header(alias="X-CivicOS-User-ID")],
) -> BriefingSubscriptionResponse:
    repository = get_briefing_repository()
    if repository is None:
        raise HTTPException(status_code=503, detail="Briefing storage is not configured")
    subscription = await repository.unsubscribe(
        organization_id=organization_id, user_id=user_id, subscription_id=subscription_id
    )
    return BriefingSubscriptionResponse.model_validate(_briefing_subscription_payload(subscription))


@app.get("/v1/briefings", response_model=list[DailyBriefingResponse])
async def list_daily_briefings(
    organization_id: Annotated[UUID, Header(alias="X-CivicOS-Organization-ID")],
    user_id: Annotated[UUID, Header(alias="X-CivicOS-User-ID")],
    limit: Annotated[int, Query(ge=1, le=90)] = 30,
) -> list[DailyBriefingResponse]:
    repository = get_briefing_repository()
    if repository is None:
        raise HTTPException(status_code=503, detail="Briefing storage is not configured")
    briefings = await repository.list_briefings(
        organization_id=organization_id, user_id=user_id, limit=limit
    )
    return [
        DailyBriefingResponse.model_validate(_daily_briefing_payload(briefing))
        for briefing in briefings
    ]


@app.post("/v1/briefings/{briefing_id}/read", response_model=DailyBriefingResponse)
async def mark_daily_briefing_read(
    briefing_id: UUID,
    organization_id: Annotated[UUID, Header(alias="X-CivicOS-Organization-ID")],
    user_id: Annotated[UUID, Header(alias="X-CivicOS-User-ID")],
) -> DailyBriefingResponse:
    repository = get_briefing_repository()
    if repository is None:
        raise HTTPException(status_code=503, detail="Briefing storage is not configured")
    briefing = await repository.mark_read(
        organization_id=organization_id, user_id=user_id, briefing_id=briefing_id
    )
    return DailyBriefingResponse.model_validate(_daily_briefing_payload(briefing))


@app.get("/v1/research/notebooks", response_model=list[NotebookResponse])
async def list_research_notebooks(
    organization_id: Annotated[UUID, Header(alias="X-CivicOS-Organization-ID")],
    user_id: Annotated[UUID, Header(alias="X-CivicOS-User-ID")],
) -> list[NotebookResponse]:
    repository = get_notebook_repository()
    if repository is None:
        raise HTTPException(status_code=503, detail="Research storage is not configured")
    notebooks = await repository.list_notebooks(organization_id=organization_id, user_id=user_id)
    return [NotebookResponse.model_validate(_notebook_payload(notebook)) for notebook in notebooks]


@app.post("/v1/research/notebooks", response_model=NotebookResponse, status_code=201)
async def create_research_notebook(
    request: CreateNotebookRequest,
    organization_id: Annotated[UUID, Header(alias="X-CivicOS-Organization-ID")],
    user_id: Annotated[UUID, Header(alias="X-CivicOS-User-ID")],
) -> NotebookResponse:
    repository = get_notebook_repository()
    if repository is None:
        raise HTTPException(status_code=503, detail="Research storage is not configured")
    notebook = await repository.create_notebook(
        organization_id=organization_id,
        user_id=user_id,
        title=request.title,
        description=request.description,
        visibility=request.visibility,
    )
    return NotebookResponse.model_validate(_notebook_payload(notebook))


@app.get("/v1/research/notebooks/{notebook_id}", response_model=NotebookSnapshotResponse)
async def get_research_notebook(
    notebook_id: UUID,
    organization_id: Annotated[UUID, Header(alias="X-CivicOS-Organization-ID")],
    user_id: Annotated[UUID, Header(alias="X-CivicOS-User-ID")],
) -> NotebookSnapshotResponse:
    repository = get_notebook_repository()
    if repository is None:
        raise HTTPException(status_code=503, detail="Research storage is not configured")
    snapshot = await repository.snapshot(
        organization_id=organization_id, user_id=user_id, notebook_id=notebook_id
    )
    return NotebookSnapshotResponse.model_validate(_snapshot_payload(snapshot))


@app.post(
    "/v1/research/notebooks/{notebook_id}/saved-searches",
    response_model=SavedSearchResponse,
    status_code=201,
)
async def save_notebook_search(
    notebook_id: UUID,
    request: SaveSearchRequest,
    organization_id: Annotated[UUID, Header(alias="X-CivicOS-Organization-ID")],
    user_id: Annotated[UUID, Header(alias="X-CivicOS-User-ID")],
) -> SavedSearchResponse:
    repository = get_notebook_repository()
    if repository is None:
        raise HTTPException(status_code=503, detail="Research storage is not configured")
    saved_search = await repository.save_search(
        organization_id=organization_id,
        user_id=user_id,
        notebook_id=notebook_id,
        title=request.title,
        query_text=request.query_text,
        filters=request.filters,
    )
    return SavedSearchResponse.model_validate(_saved_search_payload(saved_search))


@app.post(
    "/v1/research/notebooks/{notebook_id}/documents",
    response_model=SavedDocumentResponse,
)
async def save_notebook_document(
    notebook_id: UUID,
    request: SaveDocumentRequest,
    organization_id: Annotated[UUID, Header(alias="X-CivicOS-Organization-ID")],
    user_id: Annotated[UUID, Header(alias="X-CivicOS-User-ID")],
) -> SavedDocumentResponse:
    repository = get_notebook_repository()
    if repository is None:
        raise HTTPException(status_code=503, detail="Research storage is not configured")
    document = await repository.save_document(
        organization_id=organization_id,
        user_id=user_id,
        notebook_id=notebook_id,
        document_id=request.document_id,
        note=request.note,
    )
    return SavedDocumentResponse.model_validate(_saved_document_payload(document))


@app.post("/v1/research/notebooks/{notebook_id}/notes", response_model=NotebookEntryResponse)
async def add_notebook_note(
    notebook_id: UUID,
    request: AddNoteRequest,
    organization_id: Annotated[UUID, Header(alias="X-CivicOS-Organization-ID")],
    user_id: Annotated[UUID, Header(alias="X-CivicOS-User-ID")],
) -> NotebookEntryResponse:
    repository = get_notebook_repository()
    if repository is None:
        raise HTTPException(status_code=503, detail="Research storage is not configured")
    entry = await repository.add_note(
        organization_id=organization_id,
        user_id=user_id,
        notebook_id=notebook_id,
        title=request.title,
        body_markdown=request.body_markdown,
    )
    return NotebookEntryResponse.model_validate(_entry_payload(entry))


@app.post("/v1/research/notebooks/{notebook_id}/highlights", response_model=NotebookEntryResponse)
async def add_notebook_highlight(
    notebook_id: UUID,
    request: AddHighlightRequest,
    organization_id: Annotated[UUID, Header(alias="X-CivicOS-Organization-ID")],
    user_id: Annotated[UUID, Header(alias="X-CivicOS-User-ID")],
) -> NotebookEntryResponse:
    if (
        request.start_offset is not None
        and request.end_offset is not None
        and request.end_offset < request.start_offset
    ):
        raise HTTPException(status_code=422, detail="end_offset must not be before start_offset")
    repository = get_notebook_repository()
    if repository is None:
        raise HTTPException(status_code=503, detail="Research storage is not configured")
    entry = await repository.add_highlight(
        organization_id=organization_id,
        user_id=user_id,
        notebook_id=notebook_id,
        document_version_id=request.document_version_id,
        excerpt=request.excerpt,
        start_offset=request.start_offset,
        end_offset=request.end_offset,
        note=request.note,
    )
    return NotebookEntryResponse.model_validate(_entry_payload(entry))


@app.post("/v1/research/notebooks/{notebook_id}/summaries", response_model=NotebookEntryResponse)
async def generate_notebook_summary(
    notebook_id: UUID,
    request: GenerateSummaryRequest,
    organization_id: Annotated[UUID, Header(alias="X-CivicOS-Organization-ID")],
    user_id: Annotated[UUID, Header(alias="X-CivicOS-User-ID")],
) -> NotebookEntryResponse:
    service = get_notebook_service()
    if service is None:
        raise HTTPException(status_code=503, detail="Research storage is not configured")
    try:
        entry = await service.generate_summary(
            organization_id=organization_id,
            user_id=user_id,
            notebook_id=notebook_id,
            focus=request.focus,
        )
    except AnswerGenerationUnavailableError as error:
        raise HTTPException(status_code=503, detail=str(error)) from error
    except NotebookGroundingError as error:
        raise HTTPException(status_code=422, detail=str(error)) from error
    return NotebookEntryResponse.model_validate(_entry_payload(entry))


@app.post("/v1/research/notebooks/{notebook_id}/timelines", response_model=NotebookEntryResponse)
async def create_notebook_timeline(
    notebook_id: UUID,
    organization_id: Annotated[UUID, Header(alias="X-CivicOS-Organization-ID")],
    user_id: Annotated[UUID, Header(alias="X-CivicOS-User-ID")],
) -> NotebookEntryResponse:
    service = get_notebook_service()
    if service is None:
        raise HTTPException(status_code=503, detail="Research storage is not configured")
    try:
        entry = await service.create_timeline(
            organization_id=organization_id, user_id=user_id, notebook_id=notebook_id
        )
    except NotebookGroundingError as error:
        raise HTTPException(status_code=422, detail=str(error)) from error
    return NotebookEntryResponse.model_validate(_entry_payload(entry))


@app.get("/v1/research/notebooks/{notebook_id}/export")
async def export_research_notebook(
    notebook_id: UUID,
    organization_id: Annotated[UUID, Header(alias="X-CivicOS-Organization-ID")],
    user_id: Annotated[UUID, Header(alias="X-CivicOS-User-ID")],
    format: Literal["markdown", "json"] = "markdown",
) -> Response:
    service = get_notebook_service()
    if service is None:
        raise HTTPException(status_code=503, detail="Research storage is not configured")
    media_type, content = await service.export(
        organization_id=organization_id,
        user_id=user_id,
        notebook_id=notebook_id,
        format="json" if format == "json" else "markdown",
    )
    extension = "json" if format == "json" else "md"
    return Response(
        content=content,
        media_type=media_type,
        headers={
            "Content-Disposition": f'attachment; filename="notebook-{notebook_id}.{extension}"'
        },
    )


def _search_hit_payload(hit: SearchHit) -> dict[str, object]:
    return {
        "document_id": hit.document_id,
        "document_version_id": hit.document_version_id,
        "title": hit.title,
        "document_type": hit.document_type,
        "source_name": hit.source_name,
        "canonical_url": hit.canonical_url,
        "department_id": hit.department_id,
        "published_at": hit.published_at,
        "excerpt": hit.excerpt,
        "score": hit.score,
        "match_kind": hit.match_kind,
    }


def _grounded_answer_payload(answer: GroundedAnswer) -> dict[str, object]:
    return {
        "status": answer.status,
        "answer": answer.answer,
        "claims": [
            {"text": claim.text, "citation_ids": list(claim.citation_ids)}
            for claim in answer.claims
        ],
        "citations": [
            {
                "citation_id": citation.citation_id,
                "document_id": citation.document_id,
                "document_version_id": citation.document_version_id,
                "title": citation.title,
                "source_name": citation.source_name,
                "source_url": citation.source_url,
                "published_at": citation.published_at,
                "excerpt": citation.excerpt,
            }
            for citation in answer.citations
        ],
        "confidence": _confidence_payload(answer.confidence),
        "semantic_available": answer.semantic_available,
    }


def _confidence_payload(confidence: Confidence) -> dict[str, object]:
    return {
        "score": confidence.score,
        "level": confidence.level,
        "rationale": list(confidence.rationale),
    }


def _notebook_payload(notebook: Notebook) -> dict[str, object]:
    return {
        "id": notebook.id,
        "title": notebook.title,
        "description": notebook.description,
        "visibility": notebook.visibility,
        "created_at": notebook.created_at,
        "updated_at": notebook.updated_at,
    }


def _entry_payload(entry: NotebookEntry) -> dict[str, object]:
    return {
        "id": entry.id,
        "position": entry.position,
        "entry_type": entry.entry_type,
        "title": entry.title,
        "body_markdown": entry.body_markdown,
        "structured_content": entry.structured_content,
        "created_at": entry.created_at,
        "updated_at": entry.updated_at,
    }


def _saved_search_payload(search: SavedSearch) -> dict[str, object]:
    return {
        "id": search.id,
        "title": search.title,
        "query_text": search.query_text,
        "filters": search.filters,
        "created_at": search.created_at,
        "updated_at": search.updated_at,
    }


def _saved_document_payload(document: SavedDocument) -> dict[str, object]:
    return {
        "document_id": document.document_id,
        "document_version_id": document.document_version_id,
        "title": document.title,
        "document_type": document.document_type,
        "source_name": document.source_name,
        "source_url": document.source_url,
        "published_at": document.published_at,
        "note": document.note,
        "saved_at": document.saved_at,
    }


def _source_reference_payload(reference: SourceReference) -> dict[str, object]:
    return {
        "citation_id": reference.citation_id,
        "notebook_entry_id": reference.notebook_entry_id,
        "document_id": reference.document_id,
        "document_version_id": reference.document_version_id,
        "title": reference.title,
        "source_name": reference.source_name,
        "source_url": reference.source_url,
        "published_at": reference.published_at,
        "excerpt": reference.excerpt,
        "locator": reference.locator,
        "note": reference.note,
    }


def _snapshot_payload(snapshot: NotebookSnapshot) -> dict[str, object]:
    return {
        "notebook": _notebook_payload(snapshot.notebook),
        "entries": [_entry_payload(entry) for entry in snapshot.entries],
        "saved_searches": [_saved_search_payload(search) for search in snapshot.saved_searches],
        "saved_documents": [
            _saved_document_payload(document) for document in snapshot.saved_documents
        ],
        "source_references": [
            _source_reference_payload(reference) for reference in snapshot.source_references
        ],
    }


def _briefing_subscription_payload(subscription: BriefingSubscription) -> dict[str, object]:
    return {
        "id": subscription.id,
        "delivery_channel": subscription.delivery_channel,
        "is_active": subscription.is_active,
        "created_at": subscription.created_at,
        "updated_at": subscription.updated_at,
    }


def _daily_briefing_payload(briefing: DailyBriefing) -> dict[str, object]:
    return {
        "id": briefing.id,
        "briefing_date": briefing.briefing_date,
        "content": briefing.content,
        "generated_at": briefing.generated_at,
        "delivery_status": briefing.delivery_status,
        "delivered_at": briefing.delivered_at,
        "read_at": briefing.read_at,
    }


def _managed_user_payload(user: ManagedUser) -> dict[str, object]:
    return {
        "user_id": user.user_id,
        "external_subject": user.external_subject,
        "email": user.email,
        "display_name": user.display_name,
        "role_key": user.role_key,
        "is_active": user.is_active,
        "created_at": user.created_at,
        "updated_at": user.updated_at,
    }


def _founder_opportunity_payload(opportunity: FounderOpportunity) -> dict[str, object]:
    return {
        "id": opportunity.id,
        "signal_id": opportunity.signal_id,
        "signal_type": opportunity.signal_type,
        "title": opportunity.title,
        "what_happened": opportunity.what_happened,
        "why_it_matters": opportunity.why_it_matters,
        "where_money_may_be": opportunity.where_money_may_be,
        "who_might_pay": opportunity.who_might_pay,
        "action_to_take": opportunity.action_to_take,
        "urgency": opportunity.urgency,
        "score": opportunity.score,
        "evidence": opportunity.evidence,
        "affected_organizations": opportunity.affected_organizations,
        "source_url": opportunity.source_url,
        "document_title": opportunity.document_title,
        "discovered_at": opportunity.discovered_at,
    }


def _founder_signal_payload(signal: FounderSignal) -> dict[str, object]:
    return {
        "id": signal.id,
        "signal_type": signal.signal_type,
        "title": signal.title,
        "summary": signal.summary,
        "why_it_matters": signal.why_it_matters,
        "commercial_significance": signal.commercial_significance,
        "confidence_score": signal.confidence_score,
        "evidence": signal.evidence,
        "affected_organizations": signal.affected_organizations,
        "potential_customer_segments": signal.potential_customer_segments,
        "source_url": signal.source_url,
        "discovered_at": signal.discovered_at,
    }


def _founder_watchlist_payload(watchlist: FounderWatchlist) -> dict[str, object]:
    return {
        "id": watchlist.id,
        "watch_type": watchlist.watch_type,
        "name": watchlist.name,
        "normalized_term": watchlist.normalized_term,
        "criteria": watchlist.criteria,
        "is_active": watchlist.is_active,
        "match_count": watchlist.match_count,
        "latest_match_at": watchlist.latest_match_at,
        "created_at": watchlist.created_at,
    }


def _founder_brief_payload(brief: FounderBrief) -> dict[str, object]:
    return {
        "id": brief.id,
        "briefing_date": brief.briefing_date,
        "content": brief.content,
        "generated_at": brief.generated_at,
    }

from contextlib import asynccontextmanager
from typing import Annotated
from uuid import UUID
from fastapi import Depends, FastAPI, HTTPException, Query
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError, IntegrityError
from sqlalchemy.orm import Session
from .auth import CognitoVerifier, Principal
from .config import Settings
from .schemas import NewTicket, Claim, Outcome, TicketView, Status
from . import service

bearer = HTTPBearer(auto_error=False)


def create_app(settings: Settings | None = None, *, engine=None, verifier=None):
    settings = settings or Settings()
    verifier = verifier or CognitoVerifier(settings)
    try:
        engine = engine if engine is not None else settings.engine()
    except ValueError:
        engine = None  # Health can explain setup without leaking credentials.

    @asynccontextmanager
    async def lifespan(app):
        yield
        verifier.close()
        if engine is not None:
            engine.dispose()

    app = FastAPI(title="Sahayak Portal API", lifespan=lifespan, docs_url=None, redoc_url=None)
    app.add_middleware(CORSMiddleware, allow_origins=[settings.portal_origin],
                       allow_methods=["GET", "POST"], allow_headers=["Authorization", "Content-Type"])

    @app.middleware("http")
    async def no_cache(request, call_next):
        response = await call_next(request)
        response.headers["Cache-Control"] = "no-store"
        response.headers["X-Content-Type-Options"] = "nosniff"
        return response

    @app.exception_handler(RequestValidationError)
    async def validation_error(request, error):
        return JSONResponse(status_code=422, content={"detail": "Check the submitted fields and try again"})

    @app.exception_handler(SQLAlchemyError)
    async def database_error(request, error):
        conflict = isinstance(error, IntegrityError) or getattr(getattr(error, "orig", None), "sqlstate", "") in {"P0001", "55P03", "40001"}
        return JSONResponse(status_code=409 if conflict else 503, content={"detail":
            "The ticket could not be changed. Refresh and try again." if conflict else
            "Database connection or setup is unavailable. Please try again shortly."})

    def principal(credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(bearer)]):
        if credentials is None or credentials.scheme.lower() != "bearer":
            raise HTTPException(401, "Please sign in")
        return verifier.verify(credentials.credentials)

    def database():
        if engine is None:
            raise HTTPException(503, "The database connection is not configured yet")
        with Session(engine, expire_on_commit=False) as session:
            version = session.scalar(text("SELECT version_num FROM public.alembic_version"))
            if version not in {"0002_portal", "0003_dispatch"}:
                raise HTTPException(503, "The database migration must be completed first")
            yield session

    def actor(p: Annotated[Principal, Depends(principal)], db: Annotated[Session, Depends(database)]):
        return service.actor_for(db, p)

    DB = Annotated[Session, Depends(database)]
    Who = Annotated[service.Actor, Depends(actor)]

    @app.get("/health")
    def health():
        return {"status": "running", "database_configured": engine is not None}

    @app.get("/api/me")
    def me(who: Who):
        return {"id": who.id, "name": who.name, "roles": sorted(who.roles), "phone_ready": who.phone_ready}

    @app.get("/api/tickets")
    def listing(who: Who, db: DB, status: Status | None = None, before: Annotated[int | None, Query(ge=1)] = None):
        rows = service.tickets(db, who, status, before)
        return {"items": [TicketView.model_validate(t) for t in rows[:50]],
                "next_cursor": rows[49].ticket_number if len(rows) > 50 else None}

    @app.get("/api/tickets/{ticket_id}", response_model=TicketView)
    def detail(ticket_id: UUID, who: Who, db: DB):
        return service.ticket(db, who, ticket_id)

    @app.post("/api/tickets", response_model=TicketView)
    def create(data: NewTicket, who: Who, db: DB):
        result = TicketView.model_validate(service.create_ticket(db, who, data))
        db.commit()
        return result

    @app.post("/api/tickets/{ticket_id}/claim", response_model=TicketView)
    def claim(ticket_id: UUID, data: Claim, who: Who, db: DB):
        result = TicketView.model_validate(service.claim_ticket(db, who, ticket_id, data.expected_version))
        db.commit()
        return result

    @app.post("/api/tickets/{ticket_id}/outcome", response_model=TicketView)
    def outcome(ticket_id: UUID, data: Outcome, who: Who, db: DB):
        result = TicketView.model_validate(service.record_outcome(db, who, ticket_id, data))
        db.commit()
        return result

    app.state.principal_dependency = principal
    app.state.database_dependency = database
    return app


app = create_app()

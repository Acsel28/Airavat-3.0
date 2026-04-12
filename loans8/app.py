from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from loans8.api.dependencies import ensure_db_ready
from loans8.api.routers import negotiate, offer
from loans8.api.routers import negotiate_v2, offer_v2, search
from loans8.api.services.negotiation_store import init_negotiation_store
from loans8.api.services.session_store import init_session_store
from loans8.stt import router as stt_router


@asynccontextmanager
async def lifespan(app: FastAPI):
    ensure_db_ready()
    init_session_store()
    init_negotiation_store()
    from loans8.stt import storage as stt_storage
    from loans8.stt import transcriber

    _ = transcriber.model
    stt_storage.init_db()
    yield


app = FastAPI(lifespan=lifespan)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)
app.include_router(offer.router, prefix="/loan")
app.include_router(negotiate.router, prefix="/loan")
app.include_router(search.router)
app.include_router(offer_v2.router)
app.include_router(negotiate_v2.router)
app.include_router(stt_router.router)

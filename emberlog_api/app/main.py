import logging

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from emberlog_api.app.api.v1.routers import incidents, sse
from emberlog_api.app.core.lifespan import lifespan
from emberlog_api.utils.loggersetup import configure_logging


configure_logging()
log = logging.getLogger("emberlog_api.app.main")

app = FastAPI(lifespan=lifespan, title="Emberlog API", version="1.0.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # tighten in prod
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(incidents.router, prefix="/api/v1")
app.include_router(sse.router, prefix="/api/v1")

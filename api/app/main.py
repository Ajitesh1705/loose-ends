from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.routers import health, sources

app = FastAPI(title="Loose Ends API")

# Demo runs web (localhost:3000) against api (localhost:8000); allow the browser.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(health.router)
app.include_router(sources.router)

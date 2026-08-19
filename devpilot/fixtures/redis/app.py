"""Small FastAPI example; no real Redis connection is made by this fixture."""
from fastapi import FastAPI
from service import redis_url

app = FastAPI(title="DevPilot Redis fixture")


@app.get("/health")
def health():
    return {"status": "configuration-only demo", "redis_url": redis_url()}

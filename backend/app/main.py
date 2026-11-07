import os

import psycopg
from fastapi import FastAPI, HTTPException

app = FastAPI(title="Cafe Kiosk API")


@app.get("/api/health")
def health():
    try:
        with psycopg.connect(os.environ["DATABASE_URL"], connect_timeout=3) as connection:
            connection.execute("SELECT 1")
    except psycopg.Error:
        raise HTTPException(status_code=503, detail="Database unavailable") from None
    return {"status": "ok", "database": "connected"}

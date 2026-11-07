import psycopg
from fastapi import FastAPI, HTTPException
from app.db.connection import connect
from app.routers.menus import router as menus_router

app = FastAPI(title="Cafe Kiosk API")
app.include_router(menus_router)


@app.get("/api/health")
def health():
    try:
        with connect() as connection:
            connection.execute("SELECT 1")
    except psycopg.Error:
        raise HTTPException(status_code=503, detail="Database unavailable") from None
    return {"status": "ok", "database": "connected"}

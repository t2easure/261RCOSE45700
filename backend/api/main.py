from dotenv import load_dotenv
from pathlib import Path
load_dotenv(Path(__file__).parent.parent.parent / '.env')

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from db.database import init_db
from api.routers import search, fashion_reports

app = FastAPI(title="CRAI API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://localhost:3001", "http://localhost:3002"],
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.on_event("startup")
def startup():
    init_db()


app.include_router(search.router)
app.include_router(fashion_reports.router)

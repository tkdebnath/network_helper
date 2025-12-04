from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from contextlib import asynccontextmanager
from app.db.session import create_db_and_tables, engine
from app.api.endpoints import router as api_router
from app.db.models import DeviceQueue
from sqlmodel import Session, delete
import os
from dotenv import load_dotenv

env_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), "env.env")
load_dotenv(env_path)

@asynccontextmanager
async def lifespan(app: FastAPI):
    create_db_and_tables()
    # Clear the queue on startup
    with Session(engine) as session:
        session.exec(delete(DeviceQueue))
        session.commit()
    yield

app = FastAPI(lifespan=lifespan)

app.include_router(api_router, prefix="/api")

# Mount frontend if it exists
frontend_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), "frontend")
if os.path.exists(frontend_path):
    app.mount("/", StaticFiles(directory=frontend_path, html=True), name="frontend")

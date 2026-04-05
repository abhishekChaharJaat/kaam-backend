from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import get_settings
from app.database import connect_db, close_db, get_db
from app.utils.seed import seed_categories
from app.routes.auth import router as auth_router
from app.routes.users import router as users_router
from app.routes.service_profiles import router as service_profiles_router
from app.routes.categories import router as categories_router
from app.routes.jobs import router as jobs_router
from app.routes.conversations import router as conversations_router
from app.routes.websocket import router as ws_router
from app.routes.notifications import router as notifications_router
from app.routes.reviews import router as reviews_router
from app.routes.uploads import router as uploads_router
from app.routes.reports import router as reports_router
from app.routes.saved_users import router as saved_users_router


@asynccontextmanager
async def lifespan(app: FastAPI):
    await connect_db()
    await seed_categories(get_db())
    yield
    await close_db()


settings = get_settings()

app = FastAPI(
    title=settings.APP_NAME,
    version=settings.APP_VERSION,
    lifespan=lifespan,
)

origins = [o.strip() for o in settings.CORS_ORIGINS.split(",")]
app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


app.include_router(auth_router)
app.include_router(users_router)
app.include_router(service_profiles_router)
app.include_router(categories_router)
app.include_router(jobs_router)
app.include_router(conversations_router)
app.include_router(ws_router)
app.include_router(notifications_router)
app.include_router(reviews_router)
app.include_router(uploads_router)
app.include_router(reports_router)
app.include_router(saved_users_router)


@app.get("/health")
async def health_check():
    return {"status": "ok", "version": settings.APP_VERSION}

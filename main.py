# main.py
from fastapi import FastAPI
from app import routes
from core.settings import settings
from fastapi.middleware.cors import CORSMiddleware
from core.scripts.create_db_records import lifespan


app = FastAPI(debug=settings.debug, title="Meme Manager", lifespan=lifespan,)
app.include_router(routes.router)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False, # True
    allow_methods=["*"],
    allow_headers=["*"],
)


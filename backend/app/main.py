from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from langchain_anthropic import ChatAnthropic
from pymongo import MongoClient

from app.api.routes import router
from app.config import get_settings
from app.connectors.registry import ConnectionRegistry
from app.llm.pipeline import QueryPipeline
from app.store.conversations import ConversationStore
from app.store.dashboard import DashboardStore
from app.store.query_logger import QueryLogger


@asynccontextmanager
async def lifespan(app: FastAPI):
    settings = get_settings()

    meta_client = MongoClient(settings.APP_MONGODB_URI, serverSelectionTimeoutMS=5000)
    meta_db = meta_client[settings.APP_DATABASE]

    registry = ConnectionRegistry(
        meta_db,
        schema_sample_size=settings.SCHEMA_SAMPLE_SIZE,
        schema_cache_ttl=settings.SCHEMA_CACHE_TTL,
    )
    registry.ensure_demo("demo-ecommerce", "mongodb",
                         settings.DEMO_MONGODB_URI, settings.DEMO_DATABASE)
    registry.ensure_demo("demo-hr", "postgresql",
                         settings.DEMO_POSTGRES_URI, settings.DEMO_POSTGRES_DATABASE)

    llm = ChatAnthropic(
        model=settings.LLM_MODEL,
        max_tokens=settings.LLM_MAX_TOKENS,
        anthropic_api_key=settings.ANTHROPIC_API_KEY,
    )
    query_logger = QueryLogger(meta_db)
    pipeline = QueryPipeline(
        llm,
        query_logger=query_logger,
        preview_limit=settings.LLM_PREVIEW_LIMIT,
        max_results=settings.MAX_QUERY_RESULTS,
    )

    app.state.settings = settings
    app.state.meta_db = meta_db
    app.state.registry = registry
    app.state.conversations = ConversationStore(meta_db)
    app.state.dashboard = DashboardStore(meta_db)
    app.state.query_logger = query_logger
    app.state.pipeline = pipeline
    print(f"QueryLens ready | model={settings.LLM_MODEL} | meta_db={settings.APP_DATABASE}")
    yield
    registry.close_all()
    meta_client.close()
    print("QueryLens shut down.")


app = FastAPI(
    title="QueryLens",
    description="Chat with your database — natural language queries for MongoDB (and soon PostgreSQL).",
    version="0.1.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(router)

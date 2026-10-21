from fastapi import FastAPI

from statement_categorizer import rules_api
from statement_categorizer.api import router
from statement_categorizer.config import get_settings
from statement_categorizer.db import Database


def create_app(database: Database | None = None) -> FastAPI:
    app = FastAPI(
        title="statement-categorizer",
        version="0.1.0",
        description="Import bank statements and categorize transactions with ordered rules.",
    )
    app.state.database = database or Database(get_settings().database_url)
    # Tables are created on startup to keep the project self-contained; a production setup
    # would run Alembic migrations instead.
    app.state.database.create_schema()
    app.include_router(router)
    app.include_router(rules_api.router)

    @app.get("/health", tags=["ops"])
    def health() -> dict[str, str]:
        return {"status": "ok"}

    return app


app = create_app()

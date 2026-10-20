from fastapi import FastAPI


def create_app() -> FastAPI:
    app = FastAPI(
        title="statement-categorizer",
        version="0.1.0",
        description="Import bank statements and categorize transactions with ordered rules.",
    )

    @app.get("/health", tags=["ops"])
    def health() -> dict[str, str]:
        return {"status": "ok"}

    return app


app = create_app()

temporal server start-dev

uv run python -m src.app.temporal.worker

cd agent
uv run uvicorn src.app.main:app --reload --port 8000

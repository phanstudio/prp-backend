.PHONY: install up
install:
	uv sync

up:
	uv run uvicorn main:app --reload --port 8000

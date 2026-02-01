.PHONY: install check format test clean

install:
	uv sync

check:
	uv run ruff format --check src/ tests/
	uv run ruff check src/ tests/
	uv run ty check src/

format:
	uv run ruff format src/ tests/

test:
	uv run pytest tests/ -v

clean:
	find . -type d -name __pycache__ -exec rm -rf {} +
	find . -type d -name .pytest_cache -exec rm -rf {} +
	rm -rf .ruff_cache

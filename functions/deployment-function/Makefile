.PHONY: test quality reqs deploy clean install

# Default target
help:
	@echo "Available commands:"
	@echo "  install  - Install dependencies with uv"
	@echo "  test     - Run pytest tests"
	@echo "  quality  - Run ruff linting and formatting"
	@echo "  reqs     - Export dependencies to requirements.txt"
	@echo "  deploy   - Deploy function (runs tests, quality, reqs first)"
	@echo "  clean    - Remove cache files and requirements.txt"

# Install dependencies
install:
	uv sync --group dev

# Run tests
test:
	uv run pytest tests/ -v

# Run ruff for code quality
quality:
	uv run ruff format .
	uv run ruff check .

# Export dependencies to requirements.txt
reqs:
	uv export --format requirements.txt > requirements.txt

# Deploy function (run tests, quality, and reqs first)
deploy: test quality reqs
	@echo "Pre-deployment checks passed. Deploying function..."
	func azure functionapp publish kubemooc-deployment-func --python

# Clean up generated files
clean:
	rm -rf __pycache__/
	rm -rf .pytest_cache/
	rm -rf .ruff_cache/
	rm -f requirements.txt
	find . -name "*.pyc" -delete
	find . -name "__pycache__" -type d -exec rm -rf {} +

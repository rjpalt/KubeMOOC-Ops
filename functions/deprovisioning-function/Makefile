# Makefile for deprovisioning function development

.PHONY: help install install-dev test lint format type-check clean run logs deploy

help: ## Show this help message
	@echo "Available commands:"
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | sort | awk 'BEGIN {FS = ":.*?## "}; {printf "\033[36m%-20s\033[0m %s\n", $$1, $$2}'

install: ## Install production dependencies
	uv sync --no-group dev

install-dev: ## Install development dependencies
	uv sync --group dev

test: ## Run tests with coverage
	uv run pytest tests/ -v --tb=short

lint: ## Run linting with ruff
	uv run ruff check .

format: ## Format code with ruff
	uv run ruff format .

type-check: ## Run type checking with mypy
	uv run mypy .

clean: ## Clean cache and temporary files
	rm -rf .pytest_cache .mypy_cache .ruff_cache __pycache__
	find . -name "*.pyc" -delete
	find . -name "__pycache__" -type d -exec rm -rf {} +

run: ## Run the function locally
	@echo "Starting Azure Function locally..."
	@echo "Make sure you have Azure Function Core Tools installed:"
	@echo "  npm install -g azure-functions-core-tools@4"
	uv run func start

logs: ## Show function logs (when running locally)
	@echo "Function logs will appear in the terminal where 'make run' was executed"

deploy: ## Deploy to Azure (requires Azure CLI setup)
	@echo "Deploying to Azure Function App..."
	@echo "Make sure you've set up the Azure resources first!"
	@echo "Exporting requirements.txt for Azure Functions..."
	uv export --format requirements.txt > requirements.txt
	func azure functionapp publish Deprovisioning-Function --python

# Development workflow shortcuts
dev-setup: install-dev ## Complete development setup
	@echo "Development environment set up successfully!"
	@echo "Next steps:"
	@echo "1. Copy .env.example to .env and fill in your values"
	@echo "2. Run 'make test' to verify everything works"
	@echo "3. Run 'make run' to start the function locally"

check: lint type-check test ## Run all code quality checks

# CI/CD shortcuts  
ci: install-dev check ## Run CI pipeline locally

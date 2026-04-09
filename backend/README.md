# Child Development Assessment Agent - Backend

This is the backend service for the Child Development Assessment Agent, built with FastAPI, LlamaIndex, and LangGraph.

## Features
- RAG-based knowledge retrieval system
- Child development assessment engine
- Document management and ingestion
- Dynamic configuration system
- A/B testing framework
- ML-powered scoring and evaluation

## Getting Started
1. Install dependencies: `uv sync`
2. Configure environment variables: Copy `.env.dev.example` to `.env.dev` and fill in values
3. Start the server: `uv run start`

## Project Structure
- `src/`: Main source code
  - `config/`: Configuration management
  - `controller/`: API endpoints
  - `core/`: Core business logic
  - `model/`: Data models
  - `service/`: Business services
  - `utils/`: Utility functions
- `tests/`: Test cases
- `scripts/`: Maintenance and debug scripts

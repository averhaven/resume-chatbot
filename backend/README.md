# Resume Chatbot Backend

A FastAPI-based backend for a resume chatbot that uses RAG (Retrieval Augmented Generation) to answer questions about your resume.

## Setup

### Prerequisites
- Python 3.13+
- [uv](https://github.com/astral-sh/uv) package manager

### Installation

1. Clone the repository and navigate to the backend directory:
```bash
cd backend
```

2. Install dependencies using uv:
```bash
uv sync
```

3. Create a `.env` file from the example:
```bash
cp .env.example .env
```

4. (Optional) Modify `.env` to customize settings:
```bash
ENVIRONMENT=development
DEBUG=true
```

## Running the Server

Start the development server with auto-reload:
```bash
uv run uvicorn app.main:app --reload
```

The server will start on `http://localhost:8000`

### Available Endpoints

- `GET /health` - Health check endpoint
- `GET /docs` - Interactive API documentation (Swagger UI)
- `GET /redoc` - Alternative API documentation (ReDoc)

## Running Tests

Run all tests:
```bash
uv run pytest
```

Run tests with verbose output:
```bash
uv run pytest -v
```

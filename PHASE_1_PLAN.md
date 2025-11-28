# Phase 1: Backend Core - Detailed Breakdown

## Phase 1A: Project Foundation
- Set up Python project (pyproject.toml or requirements.txt)
- Create FastAPI project structure (folders: app/, tests/, data/)
- Add configuration management (.env, config.py)
- Set up basic logging
- Create simple health check endpoint
- Write tests for setup

## Phase 1B: WebSocket Basics
- Create WebSocket endpoint (echo/ping-pong test)
- Add connection management
- Test WebSocket manually (with a client tool)
- Write tests for WebSocket connection

## Phase 1C: Resume Data & Embeddings
- Design resume data format (JSON/YAML)
- Create your resume.json
- Set up Sentence-Transformers
- Create embeddings pipeline
- Test embedding generation
- Write tests for embeddings

## Phase 1D: Vector Store & Retrieval
- Set up ChromaDB
- Load resume embeddings into ChromaDB
- Build semantic search/retrieval function
- Test retrieval with sample questions
- Write tests for retrieval accuracy

## Deliverables
- Working FastAPI server with WebSocket endpoint
- Resume content embedded in ChromaDB
- Basic retrieval working (can find relevant resume sections)
- Tests passing

# Multi-Tenant SaaS Transformation Plan

## Overview
Transform the single-tenant resume chatbot into a multi-tenant SaaS platform where multiple users can upload their own resumes and get personalized chatbots.

**Architecture**: One resume per user, stored on the `User` model. No separate `resumes` table. `text_extractor.py` handles file-to-text extraction. `ResumeContext.from_text()` handles prompt building from stored text.

---

## Task Breakdown

### Task 1: Database Schema - Add Multi-Tenant Support ✅
**Goal:** Add user table and modify existing tables to support multi-tenancy

**Changes:**
- Create `users` table (id, username, email, password_hash, resume_filename, resume_content, chat_enabled, created_at)
- Add `user_id` column to `conversations` table
- Create Alembic migration for schema changes
- Add indexes for performance (user_id, username, email)

**Critical Files:**
- `app/db/models.py` - Add User ORM model, update Conversation
- `alembic/versions/` - New migration file
- `app/db/repositories/user.py` - New repository for User

**Verification:**
- Run migration successfully
- Tables created with correct schema
- Foreign key constraints working

---

### Task 2: User Authentication System ✅
**Goal:** Implement user registration, login, and JWT token-based authentication

**Changes:**
- Add authentication endpoints (`/auth/register`, `/auth/login`)
- Implement password hashing (bcrypt)
- Create JWT token generation and validation
- Add authentication middleware/dependency for protected routes

**Critical Files:**
- `app/api/auth.py` - Auth endpoints
- `app/core/auth.py` - Auth utilities (JWT, password hashing)
- `app/core/dependencies.py` - `get_current_user` dependency

**Verification:**
- Users can register with email/password
- Users can log in and receive JWT token
- Protected endpoints require valid token
- Invalid tokens are rejected

---

### Task 3: Resume Upload & Management ✅
**Goal:** Allow authenticated users to upload and manage their single resume

**Changes:**
- Create resume upload endpoint (accepts PDF, DOCX, TXT, Markdown, JSON)
- Implement file text extraction via `text_extractor.py` (all formats produce readable text)
- Store resume content on User model (resume_filename, resume_content)
- Add `ResumeContext.from_text()` for building system prompts from stored text
- Add endpoints to get/delete resume and toggle chat
- JSON resumes are auto-formatted as readable text (not raw JSON)

**Critical Files:**
- `app/api/resumes.py` - Resume CRUD endpoints
- `app/services/text_extractor.py` - File-to-text extraction (all formats)
- `app/services/resume_loader.py` - `ResumeContext.from_text()` for prompt building

**Verification:**
- User can upload resume file (any supported format)
- Text is extracted correctly (JSON formatted as readable text)
- Resume stored on user profile in database
- `ResumeContext.from_text()` builds valid system prompts
- Cannot access other users' resumes

---

### Task 4: Tenant Context & Data Isolation
**Goal:** Add user_id filtering throughout the application to ensure data isolation

**Changes:**
- Modify `DatabaseConversationManager` to accept and use `user_id`
- Update conversation and message repositories to filter by `user_id`
- Add tenant context to `app/core/context.py` (store user_id in contextvars)
- Ensure all database queries include tenant filtering
- Add tests to verify cross-tenant data leakage prevention

**Critical Files:**
- `app/services/conversation_db.py` - Add user_id parameter
- `app/db/repositories/conversation.py` - Add WHERE user_id = ? filters
- `app/db/repositories/message.py` - Add tenant filtering
- `app/core/context.py` - Add user_id context variable

**Verification:**
- All queries filtered by user_id
- Users cannot access other users' conversations
- Test cross-tenant isolation with multiple test users

---

### Task 5: Dynamic WebSocket Routing ✅
**Goal:** Route WebSocket connections to the correct user's resume based on URL

**Changes:**
- Change WebSocket endpoint from `/ws` to `/chat/{username}`
- Look up user by username in database
- Load that user's resume content for conversation context
- Create conversation linked to resume owner's user_id
- Handle user not found / no resume / chat disabled errors

**Critical Files:**
- `app/main.py` - Update WebSocket endpoint signature and logic
- `app/services/resume_loader.py` - Use `ResumeContext.from_text()` for per-user loading

**Verification:**
- Connect to `/chat/alice` loads Alice's resume
- Connect to `/chat/bob` loads Bob's resume
- Invalid username returns proper error
- Chat disabled returns proper error
- Conversation saved under correct user_id

---

### Task 6: Per-Tenant Resume Loading
**Goal:** Load and cache resume content per-user instead of globally

**Changes:**
- Remove global `app.state.resume_context`
- Implement per-user context loading via `ResumeContext.from_text()` (lazy load on first request)
- Add in-memory cache for resume contexts (keyed by user_id)
- Cache eviction strategy (LRU or TTL-based)
- Retire `ResumeLoader` class (legacy single-tenant startup loader)

**Critical Files:**
- `app/services/resume_loader.py` - Per-user loading with cache
- `app/main.py` - Remove global resume loading from startup

**Verification:**
- Each user's resume loads its own content
- Resume context cached appropriately
- Different users get different resume content
- Memory usage reasonable with multiple users

---

### Task 7: User Dashboard API
**Goal:** Create REST API endpoints for user dashboard functionality

**Changes:**
- Add endpoint to get user's resume info and public chatbot URL
- Add endpoint to view conversation history (`GET /api/conversations`)
- Add endpoint to get analytics (message count, conversation count)
- Return chatbot URL for user (e.g., `yoursite.com/chat/{username}`)

**Critical Files:**
- `app/api/resumes.py` - Dashboard endpoints
- `app/api/conversations.py` - New conversation history endpoints
- `app/main.py` - Register new routers

**Verification:**
- User can see their resume info
- User sees correct public chatbot URL
- User can view conversation history
- All data properly filtered by user_id

---

### Task 8: Per-Tenant Rate Limiting & Quotas
**Goal:** Implement rate limiting and usage quotas per user

**Changes:**
- Extend rate limiter to support per-user limits (not just per-session)
- Add usage tracking (messages sent this month)
- Add subscription tier support (free, pro, business)
- Enforce quota limits before processing messages
- Return user-friendly error when quota exceeded

**Critical Files:**
- `app/core/rate_limit.py` - Add user-based rate limiting
- `app/db/models.py` - Add usage tracking fields to User model
- `app/services/usage_tracker.py` - New service for tracking usage
- `app/main.py` - Add quota check in WebSocket handler

**Verification:**
- Free tier limited to X messages/month
- Pro tier has higher limits
- Quota exceeded returns proper error
- Usage resets monthly

---

### Task 9: Basic Frontend Dashboard (Optional for MVP)
**Goal:** Simple web UI for users to manage resumes

**Changes:**
- Create simple HTML/JS dashboard page
- Login/register forms
- Resume upload form
- Display user's resume info
- Display public chatbot URL with copy button
- Embed chatbot widget code snippet

**Critical Files:**
- `frontend/` - New directory for frontend code (or simple templates)
- `app/main.py` - Serve static files or templates

**Verification:**
- User can log in via web UI
- User can upload resume via form
- User sees chatbot URL
- Can copy/paste URL to test chatbot

---

## Implementation Order

Execute tasks in numerical order (1 → 9):
1. ✅ Database changes first (foundation)
2. ✅ Authentication next (required for all other features)
3. ✅ Resume upload (core feature)
4. ✅ Data isolation (security critical)
5. ✅ Dynamic routing (enables multi-tenant chatbot)
6. Resume loading (performance optimization)
7. Dashboard API (user-facing features)
8. Rate limiting (production readiness)
9. Frontend (nice-to-have, can be separate project)

---

## Critical Files Summary

**Database & Models:**
- `app/db/models.py`
- `app/db/repositories/`
- `alembic/versions/`

**Authentication:**
- `app/api/auth.py`
- `app/core/auth.py`
- `app/core/dependencies.py`

**Resume Management:**
- `app/api/resumes.py`
- `app/services/text_extractor.py` (extraction layer)
- `app/services/resume_loader.py` (`ResumeContext.from_text()` for prompt building)

**WebSocket & Conversations:**
- `app/main.py`
- `app/services/conversation_db.py`

**Configuration & Context:**
- `app/core/config.py`
- `app/core/context.py`
- `app/core/rate_limit.py`

---

## Testing Strategy

After each task:
- Write unit tests for new functionality
- Write integration tests for multi-tenant isolation
- Manually test via API/WebSocket
- Verify no cross-tenant data leakage

---

## Future Enhancements (Beyond Core MVP)

- Resume content validation (verify uploaded content is actually a resume)
- Multiple resumes per user with slugs
- Email verification
- Password reset flow
- OAuth providers (Google, GitHub)
- Custom branding per chatbot
- Analytics dashboard
- Billing integration (Stripe)
- Embeddable widget
- API keys for programmatic access
- Multi-language support
- Interview practice mode

---

## Notes

- Each task is designed to be a separate work session
- Tasks build on each other sequentially
- Database migrations should be reversible
- Security testing critical for Tasks 2, 4, and 8
- Performance testing important for Task 6

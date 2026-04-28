"""Tests for resume loader service."""

import json

import pytest

from app.services.resume_loader import (
    ResumeContext,
    ResumeContextCache,
    ResumeLoader,
    ResumeLoadError,
    create_resume_loader,
)
from app.services.token_counter import TokenCounter


class TestResumeLoader:
    """Tests for ResumeLoader and create_resume_loader."""

    def test_load_valid_json(self, tmp_path):
        """load() parses a valid JSON resume and produces formatted text."""
        resume = {
            "name": "Jane Doe",
            "title": "Engineer",
            "summary": "Experienced developer.",
        }
        path = tmp_path / "resume.json"
        path.write_text(json.dumps(resume), encoding="utf-8")

        loader = ResumeLoader(path)
        loader.load()

        text = loader.get_resume_text()
        assert "Jane Doe" in text
        assert "Engineer" in text
        assert "Experienced developer." in text

    def test_load_missing_file_raises(self, tmp_path):
        """load() raises ResumeLoadError when the file does not exist."""
        loader = ResumeLoader(tmp_path / "missing.json")

        with pytest.raises(ResumeLoadError, match="Resume file not found"):
            loader.load()

    def test_load_invalid_json_raises(self, tmp_path):
        """load() raises ResumeLoadError on malformed JSON."""
        path = tmp_path / "bad.json"
        path.write_text("not valid json", encoding="utf-8")

        loader = ResumeLoader(path)

        with pytest.raises(ResumeLoadError, match="Invalid JSON"):
            loader.load()

    def test_get_resume_text_none_before_load(self, tmp_path):
        """get_resume_text() returns None before load() is called."""
        loader = ResumeLoader(tmp_path / "resume.json")
        assert loader.get_resume_text() is None

    def test_create_resume_loader_returns_loaded_instance(self, tmp_path):
        """create_resume_loader() returns a loaded ResumeLoader."""
        path = tmp_path / "resume.json"
        path.write_text(json.dumps({"name": "Alice", "title": "Dev"}), encoding="utf-8")

        loader = create_resume_loader(path)

        assert loader.get_resume_text() is not None
        assert "Alice" in loader.get_resume_text()

    def test_format_includes_contact(self, tmp_path):
        """Formatted text includes contact details when present."""
        resume = {
            "name": "Bob",
            "title": "Dev",
            "contact": {"email": "bob@example.com", "phone": "123", "location": "NYC"},
        }
        path = tmp_path / "resume.json"
        path.write_text(json.dumps(resume), encoding="utf-8")

        loader = create_resume_loader(path)

        assert "bob@example.com" in loader.get_resume_text()

    def test_format_includes_experience(self, tmp_path):
        """Formatted text includes work experience entries."""
        resume = {
            "name": "Carol",
            "title": "Dev",
            "experience": [
                {
                    "title": "Senior Dev",
                    "company": "Acme",
                    "location": "NYC",
                    "start_date": "2020-01",
                    "current": True,
                    "responsibilities": ["Built things"],
                }
            ],
        }
        path = tmp_path / "resume.json"
        path.write_text(json.dumps(resume), encoding="utf-8")

        loader = create_resume_loader(path)
        text = loader.get_resume_text()

        assert "Senior Dev at Acme" in text
        assert "Built things" in text


class TestResumeContextFromText:
    """Tests for ResumeContext.from_text()."""

    def test_from_text_builds_prompt(self):
        """from_text() builds a system prompt containing the resume text."""
        token_counter = TokenCounter()
        resume_text = "# Jane Doe\n## Software Engineer\n\nExperienced developer."

        ctx = ResumeContext.from_text(resume_text, token_counter)

        assert "Jane Doe" in ctx.system_prompt
        assert "Software Engineer" in ctx.system_prompt
        assert ctx.system_prompt_tokens > 0

    def test_from_text_token_count_matches(self):
        """Token count from from_text() matches manual count."""
        token_counter = TokenCounter()
        resume_text = "Simple resume content for testing."

        ctx = ResumeContext.from_text(resume_text, token_counter)

        expected = token_counter.count_tokens(ctx.system_prompt)
        assert ctx.system_prompt_tokens == expected


class TestResumeContextCache:
    """Tests for the LRU ResumeContextCache."""

    def test_cache_miss_creates_context(self):
        """get_or_create() builds a new context on cache miss."""
        token_counter = TokenCounter()
        cache = ResumeContextCache()

        ctx = cache.get_or_create("user_1", "Alice is a developer.", token_counter)

        assert "Alice" in ctx.system_prompt
        assert cache.size == 1

    def test_cache_hit_returns_same_instance(self):
        """get_or_create() returns the identical object on cache hit."""
        token_counter = TokenCounter()
        cache = ResumeContextCache()

        ctx1 = cache.get_or_create("user_1", "Alice is a developer.", token_counter)
        ctx2 = cache.get_or_create("user_1", "Alice is a developer.", token_counter)

        assert ctx1 is ctx2
        assert cache.size == 1

    def test_lru_eviction_removes_oldest(self):
        """When full, the least-recently-used entry is evicted."""
        token_counter = TokenCounter()
        cache = ResumeContextCache(max_size=2)

        cache.get_or_create("a", "Resume A", token_counter)
        cache.get_or_create("b", "Resume B", token_counter)
        cache.get_or_create("c", "Resume C", token_counter)  # evicts "a"

        assert cache.size == 2
        assert "a" not in cache._cache
        assert "b" in cache._cache
        assert "c" in cache._cache

    def test_lru_eviction_respects_recent_access(self):
        """Accessing an entry promotes it, so a different entry is evicted."""
        token_counter = TokenCounter()
        cache = ResumeContextCache(max_size=2)

        cache.get_or_create("a", "Resume A", token_counter)
        cache.get_or_create("b", "Resume B", token_counter)
        cache.get_or_create("a", "Resume A", token_counter)  # promote "a"
        cache.get_or_create("c", "Resume C", token_counter)  # evicts "b"

        assert "a" in cache._cache
        assert "b" not in cache._cache
        assert "c" in cache._cache

    def test_invalidate_removes_entry(self):
        """invalidate() removes the specified entry from the cache."""
        token_counter = TokenCounter()
        cache = ResumeContextCache()

        cache.get_or_create("user_1", "Alice is a developer.", token_counter)
        assert cache.size == 1

        cache.invalidate("user_1")
        assert cache.size == 0

    def test_invalidate_missing_key_is_safe(self):
        """invalidate() on a nonexistent key raises no error."""
        cache = ResumeContextCache()
        cache.invalidate("nonexistent")  # must not raise

    def test_clear_removes_all_entries(self):
        """clear() empties the cache completely."""
        token_counter = TokenCounter()
        cache = ResumeContextCache()

        cache.get_or_create("a", "Resume A", token_counter)
        cache.get_or_create("b", "Resume B", token_counter)

        cache.clear()
        assert cache.size == 0

    def test_different_users_get_different_contexts(self):
        """Different cache keys produce different ResumeContext instances."""
        token_counter = TokenCounter()
        cache = ResumeContextCache()

        ctx_alice = cache.get_or_create(
            "alice", "Alice is a Python developer.", token_counter
        )
        ctx_bob = cache.get_or_create(
            "bob", "Bob is a JavaScript developer.", token_counter
        )

        assert "Alice" in ctx_alice.system_prompt
        assert "Bob" in ctx_bob.system_prompt
        assert ctx_alice is not ctx_bob

    def test_invalidate_then_create_rebuilds_context(self):
        """After invalidation, the next get_or_create() builds a fresh context."""
        token_counter = TokenCounter()
        cache = ResumeContextCache()

        ctx1 = cache.get_or_create("user_1", "Original resume.", token_counter)
        cache.invalidate("user_1")
        ctx2 = cache.get_or_create("user_1", "Updated resume.", token_counter)

        assert ctx1 is not ctx2
        assert "Updated" in ctx2.system_prompt

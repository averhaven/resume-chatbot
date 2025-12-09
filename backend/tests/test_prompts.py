"""Tests for prompt building service."""

import pytest

from app.services.prompts import build_initial_prompt, build_prompt, build_system_prompt


class TestBuildSystemPrompt:
    """Tests for build_system_prompt function."""

    def test_build_system_prompt(self):
        """Test building system prompt with resume."""
        resume_text = "John Doe\nSoftware Engineer\nSkills: Python, FastAPI"
        result = build_system_prompt(resume_text)

        assert isinstance(result, str)
        assert resume_text in result
        assert "assistant" in result.lower()
        assert "resume" in result.lower()

    def test_build_system_prompt_empty_resume(self):
        """Test building system prompt with empty resume."""
        result = build_system_prompt("")

        assert isinstance(result, str)
        # Should still have the template structure
        assert "assistant" in result.lower()


class TestBuildPrompt:
    """Tests for build_prompt function."""

    def test_build_prompt_no_history(self):
        """Test building prompt with no conversation history."""
        resume = "John Doe\nSoftware Engineer"
        history = []
        question = "What is your name?"

        result = build_prompt(resume, history, question)

        assert isinstance(result, list)
        assert len(result) == 2  # system + user question
        assert result[0]["role"] == "system"
        assert resume in result[0]["content"]
        assert result[1]["role"] == "user"
        assert result[1]["content"] == question

    def test_build_prompt_with_history(self):
        """Test building prompt with conversation history."""
        resume = "John Doe\nSoftware Engineer"
        history = [
            {"role": "user", "content": "What is your name?"},
            {"role": "assistant", "content": "My name is John Doe."},
            {"role": "user", "content": "What do you do?"},
            {"role": "assistant", "content": "I am a Software Engineer."},
        ]
        question = "What are your skills?"

        result = build_prompt(resume, history, question)

        assert isinstance(result, list)
        # system + 4 history + new question = 6
        assert len(result) == 6
        assert result[0]["role"] == "system"
        assert result[1]["role"] == "user"
        assert result[1]["content"] == "What is your name?"
        assert result[2]["role"] == "assistant"
        assert result[-1]["role"] == "user"
        assert result[-1]["content"] == question

    def test_build_prompt_filters_system_messages_from_history(self):
        """Test that system messages in history are filtered out."""
        resume = "John Doe"
        history = [
            {"role": "system", "content": "Old system message"},
            {"role": "user", "content": "Hello"},
            {"role": "assistant", "content": "Hi"},
        ]
        question = "How are you?"

        result = build_prompt(resume, history, question)

        # Should have: new system + user + assistant + new user = 4 messages
        assert len(result) == 4
        # First message should be the new system prompt, not the old one
        assert result[0]["role"] == "system"
        assert "Old system message" not in result[0]["content"]
        assert resume in result[0]["content"]

    def test_build_prompt_message_format(self):
        """Test that all messages have correct format."""
        resume = "John Doe"
        history = [{"role": "user", "content": "Test"}]
        question = "Question?"

        result = build_prompt(resume, history, question)

        for msg in result:
            assert isinstance(msg, dict)
            assert "role" in msg
            assert "content" in msg
            assert msg["role"] in ["system", "user", "assistant"]
            assert isinstance(msg["content"], str)


class TestBuildInitialPrompt:
    """Tests for build_initial_prompt function."""

    def test_build_initial_prompt(self):
        """Test building initial prompt (no history)."""
        resume = "John Doe\nSoftware Engineer"
        question = "Tell me about yourself"

        result = build_initial_prompt(resume, question)

        assert isinstance(result, list)
        assert len(result) == 2  # system + user
        assert result[0]["role"] == "system"
        assert resume in result[0]["content"]
        assert result[1]["role"] == "user"
        assert result[1]["content"] == question

    def test_build_initial_prompt_is_equivalent_to_build_prompt_no_history(self):
        """Test that build_initial_prompt is same as build_prompt with empty history."""
        resume = "John Doe"
        question = "Test question"

        result1 = build_initial_prompt(resume, question)
        result2 = build_prompt(resume, [], question)

        assert result1 == result2

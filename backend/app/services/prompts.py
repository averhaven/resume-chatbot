"""Prompt building service for constructing LLM prompts."""

from app.core.logger import get_logger

logger = get_logger(__name__)

# System prompt template for the resume chatbot
SYSTEM_PROMPT_TEMPLATE = """You are a helpful assistant designed to answer questions about the following resume.
Your role is to provide accurate, helpful, and professional responses based solely on the information in the resume.

Key guidelines:
- Answer questions directly and concisely
- Only provide information that can be found in or reasonably inferred from the resume
- If a question cannot be answered from the resume, politely say so
- Be professional and friendly in your responses
- Do not make up or fabricate information

Here is the resume:

{resume}

Please answer any questions about this person's background, skills, experience, education, or other relevant information from the resume."""


def build_system_prompt(resume_text: str) -> str:
    """Build the system prompt with resume context.

    Args:
        resume_text: Formatted resume text

    Returns:
        System prompt with resume injected
    """
    return SYSTEM_PROMPT_TEMPLATE.format(resume=resume_text)


def build_prompt(
    resume_text: str,
    conversation_history: list[dict[str, str]],
    new_question: str,
) -> list[dict[str, str]]:
    """Build a complete prompt for the LLM API.

    Constructs a message list in OpenAI-compatible format:
    1. System message with resume context
    2. Conversation history (alternating user/assistant messages)
    3. New user question

    Args:
        resume_text: Formatted resume text
        conversation_history: Previous messages in the conversation
        new_question: New user question to add

    Returns:
        List of message dictionaries with 'role' and 'content' keys
    """
    messages = []

    # Add system prompt with resume
    system_prompt = build_system_prompt(resume_text)
    messages.append({"role": "system", "content": system_prompt})

    # Add conversation history (excluding any existing system messages)
    for msg in conversation_history:
        if msg["role"] != "system":
            messages.append(msg)

    # Add new user question
    messages.append({"role": "user", "content": new_question})

    logger.debug(
        f"Built prompt with {len(messages)} messages "
        f"(system + {len(conversation_history)} history + new question)"
    )

    return messages


def build_initial_prompt(resume_text: str, question: str) -> list[dict[str, str]]:
    """Build a prompt for the first message in a conversation.

    This is a convenience function for when there's no conversation history.

    Args:
        resume_text: Formatted resume text
        question: User's first question

    Returns:
        List of message dictionaries with 'role' and 'content' keys
    """
    return build_prompt(resume_text, [], question)

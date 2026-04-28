"""Resume loader service for loading and formatting resume data."""

import json
from collections import OrderedDict
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from app.core.logger import get_logger
from app.services.prompts import build_system_prompt
from app.services.token_counter import TokenCounter

logger = get_logger(__name__)


class ResumeLoadError(Exception):
    """Raised when resume cannot be loaded or parsed."""

    pass


class ResumeLoader:
    """Service for loading and formatting resume data."""

    def __init__(self, resume_path: str | Path):
        """Initialize the resume loader.

        Args:
            resume_path: Path to the resume JSON file
        """
        self.resume_path = Path(resume_path)
        self._resume_data: dict[str, Any] | None = None
        self._resume_text: str | None = None

    def load(self) -> None:
        """Load and parse the resume file.

        Raises:
            ResumeLoadError: If file cannot be loaded or parsed
        """
        if not self.resume_path.exists():
            raise ResumeLoadError(f"Resume file not found: {self.resume_path}")

        try:
            with self.resume_path.open(encoding="utf-8") as f:
                self._resume_data = json.load(f)
            logger.info(f"Successfully loaded resume from {self.resume_path}")
        except json.JSONDecodeError as e:
            raise ResumeLoadError(f"Invalid JSON in resume file: {e}") from e
        except Exception as e:
            raise ResumeLoadError(f"Failed to load resume: {e}") from e

        self._resume_text = self._format_resume_as_text(self._resume_data)

    def _format_header(self, data: dict[str, Any]) -> list[str]:
        """Format resume header section.

        Args:
            data: Resume data dictionary

        Returns:
            List of formatted header lines
        """
        lines = []
        lines.append(f"# {data.get('name', 'N/A')}")
        lines.append(f"## {data.get('title', 'N/A')}")
        lines.append("")
        return lines

    def _format_contact(self, contact: dict[str, Any]) -> list[str]:
        """Format contact information section.

        Args:
            contact: Contact data dictionary

        Returns:
            List of formatted contact lines
        """
        lines = []
        lines.append("### Contact Information")
        lines.append(f"- Email: {contact.get('email', 'N/A')}")
        lines.append(f"- Phone: {contact.get('phone', 'N/A')}")
        lines.append(f"- Location: {contact.get('location', 'N/A')}")
        if contact.get("linkedin"):
            lines.append(f"- LinkedIn: {contact['linkedin']}")
        if contact.get("github"):
            lines.append(f"- GitHub: {contact['github']}")
        lines.append("")
        return lines

    def _format_summary(self, summary: str) -> list[str]:
        """Format professional summary section.

        Args:
            summary: Summary text

        Returns:
            List of formatted summary lines
        """
        lines = []
        lines.append("### Professional Summary")
        lines.append(summary)
        lines.append("")
        return lines

    def _format_experience(self, experience: list[dict[str, Any]]) -> list[str]:
        """Format work experience section.

        Args:
            experience: List of experience entries

        Returns:
            List of formatted experience lines
        """
        lines = []
        lines.append("### Work Experience")
        for exp in experience:
            title = exp.get("title", "N/A")
            company = exp.get("company", "N/A")
            location = exp.get("location", "N/A")
            start = exp.get("start_date", "N/A")
            end = (
                exp.get("end_date", "Present")
                if exp.get("current")
                else exp.get("end_date", "N/A")
            )

            lines.append(f"#### {title} at {company}")
            lines.append(f"{location} | {start} - {end}")

            if exp.get("responsibilities"):
                for resp in exp["responsibilities"]:
                    lines.append(f"- {resp}")
            lines.append("")
        return lines

    def _format_skills(self, skills: dict[str, Any]) -> list[str]:
        """Format skills section.

        Args:
            skills: Skills data dictionary

        Returns:
            List of formatted skills lines
        """
        lines = []
        lines.append("### Skills")
        if skills.get("languages"):
            lines.append(f"- **Languages**: {', '.join(skills['languages'])}")
        if skills.get("frameworks"):
            lines.append(f"- **Frameworks**: {', '.join(skills['frameworks'])}")
        if skills.get("databases"):
            lines.append(f"- **Databases**: {', '.join(skills['databases'])}")
        if skills.get("tools"):
            lines.append(f"- **Tools**: {', '.join(skills['tools'])}")
        if skills.get("other"):
            lines.append(f"- **Other**: {', '.join(skills['other'])}")
        lines.append("")
        return lines

    def _format_education(self, education: list[dict[str, Any]]) -> list[str]:
        """Format education section.

        Args:
            education: List of education entries

        Returns:
            List of formatted education lines
        """
        lines = []
        lines.append("### Education")
        for edu in education:
            degree = edu.get("degree", "N/A")
            institution = edu.get("institution", "N/A")
            location = edu.get("location", "N/A")
            grad_date = edu.get("graduation_date", "N/A")

            lines.append(f"#### {degree}")
            lines.append(f"{institution}, {location}")
            lines.append(f"Graduated: {grad_date}")
            if edu.get("gpa"):
                lines.append(f"GPA: {edu['gpa']}")
            lines.append("")
        return lines

    def _format_projects(self, projects: list[dict[str, Any]]) -> list[str]:
        """Format projects section.

        Args:
            projects: List of project entries

        Returns:
            List of formatted project lines
        """
        lines = []
        lines.append("### Notable Projects")
        for proj in projects:
            name = proj.get("name", "N/A")
            desc = proj.get("description", "N/A")
            tech = proj.get("technologies", [])

            lines.append(f"#### {name}")
            lines.append(desc)
            if tech:
                lines.append(f"Technologies: {', '.join(tech)}")
            if proj.get("url"):
                lines.append(f"URL: {proj['url']}")
            lines.append("")
        return lines

    def _format_certifications(self, certifications: list[dict[str, Any]]) -> list[str]:
        """Format certifications section.

        Args:
            certifications: List of certification entries

        Returns:
            List of formatted certification lines
        """
        lines = []
        lines.append("### Certifications")
        for cert in certifications:
            name = cert.get("name", "N/A")
            issuer = cert.get("issuer", "N/A")
            date = cert.get("date", "N/A")
            lines.append(f"- {name} - {issuer} ({date})")
        lines.append("")
        return lines

    def _format_resume_as_text(self, data: dict[str, Any]) -> str:
        """Format resume data as human-readable text for LLM prompts.

        Args:
            data: Resume data dictionary

        Returns:
            Formatted resume text
        """
        lines = []

        lines.extend(self._format_header(data))

        if data.get("contact"):
            lines.extend(self._format_contact(data["contact"]))

        if data.get("summary"):
            lines.extend(self._format_summary(data["summary"]))

        if data.get("experience"):
            lines.extend(self._format_experience(data["experience"]))

        if data.get("skills"):
            lines.extend(self._format_skills(data["skills"]))

        if data.get("education"):
            lines.extend(self._format_education(data["education"]))

        if data.get("projects"):
            lines.extend(self._format_projects(data["projects"]))

        if data.get("certifications"):
            lines.extend(self._format_certifications(data["certifications"]))

        return "\n".join(lines)

    def get_resume_text(self) -> str | None:
        """Get the formatted resume text.

        Returns:
            Formatted resume text, or None if not loaded
        """
        return self._resume_text

    def get_resume_data(self) -> dict[str, Any] | None:
        """Get the raw resume data dictionary.

        Returns:
            Resume data dictionary, or None if not loaded
        """
        return self._resume_data


def create_resume_loader(resume_path: str | Path) -> ResumeLoader:
    """Create and initialize a resume loader instance.

    Args:
        resume_path: Path to the resume JSON file

    Returns:
        Loaded ResumeLoader instance

    Raises:
        ResumeLoadError: If resume cannot be loaded
    """
    loader = ResumeLoader(resume_path)
    loader.load()
    return loader


@dataclass
class ResumeContext:
    """Encapsulates resume system prompt and token count.

    Built once per user (or on cache miss) from stored resume text.
    """

    system_prompt: str
    system_prompt_tokens: int

    @classmethod
    def from_text(
        cls, resume_text: str, token_counter: TokenCounter
    ) -> "ResumeContext":
        """Create a ResumeContext from already-extracted resume text.

        Args:
            resume_text: Pre-extracted resume text content
            token_counter: TokenCounter instance for counting tokens

        Returns:
            ResumeContext with built system prompt and token count
        """
        system_prompt = build_system_prompt(resume_text)
        system_prompt_tokens = token_counter.count_tokens(system_prompt)

        logger.info(f"Built system prompt ({system_prompt_tokens} tokens)")

        return cls(
            system_prompt=system_prompt,
            system_prompt_tokens=system_prompt_tokens,
        )


class ResumeContextCache:
    """LRU in-memory cache for ResumeContext instances, keyed by string.

    Prevents rebuilding the system prompt on every WebSocket connection.
    Cache is invalidated when a user updates or deletes their resume.
    """

    def __init__(self, max_size: int = 128):
        self._cache: OrderedDict[str, ResumeContext] = OrderedDict()
        self._max_size = max_size

    def get_or_create(
        self, key: str, resume_text: str, token_counter: TokenCounter
    ) -> ResumeContext:
        """Return a cached ResumeContext or build and cache a new one.

        Args:
            key: Cache key (e.g. str(user_id) or a sentinel for legacy use)
            resume_text: Resume text used to build the context on a cache miss
            token_counter: Used to count tokens on a cache miss

        Returns:
            Cached or newly created ResumeContext
        """
        if key in self._cache:
            self._cache.move_to_end(key)
            return self._cache[key]

        context = ResumeContext.from_text(resume_text, token_counter)
        self._cache[key] = context

        if len(self._cache) > self._max_size:
            evicted, _ = self._cache.popitem(last=False)
            logger.debug(f"Evicted LRU resume context (key={evicted!r})")

        return context

    def invalidate(self, key: str) -> None:
        """Remove a cached entry, e.g. after a resume upload or delete."""
        self._cache.pop(key, None)

    def clear(self) -> None:
        """Remove all cached entries."""
        self._cache.clear()

    @property
    def size(self) -> int:
        return len(self._cache)

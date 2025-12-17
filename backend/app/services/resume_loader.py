"""Resume loader service for loading and formatting resume data."""

import json
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

        # Convert to text format
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

        # Header
        lines.extend(self._format_header(data))

        # Contact
        if data.get("contact"):
            lines.extend(self._format_contact(data["contact"]))

        # Summary
        if data.get("summary"):
            lines.extend(self._format_summary(data["summary"]))

        # Experience
        if data.get("experience"):
            lines.extend(self._format_experience(data["experience"]))

        # Skills
        if data.get("skills"):
            lines.extend(self._format_skills(data["skills"]))

        # Education
        if data.get("education"):
            lines.extend(self._format_education(data["education"]))

        # Projects
        if data.get("projects"):
            lines.extend(self._format_projects(data["projects"]))

        # Certifications
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
    """Encapsulates resume data, system prompt, and token count.

    This class holds all resume-related data needed for chat processing,
    computed once at startup to avoid redundant work per request.
    """

    system_prompt: str
    system_prompt_tokens: int

    @classmethod
    def from_file(
        cls, path: str | Path, token_counter: TokenCounter
    ) -> "ResumeContext":
        """Create a ResumeContext from a resume file.

        Args:
            path: Path to the resume JSON file
            token_counter: TokenCounter instance for counting tokens

        Returns:
            ResumeContext with loaded resume, built system prompt, and token count

        Raises:
            ResumeLoadError: If resume cannot be loaded
        """
        loader = create_resume_loader(path)
        resume_text = loader.get_resume_text()
        system_prompt = build_system_prompt(resume_text)
        system_prompt_tokens = token_counter.count_tokens(system_prompt)

        logger.info(f"Built system prompt ({system_prompt_tokens} tokens)")

        return cls(
            system_prompt=system_prompt,
            system_prompt_tokens=system_prompt_tokens,
        )

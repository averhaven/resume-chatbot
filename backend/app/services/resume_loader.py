"""Resume loader service for loading and formatting resume data."""

import json
from pathlib import Path
from typing import Any

from app.core.logger import get_logger

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
            with open(self.resume_path, "r", encoding="utf-8") as f:
                self._resume_data = json.load(f)
            logger.info(f"Successfully loaded resume from {self.resume_path}")
        except json.JSONDecodeError as e:
            raise ResumeLoadError(f"Invalid JSON in resume file: {e}")
        except Exception as e:
            raise ResumeLoadError(f"Failed to load resume: {e}")

        # Convert to text format
        self._resume_text = self._format_resume_as_text(self._resume_data)

    def _format_resume_as_text(self, data: dict[str, Any]) -> str:
        """Format resume data as human-readable text for LLM prompts.

        Args:
            data: Resume data dictionary

        Returns:
            Formatted resume text
        """
        lines = []

        # Header
        lines.append(f"# {data.get('name', 'N/A')}")
        lines.append(f"## {data.get('title', 'N/A')}")
        lines.append("")

        # Contact
        contact = data.get("contact", {})
        lines.append("### Contact Information")
        lines.append(f"- Email: {contact.get('email', 'N/A')}")
        lines.append(f"- Phone: {contact.get('phone', 'N/A')}")
        lines.append(f"- Location: {contact.get('location', 'N/A')}")
        if contact.get("linkedin"):
            lines.append(f"- LinkedIn: {contact['linkedin']}")
        if contact.get("github"):
            lines.append(f"- GitHub: {contact['github']}")
        lines.append("")

        # Summary
        if data.get("summary"):
            lines.append("### Professional Summary")
            lines.append(data["summary"])
            lines.append("")

        # Experience
        if data.get("experience"):
            lines.append("### Work Experience")
            for exp in data["experience"]:
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

        # Skills
        if data.get("skills"):
            lines.append("### Skills")
            skills = data["skills"]
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

        # Education
        if data.get("education"):
            lines.append("### Education")
            for edu in data["education"]:
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

        # Projects
        if data.get("projects"):
            lines.append("### Notable Projects")
            for proj in data["projects"]:
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

        # Certifications
        if data.get("certifications"):
            lines.append("### Certifications")
            for cert in data["certifications"]:
                name = cert.get("name", "N/A")
                issuer = cert.get("issuer", "N/A")
                date = cert.get("date", "N/A")
                lines.append(f"- {name} - {issuer} ({date})")
            lines.append("")

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

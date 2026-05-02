from __future__ import annotations

import re


ROLE_SKILLS = {
    "Backend Developer": {
        "description": "Builds APIs, business logic, and database-backed services.",
        "skills": ["python", "django", "fastapi", "sql", "postgresql", "rest api", "git", "docker"],
    },
    "Frontend Developer": {
        "description": "Creates responsive user interfaces and client-side applications.",
        "skills": ["html", "css", "javascript", "typescript", "react", "git", "figma"],
    },
    "Full Stack Developer": {
        "description": "Works across frontend, backend, and deployment workflows.",
        "skills": ["python", "django", "html", "css", "javascript", "react", "sql", "git", "docker"],
    },
    "Data Analyst": {
        "description": "Analyzes data sets and communicates insights through reports and dashboards.",
        "skills": ["python", "sql", "excel", "power bi", "tableau", "pandas", "numpy", "matplotlib"],
    },
    "Data Scientist": {
        "description": "Builds statistical and machine learning models from structured data.",
        "skills": ["python", "pandas", "numpy", "machine learning", "scikit-learn", "sql", "matplotlib"],
    },
    "Machine Learning Engineer": {
        "description": "Deploys and maintains machine learning systems in production.",
        "skills": ["python", "machine learning", "tensorflow", "pytorch", "docker", "aws", "git"],
    },
    "DevOps Engineer": {
        "description": "Automates infrastructure, CI/CD pipelines, and deployment operations.",
        "skills": ["docker", "kubernetes", "aws", "linux", "jenkins", "ci/cd", "git"],
    },
    "Cloud Engineer": {
        "description": "Designs and manages cloud infrastructure and platform services.",
        "skills": ["aws", "azure", "gcp", "docker", "linux", "terraform", "git"],
    },
    "QA Engineer": {
        "description": "Builds and runs testing workflows to ensure software quality.",
        "skills": ["selenium", "pytest", "postman", "jira", "git", "sql"],
    },
    "Mobile App Developer": {
        "description": "Builds mobile applications and integrates them with backend services.",
        "skills": ["java", "kotlin", "swift", "rest api", "git", "firebase"],
    },
    "Business Analyst": {
        "description": "Bridges business requirements with product and technical teams.",
        "skills": ["excel", "power bi", "sql", "communication", "jira", "problem solving"],
    },
    "UI/UX Designer": {
        "description": "Designs user flows, wireframes, and product interfaces.",
        "skills": ["figma", "html", "css", "communication", "problem solving"],
    },
    "Accountant": {
        "description": "Handles bookkeeping, tax records, and financial reporting.",
        "skills": ["tally", "excel", "gst", "bookkeeping", "accounting", "bank reconciliation", "invoice processing"],
    },
    "Tally Operator": {
        "description": "Maintains day-to-day accounting entries and reports in Tally.",
        "skills": ["tally", "excel", "data entry", "gst", "invoice processing", "accounting"],
    },
    "Chef": {
        "description": "Plans and prepares food while maintaining kitchen standards and hygiene.",
        "skills": ["food preparation", "menu planning", "hygiene", "inventory management", "team leadership", "customer service"],
    },
    "Restaurant Manager": {
        "description": "Oversees restaurant operations, staff coordination, and guest satisfaction.",
        "skills": ["customer service", "inventory management", "team leadership", "cash handling", "communication", "problem solving"],
    },
    "Sales Executive": {
        "description": "Drives sales through lead generation, relationship building, and follow-ups.",
        "skills": ["sales", "lead generation", "negotiation", "communication", "crm", "customer service"],
    },
    "HR Executive": {
        "description": "Supports recruitment, onboarding, and employee coordination activities.",
        "skills": ["recruitment", "onboarding", "communication", "ms office", "problem solving", "employee relations"],
    },
    "Customer Support Executive": {
        "description": "Assists customers, resolves issues, and maintains service quality.",
        "skills": ["customer service", "communication", "problem solving", "crm", "ticketing", "ms office"],
    },
    "Graphic Designer": {
        "description": "Creates visual assets for print, digital, and marketing campaigns.",
        "skills": ["photoshop", "illustrator", "canva", "figma", "creativity", "communication"],
    },
    "Digital Marketing Executive": {
        "description": "Runs digital campaigns across search, social media, and analytics platforms.",
        "skills": ["seo", "social media marketing", "google ads", "content writing", "canva", "analytics"],
    },
    "Office Administrator": {
        "description": "Coordinates office records, schedules, reporting, and operational support.",
        "skills": ["ms office", "excel", "communication", "data entry", "reporting", "problem solving"],
    },
    "Receptionist": {
        "description": "Manages front desk operations, visitors, calls, and scheduling.",
        "skills": ["communication", "customer service", "ms office", "scheduling", "cash handling"],
    },
    "Data Entry Operator": {
        "description": "Enters and maintains records accurately across digital systems.",
        "skills": ["data entry", "excel", "ms office", "typing", "accuracy", "reporting"],
    },
}


COLLABORATION_SKILLS = {
    "agile": (r"\bagile\b", r"\bscrum\b"),
    "project management": (r"\bproject management\b",),
    "leadership": (r"\bleadership\b", r"\blead\b"),
    "communication": (r"\bcommunication\b", r"\bpresentation\b"),
    "problem solving": (r"\bproblem solving\b", r"\btroubleshooting\b"),
    "teamwork": (r"\bteamwork\b", r"\bcross-functional\b", r"\bcollaboration\b"),
}


def skill_pattern(skill: str) -> tuple[str, ...]:
    aliases = {
        "aws": (r"\baws\b", r"\bamazon web services\b"),
        "ci/cd": (r"\bci/cd\b", r"\bcontinuous integration\b", r"\bcontinuous deployment\b"),
        "gcp": (r"\bgcp\b", r"\bgoogle cloud\b"),
        "git": (r"\bgit\b", r"\bgithub\b", r"\bgitlab\b"),
        "gst": (r"\bgst\b", r"\bgoods and services tax\b"),
        "ms office": (r"\bms office\b", r"\bmicrosoft office\b"),
        "postgresql": (r"\bpostgres(?:ql)?\b",),
        "power bi": (r"\bpower\s+bi\b",),
        "rest api": (r"\brest(?:ful)?\s+api\b", r"\bapi integration\b", r"\bapi development\b"),
        "scikit-learn": (r"\bscikit-learn\b", r"\bsklearn\b"),
        "tally erp": (r"\btally\s+erp\b", r"\btally\.erp\b"),
        "tally prime": (r"\btally\s+prime\b",),
        "tds": (r"\btds\b", r"\btax deducted at source\b"),
    }
    if skill in COLLABORATION_SKILLS:
        return COLLABORATION_SKILLS[skill]
    if skill in aliases:
        return aliases[skill]
    return (rf"\b{re.escape(skill)}\b",)


def build_skill_library() -> dict[str, dict[str, tuple[str, ...]]]:
    role_skills = {skill for details in ROLE_SKILLS.values() for skill in details["skills"]}
    role_skills.update(COLLABORATION_SKILLS)
    return {
        "Role Skills": {
            skill: skill_pattern(skill)
            for skill in sorted(role_skills)
        }
    }


SKILL_LIBRARY = build_skill_library()

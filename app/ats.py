import re
import uuid
import json
from datetime import datetime
from pypdf import PdfReader
from io import BytesIO
from typing import Dict, Any, List

KNOWN_SKILLS = [
    "python", "fastapi", "django", "flask", "typescript", "javascript", "react", "next.js",
    "vue", "angular", "node.js", "express", "postgresql", "mysql", "mongodb", "redis",
    "docker", "kubernetes", "terraform", "aws", "gcp", "azure", "oracle cloud", "oci",
    "qa", "qa automation", "cypress", "playwright", "selenium", "jest", "postman", "testrail",
    "ci/cd", "github actions", "git", "rest apis", "graphql", "stripe", "spei", "jwt", "tailwind",
    "linux", "nginx", "prometheus", "figma"
]

def parse_cv_pdf(file_bytes: bytes, filename: str) -> Dict[str, Any]:
    reader = PdfReader(BytesIO(file_bytes))
    full_text = ""
    for page in reader.pages:
        txt = page.extract_text()
        if txt:
            full_text += txt + "\n"

    # Extract Name (usually the first strong heading line)
    lines = [l.strip() for l in full_text.split("\n") if l.strip()]
    name = "Candidato Desconocido"
    if lines:
        first_line = lines[0]
        # Remove labels like CV, Resume
        clean_first = re.sub(r'(?i)(curriculum|vitae|resume|cv)\s*:?', '', first_line).strip()
        if len(clean_first) > 2:
            name = clean_first

    # Extract Seniority
    seniority = "Mid"
    text_lower = full_text.lower()
    if "senior" in text_lower or "lead" in text_lower or "arquitect" in text_lower or "5 años" in text_lower or "6 años" in text_lower or "7 años" in text_lower:
        seniority = "Senior"
    elif "junior" in text_lower or "trainee" in text_lower or "practicante" in text_lower or "1 año" in text_lower:
        seniority = "Junior"

    # Extract Primary Role
    role = "Software Engineer"
    if "fullstack" in text_lower or "full-stack" in text_lower:
        role = "Fullstack Developer"
    elif "frontend" in text_lower or "front-end" in text_lower or "ui developer" in text_lower:
        role = "Frontend Developer"
    elif "backend" in text_lower or "back-end" in text_lower or "api developer" in text_lower:
        role = "Backend Developer"
    elif "qa" in text_lower or "quality assurance" in text_lower or "automation" in text_lower or "tester" in text_lower:
        role = "QA Automation Engineer"
    elif "devops" in text_lower or "cloud" in text_lower or "sre" in text_lower or "sysadmin" in text_lower:
        role = "DevOps & Cloud Engineer"

    # Extract matching skills
    detected_skills = []
    for skill in KNOWN_SKILLS:
        pattern = r'\b' + re.escape(skill) + r'\b'
        if re.search(pattern, text_lower):
            # Prettify skill name
            detected_skills.append(skill.title() if len(skill) > 3 else skill.upper())

    if not detected_skills:
        detected_skills = ["Software Development", "Problem Solving", "Git"]

    # Productivity factor calculation
    prod_factor = 1.0
    if seniority == "Senior":
        prod_factor = 1.35
    elif seniority == "Junior":
        prod_factor = 0.75
    else:
        prod_factor = 1.0

    return {
        "name": name,
        "role": role,
        "seniority": seniority,
        "skills": detected_skills,
        "productivity_factor": prod_factor,
        "raw_text_summary": full_text[:400]
    }

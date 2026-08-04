SECTION_KEYWORDS: dict[str, list[str]] = {
    "experience": ["expérience", "experience", "parcours professionnel", "work history"],
    "education": ["formation", "education", "études", "academic background"],
    "skills": ["compétences", "skills", "competencies"],
}


def detect_sections(text: str) -> set[str]:
    lowered = text.lower()
    detected = set()
    for section, keywords in SECTION_KEYWORDS.items():
        if any(keyword in lowered for keyword in keywords):
            detected.add(section)
    return detected

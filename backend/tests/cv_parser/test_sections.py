from app.cv_parser.sections import detect_sections


def test_detects_french_sections():
    text = "Expérience professionnelle\n...\nFormation\n...\nCompétences\n..."
    assert detect_sections(text) == {"experience", "education", "skills"}


def test_detects_english_sections():
    text = "Work History\n...\nEducation\n...\nSkills\n..."
    assert detect_sections(text) == {"experience", "education", "skills"}


def test_missing_sections_not_detected():
    text = "Just a paragraph with no headers at all."
    assert detect_sections(text) == set()

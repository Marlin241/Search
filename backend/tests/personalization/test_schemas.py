from app.personalization.schemas import CoverLetter


def test_cover_letter_strips_literal_backslash_n_before_closing_formula():
    letter = CoverLetter(
        greeting="Madame, Monsieur,",
        body_paragraphs=["Je vous écris pour candidater à ce poste.\\n\\n"],
        closing_formula="Cordialement,",
        signature="Guy Roland Mombo Ndinga",
    )

    assert "\\n" not in letter.body_paragraphs[0]
    assert letter.body_paragraphs[0] == "Je vous écris pour candidater à ce poste."


def test_cover_letter_strips_literal_backslash_n_from_every_text_field():
    letter = CoverLetter(
        greeting="Madame, Monsieur,\\n",
        body_paragraphs=["Paragraphe.\\n"],
        closing_formula="\\nCordialement,",
        signature="Jane Doe\\n",
    )

    assert letter.greeting == "Madame, Monsieur,"
    assert letter.body_paragraphs == ["Paragraphe."]
    assert letter.closing_formula == "Cordialement,"
    assert letter.signature == "Jane Doe"


def test_cover_letter_collapses_stray_whitespace_left_by_the_cleanup():
    letter = CoverLetter(
        greeting="Madame, Monsieur,",
        body_paragraphs=["Première phrase.\\n\\nDeuxième phrase."],
        closing_formula="Cordialement,",
        signature="Jane Doe",
    )

    assert letter.body_paragraphs == ["Première phrase. Deuxième phrase."]


def test_cover_letter_leaves_clean_text_unchanged():
    letter = CoverLetter(
        greeting="Madame, Monsieur,",
        body_paragraphs=["Je vous écris pour candidater à ce poste."],
        closing_formula="Cordialement,",
        signature="Jane Doe",
    )

    assert letter.greeting == "Madame, Monsieur,"
    assert letter.body_paragraphs == ["Je vous écris pour candidater à ce poste."]
    assert letter.closing_formula == "Cordialement,"
    assert letter.signature == "Jane Doe"

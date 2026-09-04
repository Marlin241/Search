from app.notifications.email_layout import html_to_text, render_email


def test_html_to_text_keeps_link_urls():
    text = html_to_text('<p>Clique <a href="https://example.com/reset">ici</a>.</p>')
    assert "ici (https://example.com/reset)" in text


def test_html_to_text_drops_unsafe_link_marker_without_url():
    # safe_href() neutralise les schémas dangereux en "#" - html_to_text ne
    # doit pas republier ce "#" comme s'il s'agissait d'une vraie URL.
    text = html_to_text('<p><a href="#">lien</a></p>')
    assert "#" not in text
    assert "lien" in text


def test_html_to_text_strips_tags_and_collapses_blank_lines():
    html_body = "<p>Bonjour</p><p>  </p><ul><li>Un</li><li>Deux</li></ul>"
    text = html_to_text(html_body)
    assert text == "Bonjour\n\nUn\n\nDeux"


def test_html_to_text_unescapes_entities():
    text = html_to_text("<p>Candidature &amp; entretien</p>")
    assert text == "Candidature & entretien"


def test_html_to_text_drops_head_and_style_blocks():
    html_body = (
        "<html><head><title>t</title><style>p{color:red}</style></head>"
        "<body><p>Contenu</p></body></html>"
    )
    text = html_to_text(html_body)
    assert text == "Contenu"


def test_render_email_produces_a_non_empty_text_alternative():
    body = render_email(
        heading="Titre",
        paragraphs=["Un paragraphe.", '<a href="https://example.com">Lien</a>'],
        cta=("Action", "https://example.com/cta"),
        context_line="Contexte.",
    )
    text = html_to_text(body)
    assert "Titre" in text
    assert "Un paragraphe." in text
    assert "Lien (https://example.com)" in text
    assert "Action (https://example.com/cta)" in text

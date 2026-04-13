from app.services.rag_service import _sanitize_output_text


def test_sanitize_output_text_removes_bullets_and_limits_sentences() -> None:
    raw_text = (
        "- Para este tramite puedes acercarte a la dependencia responsable.\n"
        "- Presenta los documentos requeridos segun el contexto.\n"
        "- Valida en la fuente oficial.\n"
    )

    cleaned = _sanitize_output_text(raw_text, total_tramites=1)

    assert cleaned.startswith("Para este tramite")
    assert "- " not in cleaned
    assert cleaned.count(".") <= 2


def test_sanitize_output_text_removes_related_section_marker() -> None:
    raw_text = (
        "Orientacion inicial sobre el tramite principal.\n\n"
        "Tambien pueden interesarte:\n"
        "- Otro tramite"
    )

    cleaned = _sanitize_output_text(raw_text, total_tramites=2)

    assert "Tambien pueden interesarte" not in cleaned
    assert "Otro tramite" not in cleaned

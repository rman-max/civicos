from civicos_ingestion.extractors import document_type_for, extract_csv, extract_document


def test_detects_supported_types_from_content_type_or_extension() -> None:
    assert document_type_for("application/pdf", "https://city.example/agenda") == "pdf"
    assert document_type_for("application/octet-stream", "https://city.example/budget.csv") == "csv"
    assert document_type_for("text/plain", "https://city.example/readme.txt") is None


def test_extracts_html_title_text_and_links() -> None:
    document = extract_document(
        media_type="text/html",
        url="https://city.example/council",
        body=b"<html><title>Council Agenda</title><body>July meeting <a href='/agenda.pdf'>PDF</a></body></html>",
    )

    assert document.title == "Council Agenda"
    assert document.text == "Council Agenda July meeting PDF"
    assert document.metadata["links"] == ["/agenda.pdf"]


def test_extracts_csv_rows() -> None:
    assert extract_csv(b"project,amount\nPark,1000\n") == "project | amount\nPark | 1000"

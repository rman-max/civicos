from __future__ import annotations

import csv
import io
import re
from html.parser import HTMLParser
from pathlib import PurePosixPath
from urllib.parse import unquote, urlsplit
from zipfile import ZipFile

from defusedxml import ElementTree as element_tree
from pypdf import PdfReader

from civicos_ingestion.models import ExtractedDocument

SUPPORTED_MEDIA_TYPES = {
    "text/html",
    "application/pdf",
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    "text/csv",
}


class _HtmlDocumentParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.links: list[str] = []
        self._title_depth = 0
        self._title: list[str] = []
        self._text: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag == "title":
            self._title_depth += 1
        if tag == "a":
            href = dict(attrs).get("href")
            if href:
                self.links.append(href)

    def handle_endtag(self, tag: str) -> None:
        if tag == "title" and self._title_depth:
            self._title_depth -= 1

    def handle_data(self, data: str) -> None:
        self._text.append(data)
        if self._title_depth:
            self._title.append(data)

    @property
    def title(self) -> str:
        return normalize_text(" ".join(self._title))

    @property
    def text(self) -> str:
        return normalize_text(" ".join(self._text))


def normalize_text(value: str) -> str:
    return re.sub(r"\s+", " ", value).strip()


def file_name_from_url(url: str) -> str:
    name = PurePosixPath(unquote(urlsplit(url).path)).name
    return name or urlsplit(url).netloc


def document_type_for(media_type: str, url: str) -> str | None:
    normalized_media_type = media_type.split(";", 1)[0].strip().lower()
    suffix = PurePosixPath(urlsplit(url).path).suffix.lower()
    if normalized_media_type == "text/html" or suffix in {".html", ".htm"}:
        return "html"
    if normalized_media_type == "application/pdf" or suffix == ".pdf":
        return "pdf"
    if (
        normalized_media_type == "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
        or suffix == ".docx"
    ):
        return "docx"
    if normalized_media_type in {"text/csv", "application/csv"} or suffix == ".csv":
        return "csv"
    return None


def extract_document(*, media_type: str, url: str, body: bytes) -> ExtractedDocument:
    document_type = document_type_for(media_type, url)
    if document_type is None:
        raise ValueError(f"Unsupported document type for {url}")
    if document_type == "html":
        parser = _HtmlDocumentParser()
        parser.feed(body.decode("utf-8", errors="replace"))
        return ExtractedDocument(
            title=parser.title or file_name_from_url(url),
            document_type=document_type,
            text=parser.text,
            metadata={"links": parser.links},
        )
    if document_type == "pdf":
        return ExtractedDocument(
            title=file_name_from_url(url),
            document_type=document_type,
            text=extract_pdf(body),
            metadata={},
        )
    if document_type == "docx":
        return ExtractedDocument(
            title=file_name_from_url(url),
            document_type=document_type,
            text=extract_docx(body),
            metadata={},
        )
    return ExtractedDocument(
        title=file_name_from_url(url),
        document_type=document_type,
        text=extract_csv(body),
        metadata={},
    )


def extract_pdf(body: bytes) -> str:
    reader = PdfReader(io.BytesIO(body))
    return normalize_text("\n".join(page.extract_text() or "" for page in reader.pages))


def extract_docx(body: bytes) -> str:
    namespace = "{http://schemas.openxmlformats.org/wordprocessingml/2006/main}t"
    with ZipFile(io.BytesIO(body)) as archive:
        document_xml = archive.read("word/document.xml")
    root = element_tree.fromstring(document_xml)
    return normalize_text(" ".join(node.text or "" for node in root.iter(namespace)))


def extract_csv(body: bytes) -> str:
    decoded = body.decode("utf-8-sig", errors="replace")
    rows = csv.reader(io.StringIO(decoded))
    return "\n".join(" | ".join(normalize_text(cell) for cell in row) for row in rows)

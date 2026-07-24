import asyncio
from uuid import UUID

import httpx

from civicos_ingestion.crawler import CivicCrawler, allowed_path, allowed_url, normalized_url
from civicos_ingestion.models import Source


def test_allowed_url_rejects_off_domain_and_credentialed_urls() -> None:
    domains = {"stjoe.gov"}
    assert allowed_url("https://meetings.stjoe.gov/agenda.pdf", domains)
    assert not allowed_url("https://stjoe.gov.attacker.example/agenda.pdf", domains)
    assert not allowed_url("https://user:pass@stjoe.gov/agenda.pdf", domains)
    assert not allowed_url("file:///tmp/agenda.pdf", domains)


def test_normalized_url_drops_fragment() -> None:
    assert normalized_url("https://stjoe.gov/a#section") == "https://stjoe.gov/a"


def test_allowed_path_accepts_configured_path_prefixes_only() -> None:
    prefixes = {"/AgendaCenter/County-Council-4", "/AgendaCenter/ViewFile"}
    assert allowed_path("https://stjoe.gov/AgendaCenter/County-Council-4", prefixes)
    assert allowed_path("https://stjoe.gov/AgendaCenter/ViewFile/Agenda/_01062026-2426", prefixes)
    assert not allowed_path("https://stjoe.gov/Departments/Assessor", prefixes)


def test_crawler_follows_only_allowed_links_and_supported_documents() -> None:
    source = Source(
        id=UUID("00000000-0000-0000-0000-000000000001"),
        organization_id=UUID("00000000-0000-0000-0000-000000000002"),
        name="Official records",
        canonical_url="https://records.example.test/",
        acquisition_policy={"respect_robots": True},
        scan_interval_seconds=3600,
        max_pages_per_scan=10,
        request_timeout_seconds=5,
    )

    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/robots.txt":
            return httpx.Response(200, text="User-agent: *\nAllow: /")
        if request.url.path == "/":
            return httpx.Response(
                200,
                headers={"content-type": "text/html"},
                text='<a href="agenda.pdf">Agenda</a><a href="https://elsewhere.test/x">Offsite</a>',
            )
        if request.url.path == "/agenda.pdf":
            return httpx.Response(200, headers={"content-type": "application/pdf"}, content=b"%PDF-1.4")
        raise AssertionError(f"Unexpected request: {request.url}")

    crawler = CivicCrawler(user_agent="CivicOS test", transport=httpx.MockTransport(handler))
    result = asyncio.run(crawler.crawl(source))

    assert result.pages_crawled == 2
    assert [resource.final_url for resource in result.resources] == [
        "https://records.example.test/",
        "https://records.example.test/agenda.pdf",
    ]


def test_crawler_honors_source_path_scope() -> None:
    source = Source(
        id=UUID("00000000-0000-0000-0000-000000000003"),
        organization_id=UUID("00000000-0000-0000-0000-000000000004"),
        name="County Council records",
        canonical_url="https://records.example.test/AgendaCenter/County-Council-4",
        acquisition_policy={
            "respect_robots": True,
            "allowed_path_prefixes": ["/AgendaCenter/County-Council-4", "/AgendaCenter/ViewFile"],
        },
        scan_interval_seconds=3600,
        max_pages_per_scan=10,
        request_timeout_seconds=5,
    )

    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/robots.txt":
            return httpx.Response(200, text="User-agent: *\nAllow: /")
        if request.url.path == "/AgendaCenter/County-Council-4":
            return httpx.Response(
                200,
                headers={"content-type": "text/html"},
                text=(
                    '<a href="/AgendaCenter/ViewFile/Agenda/_01062026-2426">Agenda</a>'
                    '<a href="/Departments/Assessor">Out of scope</a>'
                ),
            )
        if request.url.path == "/AgendaCenter/ViewFile/Agenda/_01062026-2426":
            return httpx.Response(200, headers={"content-type": "application/pdf"}, content=b"%PDF-1.4")
        raise AssertionError(f"Unexpected request: {request.url}")

    crawler = CivicCrawler(user_agent="CivicOS test", transport=httpx.MockTransport(handler))
    result = asyncio.run(crawler.crawl(source))

    assert result.pages_crawled == 2
    assert [resource.final_url for resource in result.resources] == [
        "https://records.example.test/AgendaCenter/County-Council-4",
        "https://records.example.test/AgendaCenter/ViewFile/Agenda/_01062026-2426",
    ]

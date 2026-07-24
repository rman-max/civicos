from __future__ import annotations

from collections import deque
from dataclasses import dataclass
from hashlib import sha256
from urllib.parse import urldefrag, urljoin, urlsplit
from urllib.robotparser import RobotFileParser

import httpx

from civicos_ingestion.extractors import _HtmlDocumentParser, document_type_for
from civicos_ingestion.models import FetchedResource, Source


@dataclass(frozen=True)
class CrawlResult:
    resources: list[FetchedResource]
    pages_crawled: int


def normalized_url(url: str) -> str:
    clean_url, _ = urldefrag(url)
    parts = urlsplit(clean_url)
    return parts._replace(fragment="").geturl()


def allowed_url(url: str, allowed_domains: set[str]) -> bool:
    parts = urlsplit(url)
    if parts.scheme not in {"http", "https"} or not parts.hostname:
        return False
    if parts.username or parts.password:
        return False
    host = parts.hostname.lower().rstrip(".")
    return any(host == domain or host.endswith(f".{domain}") for domain in allowed_domains)


def allowed_path(url: str, allowed_path_prefixes: set[str]) -> bool:
    """Return whether a URL path is within an administrator-approved scope."""
    path = urlsplit(url).path or "/"
    for prefix in allowed_path_prefixes:
        normalized_prefix = prefix.rstrip("/") or "/"
        if normalized_prefix == "/" or path == normalized_prefix or path.startswith(f"{normalized_prefix}/"):
            return True
    return False


class CivicCrawler:
    """A bounded crawler for administrator-approved government source domains."""

    def __init__(
        self,
        *,
        user_agent: str,
        max_content_bytes: int = 25_000_000,
        transport: httpx.AsyncBaseTransport | None = None,
    ) -> None:
        self._user_agent = user_agent
        self._max_content_bytes = max_content_bytes
        self._transport = transport
        self._robots: dict[str, RobotFileParser] = {}

    async def crawl(self, source: Source) -> CrawlResult:
        policy = source.acquisition_policy
        initial_url = normalized_url(source.canonical_url)
        canonical_host = urlsplit(initial_url).hostname
        if canonical_host is None:
            raise ValueError(f"Source {source.id} has no canonical host")
        policy_domains = policy.get("allowed_domains", [])
        if not isinstance(policy_domains, list) or not all(isinstance(domain, str) for domain in policy_domains):
            raise ValueError("acquisition_policy.allowed_domains must be a string array")
        allowed_domains = {canonical_host.lower().rstrip(".")}
        allowed_domains.update(domain.lower().rstrip(".") for domain in policy_domains)
        policy_path_prefixes = policy.get("allowed_path_prefixes", ["/"])
        if not isinstance(policy_path_prefixes, list) or not all(
            isinstance(prefix, str) and prefix.startswith("/") for prefix in policy_path_prefixes
        ):
            raise ValueError("acquisition_policy.allowed_path_prefixes must be an array of absolute paths")
        allowed_path_prefixes = set(policy_path_prefixes)
        if not allowed_path(initial_url, allowed_path_prefixes):
            raise ValueError("Source canonical_url is outside acquisition_policy.allowed_path_prefixes")
        max_content_bytes = policy.get("max_content_bytes", self._max_content_bytes)
        if not isinstance(max_content_bytes, int) or not 1 <= max_content_bytes <= self._max_content_bytes:
            raise ValueError("acquisition_policy.max_content_bytes is outside the permitted range")
        respect_robots = policy.get("respect_robots", True)
        if not isinstance(respect_robots, bool):
            raise ValueError("acquisition_policy.respect_robots must be a boolean")

        queue: deque[str] = deque([initial_url])
        visited: set[str] = set()
        resources: list[FetchedResource] = []
        pages_crawled = 0
        timeout = httpx.Timeout(source.request_timeout_seconds)
        headers = {
            "User-Agent": self._user_agent,
            "Accept": (
                "text/html,application/pdf,"
                "application/vnd.openxmlformats-officedocument.wordprocessingml.document,"
                "text/csv;q=0.9,*/*;q=0.1"
            ),
        }

        async with httpx.AsyncClient(
            timeout=timeout,
            follow_redirects=True,
            headers=headers,
            transport=self._transport,
        ) as client:
            while queue and pages_crawled < source.max_pages_per_scan:
                candidate = queue.popleft()
                if (
                    candidate in visited
                    or not allowed_url(candidate, allowed_domains)
                    or not allowed_path(candidate, allowed_path_prefixes)
                ):
                    continue
                visited.add(candidate)
                if respect_robots and not await self._allowed_by_robots(client, candidate):
                    continue
                resource = await self._fetch_resource(
                    client=client,
                    candidate=candidate,
                    allowed_domains=allowed_domains,
                    allowed_path_prefixes=allowed_path_prefixes,
                    max_content_bytes=max_content_bytes,
                )
                pages_crawled += 1
                if resource is None:
                    continue
                resources.append(resource)
                if document_type_for(resource.media_type, resource.final_url) == "html":
                    parser = _HtmlDocumentParser()
                    parser.feed(resource.body.decode("utf-8", errors="replace"))
                    for href in parser.links:
                        next_url = normalized_url(urljoin(resource.final_url, href))
                        if (
                            next_url not in visited
                            and allowed_url(next_url, allowed_domains)
                            and allowed_path(next_url, allowed_path_prefixes)
                        ):
                            queue.append(next_url)
        return CrawlResult(resources=resources, pages_crawled=pages_crawled)

    async def _fetch_resource(
        self,
        *,
        client: httpx.AsyncClient,
        candidate: str,
        allowed_domains: set[str],
        allowed_path_prefixes: set[str],
        max_content_bytes: int,
    ) -> FetchedResource | None:
        async with client.stream("GET", candidate) as response:
            final_url = normalized_url(str(response.url))
            if not allowed_url(final_url, allowed_domains) or not allowed_path(final_url, allowed_path_prefixes):
                return None
            if response.status_code < 200 or response.status_code >= 300:
                return None
            content_length = response.headers.get("content-length")
            if content_length is not None:
                try:
                    if int(content_length) > max_content_bytes:
                        return None
                except ValueError:
                    return None
            chunks: list[bytes] = []
            byte_count = 0
            async for chunk in response.aiter_bytes():
                byte_count += len(chunk)
                if byte_count > max_content_bytes:
                    return None
                chunks.append(chunk)
            media_type = response.headers.get("content-type", "").split(";", 1)[0].lower()
            media_type = media_type or "application/octet-stream"
            if document_type_for(media_type, final_url) is None:
                return None
            return FetchedResource(
                source_url=candidate,
                final_url=final_url,
                status_code=response.status_code,
                media_type=media_type,
                body=b"".join(chunks),
                etag=response.headers.get("etag"),
                last_modified=response.headers.get("last-modified"),
            )

    async def _allowed_by_robots(self, client: httpx.AsyncClient, url: str) -> bool:
        parts = urlsplit(url)
        origin = f"{parts.scheme}://{parts.netloc}"
        parser = self._robots.get(origin)
        if parser is None:
            parser = RobotFileParser()
            robots_url = f"{origin}/robots.txt"
            try:
                response = await client.get(robots_url)
                if response.status_code == 200:
                    parser.parse(response.text.splitlines())
                else:
                    parser.parse(["User-agent: *", "Allow: /"])
            except httpx.HTTPError:
                parser.parse(["User-agent: *", "Disallow: /"])
            self._robots[origin] = parser
        return parser.can_fetch(self._user_agent, url)


def content_hash(content: bytes) -> str:
    return sha256(content).hexdigest()

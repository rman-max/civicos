from __future__ import annotations

from typing import Any, Protocol

import httpx

from civicos_ingestion.models import VectorIndexJob


class VectorIndexer(Protocol):
    async def index(self, job: VectorIndexJob) -> None: ...


class OpenAICompatibleEmbeddingClient:
    def __init__(self, *, base_url: str, model: str, api_key: str | None, max_characters: int) -> None:
        self._base_url = base_url.rstrip("/")
        self._model = model
        self._api_key = api_key
        self._max_characters = max_characters

    async def embed(self, text: str) -> list[float]:
        headers = {"Authorization": f"Bearer {self._api_key}"} if self._api_key else {}
        payload = {"model": self._model, "input": text[: self._max_characters]}
        async with httpx.AsyncClient(timeout=30) as client:
            response = await client.post(f"{self._base_url}/embeddings", headers=headers, json=payload)
        response.raise_for_status()
        data = response.json()
        embedding = data["data"][0]["embedding"]
        if not isinstance(embedding, list) or not all(isinstance(value, int | float) for value in embedding):
            raise ValueError("Embedding provider returned an invalid vector")
        return [float(value) for value in embedding]


class QdrantVectorIndexer:
    def __init__(
        self,
        *,
        qdrant_url: str,
        collection: str,
        api_key: str | None,
        embedding_client: OpenAICompatibleEmbeddingClient,
    ) -> None:
        self._qdrant_url = qdrant_url.rstrip("/")
        self._collection = collection
        self._api_key = api_key
        self._embedding_client = embedding_client

    async def index(self, job: VectorIndexJob) -> None:
        text = f"{job.title}\n\n{job.extracted_text}"
        vector = await self._embedding_client.embed(text)
        headers = {"api-key": self._api_key} if self._api_key else {}
        async with httpx.AsyncClient(timeout=30) as client:
            await self._ensure_collection(client, headers=headers, vector_size=len(vector))
            response = await client.put(
                f"{self._qdrant_url}/collections/{self._collection}/points?wait=true",
                headers=headers,
                json={"points": [{"id": str(job.document_id), "vector": vector, "payload": self._payload(job)}]},
            )
        response.raise_for_status()

    async def _ensure_collection(self, client: httpx.AsyncClient, *, headers: dict[str, str], vector_size: int) -> None:
        response = await client.get(f"{self._qdrant_url}/collections/{self._collection}", headers=headers)
        if response.status_code == 200:
            return
        if response.status_code != 404:
            response.raise_for_status()
        create_response = await client.put(
            f"{self._qdrant_url}/collections/{self._collection}",
            headers=headers,
            json={"vectors": {"size": vector_size, "distance": "Cosine"}},
        )
        if create_response.status_code not in {200, 409}:
            create_response.raise_for_status()

    @staticmethod
    def _payload(job: VectorIndexJob) -> dict[str, Any]:
        return {
            "organization_id": str(job.organization_id),
            "document_id": str(job.document_id),
            "document_version_id": str(job.document_version_id),
            "source_id": str(job.source_id) if job.source_id else None,
            "department_id": str(job.department_id) if job.department_id else None,
            "topic_ids": [str(topic_id) for topic_id in job.topic_ids],
            "document_type": job.document_type,
            "published_at": job.published_at.isoformat() if job.published_at else None,
        }

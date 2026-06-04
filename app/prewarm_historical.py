from __future__ import annotations

import asyncio

import httpx

from app.nhl_service import NhlApiService


async def _main() -> None:
    client = httpx.AsyncClient(
        follow_redirects=True,
        timeout=httpx.Timeout(30.0, connect=10.0),
        headers={"User-Agent": "nhl-builder-prewarm/1.0", "Accept": "application/json"},
    )
    service = NhlApiService(client)
    try:
        await service.initialize()
        await service.prewarm_missing()
    finally:
        await service.aclose()


if __name__ == "__main__":
    asyncio.run(_main())

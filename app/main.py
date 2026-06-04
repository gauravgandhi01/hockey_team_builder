from __future__ import annotations

import asyncio
import os
from contextlib import asynccontextmanager, suppress
from pathlib import Path

import httpx
from fastapi import Depends, FastAPI, HTTPException, Request
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from app.models import DrawRequest, GradeRequest
from app.nhl_service import NhlApiService

BASE_DIR = Path(__file__).resolve().parent
TEMPLATES = Jinja2Templates(directory=str(BASE_DIR / "templates"))


def create_app(service: NhlApiService | None = None, start_background_prewarm: bool = True) -> FastAPI:
    admin_path = os.getenv("LINECRAFT_ADMIN_PATH", "/_linecraft_admin")
    if not admin_path.startswith("/"):
        admin_path = f"/{admin_path}"
    admin_key = os.getenv("LINECRAFT_ADMIN_KEY")

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        prewarm_task: asyncio.Task[None] | None = None
        if service is not None:
            app.state.nhl_service = service
            await service.initialize()
            try:
                yield
            finally:
                await service.aclose()
            return

        client = httpx.AsyncClient(
            follow_redirects=True,
            timeout=httpx.Timeout(30.0, connect=10.0),
            headers={"User-Agent": "nhl-builder/2.0", "Accept": "application/json"},
        )
        created_service = NhlApiService(client)
        app.state.nhl_service = created_service
        await created_service.initialize()
        if start_background_prewarm:
            prewarm_task = asyncio.create_task(created_service.prewarm_missing())
        try:
            yield
        finally:
            if prewarm_task is not None:
                prewarm_task.cancel()
                with suppress(asyncio.CancelledError):
                    await prewarm_task
            await created_service.aclose()

    app = FastAPI(title="linecraft", lifespan=lifespan)
    app.mount("/static", StaticFiles(directory=str(BASE_DIR / "static")), name="static")

    def get_service(request: Request) -> NhlApiService:
        return request.app.state.nhl_service

    def require_admin_access(request: Request) -> str:
        if not admin_key:
            raise HTTPException(status_code=404, detail="Not found.")
        provided_key = request.query_params.get("key") or request.headers.get("X-Linecraft-Admin-Key")
        if provided_key != admin_key:
            raise HTTPException(status_code=404, detail="Not found.")
        return provided_key

    @app.get("/", response_class=HTMLResponse)
    async def index(request: Request) -> HTMLResponse:
        return TEMPLATES.TemplateResponse(
            request=request,
            name="index.html",
            context={},
        )

    @app.get(admin_path, response_class=HTMLResponse)
    async def admin_dashboard(
        request: Request,
        decade: str = "2010s",
        role: str = "C",
        key: str = Depends(require_admin_access),
        nhl_service: NhlApiService = Depends(get_service),
    ) -> HTMLResponse:
        snapshot = await nhl_service.get_admin_snapshot(decade, role)
        return TEMPLATES.TemplateResponse(
            request=request,
            name="admin.html",
            context={
                "admin_path": admin_path,
                "admin_key": key,
                "snapshot": snapshot,
                "decades": ["1980s", "1990s", "2000s", "2010s", "2020s"],
                "roles": ["C", "W", "D", "G"],
            },
        )

    @app.post("/api/game/draw")
    async def game_draw(payload: DrawRequest, nhl_service: NhlApiService = Depends(get_service)):
        return await nhl_service.get_random_draw(
            payload.openSlots,
            payload.excludeCandidateKeys,
            hard_mode=payload.hardMode,
            lock_franchise_abbrev=payload.lockFranchiseAbbrev,
            lock_decade=payload.lockDecade,
            exclude_pair_key=payload.excludePairKey,
        )

    @app.post("/api/game/grade")
    async def game_grade(payload: GradeRequest, nhl_service: NhlApiService = Depends(get_service)):
        return await nhl_service.grade_lineup(payload.lineup)

    return app


app = create_app()

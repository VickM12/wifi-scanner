from __future__ import annotations

from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, Header, HTTPException, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from .hub import hub
from .recording import SUGGESTED_LABELS


class ControlBody(BaseModel):
    running: bool | None = None
    demo: bool | None = None
    threshold: float | None = Field(default=None, ge=0.05, le=1.0)
    iface: str | None = None
    csi_port: int | None = Field(default=None, ge=1024, le=65535)
    sample_interval: float | None = Field(default=None, ge=0.05, le=2.0)
    baseline_window: float | None = Field(default=None, ge=2.0, le=60.0)
    motion_window: float | None = Field(default=None, ge=0.3, le=10.0)
    noise_floor: float | None = Field(default=None, ge=0.05, le=5.0)
    node_id: str | None = None
    hub_url: str | None = None
    share_token: str | None = None
    push_to_hub: bool | None = None


class CalibrateBody(BaseModel):
    action: str = Field(pattern="^(start|stop|reset)$")


class RecordBody(BaseModel):
    action: str = Field(pattern="^(start|stop)$")
    label: str = "empty_room"
    custom_label: str | None = None
    format: str = "csv"


class NodeIngestBody(BaseModel):
    token: str | None = None
    node: dict


@asynccontextmanager
async def lifespan(_app: FastAPI):
    await hub.start()
    try:
        yield
    finally:
        await hub.stop()


app = FastAPI(title="WiFi Radar", version="0.3.0", lifespan=lifespan)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/api/health")
def health() -> dict:
    snap = hub.snapshot()
    return {
        "ok": True,
        "status": snap.status,
        "error": snap.error,
        "settings": snap.settings,
        "csi_packets": hub.csi_hub.esp32.packets,
        "csi_status": snap.csi_status,
        "network": snap.network,
        "nodes": len(snap.nodes),
    }


@app.get("/api/aps")
def aps() -> dict:
    return hub.snapshot().to_dict()


@app.get("/api/interfaces")
def interfaces() -> dict:
    return {"interfaces": [i.to_dict() for i in hub.collector.list_interfaces()]}


@app.get("/api/labels")
def labels() -> dict:
    return {"labels": SUGGESTED_LABELS}


@app.get("/api/nodes")
def nodes() -> dict:
    snap = hub.snapshot()
    return {"nodes": snap.nodes, "network": snap.network}


@app.post("/api/control")
async def control(body: ControlBody) -> dict:
    await hub.apply_settings(**body.model_dump())
    return hub.settings_dict()


@app.post("/api/calibrate")
async def calibrate(body: CalibrateBody) -> dict:
    return await hub.calibrate(body.action)


@app.post("/api/record")
async def record(body: RecordBody) -> dict:
    label = body.label
    if label == "custom" and body.custom_label:
        label = body.custom_label
    return await hub.record(body.action, label=label, fmt=body.format)


@app.post("/api/nodes/ingest")
def ingest_node(
    body: NodeIngestBody,
    authorization: str | None = Header(default=None),
) -> dict:
    token = body.token
    if authorization and authorization.lower().startswith("bearer "):
        token = authorization.split(" ", 1)[1]
    try:
        stored = hub.ingest_node(body.node, token=token)
    except PermissionError as exc:
        raise HTTPException(status_code=401, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return {"ok": True, "id": stored["id"]}


@app.websocket("/ws/live")
async def live(ws: WebSocket) -> None:
    await hub.register(ws)
    try:
        while True:
            await ws.receive_text()
    except WebSocketDisconnect:
        hub.unregister(ws)
    except Exception:
        hub.unregister(ws)


dist = Path(__file__).resolve().parents[2] / "frontend" / "dist"
if dist.is_dir():
    app.mount("/", StaticFiles(directory=str(dist), html=True), name="ui")

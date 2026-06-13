import asyncio
import json
from typing import List, Optional

from fastapi import Depends, FastAPI, Header, HTTPException, WebSocket, WebSocketDisconnect, status
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

import config
import database
import security
import socket_server

app = FastAPI(title="Temperature and Humidity Monitor API", version="1.1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


class LoginRequest(BaseModel):
    username: str
    password: str


class UserCreateRequest(BaseModel):
    username: str = Field(min_length=1, max_length=50)
    password: str
    role: str = "user"
    devices: List[str] = Field(default_factory=list)


class UserUpdateRequest(BaseModel):
    password: Optional[str] = None
    role: Optional[str] = None
    is_active: Optional[bool] = None
    devices: Optional[List[str]] = None


def extract_bearer_token(authorization: Optional[str]) -> Optional[str]:
    if not authorization:
        return None
    scheme, _, token = authorization.partition(" ")
    if scheme.lower() != "bearer" or not token:
        return None
    return token


async def get_current_user(authorization: Optional[str] = Header(default=None)) -> dict:
    token = extract_bearer_token(authorization)
    user = await database.get_user_by_token(token or "")
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Not authenticated",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return user


async def require_admin(current_user: dict = Depends(get_current_user)) -> dict:
    if current_user.get("role") != "admin":
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Admin access required")
    return current_user


class ConnectionManager:
    def __init__(self):
        self.active_connections: List[dict] = []

    async def connect(self, websocket: WebSocket, user: dict):
        await websocket.accept()
        self.active_connections.append({"websocket": websocket, "user": user})
        print(f"WebSocket connected: {user['username']} ({len(self.active_connections)} active)")

    def disconnect(self, websocket: WebSocket):
        self.active_connections = [
            item for item in self.active_connections if item["websocket"] is not websocket
        ]
        print(f"WebSocket disconnected ({len(self.active_connections)} active)")

    async def broadcast(self, message: dict):
        if not self.active_connections:
            return

        data = message.get("data") or {}
        device_id = data.get("device_id")
        disconnected = []

        for item in list(self.active_connections):
            websocket = item["websocket"]
            user = item["user"]
            if not database.user_can_access_device(user, device_id):
                continue
            try:
                await websocket.send_text(json.dumps(message))
            except Exception:
                disconnected.append(websocket)

        for websocket in disconnected:
            self.disconnect(websocket)


manager = ConnectionManager()


async def handle_socket_data(data: dict, raw_data_hex: str = None):
    device_id = data.get("device_id", "Unknown")
    try:
        await database.save_temperature_data(data)
        await manager.broadcast({"type": "data", "data": data})
        print(f"Device {device_id} data saved and broadcast")
    except Exception as e:
        print(f"Failed to process device {device_id}: {e}")
        import traceback
        traceback.print_exc()


@app.get("/")
async def root():
    return {"message": "Temperature and Humidity Monitor API", "version": "1.1.0"}


@app.post("/api/auth/login")
async def login(payload: LoginRequest):
    user = await database.authenticate_user(payload.username, payload.password)
    if not user:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid username or password")
    token = security.create_token()
    session = await database.create_session(user["id"], token)
    return {
        "access_token": token,
        "token_type": "bearer",
        "expires_at": session["expires_at"],
        "user": user,
    }


@app.post("/api/auth/logout")
async def logout(authorization: Optional[str] = Header(default=None)):
    token = extract_bearer_token(authorization)
    if token:
        await database.revoke_session(token)
    return {"ok": True}


@app.get("/api/auth/me")
async def me(current_user: dict = Depends(get_current_user)):
    return {"user": current_user}


@app.get("/api/admin/users")
async def admin_list_users(_: dict = Depends(require_admin)):
    return {"users": await database.list_users()}


@app.post("/api/admin/users", status_code=status.HTTP_201_CREATED)
async def admin_create_user(payload: UserCreateRequest, _: dict = Depends(require_admin)):
    try:
        user = await database.create_user(
            username=payload.username,
            password=payload.password,
            role=payload.role,
            device_ids=payload.devices,
        )
        return {"user": user}
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e)) from e


@app.put("/api/admin/users/{user_id}")
async def admin_update_user(user_id: int, payload: UserUpdateRequest, _: dict = Depends(require_admin)):
    try:
        user = await database.update_user(
            user_id=user_id,
            password=payload.password,
            role=payload.role,
            is_active=payload.is_active,
            device_ids=payload.devices,
        )
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e)) from e
    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")
    return {"user": user}


@app.delete("/api/admin/users/{user_id}")
async def admin_delete_user(user_id: int, _: dict = Depends(require_admin)):
    deleted = await database.delete_user(user_id)
    if not deleted:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="User not found or cannot be deleted")
    return {"ok": True}


@app.get("/api/devices")
async def get_devices(current_user: dict = Depends(get_current_user)):
    devices = await database.get_device_list(database.visible_devices_for_user(current_user))
    return {"devices": devices}


@app.get("/api/latest")
async def get_latest(device_id: str = None, current_user: dict = Depends(get_current_user)):
    if device_id and not database.user_can_access_device(current_user, device_id):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Device access denied")
    data = await database.get_latest_data(device_id, database.visible_devices_for_user(current_user))
    return {"data": data}


@app.get("/api/history")
async def get_history(
        device_id: str,
        hours: int = 24,
        limit: int = 1000,
        current_user: dict = Depends(get_current_user),
):
    if not database.user_can_access_device(current_user, device_id):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Device access denied")
    history = await database.get_temperature_history(
        device_id,
        hours,
        limit,
        database.visible_devices_for_user(current_user),
    )
    return {"history": history}


@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    token = websocket.query_params.get("token")
    user = await database.get_user_by_token(token or "")
    if not user:
        await websocket.close(code=1008)
        return

    await manager.connect(websocket, user)
    try:
        while True:
            await websocket.receive_text()
    except WebSocketDisconnect:
        manager.disconnect(websocket)
    except Exception as e:
        print(f"WebSocket error: {e}")
        manager.disconnect(websocket)


@app.on_event("startup")
async def startup_event():
    print("Starting system...")
    await database.init_db()
    print("Database initialized")

    sock_srv = socket_server.SocketServer(handle_socket_data)
    if config.config.SOCKET_PROTOCOL == "UDP":
        asyncio.create_task(sock_srv.start_udp())
    else:
        asyncio.create_task(sock_srv.start_tcp())

    print("Socket service started")
    print(f"API: http://{config.config.API_HOST}:{config.config.API_PORT}")
    print(f"Socket: {config.config.SOCKET_HOST}:{config.config.SOCKET_PORT}")


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        "main:app",
        host=config.config.API_HOST,
        port=config.config.API_PORT,
        reload=True,
    )

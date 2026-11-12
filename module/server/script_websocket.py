# This Python file uses the following encoding: utf-8
# @author runhey
# github https://github.com/runhey
from typing import Iterable
import asyncio

from fastapi import WebSocket, WebSocketDisconnect
from starlette.websockets import WebSocketState


class ScriptWSManager:

    def __init__(self):
        self.active_connections: list[WebSocket] = []
        self._ws_lock: asyncio.Lock | None = None

    def _get_ws_lock(self) -> asyncio.Lock:
        if self._ws_lock is None:
            self._ws_lock = asyncio.Lock()
        return self._ws_lock

    async def connect(self, ws: WebSocket):
        # 等待连接
        await ws.accept()
        async with self._get_ws_lock():
            if ws not in self.active_connections:
                self.active_connections.append(ws)

    async def disconnect(self, ws: WebSocket, code: int = 1000):
        # 关闭时移除 ws 对象，重复调用也应安全
        async with self._get_ws_lock():
            if ws in self.active_connections:
                self.active_connections.remove(ws)
        if ws.client_state == WebSocketState.DISCONNECTED:
            return
        try:
            # 给前端发送最后一次关闭信号
            await ws.close(code=code)
        except (RuntimeError, WebSocketDisconnect):
            return
        except Exception:
            return

    async def close_all(self, code: int = 1001):
        """主动关闭当前脚本下的全部 WebSocket 连接。"""
        async with self._get_ws_lock():
            connections = list(self.active_connections)
            self.active_connections.clear()
        for connection in connections:
            if connection.client_state == WebSocketState.DISCONNECTED:
                continue
            try:
                await connection.close(code=code)
            except (RuntimeError, WebSocketDisconnect):
                continue
            except Exception:
                continue

    async def send_text(self, ws: WebSocket, message: str) -> bool:
        return await self._send(ws, ws.send_text, message)

    async def send_json(self, ws: WebSocket, data: dict) -> bool:
        return await self._send(ws, ws.send_json, data)

    async def broadcast(self, message: str):
        # 广播消息
        await self._broadcast(self.active_connections, lambda connection: connection.send_text(message))

    async def broadcast_state(self, data: dict):
        # 广播自身的状态
        await self._broadcast(self.active_connections, lambda connection: connection.send_json(data))

    async def broadcast_log(self, log: str):
        # 广播日志
        await self._broadcast(self.active_connections, lambda connection: connection.send_text(log))

    async def _send(self, ws: WebSocket, sender, payload) -> bool:
        if ws.client_state == WebSocketState.DISCONNECTED:
            await self.disconnect(ws)
            return False
        try:
            await sender(payload)
            return True
        except (RuntimeError, WebSocketDisconnect):
            await self.disconnect(ws)
            return False
        except Exception:
            await self.disconnect(ws)
            return False

    async def _broadcast(self, connections: Iterable[WebSocket], sender_factory) -> None:
        async with self._get_ws_lock():
            snapshot = list(connections)
        dead_connections: list[WebSocket] = []
        for connection in snapshot:
            if connection.client_state == WebSocketState.DISCONNECTED:
                dead_connections.append(connection)
                continue
            try:
                await sender_factory(connection)
            except (RuntimeError, WebSocketDisconnect):
                dead_connections.append(connection)
            except Exception:
                dead_connections.append(connection)
        for connection in dead_connections:
            await self.disconnect(connection)





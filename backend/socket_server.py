import socket
import asyncio
import logging
from typing import Callable
from parser import DataParser
import config

logger = logging.getLogger("socket_server")


class UDPProtocol(asyncio.DatagramProtocol):
    """异步 UDP 协议处理器"""

    def __init__(self, callback: Callable):
        self.callback = callback
        self.transport = None

    def connection_made(self, transport):
        self.transport = transport

    def datagram_received(self, data, addr):
        logger.debug("UDP 收到数据 from %s len=%d hex=%s", addr, len(data), data.hex())
        parsed = DataParser.parse(data)
        if parsed:
            asyncio.create_task(self._safe_callback(parsed))
        else:
            logger.warning("UDP 解析失败 from %s", addr)

    async def _safe_callback(self, data: dict):
        try:
            await self.callback(data)
        except Exception:
            logger.exception("业务回调严重错误 device=%s", data.get('device_id', 'Unknown'))


class SocketServer:
    """Socket 数据接收服务"""

    def __init__(self, callback: Callable):
        self.host = config.config.SOCKET_HOST
        self.port = config.config.SOCKET_PORT
        self.protocol = config.config.SOCKET_PROTOCOL.upper()
        self.callback = callback
        self._server = None
        self._udp_transport = None

    async def start_udp(self):
        """启动 UDP 服务 (异步 DatagramProtocol)"""
        loop = asyncio.get_running_loop()
        transport, _ = await loop.create_datagram_endpoint(
            lambda: UDPProtocol(self.callback),
            local_addr=(self.host, self.port)
        )
        self._udp_transport = transport
        logger.info("UDP Socket 服务启动: %s:%s", self.host, self.port)

    async def start_tcp(self):
        """启动 TCP 服务"""
        self._server = await asyncio.start_server(
            self.handle_tcp_client,
            self.host,
            self.port
        )
        logger.info("TCP Socket 服务启动: %s:%s", self.host, self.port)
        async with self._server:
            await self._server.serve_forever()

    async def handle_tcp_client(self, reader, writer):
        """处理 TCP 客户端连接"""
        addr = writer.get_extra_info('peername')
        logger.info("新连接: %s", addr)
        timeout = config.config.TCP_TIMEOUT

        try:
            while True:
                try:
                    data = await asyncio.wait_for(reader.read(1024), timeout=timeout)
                except asyncio.TimeoutError:
                    logger.warning("TCP 读超时 %s (timeout=%ds)", addr, timeout)
                    break

                if not data:
                    break

                logger.debug("TCP 收到数据 from %s hex=%s", addr, data.hex())
                parsed = DataParser.parse(data)
                if parsed:
                    asyncio.create_task(self._safe_callback(parsed))

        except Exception:
            logger.exception("TCP 连接异常 %s", addr)
        finally:
            writer.close()
            await writer.wait_closed()
            logger.info("连接关闭: %s", addr)

    async def _safe_callback(self, data: dict):
        try:
            await self.callback(data)
        except Exception:
            logger.exception("业务回调严重错误 device=%s", data.get('device_id', 'Unknown'))

    async def close(self):
        """关闭服务"""
        if self._udp_transport:
            self._udp_transport.close()
            logger.info("UDP Socket 服务已关闭")
        if self._server:
            self._server.close()
            await self._server.wait_closed()
            logger.info("TCP Socket 服务已关闭")

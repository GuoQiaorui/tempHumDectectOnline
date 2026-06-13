import struct
import logging
from datetime import datetime
from typing import Optional, Dict

logger = logging.getLogger("parser")


class DataParser:
    """
    数据包解析器

    数据包格式 (22 字节):
    ┌────────┬────────┬────────┬────────┬────────┬────────┐
    │ 头 2B  │ 设备 ID 4B│ 温度 4B │ 湿度 4B  │ 时间戳 4B │ 校验和 4B │
    │ 0xAA0xBB│ 0x0001  │ float  │ float  │ uint32 │ uint32 │
    └────────┴────────┴────────┴────────┴────────┴────────┘
    """

    HEADER = b"\xAA\xBB"
    PACKET_LENGTH = 22

    @classmethod
    def parse(cls, data: bytes) -> Optional[Dict]:
        """解析字节数据为温湿度数据"""
        try:
            logger.debug("开始解析数据包 len=%d hex=%s", len(data), data.hex())

            if len(data) < cls.PACKET_LENGTH:
                logger.warning("数据包长度不足: %d < %d", len(data), cls.PACKET_LENGTH)
                return None

            header = data[:2]
            if header != cls.HEADER:
                logger.warning("数据包头部错误: %s != %s", header.hex(), cls.HEADER.hex())
                return None

            unpacked = struct.unpack('>2sIffII', data[:22])
            header, device_id, temp, humidity, timestamp, checksum = unpacked

            # 验证校验和
            rounded_temp = round(temp, 2)
            rounded_humidity = round(humidity, 2)
            calc_checksum = (device_id + int(rounded_temp * 100) + int(rounded_humidity * 100)) & 0xFFFFFFFF

            if checksum != calc_checksum:
                logger.warning(
                    "校验和失败 device=DEV%04d recv=%08X calc=%08X",
                    device_id, checksum, calc_checksum
                )
                return None

            dt = datetime.fromtimestamp(timestamp)

            return {
                "device_id": f"DEV{device_id:04d}",
                "temperature": round(temp, 2),
                "humidity": round(humidity, 2),
                "timestamp": dt.isoformat(),
                "raw_data": data[:22].hex()
            }

        except struct.error as e:
            logger.error("解包错误: %s", e)
            return None
        except Exception as e:
            logger.error("解析错误: %s", e)
            return None

    @classmethod
    def pack(cls, device_id: int, temp: float, humidity: float) -> bytes:
        """打包数据为字节 (用于测试)"""
        timestamp = int(datetime.now().timestamp())
        checksum = (device_id + int(temp * 100) + int(humidity * 100)) & 0xFFFF

        data = struct.pack(
            '>2sIffII',
            cls.HEADER,
            device_id,
            temp,
            humidity,
            timestamp,
            checksum
        )
        return data
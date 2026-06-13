#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
温湿度数据模拟发送器
用于测试 Socket 数据接收服务
"""

import socket
import time
import random
import struct
from datetime import datetime

# ================= 配置区域 =================
SERVER_HOST = '127.0.0.1'  # 后端服务地址
SERVER_PORT = 9999  # Socket 监听端口
DEVICE_ID = 1  # 设备 ID
SEND_INTERVAL = 2  # 发送间隔 (秒)
SEND_COUNT = 3  # 发送次数 (0 表示无限)


# ===========================================

class TestDataSender:
    """测试数据发送器"""

    # 数据包格式定义 (必须与后端 parser.py 完全一致)
    HEADER = b"\xAA\xBB"
    # 格式：头(2) + 设备 ID(4) + 温度(4) + 湿度(4) + 时间戳(4) + 校验和(4) = 22 字节
    PACK_FORMAT = '>2sIffII'
    PACKET_LENGTH = 22

    def __init__(self, host, port):
        self.host = host
        self.port = port
        self.sock = None

    def connect(self):
        """创建 UDP Socket 连接"""
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        print(f"🔌 已创建 UDP Socket")

    def pack_data(self, device_id, temp, humidity):
        """
        打包数据为字节流

        数据包结构 (22 字节):
        ┌────────┬────────┬────────┬────────┬────────┬────────┐
        │ 头 2B  │ 设备 ID │ 温度   │ 湿度   │ 时间戳  │ 校验和  │
        │ 0xAA0xBB│ 4B    │ 4B    │ 4B    │ 4B    │ 4B    │
        └────────┴────────┴────────┴────────┴────────┴────────┘
        """
        timestamp = int(datetime.now().timestamp())

        # 计算校验和 (与后端验证逻辑一致)
        checksum = (device_id + int(temp * 100) + int(humidity * 100)) & 0xFFFFFFFF

        # 打包数据
        data = struct.pack(
            self.PACK_FORMAT,
            self.HEADER,
            device_id,
            temp,
            humidity,
            timestamp,
            checksum
        )

        return data, checksum

    def send(self, device_id, temp, humidity):
        """发送单条数据"""
        try:
            # 打包数据
            data, checksum = self.pack_data(device_id, temp, humidity)

            # 验证数据包长度
            if len(data) != self.PACKET_LENGTH:
                print(f"❌ 数据包长度错误：{len(data)} != {self.PACKET_LENGTH}")
                return False

            # 发送数据
            self.sock.sendto(data, (self.host, self.port))

            # 打印发送信息
            print(f"📤 发送成功 | 设备: DEV{device_id:04d} | "
                  f"温度: {temp:.2f}°C | 湿度: {humidity:.2f}% | "
                  f"校验: {checksum:08X} | 长度: {len(data)} 字节")
            print(f"   Hex: {data.hex()}")

            return True

        except Exception as e:
            print(f"❌ 发送失败：{e}")
            return False

    def close(self):
        """关闭连接"""
        if self.sock:
            self.sock.close()
            print("📴 Socket 已关闭")

    def run(self, count=0):
        """运行发送测试"""
        print("=" * 60)
        print("🌡️ 温湿度数据模拟发送器")
        print("=" * 60)
        print(f"📍 目标地址：{self.host}:{self.port}")
        print(f"📦 数据包长度：{self.PACKET_LENGTH} 字节")
        print(f"⏱️  发送间隔：{SEND_INTERVAL} 秒")
        print(f"📊 发送次数：{count if count > 0 else '无限'}")
        print("=" * 60)
        print("按 Ctrl+C 停止发送\n")

        self.connect()

        sent_count = 0
        try:
            while count == 0 or sent_count < count:
                # 生成模拟数据 (温度 20-30°C, 湿度 40-80%)
                temp = round(random.uniform(20.0, 30.0), 2)
                humidity = round(random.uniform(40.0, 80.0), 2)

                # 发送数据
                if self.send(DEVICE_ID, temp, humidity):
                    sent_count += 1

                # 等待间隔
                time.sleep(SEND_INTERVAL)

        except KeyboardInterrupt:
            print(f"\n⚠️  用户中断，已发送 {sent_count} 条数据")
        finally:
            self.close()
            print(f"✅ 测试完成，共发送 {sent_count} 条数据")


def main():
    """主函数"""
    sender = TestDataSender(SERVER_HOST, SERVER_PORT)
    sender.run(count=SEND_COUNT)


if __name__ == "__main__":
    main()
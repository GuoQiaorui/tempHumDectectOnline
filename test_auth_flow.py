#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
End-to-end smoke test for auth, device permissions, and TCP data upload.

Prerequisite:
  python backend/main.py
"""

import json
import socket
import struct
import time
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime


API_BASE = "http://127.0.0.1:8000/api"
SOCKET_HOST = "127.0.0.1"
SOCKET_PORT = 9999
USERNAME = "testuser"
PASSWORD = "Test12345"
DEVICE_NUMBER = 1
DEVICE_ID = "DEV0001"


def request(method, path, payload=None, token=None, expected_status=200):
    data = None
    headers = {"Accept": "application/json"}
    if payload is not None:
        data = json.dumps(payload).encode("utf-8")
        headers["Content-Type"] = "application/json"
    if token:
        headers["Authorization"] = f"Bearer {token}"

    req = urllib.request.Request(
        f"{API_BASE}{path}",
        data=data,
        headers=headers,
        method=method,
    )
    try:
        with urllib.request.urlopen(req, timeout=10) as response:
            body = response.read().decode("utf-8")
            if response.status != expected_status:
                raise AssertionError(f"{method} {path}: expected {expected_status}, got {response.status}")
            return json.loads(body) if body else None
    except urllib.error.HTTPError as exc:
        body = exc.read().decode("utf-8")
        if exc.code == expected_status:
            return json.loads(body) if body else None
        raise AssertionError(f"{method} {path}: expected {expected_status}, got {exc.code}, body={body}") from exc


def pack_data(device_id, temp, humidity):
    timestamp = int(datetime.now().timestamp())
    checksum = (device_id + int(temp * 100) + int(humidity * 100)) & 0xFFFFFFFF
    return struct.pack(">2sIffII", b"\xAA\xBB", device_id, temp, humidity, timestamp, checksum)


def send_tcp_data(temp=26.5, humidity=58.5):
    packet = pack_data(DEVICE_NUMBER, temp, humidity)
    with socket.create_connection((SOCKET_HOST, SOCKET_PORT), timeout=10) as sock:
        sock.sendall(packet)
    return temp, humidity


def wait_for_uploaded_record(token, temp, humidity, timeout=10):
    deadline = time.time() + timeout
    query = urllib.parse.urlencode({"device_id": DEVICE_ID, "limit": 20})
    while time.time() < deadline:
        history = request("GET", f"/history?{query}", token=token)["history"]
        for row in history:
            if (
                row.get("device_id") == DEVICE_ID
                and abs(float(row["temperature"]) - temp) < 0.05
                and abs(float(row["humidity"]) - humidity) < 0.05
            ):
                return row
        time.sleep(0.5)
    raise AssertionError("Uploaded TCP data was not visible in /api/history")


def main():
    request("POST", "/auth/login", {"username": USERNAME, "password": "wrongpass1"}, expected_status=401)
    login = request("POST", "/auth/login", {"username": USERNAME, "password": PASSWORD})
    token = login["access_token"]
    user = login["user"]
    assert user["username"] == USERNAME
    assert DEVICE_ID in user["devices"]

    devices = request("GET", "/devices", token=token)["devices"]
    assert any(item["device_id"] == DEVICE_ID for item in devices)

    query = urllib.parse.urlencode({"device_id": DEVICE_ID, "limit": 5})
    request("GET", f"/history?{query}", token=token)

    temp, humidity = send_tcp_data()
    row = wait_for_uploaded_record(token, temp, humidity)
    request("POST", "/auth/logout", token=token)

    print("PASS auth flow")
    print(json.dumps({"uploaded_record": row}, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()

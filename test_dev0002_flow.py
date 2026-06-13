#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Smoke test for DEV0002 data upload with account testuser1/Test12345.

Prerequisite:
  Backend service is running on http://127.0.0.1:8000
  TCP socket service is running on 127.0.0.1:9999
"""

import json
import random
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

ADMIN_USERNAME = "admin"
ADMIN_PASSWORD = "admin123"
USERNAME = "testuser1"
PASSWORD = "Test12345"
DEVICE_NUMBER = 2
DEVICE_ID = "DEV0002"
SEND_COUNT = 10
SEND_INTERVAL_SECONDS = 2
BASE_TEMPERATURE = 26.5
BASE_HUMIDITY = 58.5


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


def login(username, password):
    return request("POST", "/auth/login", {"username": username, "password": password})["access_token"]


def ensure_test_user():
    admin_token = login(ADMIN_USERNAME, ADMIN_PASSWORD)
    users = request("GET", "/admin/users", token=admin_token)["users"]
    existing = next((user for user in users if user["username"] == USERNAME), None)

    payload = {
        "username": USERNAME,
        "password": PASSWORD,
        "role": "user",
        "devices": [DEVICE_ID],
    }

    if existing:
        request(
            "PUT",
            f"/admin/users/{existing['id']}",
            {
                "password": PASSWORD,
                "role": "user",
                "is_active": True,
                "devices": [DEVICE_ID],
            },
            token=admin_token,
        )
    else:
        request("POST", "/admin/users", payload, token=admin_token, expected_status=201)

    request("POST", "/auth/logout", token=admin_token)


def pack_data(device_number, temp, humidity):
    timestamp = int(datetime.now().timestamp())
    checksum = (device_number + int(temp * 100) + int(humidity * 100)) & 0xFFFFFFFF
    return struct.pack(">2sIffII", b"\xAA\xBB", device_number, temp, humidity, timestamp, checksum)


def send_tcp_packet(temp, humidity):
    packet = pack_data(DEVICE_NUMBER, temp, humidity)
    with socket.create_connection((SOCKET_HOST, SOCKET_PORT), timeout=10) as sock:
        sock.sendall(packet)
    return temp, humidity


def build_test_payloads():
    payloads = []
    temperature = BASE_TEMPERATURE
    humidity = BASE_HUMIDITY
    for _ in range(SEND_COUNT):
        temperature = min(30.0, max(20.0, temperature + random.uniform(-0.35, 0.35)))
        humidity = min(80.0, max(40.0, humidity + random.uniform(-1.0, 1.0)))
        payloads.append((round(temperature, 2), round(humidity, 2)))
    return payloads


def send_tcp_data_batch(payloads):
    sent = []
    for index, (temp, humidity) in enumerate(payloads, start=1):
        sent.append(send_tcp_packet(temp, humidity))
        print(f"sent {index}/{len(payloads)} DEV0002 temp={temp:.2f} humidity={humidity:.2f}")
        time.sleep(SEND_INTERVAL_SECONDS)
    return sent


def wait_for_uploaded_records(token, expected_payloads, timeout=15):
    deadline = time.time() + timeout
    query = urllib.parse.urlencode({"device_id": DEVICE_ID, "limit": 100})
    while time.time() < deadline:
        history = request("GET", f"/history?{query}", token=token)["history"]
        matched = []
        for temp, humidity in expected_payloads:
            found = next(
                (
                    row for row in history
                    if row.get("device_id") == DEVICE_ID
                    and abs(float(row["temperature"]) - temp) < 0.05
                    and abs(float(row["humidity"]) - humidity) < 0.05
                ),
                None,
            )
            if found:
                matched.append(found)
        if len(matched) == len(expected_payloads):
            return matched
        time.sleep(0.5)
    raise AssertionError(f"Expected {len(expected_payloads)} DEV0002 records were not all visible in /api/history")


def main():
    ensure_test_user()

    token = login(USERNAME, PASSWORD)
    devices = request("GET", "/devices", token=token)["devices"]
    assert any(item["device_id"] == DEVICE_ID for item in devices), devices

    payloads = build_test_payloads()
    send_tcp_data_batch(payloads)
    rows = wait_for_uploaded_records(token, payloads)
    request("POST", "/auth/logout", token=token)

    print("PASS DEV0002 auth and TCP upload flow")
    print(json.dumps({
        "account": USERNAME,
        "device": DEVICE_ID,
        "sent_count": len(payloads),
        "verified_count": len(rows),
        "uploaded_records": rows,
    }, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()

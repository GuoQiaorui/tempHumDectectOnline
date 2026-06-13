# Production Deployment

This project can run on one cloud server with Docker Compose.

## Recommended ECS Baseline

For a small temperature/humidity monitoring deployment:

- 2 vCPU / 2 GB RAM
- Ubuntu 22.04 or 24.04
- 40 GB cloud disk
- Fixed public IPv4 address
- 1-5 Mbps bandwidth for testing or low-frequency uploads

Upgrade when device count, upload frequency, or retention period grows.

## Required Ports

Open these in the cloud security group:

- `80/tcp`: web UI
- `443/tcp`: optional HTTPS reverse proxy later
- `9999/tcp`: device TCP upload
- `22/tcp`: SSH, restrict to your own IP

Do not expose `8000/tcp` publicly. It is only used inside Docker by Nginx.

## Deploy

```bash
cd /opt/FastAPIProject
docker compose -f docker-compose.prod.yml up -d --build
docker compose -f docker-compose.prod.yml ps
```

Open:

```text
http://SERVER_PUBLIC_IP
```

Device TCP target:

```text
SERVER_PUBLIC_IP:9999
```

## Test From Your Local Machine

Update the test script constants if you want to test the cloud server from your PC:

```python
API_BASE = "http://SERVER_PUBLIC_IP/api"
SOCKET_HOST = "SERVER_PUBLIC_IP"
SOCKET_PORT = 9999
```

Then run:

```powershell
.venv\Scripts\python.exe test_dev0002_flow.py
```

## Data Persistence

SQLite data is stored in Docker volume `backend_data` at:

```text
/data/temperature.db
```

Backup example:

```bash
mkdir -p /backup
docker run --rm \
  -v fastapiproject_backend_data:/data \
  -v /backup:/backup \
  alpine \
  cp /data/temperature.db /backup/temperature-$(date +%F-%H%M%S).db
```

## 4G Module Notes

The 4G module only needs to send TCP packets to:

```text
SERVER_PUBLIC_IP:9999
```

No code change is required if the packet format remains unchanged:

- header: `AA BB`
- device id: uint32
- temperature: float
- humidity: float
- timestamp: uint32
- checksum: uint32

Only change code if the 4G module sends a different packet format or uses UDP/MQTT/HTTP instead of TCP.

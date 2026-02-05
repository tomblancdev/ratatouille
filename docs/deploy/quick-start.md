# 🚀 Quick Start

Get Ratatouille up and running in minutes.

---

## Prerequisites

- **Docker** or **Podman** with Docker Compose
- **4GB+ RAM** available for containers
- **Ports available**: 3030, 9000, 9001, 19120

---

## 1. Start the Platform

```bash
cd ratatouille

# Start all services
make up

# Or manually:
docker compose up -d --build
```

Wait for all services to be healthy (~30 seconds on first run).

---

## 2. Verify Services

```bash
make status
# or: docker compose ps
```

You should see:

```
ratatouille-minio       running (healthy)
ratatouille-nessie      running (healthy)
ratatouille-dagster     running
ratatouille-minio-init  exited (0)  ← this is normal
```

---

## 3. Access the UIs

| Service | URL | Credentials |
|---------|-----|-------------|
| **Dagster** | http://localhost:3030 | None |
| **MinIO Console** | http://localhost:9001 | `ratatouille` / `ratatouille123` |
| **Nessie** | http://localhost:19120 | None |

---

## 4. Quick Commands

```bash
make up        # Start platform
make down      # Stop platform
make logs      # Follow all logs
make status    # Container status
make clean     # Stop + delete all data
```

---

## Troubleshooting

### Services won't start

```bash
# Check logs
docker compose logs -f

# Common issues:
# - Port already in use: stop other services or change ports
# - Not enough memory: increase Docker memory limit
```

### Can't connect to services

```bash
# Make sure containers are healthy
make status

# Test MinIO
curl http://localhost:9000/minio/health/live

# Test Nessie
curl http://localhost:19120/api/v2/config
```

---

## Next Steps

- 📊 **[Getting Started Guide](../guide/getting-started.md)** - Build your first pipeline
- ⚙️ **[Configuration](configuration.md)** - Customize settings
- 🔧 **[Docker Compose Setup](docker-compose.md)** - Detailed Docker configuration

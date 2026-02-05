# 🛠️ Deployment Guide

> For **Platform Operators** - Setting up and running Ratatouille

---

## Quick Links

| I want to... | Go to... |
|--------------|----------|
| Get started quickly | [Quick Start](quick-start.md) |
| Configure Docker Compose | [Docker Compose Setup](docker-compose.md) |
| Customize settings | [Configuration](configuration.md) |
| Secure for production | [Security](security.md) |
| Monitor services | [Monitoring](monitoring.md) |
| Set up backups | [Backup & Recovery](backup-recovery.md) |
| Deploy on Kubernetes | [Kubernetes](kubernetes.md) |
| Scale to production | [Scaling](scaling.md) |
| Fix problems | [Troubleshooting](troubleshooting.md) |

---

## Prerequisites

- **Docker** or **Podman** with Docker Compose
- **4GB+ RAM** available for containers
- **Ports available**: 3030, 8889, 9000, 9001, 19120

---

## Getting Started

```bash
# Clone repository
git clone https://github.com/your-org/ratatouille
cd ratatouille

# Start all services
make up

# Verify
make status
```

Access the UIs:

| Service | URL | Credentials |
|---------|-----|-------------|
| **Dagster** | http://localhost:3030 | None |
| **Jupyter** | http://localhost:8889 | Token: `ratatouille` |
| **MinIO Console** | http://localhost:9001 | `ratatouille` / `ratatouille123` |

---

## Documentation Index

### Setup

- **[Quick Start](quick-start.md)** - Get running in 5 minutes
- **[Docker Compose](docker-compose.md)** - Detailed Docker configuration
- **[Kubernetes](kubernetes.md)** - K3s/K8s deployment

### Configuration

- **[Configuration](configuration.md)** - Environment variables and profiles
- **[Security](security.md)** - Production hardening

### Operations

- **[Monitoring](monitoring.md)** - Health checks, logs, alerts
- **[Backup & Recovery](backup-recovery.md)** - Data protection
- **[Scaling](scaling.md)** - Grow with your data
- **[Troubleshooting](troubleshooting.md)** - Common issues and fixes

---

## Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                     RATATOUILLE PLATFORM                         │
│                                                                  │
│  ┌──────────────────────────────────────────────────────────┐  │
│  │                    User Applications                       │  │
│  │   Dagster UI (3030)    Jupyter (8889)    MinIO (9001)    │  │
│  └──────────────────────────────────────────────────────────┘  │
│                               │                                  │
│  ┌──────────────────────────────────────────────────────────┐  │
│  │                    Core Services                           │  │
│  │   ┌────────────┐    ┌────────────┐    ┌────────────┐     │  │
│  │   │   MinIO    │    │   Nessie   │    │  Dagster   │     │  │
│  │   │  (Storage) │    │  (Catalog) │    │  (Orch)    │     │  │
│  │   └────────────┘    └────────────┘    └────────────┘     │  │
│  └──────────────────────────────────────────────────────────┘  │
│                               │                                  │
│  ┌──────────────────────────────────────────────────────────┐  │
│  │                    Data Layers                             │  │
│  │      Bronze    →    Silver    →    Gold                   │  │
│  │     (Raw)         (Cleaned)      (Business)               │  │
│  └──────────────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────────────┘
```

---

## Next Steps

After deployment:

1. **Configure** - Review [Configuration](configuration.md) options
2. **Secure** - Follow [Security](security.md) checklist for production
3. **Monitor** - Set up [Monitoring](monitoring.md) and alerts
4. **Hand off** - Direct data engineers to the [User Guide](../guide/README.md)

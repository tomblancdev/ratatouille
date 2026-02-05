# 🔒 Security

Production security hardening.

---

## Default Credentials

⚠️ **Default credentials are for development only!**

| Service | Default User | Default Password |
|---------|--------------|------------------|
| MinIO | `ratatouille` | `ratatouille123` |
| Jupyter | - | Token: `ratatouille` |
| Nessie | - | No auth |

---

## Change Default Passwords

### Via Environment Variables

```bash
# .env file
MINIO_ROOT_USER=your_secure_username
MINIO_ROOT_PASSWORD=your_very_long_secure_password_32chars
JUPYTER_TOKEN=another_secure_random_token
```

### Password Requirements

- **MinIO:** Minimum 8 characters (recommend 32+)
- **Jupyter Token:** Any string (recommend 32+ random chars)

### Generate Secure Passwords

```bash
# Generate random password
openssl rand -base64 32

# Or using Python
python3 -c "import secrets; print(secrets.token_urlsafe(32))"
```

---

## Network Security

### Restrict Access

By default, all ports are exposed to `localhost`. For production:

1. **Use a reverse proxy** (nginx, traefik)
2. **Bind to internal network only**
3. **Enable firewall rules**

### Internal-Only Binding

```yaml
# docker-compose.override.yml
services:
  dagster:
    ports:
      - "127.0.0.1:3030:3000"  # Only localhost

  jupyter:
    ports:
      - "127.0.0.1:8889:8888"

  minio:
    ports:
      - "127.0.0.1:9000:9000"
      - "127.0.0.1:9001:9001"
```

### Firewall Rules

```bash
# Allow only specific IPs to access services
sudo ufw allow from 10.0.0.0/8 to any port 3030
sudo ufw allow from 10.0.0.0/8 to any port 9001
```

---

## TLS/HTTPS

### Using Reverse Proxy (Recommended)

Deploy nginx or traefik in front of services:

```yaml
# docker-compose.override.yml
services:
  nginx:
    image: nginx:alpine
    ports:
      - "443:443"
    volumes:
      - ./nginx.conf:/etc/nginx/nginx.conf
      - ./certs:/etc/nginx/certs

  # Remove public port mappings from other services
  dagster:
    ports: []  # Internal only

  jupyter:
    ports: []
```

**nginx.conf:**

```nginx
server {
    listen 443 ssl;
    server_name ratatouille.example.com;

    ssl_certificate /etc/nginx/certs/fullchain.pem;
    ssl_certificate_key /etc/nginx/certs/privkey.pem;

    location / {
        proxy_pass http://dagster:3000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
    }
}
```

### MinIO TLS

MinIO supports native TLS:

```yaml
services:
  minio:
    environment:
      MINIO_BROWSER_REDIRECT_URL: https://minio.example.com:9001
    volumes:
      - ./certs/public.crt:/root/.minio/certs/public.crt
      - ./certs/private.key:/root/.minio/certs/private.key
```

---

## Authentication

### Jupyter Authentication

```bash
# Use strong token
JUPYTER_TOKEN=$(openssl rand -base64 32)
```

### MinIO Users

Create additional users with limited permissions:

```bash
# Create read-only user
docker compose exec minio mc admin user add myminio readonly_user password123

# Create policy
docker compose exec minio mc admin policy attach myminio readonly --user readonly_user
```

### Nessie Authentication

For production, enable Nessie authentication:

```yaml
services:
  nessie:
    environment:
      NESSIE_AUTH_TYPE: BEARER
      # Additional auth config...
```

---

## Secrets Management

### Docker Secrets (Swarm)

```yaml
services:
  minio:
    secrets:
      - minio_root_password
    environment:
      MINIO_ROOT_PASSWORD_FILE: /run/secrets/minio_root_password

secrets:
  minio_root_password:
    external: true
```

### HashiCorp Vault

For enterprise deployments, integrate with Vault:

```bash
# Fetch secrets at runtime
export MINIO_ROOT_PASSWORD=$(vault kv get -field=password secret/ratatouille/minio)
```

### Environment Files

Keep secrets out of git:

```bash
# .gitignore
.env
.env.*
**/secrets/
```

---

## Container Security

### Run as Non-Root

```yaml
services:
  dagster:
    user: "1000:1000"  # Run as non-root user
```

### Read-Only Filesystem

```yaml
services:
  dagster:
    read_only: true
    tmpfs:
      - /tmp
    volumes:
      - dagster_storage:/app/storage
```

### Resource Limits

Prevent resource exhaustion:

```yaml
services:
  dagster:
    deploy:
      resources:
        limits:
          cpus: '2'
          memory: 4G
        reservations:
          memory: 1G
```

---

## Data Security

### Encryption at Rest

MinIO supports server-side encryption:

```yaml
services:
  minio:
    environment:
      MINIO_KMS_AUTO_ENCRYPTION: "on"
      # Configure KMS for encryption keys
```

### Bucket Policies

Restrict bucket access:

```bash
# Create read-only policy for specific bucket
docker compose exec minio mc admin policy create myminio bronze-readonly bronze-policy.json
```

**bronze-policy.json:**

```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Action": ["s3:GetObject"],
      "Resource": ["arn:aws:s3:::warehouse/bronze/*"]
    }
  ]
}
```

---

## Audit Logging

### MinIO Audit Logs

Enable audit logging:

```yaml
services:
  minio:
    environment:
      MINIO_AUDIT_WEBHOOK_ENABLE: "on"
      MINIO_AUDIT_WEBHOOK_ENDPOINT: "http://logger:8080/audit"
```

### Access Logs

Log all access via reverse proxy:

```nginx
# nginx.conf
access_log /var/log/nginx/ratatouille.access.log;
error_log /var/log/nginx/ratatouille.error.log;
```

---

## Security Checklist

Before production:

- [ ] Change all default passwords
- [ ] Change Jupyter token
- [ ] Enable TLS/HTTPS
- [ ] Restrict network access (firewall)
- [ ] Use Docker secrets or Vault
- [ ] Enable MinIO bucket policies
- [ ] Set resource limits
- [ ] Enable audit logging
- [ ] Regular security updates
- [ ] Backup encryption keys

---

## Incident Response

### Suspected Breach

1. **Isolate:** Remove public access immediately
2. **Rotate:** Change all credentials
3. **Audit:** Review access logs
4. **Backup:** Export data for forensics
5. **Rebuild:** Redeploy from clean images

### Credential Rotation

```bash
# Generate new credentials
NEW_MINIO_PASS=$(openssl rand -base64 32)

# Update .env
sed -i "s/MINIO_ROOT_PASSWORD=.*/MINIO_ROOT_PASSWORD=$NEW_MINIO_PASS/" .env

# Restart services
docker compose down && docker compose up -d
```

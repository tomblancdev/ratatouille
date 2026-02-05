# ☸️ Kubernetes Deployment

Deploy Ratatouille on K3s/Kubernetes for production scale.

---

## Overview

Ratatouille is designed to scale from Docker Compose to Kubernetes with minimal changes:

```
┌─────────────────── Single Node ───────────────────┐
│         docker compose up -d                       │
│  ┌────────┐ ┌────────┐ ┌───────┐ ┌───────┐       │
│  │ MinIO  │ │ Nessie │ │Dagster│ │Jupyter│       │
│  └────────┘ └────────┘ └───────┘ └───────┘       │
└────────────────────────────────────────────────────┘
                    │
                    │ Same images, same config
                    ▼
┌─────────────────── K3s Cluster ───────────────────┐
│   Node 1          Node 2          Node 3          │
│  ┌────────┐      ┌────────┐      ┌────────┐      │
│  │ MinIO  │      │Dagster │      │Jupyter │      │
│  │ Nessie │      │Workers │      │        │      │
│  └────────┘      └────────┘      └────────┘      │
└────────────────────────────────────────────────────┘
```

---

## Prerequisites

- K3s or Kubernetes cluster
- `kubectl` configured
- Helm (optional, for charts)
- Persistent storage (local-path or cloud PVs)

---

## Quick Start with K3s

### Install K3s

```bash
# Single node K3s
curl -sfL https://get.k3s.io | sh -

# Verify
sudo k3s kubectl get nodes
```

### Deploy Ratatouille

```bash
# Create namespace
kubectl create namespace ratatouille

# Apply manifests
kubectl apply -f k8s/ -n ratatouille
```

---

## Kubernetes Manifests

### Namespace

```yaml
# k8s/namespace.yaml
apiVersion: v1
kind: Namespace
metadata:
  name: ratatouille
```

### MinIO Deployment

```yaml
# k8s/minio.yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: minio
  namespace: ratatouille
spec:
  replicas: 1
  selector:
    matchLabels:
      app: minio
  template:
    metadata:
      labels:
        app: minio
    spec:
      containers:
        - name: minio
          image: minio/minio:latest
          args:
            - server
            - /data
            - --console-address
            - ":9001"
          env:
            - name: MINIO_ROOT_USER
              valueFrom:
                secretKeyRef:
                  name: ratatouille-secrets
                  key: minio-user
            - name: MINIO_ROOT_PASSWORD
              valueFrom:
                secretKeyRef:
                  name: ratatouille-secrets
                  key: minio-password
          ports:
            - containerPort: 9000
            - containerPort: 9001
          volumeMounts:
            - name: data
              mountPath: /data
          resources:
            limits:
              memory: 1Gi
            requests:
              memory: 512Mi
          livenessProbe:
            httpGet:
              path: /minio/health/live
              port: 9000
            initialDelaySeconds: 10
            periodSeconds: 10
      volumes:
        - name: data
          persistentVolumeClaim:
            claimName: minio-pvc
---
apiVersion: v1
kind: Service
metadata:
  name: minio
  namespace: ratatouille
spec:
  ports:
    - name: api
      port: 9000
      targetPort: 9000
    - name: console
      port: 9001
      targetPort: 9001
  selector:
    app: minio
```

### Nessie Deployment

```yaml
# k8s/nessie.yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: nessie
  namespace: ratatouille
spec:
  replicas: 1
  selector:
    matchLabels:
      app: nessie
  template:
    metadata:
      labels:
        app: nessie
    spec:
      containers:
        - name: nessie
          image: ghcr.io/projectnessie/nessie:latest
          env:
            - name: NESSIE_VERSION_STORE_TYPE
              value: ROCKSDB
            - name: QUARKUS_HTTP_PORT
              value: "19120"
          ports:
            - containerPort: 19120
          volumeMounts:
            - name: data
              mountPath: /nessie/data
          resources:
            limits:
              memory: 768Mi
            requests:
              memory: 256Mi
          livenessProbe:
            httpGet:
              path: /api/v2/config
              port: 19120
            initialDelaySeconds: 30
            periodSeconds: 10
      volumes:
        - name: data
          persistentVolumeClaim:
            claimName: nessie-pvc
---
apiVersion: v1
kind: Service
metadata:
  name: nessie
  namespace: ratatouille
spec:
  ports:
    - port: 19120
      targetPort: 19120
  selector:
    app: nessie
```

### Dagster Deployment

```yaml
# k8s/dagster.yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: dagster
  namespace: ratatouille
spec:
  replicas: 1
  selector:
    matchLabels:
      app: dagster
  template:
    metadata:
      labels:
        app: dagster
    spec:
      containers:
        - name: dagster
          image: your-registry/ratatouille:latest
          command: ["dagster", "dev", "-h", "0.0.0.0", "-p", "3000"]
          env:
            - name: S3_ENDPOINT
              value: http://minio:9000
            - name: NESSIE_URI
              value: http://nessie:19120/api/v2
            - name: ICEBERG_WAREHOUSE
              value: s3://warehouse/
            - name: S3_ACCESS_KEY
              valueFrom:
                secretKeyRef:
                  name: ratatouille-secrets
                  key: minio-user
            - name: S3_SECRET_KEY
              valueFrom:
                secretKeyRef:
                  name: ratatouille-secrets
                  key: minio-password
          ports:
            - containerPort: 3000
          volumeMounts:
            - name: workspaces
              mountPath: /app/workspaces
          resources:
            limits:
              memory: 2Gi
            requests:
              memory: 1Gi
      volumes:
        - name: workspaces
          persistentVolumeClaim:
            claimName: dagster-pvc
---
apiVersion: v1
kind: Service
metadata:
  name: dagster
  namespace: ratatouille
spec:
  ports:
    - port: 3000
      targetPort: 3000
  selector:
    app: dagster
```

### Secrets

```yaml
# k8s/secrets.yaml
apiVersion: v1
kind: Secret
metadata:
  name: ratatouille-secrets
  namespace: ratatouille
type: Opaque
stringData:
  minio-user: ratatouille
  minio-password: your-secure-password
  jupyter-token: your-jupyter-token
```

### Persistent Volumes

```yaml
# k8s/storage.yaml
apiVersion: v1
kind: PersistentVolumeClaim
metadata:
  name: minio-pvc
  namespace: ratatouille
spec:
  accessModes:
    - ReadWriteOnce
  resources:
    requests:
      storage: 50Gi
---
apiVersion: v1
kind: PersistentVolumeClaim
metadata:
  name: nessie-pvc
  namespace: ratatouille
spec:
  accessModes:
    - ReadWriteOnce
  resources:
    requests:
      storage: 10Gi
---
apiVersion: v1
kind: PersistentVolumeClaim
metadata:
  name: dagster-pvc
  namespace: ratatouille
spec:
  accessModes:
    - ReadWriteOnce
  resources:
    requests:
      storage: 20Gi
```

---

## Ingress

### With Traefik (K3s default)

```yaml
# k8s/ingress.yaml
apiVersion: networking.k8s.io/v1
kind: Ingress
metadata:
  name: ratatouille-ingress
  namespace: ratatouille
  annotations:
    traefik.ingress.kubernetes.io/router.entrypoints: websecure
    traefik.ingress.kubernetes.io/router.tls: "true"
spec:
  rules:
    - host: dagster.example.com
      http:
        paths:
          - path: /
            pathType: Prefix
            backend:
              service:
                name: dagster
                port:
                  number: 3000
    - host: minio.example.com
      http:
        paths:
          - path: /
            pathType: Prefix
            backend:
              service:
                name: minio
                port:
                  number: 9001
```

---

## Scaling

### Horizontal Pod Autoscaler

```yaml
apiVersion: autoscaling/v2
kind: HorizontalPodAutoscaler
metadata:
  name: dagster-hpa
  namespace: ratatouille
spec:
  scaleTargetRef:
    apiVersion: apps/v1
    kind: Deployment
    name: dagster
  minReplicas: 1
  maxReplicas: 5
  metrics:
    - type: Resource
      resource:
        name: memory
        target:
          type: Utilization
          averageUtilization: 80
```

### MinIO Cluster

For high availability, deploy MinIO in cluster mode:

```bash
# Use MinIO Operator
kubectl apply -f https://github.com/minio/operator/releases/latest/download/minio-operator.yaml
```

---

## Monitoring

### Prometheus ServiceMonitor

```yaml
apiVersion: monitoring.coreos.com/v1
kind: ServiceMonitor
metadata:
  name: minio
  namespace: ratatouille
spec:
  selector:
    matchLabels:
      app: minio
  endpoints:
    - port: api
      path: /minio/v2/metrics/cluster
```

---

## Troubleshooting

### Check Pod Status

```bash
kubectl get pods -n ratatouille
kubectl describe pod dagster-xxx -n ratatouille
kubectl logs dagster-xxx -n ratatouille
```

### Access Services Locally

```bash
# Port forward
kubectl port-forward svc/dagster 3030:3000 -n ratatouille
kubectl port-forward svc/minio 9001:9001 -n ratatouille
```

### Debug Network

```bash
# Test service connectivity
kubectl run debug --rm -it --image=curlimages/curl -n ratatouille -- sh
curl http://minio:9000/minio/health/live
curl http://nessie:19120/api/v2/config
```

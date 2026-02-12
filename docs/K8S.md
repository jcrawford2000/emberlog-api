# Kubernetes Deployment (Kustomize)

This repo includes minimal Kustomize manifests for K3S + Traefik in `k8s/`.

## Apply
```bash
kubectl apply -k k8s/overlays/home
```

## Check Status
```bash
kubectl get pods -n emberlog
kubectl describe ingress -n emberlog emberlog-api
```

## Secret Management
`DATABASE_URL` must come from a Kubernetes Secret.

Recommended command to create the real secret:

```bash
kubectl create secret generic emberlog-api-secrets -n emberlog \
  --from-literal=DATABASE_URL='postgresql://...'
```

A template manifest exists at `k8s/base/secret-template.yaml`.
If you apply that template directly, replace `REPLACE_ME` first.

## Ingress Testing
```bash
curl -H "Host: emberlog-api.pi-rack.com" http://<ingress-ip>/healthz
curl -H "Host: emberlog-api.pi-rack.com" http://<ingress-ip>/readyz
```

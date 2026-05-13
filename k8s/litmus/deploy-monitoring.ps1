
Write-Host "Create monitoring namespace" -ForegroundColor Yellow
kubectl create ns monitoring

Write-Host "Deploying Prometheus components" -ForegroundColor Yellow
kubectl -n monitoring apply -f monitoring/prometheus/prometheus-scrape-configuration/
kubectl -n monitoring apply -f monitoring/metrics-exporters/node-exporter/
kubectl -n monitoring apply -f monitoring/metrics-exporters/kube-state-metrics/

Write-Host "Deploying Litmus chaos-exporter" -ForegroundColor Yellow
kubectl -n litmus apply -f monitoring/metrics-exporters/litmus-metrics/chaos-exporter/



# Apply Grafana
Write-Host "Deploying Grafana" -ForegroundColor Yellow
kubectl -n monitoring apply -f monitoring/prometheus/prometheus-scrape-configuration/
kubectl -n monitoring apply -f monitoring/metrics-exporters/node-exporter/
kubectl -n monitoring apply -f monitoring/metrics-exporters/kube-state-metrics/

kubectl -n litmus apply -f monitoring/metrics-exporters/litmus-metrics/chaos-exporter/

kubectl -n monitoring apply -f monitoring/grafana/


# Prometheus Port Forward it manually to access it via the system ip:9090
# kubectl port-forward -n monitoring --address 0.0.0.0 svc/prometheus-k8s 9090:9090

# Grafana Port Forward it manually to access it via the system ip:3000
# kubectl port-forward -n monitoring --address 0.0.0.0 svc/grafana  3000:3000
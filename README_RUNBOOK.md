# SRD Monitoring (System Radar Dashboard)

This package contains the Flask web app (with RBAC), Grafana HTTP API provisioning, Prometheus/Alertmanager configs, and Windows stress scripts.

## Quick start

1) Install Windows Exporter, Prometheus, Alertmanager, Grafana (local defaults).
2) Start Prometheus with `prometheus/prometheus.yml` (it includes `rules.yml`).
3) Start Alertmanager with `alertmanager/alertmanager.yml` (fill SMTP creds).
4) Create a Grafana **Service Account** token and paste into `backend/.env` (copy from `.env.example`).
5) In `backend/`:
   ```powershell
   python -m venv .venv
   .\.venv\Scripts\activate
   pip install -r requirements.txt
   copy .env.example .env
   notepad .env
   python app.py
   ```
6) Open http://127.0.0.1:5050 → login (first run creates default admin).
7) Admin Console → **Provision** (AJAX) to create datasource/folder/dashboard in Grafana.
8) Admin → **Quick Thresholds (AJAX)** or **Alert Thresholds (Form)** to update rules & reload Prometheus.
9) Use `stress/*.ps1` to trigger alerts.

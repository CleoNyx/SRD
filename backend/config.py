import os
from dotenv import load_dotenv

load_dotenv()

class Settings:
    SECRET_KEY = os.getenv("FLASK_SECRET_KEY", "dev-secret")
    FLASK_HOST = os.getenv("FLASK_HOST", "127.0.0.1")
    FLASK_PORT = int(os.getenv("FLASK_PORT", "5050"))

    GRAFANA_URL = os.getenv("GRAFANA_URL", "http://localhost:3001")
    GRAFANA_TOKEN = os.getenv("GRAFANA_TOKEN")

    PROMETHEUS_URL = os.getenv("PROMETHEUS_URL", "http://localhost:9090")

    GRAFANA_FOLDER_TITLE = os.getenv("GRAFANA_FOLDER_TITLE", "SRD - API Provisioned")
    GRAFANA_DASHBOARD_TITLE = os.getenv("GRAFANA_DASHBOARD_TITLE", "SRD - Network Resources (HTTP API)")

    PROM_RULES_PATH = os.getenv("PROM_RULES_PATH", "prometheus/rules.yml")
    PROM_RELOAD_URL = os.getenv("PROM_RELOAD_URL", "http://localhost:9090/-/reload")
    ALERTMANAGER_RELOAD_URL = os.getenv("ALERTMANAGER_RELOAD_URL", "http://localhost:9093/-/reload")

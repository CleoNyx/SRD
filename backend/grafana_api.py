import json, requests
from typing import Tuple, Any, Dict

def _headers(token: str) -> Dict[str, str]:
    return {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}

def ensure_prometheus_datasource(grafana_url, token, prom_url) -> Tuple[str, str]:
    r = requests.get(f"{grafana_url}/api/datasources", headers=_headers(token), timeout=15)
    r.raise_for_status()
    for ds in r.json():
        if ds.get("type") == "prometheus" and ds.get("url") == prom_url:
            return ds["uid"], ds["name"]
    payload = {
        "name": "Prometheus (SRD)",
        "type": "prometheus",
        "access": "proxy",
        "url": prom_url,
        "basicAuth": False,
        "isDefault": True
    }
    r = requests.post(f"{grafana_url}/api/datasources", headers=_headers(token), data=json.dumps(payload), timeout=15)
    r.raise_for_status()
    return r.json()["datasource"]["uid"], r.json()["datasource"]["name"]

def ensure_folder(grafana_url, token, title) -> str:
    r = requests.get(f"{grafana_url}/api/folders", headers=_headers(token), timeout=15)
    r.raise_for_status()
    for f in r.json():
        if f.get("title") == title:
            return f["uid"]
    r = requests.post(f"{grafana_url}/api/folders", headers=_headers(token),
                      data=json.dumps({"title": title}), timeout=15)
    r.raise_for_status()
    return r.json()["uid"]

def upsert_dashboard(grafana_url, token, folder_uid, dashboard_json, overwrite=True) -> Dict[str, Any]:
    payload = {
        "dashboard": dashboard_json,
        "folderUid": folder_uid,
        "overwrite": overwrite,
        "message": "Provisioned by SRD Flask app"
    }
    r = requests.post(f"{grafana_url}/api/dashboards/db", headers=_headers(token), data=json.dumps(payload), timeout=20)
    r.raise_for_status()
    return r.json()

def list_dashboards(grafana_url, token) -> Any:
    r = requests.get(f"{grafana_url}/api/search?type=dash-db", headers=_headers(token), timeout=15)
    r.raise_for_status()
    return r.json()

def list_datasources(grafana_url, token) -> Any:
    r = requests.get(f"{grafana_url}/api/datasources", headers=_headers(token), timeout=15)
    r.raise_for_status()
    return r.json()

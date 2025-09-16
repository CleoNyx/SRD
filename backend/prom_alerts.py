import os, requests, yaml
from typing import Dict

DEFAULT_THRESHOLDS = {"cpu": 80, "memory": 80, "disk": 80}

def build_rules_yaml(thresholds: Dict[str, int]) -> str:
    t = {**DEFAULT_THRESHOLDS, **thresholds}
    doc = {
        "groups": [{
            "name": "srd_windows_resource_alerts",
            "rules": [
                {
                    "alert": "HighCPU",
                    "expr": f"(100 - (avg by (instance) (irate(windows_cpu_time_total{{mode=\"idle\"}}[5m])) * 100)) > {t['cpu']}",
                    "for": "5m",
                    "labels": {"severity": "warning"},
                    "annotations": {
                        "summary": "High CPU usage",
                        "description": f"CPU usage >{t['cpu']}% for 5 minutes"
                    }
                },
                {
                    "alert": "HighMemory",
                    "expr": f"((1 - (windows_memory_available_bytes / windows_memory_physical_total_bytes)) * 100) > {t['memory']}",
                    "for": "5m",
                    "labels": {"severity": "warning"},
                    "annotations": {
                        "summary": "High Memory usage",
                        "description": f"Memory usage >{t['memory']}% for 5 minutes"
                    }
                },
                {
                    "alert": "HighDisk",
                    "expr": f"(100 - (sum by (instance, volume) (windows_logical_disk_free_bytes) / sum by (instance, volume) (windows_logical_disk_size_bytes) * 100)) > {t['disk']}",
                    "for": "10m",
                    "labels": {"severity": "warning"},
                    "annotations": {
                        "summary": "High Disk usage",
                        "description": f"Disk utilisation >{t['disk']}% for 10 minutes"
                    }
                }
            ]
        }]
    }
    return yaml.dump(doc, sort_keys=False)

def write_rules_and_reload(path: str, yaml_text: str, prom_reload_url: str, alert_reload_url: str):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        f.write(yaml_text)
    requests.post(prom_reload_url, timeout=10)
    try:
        requests.post(alert_reload_url, timeout=10)
    except Exception:
        pass

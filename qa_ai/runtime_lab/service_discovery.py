"""
service_discovery.py - Port probing and HTTP readiness checks.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
import socket
import time
from urllib.request import Request, urlopen
from urllib.error import URLError, HTTPError


class ServiceDiscovery:
    """Detects open ports and waits for service readiness."""

    def detect_open_ports(self, host: str, ports: List[int], timeout_seconds: float = 0.2) -> List[int]:
        open_ports: List[int] = []
        for port in ports:
            if self._is_port_open(host, int(port), timeout_seconds=timeout_seconds):
                open_ports.append(int(port))
        return open_ports

    def wait_for_service(
        self,
        host: str,
        port: int,
        timeout_seconds: float = 30.0,
        health_paths: Optional[List[str]] = None,
    ) -> Dict[str, Any]:
        started_at = datetime.now(timezone.utc).isoformat()
        end_time = time.time() + float(timeout_seconds)
        base_url = f"http://{host}:{int(port)}"
        paths = health_paths or ["/health", "/", "/docs"]
        attempts = 0

        while time.time() < end_time:
            attempts += 1
            if self._is_port_open(host, int(port), timeout_seconds=0.2):
                for path in paths:
                    probe = self._probe_http(f"{base_url}{path}")
                    if probe.get("ok"):
                        return {
                            "ready": True,
                            "base_url": base_url,
                            "path": path,
                            "status_code": probe.get("status_code"),
                            "attempts": attempts,
                            "started_at": started_at,
                            "completed_at": datetime.now(timezone.utc).isoformat(),
                        }
            time.sleep(0.2)

        return {
            "ready": False,
            "base_url": base_url,
            "attempts": attempts,
            "timeout_seconds": timeout_seconds,
            "started_at": started_at,
            "completed_at": datetime.now(timezone.utc).isoformat(),
            "error": "service_readiness_timeout",
        }

    def infer_base_url(self, host: str, ports: List[int]) -> Optional[str]:
        open_ports = self.detect_open_ports(host, ports)
        if not open_ports:
            return None
        return f"http://{host}:{open_ports[0]}"

    def _is_port_open(self, host: str, port: int, timeout_seconds: float = 0.2) -> bool:
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(timeout_seconds)
        try:
            return sock.connect_ex((host, port)) == 0
        finally:
            sock.close()

    def _probe_http(self, url: str) -> Dict[str, Any]:
        request = Request(url, method="GET")
        try:
            with urlopen(request, timeout=2.0) as response:
                return {"ok": True, "status_code": int(response.status)}
        except HTTPError as err:
            return {"ok": True, "status_code": int(err.code)}
        except URLError as err:
            return {"ok": False, "error": str(err.reason)}
        except Exception as err:  # pragma: no cover - defensive path
            return {"ok": False, "error": str(err)}

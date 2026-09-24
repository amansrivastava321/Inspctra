"""
security_engine.py - Safe passive security checking engine for Inspectra.

No network requests, no exploit payloads, no port scans, and no crawling.
Operates purely by analyzing captured HTTP response headers, cookies, and network requests.
"""
from __future__ import annotations

import urllib.parse
from typing import Any, Dict, List, Optional


class SecurityEngine:
    """
    Passive analyzer to identify missing security headers, insecure cookies,
    mixed-content risks, information disclosures, and protocol downgrades.
    """

    @staticmethod
    def analyze_response(
        headers: Dict[str, str],
        url: str,
        original_url: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        findings = []
        parsed = urllib.parse.urlparse(url)
        scheme = parsed.scheme.lower()

        # 1. Insecure http URL warning
        if scheme == "http":
            findings.append({
                "id": "insecure-http",
                "title": "Insecure Connection (HTTP)",
                "severity": "high",
                "description": f"The page navigated to {url} over plain HTTP, exposing traffic to interception.",
                "recommendation": "Migrate the endpoint to HTTPS and enforce TLS.",
                "category": "protocol",
            })

        # 2. Redirect downgrade warning
        if (
            original_url
            and original_url.lower().startswith("https://")
            and url.lower().startswith("http://")
        ):
            findings.append({
                "id": "https-to-http-redirect",
                "title": "HTTPS to HTTP Redirect Downgrade",
                "severity": "high",
                "description": f"The request started on secure HTTPS ({original_url}) but redirected to insecure HTTP ({url}).",
                "recommendation": "Configure redirects to preserve HTTPS security and block downgrades.",
                "category": "protocol",
            })

        # Headers check (normalize keys to lowercase)
        norm_headers = {k.lower(): str(v) for k, v in headers.items()}

        # 3. Content-Security-Policy presence
        if "content-security-policy" not in norm_headers:
            findings.append({
                "id": "missing-csp",
                "title": "Content Security Policy (CSP) Missing",
                "severity": "high",
                "description": "Content-Security-Policy header is missing. This exposes the app to Cross-Site Scripting (XSS) and data injection attacks.",
                "recommendation": "Implement a strong Content-Security-Policy header defining trusted sources for scripts, styles, and other resources.",
                "category": "header",
            })

        # 4. Strict-Transport-Security presence
        if scheme == "https" and "strict-transport-security" not in norm_headers:
            findings.append({
                "id": "missing-hsts",
                "title": "HTTP Strict Transport Security (HSTS) Missing",
                "severity": "medium",
                "description": "Strict-Transport-Security header is missing on HTTPS page. Attackers can perform SSL stripping to downgrade connections to HTTP.",
                "recommendation": "Add the Strict-Transport-Security header with a suitable max-age (e.g., max-age=31536000; includeSubDomains).",
                "category": "header",
            })

        # 5. X-Frame-Options
        if "x-frame-options" not in norm_headers and "frame-ancestors" not in norm_headers.get("content-security-policy", ""):
            findings.append({
                "id": "missing-x-frame-options",
                "title": "X-Frame-Options Header Missing",
                "severity": "medium",
                "description": "X-Frame-Options header (or CSP frame-ancestors directive) is missing. The site can be embedded in an iframe, exposing it to clickjacking attacks.",
                "recommendation": "Set X-Frame-Options to DENY or SAMEORIGIN, or configure frame-ancestors in CSP.",
                "category": "header",
            })

        # 6. X-Content-Type-Options
        x_content = norm_headers.get("x-content-type-options", "").lower()
        if "nosniff" not in x_content:
            findings.append({
                "id": "missing-x-content-type-options",
                "title": "X-Content-Type-Options Header Missing or Invalid",
                "severity": "medium",
                "description": "X-Content-Type-Options is missing or not set to 'nosniff'. This enables MIME-type sniffing, allowing attackers to upload malicious scripts disguised as images.",
                "recommendation": "Set the X-Content-Type-Options header to 'nosniff'.",
                "category": "header",
            })

        # 7. Referrer-Policy
        if "referrer-policy" not in norm_headers:
            findings.append({
                "id": "missing-referrer-policy",
                "title": "Referrer-Policy Header Missing",
                "severity": "low",
                "description": "Referrer-Policy header is missing. Sensitive path or query parameters in the URL may be leaked to third-party sites via the Referer header.",
                "recommendation": "Configure a secure Referrer-Policy header (e.g., no-referrer or strict-origin-when-cross-origin).",
                "category": "header",
            })

        # 8. Permissions-Policy / Feature-Policy
        if "permissions-policy" not in norm_headers and "feature-policy" not in norm_headers:
            findings.append({
                "id": "missing-permissions-policy",
                "title": "Permissions-Policy Header Missing",
                "severity": "low",
                "description": "Permissions-Policy header is missing, allowing access to powerful browser APIs (camera, microphone, geolocation) by default.",
                "recommendation": "Implement a Permissions-Policy header to restrict browser features and access to hardware APIs.",
                "category": "header",
            })

        # 9. Exposed Server Header
        server = norm_headers.get("server")
        if server:
            findings.append({
                "id": "exposed-server",
                "title": "Exposed Server Header",
                "severity": "low",
                "description": f"The Server header is present and exposes software information: '{server}'. This helps attackers identify vulnerabilities.",
                "recommendation": "Configure the web server to remove or obscure the Server header.",
                "category": "information_disclosure",
            })

        # 10. Exposed X-Powered-By
        powered_by = norm_headers.get("x-powered-by")
        if powered_by:
            findings.append({
                "id": "exposed-x-powered-by",
                "title": "Exposed X-Powered-By Header",
                "severity": "low",
                "description": f"The X-Powered-By header exposes backend technology details: '{powered_by}'.",
                "recommendation": "Disable the X-Powered-By header in your application server settings.",
                "category": "information_disclosure",
            })

        # 11. Sensitive headers
        for k in ("x-aspnet-version", "x-aspnetmvc-version", "x-generator"):
            if k in norm_headers:
                findings.append({
                    "id": f"exposed-{k}",
                    "title": f"Exposed {k} Header",
                    "severity": "info",
                    "description": f"The header '{k}' is present and discloses platform configuration details.",
                    "recommendation": "Remove technical fingerprinting headers from responses.",
                    "category": "information_disclosure",
                })

        return findings

    @staticmethod
    def analyze_cookies(cookie_headers: List[str]) -> List[Dict[str, Any]]:
        findings = []
        for cookie_str in cookie_headers:
            if not cookie_str:
                continue
            parts = [p.strip() for p in cookie_str.split(";")]
            if not parts:
                continue
            name_val = parts[0]
            cookie_name = name_val.split("=")[0] if "=" in name_val else name_val

            # Parse attributes
            attrs = {}
            for p in parts[1:]:
                subparts = p.split("=", 1)
                key = subparts[0].lower().strip()
                val = subparts[1].strip() if len(subparts) > 1 else True
                attrs[key] = val

            # Secure flag
            if "secure" not in attrs:
                findings.append({
                    "id": f"cookie-missing-secure-{cookie_name}",
                    "title": f"Cookie Missing Secure Flag: '{cookie_name}'",
                    "severity": "medium",
                    "description": f"The cookie '{cookie_name}' is missing the Secure attribute, allowing it to be transmitted over unencrypted HTTP connections.",
                    "recommendation": "Set the 'Secure' attribute on all sensitive cookies.",
                    "category": "cookie",
                })

            # HttpOnly flag
            if "httponly" not in attrs:
                findings.append({
                    "id": f"cookie-missing-httponly-{cookie_name}",
                    "title": f"Cookie Missing HttpOnly Flag: '{cookie_name}'",
                    "severity": "medium",
                    "description": f"The cookie '{cookie_name}' is missing the HttpOnly attribute, making it accessible to client-side scripts and vulnerable to XSS theft.",
                    "recommendation": "Set the 'HttpOnly' attribute on session cookies and token stores.",
                    "category": "cookie",
                })

            # SameSite flag
            if "samesite" not in attrs:
                findings.append({
                    "id": f"cookie-missing-samesite-{cookie_name}",
                    "title": f"Cookie Missing SameSite Flag: '{cookie_name}'",
                    "severity": "low",
                    "description": f"The cookie '{cookie_name}' does not specify a SameSite attribute, exposing it to Cross-Site Request Forgery (CSRF) risks.",
                    "recommendation": "Set SameSite to 'Lax' or 'Strict' depending on cross-site needs.",
                    "category": "cookie",
                })

        return findings

    @staticmethod
    def analyze_network(
        network_requests: List[Dict[str, Any]], page_url: str
    ) -> List[Dict[str, Any]]:
        findings = []
        parsed_page = urllib.parse.urlparse(page_url)
        page_scheme = parsed_page.scheme.lower()

        for req in network_requests:
            req_url = req.get("url", "")
            if not req_url:
                continue
            parsed_req = urllib.parse.urlparse(req_url)
            req_scheme = parsed_req.scheme.lower()

            # Mixed Content check
            if page_scheme == "https" and req_scheme == "http":
                findings.append({
                    "id": "mixed-content",
                    "title": "Mixed Content Detected",
                    "severity": "high",
                    "description": f"The HTTPS page {page_url} loaded insecure asset {req_url} over plain HTTP.",
                    "recommendation": "Update all asset URLs to use HTTPS protocol.",
                    "category": "mixed_content",
                })

        return findings

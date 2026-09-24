"""
extract_features.py - Production-grade feature extraction engine.
Infers business capabilities, security surfaces, compliance requirements,
and technical features from codebase, routes, APIs, dependencies, and configs.
"""

from pathlib import Path
from typing import Dict, List, Optional, Any, Set, Tuple
from dataclasses import dataclass, field
from enum import Enum
import re
import json
import logging

from qa_ai.agents.file_walker import iter_source_files

logger = logging.getLogger(__name__)


# ─── Data Models ───────────────────────────────────────

class FeatureCategory(Enum):
    """Broad category of feature."""
    BUSINESS = "business"
    SECURITY = "security"
    TECHNICAL = "technical"
    COMPLIANCE = "compliance"
    INTEGRATION = "integration"
    INFRASTRUCTURE = "infrastructure"
    UX = "ux"


class ConfidenceLevel(Enum):
    """Confidence that a feature is actually present."""
    HIGH = "high"       # 0.8-1.0
    MEDIUM = "medium"   # 0.5-0.79
    LOW = "low"         # 0.3-0.49
    SPECULATIVE = "speculative"  # <0.3


@dataclass
class FeatureEvidence:
    """Evidence for a feature being present."""
    file: str
    matched_keywords: List[str]
    confidence: float
    line_number: Optional[int] = None
    context_snippet: Optional[str] = None
    evidence_type: str = "keyword_match"  # keyword_match, dependency, route, api, config


@dataclass
class Feature:
    """A detected feature in the application."""
    name: str
    category: FeatureCategory
    detected: bool = False
    confidence: float = 0.0
    confidence_level: ConfidenceLevel = ConfidenceLevel.SPECULATIVE
    evidence: List[FeatureEvidence] = field(default_factory=list)
    evidence_count: int = 0
    risk_level: Optional[str] = None  # critical, high, medium, low
    related_apis: List[str] = field(default_factory=list)
    related_screens: List[str] = field(default_factory=list)
    dependencies: List[str] = field(default_factory=list)
    description: str = ""

    def to_dict(self) -> dict:
        return {
            "name": self.name,
            "category": self.category.value,
            "detected": self.detected,
            "confidence": self.confidence,
            "confidence_level": self.confidence_level.value,
            "evidence": [self._evidence_to_dict(e) for e in self.evidence[:20]],
            "evidence_count": self.evidence_count,
            "risk_level": self.risk_level,
            "related_apis": self.related_apis[:10],
            "related_screens": self.related_screens[:10],
            "dependencies": self.dependencies,
            "description": self.description,
        }

    def _evidence_to_dict(self, e: FeatureEvidence) -> dict:
        return {
            "file": e.file,
            "matched_keywords": e.matched_keywords,
            "confidence": e.confidence,
            "line_number": e.line_number,
            "context_snippet": e.context_snippet,
            "type": e.evidence_type,
        }


# ─── Feature Definitions ───────────────────────────────

# Each feature has: name, category, keywords, risk_level, dependencies, file_patterns
FEATURE_DEFINITIONS: Dict[str, dict] = {
    # ─── Business Features ──────────────────────────
    "authentication": {
        "category": FeatureCategory.BUSINESS,
        "risk_level": "critical",
        "keywords": [
            "login", "logout", "signup", "sign_up", "register", "create_account",
            "otp", "one_time_password", "password", "passcode", "token",
            "jwt", "json_web_token", "oauth", "openid", "sso", "single_sign_on",
            "two_factor", "2fa", "mfa", "multi_factor", "biometric",
            "fingerprint", "face_id", "touch_id",
        ],
        "file_patterns": [
            r".*auth.*\.(dart|ts|tsx|js|jsx|py)$",
            r".*login.*\.(dart|ts|tsx|js|jsx|py)$",
            r".*signup.*\.(dart|ts|tsx|js|jsx|py)$",
        ],
        "dependencies": [
            "firebase_auth", "auth0", "next-auth", "passport", "devise",
            "omniauth", "spring-security", "django-allauth", "flask-login",
        ],
        "description": "User authentication and session management",
    },
    
    "authorization": {
        "category": FeatureCategory.SECURITY,
        "risk_level": "critical",
        "keywords": [
            "role", "permission", "acl", "access_control", "rbac",
            "can_activate", "auth_guard", "protected_route", "private_route",
            "admin_only", "moderator", "superuser", "staff",
            "ability", "policy", "scope", "claims",
        ],
        "file_patterns": [
            r".*guard.*\.(dart|ts|tsx|js|jsx|py)$",
            r".*permission.*\.(dart|ts|tsx|js|jsx|py)$",
            r".*role.*\.(dart|ts|tsx|js|jsx|py)$",
        ],
        "dependencies": [],
        "description": "Role-based access control and authorization",
    },
    
    "payments": {
        "category": FeatureCategory.BUSINESS,
        "risk_level": "critical",
        "keywords": [
            "payment", "checkout", "stripe", "razorpay", "paypal",
            "invoice", "billing", "subscription", "plan", "pricing",
            "charge", "refund", "transaction", "receipt",
            "credit_card", "debit_card", "upi", "wallet",
            "idempotency", "payment_intent", "payment_method",
        ],
        "file_patterns": [
            r".*payment.*\.(dart|ts|tsx|js|jsx|py|rb)$",
            r".*billing.*\.(dart|ts|tsx|js|jsx|py|rb)$",
            r".*checkout.*\.(dart|ts|tsx|js|jsx|py|rb)$",
            r".*invoice.*\.(dart|ts|tsx|js|jsx|py|rb)$",
        ],
        "dependencies": [
            "stripe", "flutter_stripe", "stripe_sdk", "razorpay_flutter",
            "@stripe/stripe-js", "react-stripe-js", "django-stripe",
        ],
        "description": "Payment processing and billing",
    },
    
    "admin_panel": {
        "category": FeatureCategory.BUSINESS,
        "risk_level": "high",
        "keywords": [
            "admin", "administrator", "dashboard", "staff", "moderator",
            "manage", "management", "superuser", "impersonate",
            "audit_log", "activity_log", "user_management",
        ],
        "file_patterns": [
            r".*admin.*\.(dart|ts|tsx|js|jsx|py|rb)$",
            r".*dashboard.*\.(dart|ts|tsx|js|jsx|py|rb)$",
        ],
        "dependencies": ["django-admin", "activeadmin", "rails_admin"],
        "description": "Administrative interface for managing the application",
    },
    
    "user_profile": {
        "category": FeatureCategory.BUSINESS,
        "risk_level": "medium",
        "keywords": [
            "profile", "account", "settings", "preferences",
            "avatar", "display_name", "username", "bio",
            "edit_profile", "update_profile", "change_password",
        ],
        "file_patterns": [
            r".*profile.*\.(dart|ts|tsx|js|jsx|py)$",
            r".*account.*\.(dart|ts|tsx|js|jsx|py)$",
            r".*settings.*\.(dart|ts|tsx|js|jsx|py)$",
        ],
        "dependencies": [],
        "description": "User profile management and settings",
    },
    
    "notifications": {
        "category": FeatureCategory.BUSINESS,
        "risk_level": "low",
        "keywords": [
            "notification", "push", "fcm", "firebase_messaging",
            "apns", "alert", "toast", "snackbar", "banner",
            "email", "smtp", "sendgrid", "mailgun", "ses",
            "in_app", "webhook",
        ],
        "file_patterns": [
            r".*notification.*\.(dart|ts|tsx|js|jsx|py)$",
            r".*push.*\.(dart|ts|tsx|js|jsx|py)$",
        ],
        "dependencies": [
            "firebase_messaging", "flutter_local_notifications",
            "sendgrid", "nodemailer", "django-notifications",
        ],
        "description": "Push notifications, email alerts, and in-app notifications",
    },
    
    "chat_messaging": {
        "category": FeatureCategory.BUSINESS,
        "risk_level": "medium",
        "keywords": [
            "chat", "message", "messaging", "conversation", "thread",
            "websocket", "socket.io", "stream", "realtime",
            "typing_indicator", "read_receipt", "attachment",
        ],
        "file_patterns": [
            r".*chat.*\.(dart|ts|tsx|js|jsx|py)$",
            r".*message.*\.(dart|ts|tsx|js|jsx|py)$",
        ],
        "dependencies": ["socket.io", "websocket", "pusher", "ably"],
        "description": "Real-time chat and messaging",
    },
    
    "file_management": {
        "category": FeatureCategory.BUSINESS,
        "risk_level": "high",
        "keywords": [
            "upload", "download", "file_picker", "image_picker",
            "multipart", "document", "attachment", "media",
            "gallery", "camera", "photo", "video",
            "storage", "s3", "cloudinary", "firebase_storage",
        ],
        "file_patterns": [
            r".*upload.*\.(dart|ts|tsx|js|jsx|py)$",
            r".*file.*\.(dart|ts|tsx|js|jsx|py)$",
        ],
        "dependencies": [
            "file_picker", "image_picker", "firebase_storage",
            "boto3", "cloudinary", "multer",
        ],
        "description": "File upload, download, and media management",
    },
    
    # ─── Technical Features ─────────────────────────
    "offline_support": {
        "category": FeatureCategory.TECHNICAL,
        "risk_level": "medium",
        "keywords": [
            "offline", "sync", "queue", "local", "cache",
            "persist", "drift", "sqlite", "hive", "shared_preferences",
            "async_storage", "realm", "watermelondb",
            "background_sync", "connectivity", "network_aware",
        ],
        "file_patterns": [
            r".*offline.*\.(dart|ts|tsx|js|jsx)$",
            r".*sync.*\.(dart|ts|tsx|js|jsx)$",
            r".*cache.*\.(dart|ts|tsx|js|jsx)$",
        ],
        "dependencies": ["drift", "hive", "sqlite", "realm", "pouchdb"],
        "description": "Offline-first architecture with data synchronization",
    },
    
    "real_time": {
        "category": FeatureCategory.TECHNICAL,
        "risk_level": "low",
        "keywords": [
            "realtime", "real_time", "websocket", "socket",
            "stream", "subscription", "pubsub", "pub_sub",
            "firebase_realtime", "firestore", "supabase_realtime",
            "graphql_subscription", "server_sent_events", "sse",
        ],
        "file_patterns": [],
        "dependencies": [
            "socket.io", "graphql-ws", "firebase_database",
            "supabase_realtime", "ably", "pusher",
        ],
        "description": "Real-time data synchronization and live updates",
    },
    
    "search": {
        "category": FeatureCategory.TECHNICAL,
        "risk_level": "low",
        "keywords": [
            "search", "filter", "sort", "query", "elasticsearch",
            "algolia", "full_text", "fuzzy", "autocomplete",
            "typeahead", "suggest",
        ],
        "file_patterns": [
            r".*search.*\.(dart|ts|tsx|js|jsx|py)$",
            r".*filter.*\.(dart|ts|tsx|js|jsx|py)$",
        ],
        "dependencies": ["elasticsearch", "algolia", "meilisearch", "typesense"],
        "description": "Search and filtering functionality",
    },
    
    "analytics": {
        "category": FeatureCategory.TECHNICAL,
        "risk_level": "low",
        "keywords": [
            "analytics", "tracking", "event", "metric", "funnel",
            "mixpanel", "segment", "amplitude", "firebase_analytics",
            "google_analytics", "gtag", "heap", "posthog",
        ],
        "file_patterns": [],
        "dependencies": [
            "firebase_analytics", "mixpanel_flutter", "segment",
            "@amplitude/analytics-browser", "posthog-js",
        ],
        "description": "User behavior analytics and event tracking",
    },
    
    "crash_reporting": {
        "category": FeatureCategory.TECHNICAL,
        "risk_level": "low",
        "keywords": [
            "crash", "error_reporting", "sentry", "bugsnag",
            "firebase_crashlytics", "crashlytics", "log",
            "exception", "stack_trace", "fatal",
        ],
        "file_patterns": [],
        "dependencies": [
            "firebase_crashlytics", "sentry_flutter", "sentry",
            "@sentry/react", "bugsnag",
        ],
        "description": "Crash reporting and error monitoring",
    },
    
    "maps_location": {
        "category": FeatureCategory.TECHNICAL,
        "risk_level": "low",
        "keywords": [
            "map", "maps", "location", "geolocation", "gps",
            "latitude", "longitude", "coordinate", "geocoding",
            "google_maps", "mapbox", "openstreetmap", "osm",
            "marker", "polyline", "region", "radius",
        ],
        "file_patterns": [
            r".*map.*\.(dart|ts|tsx|js|jsx)$",
            r".*location.*\.(dart|ts|tsx|js|jsx)$",
        ],
        "dependencies": [
            "google_maps_flutter", "mapbox_gl", "location",
            "geolocator", "react-native-maps", "leaflet",
        ],
        "description": "Maps, geolocation, and location-based features",
    },
    
    "ai_ml": {
        "category": FeatureCategory.TECHNICAL,
        "risk_level": "medium",
        "keywords": [
            "openai", "ollama", "llm", "gpt", "gemini", "claude",
            "machine_learning", "ml", "model", "inference",
            "embedding", "vector", "rag", "retrieval_augmented",
            "transformer", "neural", "classification", "prediction",
            "chatgpt", "copilot", "anthropic", "langchain", "llamaindex",
        ],
        "file_patterns": [
            r".*ai.*\.(dart|ts|tsx|js|jsx|py)$",
            r".*llm.*\.(dart|ts|tsx|js|jsx|py)$",
            r".*ml.*\.py$",
        ],
        "dependencies": [
            "openai", "langchain", "llamaindex", "transformers",
            "chromadb", "pinecone", "weaviate", "qdrant",
        ],
        "description": "AI/ML features, LLM integration, embeddings",
    },
    
    "i18n": {
        "category": FeatureCategory.TECHNICAL,
        "risk_level": "low",
        "keywords": [
            "i18n", "internationalization", "localization", "l10n",
            "locale", "language", "translation", "translate",
            "arb", "json_translations", "gettext", "lingui",
        ],
        "file_patterns": [
            r".*i18n.*\.(dart|ts|tsx|js|jsx)$",
            r".*localization.*\.(dart|ts|tsx|js|jsx)$",
            r".*translation.*\.(dart|ts|tsx|js|jsx|py)$",
        ],
        "dependencies": [
            "flutter_localizations", "easy_localization",
            "react-i18next", "i18next", "django-modeltranslation",
        ],
        "description": "Internationalization and multi-language support",
    },
    
    "dark_mode": {
        "category": FeatureCategory.UX,
        "risk_level": "low",
        "keywords": [
            "dark_mode", "dark_theme", "theme_mode", "theme",
            "light_mode", "system_theme", "appearance",
            "brightness", "color_scheme",
        ],
        "file_patterns": [
            r".*theme.*\.(dart|ts|tsx|js|jsx)$",
            r".*dark.*\.(dart|ts|tsx|js|jsx)$",
        ],
        "dependencies": [],
        "description": "Dark mode and theme switching support",
    },
    
    "accessibility": {
        "category": FeatureCategory.UX,
        "risk_level": "medium",
        "keywords": [
            "accessibility", "a11y", "screen_reader", "semantics",
            "aria", "role", "focus", "keyboard_navigation",
            "contrast", "wcag", "talkback", "voiceover",
        ],
        "file_patterns": [],
        "dependencies": [],
        "description": "Accessibility features and WCAG compliance",
    },
    
    # ─── Compliance Features ────────────────────────
    "gdpr_compliance": {
        "category": FeatureCategory.COMPLIANCE,
        "risk_level": "critical",
        "keywords": [
            "gdpr", "consent", "cookie_consent", "data_protection",
            "privacy_policy", "terms_of_service", "data_retention",
            "right_to_delete", "data_export", "pii",
            "personally_identifiable", "opt_in", "opt_out",
        ],
        "file_patterns": [
            r".*privacy.*\.(dart|ts|tsx|js|jsx|py)$",
            r".*consent.*\.(dart|ts|tsx|js|jsx|py)$",
            r".*gdpr.*\.(dart|ts|tsx|js|jsx|py)$",
        ],
        "dependencies": [],
        "description": "GDPR compliance: consent, data protection, privacy",
    },
    
    "pci_compliance": {
        "category": FeatureCategory.COMPLIANCE,
        "risk_level": "critical",
        "keywords": [
            "pci", "pci_dss", "cardholder_data", "pan",
            "tokenization", "vault", "secure_payment",
        ],
        "file_patterns": [],
        "dependencies": ["stripe", "braintree", "adyen"],
        "description": "PCI DSS compliance for payment processing",
    },
    
    # ─── Integration Features ───────────────────────
    "third_party_auth": {
        "category": FeatureCategory.INTEGRATION,
        "risk_level": "high",
        "keywords": [
            "google_sign_in", "facebook_login", "apple_sign_in",
            "twitter_login", "github_login", "microsoft_login",
            "social_login", "oauth", "oidc",
        ],
        "file_patterns": [],
        "dependencies": [
            "google_sign_in", "flutter_facebook_auth", "sign_in_with_apple",
            "next-auth", "@auth0/nextjs-auth0",
        ],
        "description": "Third-party social authentication",
    },
    
    "cdn": {
        "category": FeatureCategory.INFRASTRUCTURE,
        "risk_level": "low",
        "keywords": [
            "cdn", "cloudfront", "cloudinary", "imgix",
            "fastly", "akamai", "bunny", "image_optimization",
        ],
        "file_patterns": [],
        "dependencies": ["cloudinary", "imgix"],
        "description": "Content Delivery Network for assets",
    },
}


# ─── Main Extractor ──────────────────────────────────

class FeatureExtractor:
    """Production-grade feature extraction from codebase analysis."""

    def __init__(self, app_path: Path, stack_info: Optional[dict] = None):
        self.app_path = Path(app_path)
        self.stack = stack_info or {}
        self.features: Dict[str, Feature] = {}
        self._init_features()

    def _init_features(self):
        """Initialize all features from definitions."""
        for name, definition in FEATURE_DEFINITIONS.items():
            self.features[name] = Feature(
                name=name,
                category=definition["category"],
                risk_level=definition.get("risk_level"),
                description=definition.get("description", ""),
                dependencies=definition.get("dependencies", []),
            )

    def extract(self) -> dict:
        """Extract all features from the codebase."""
        logger.info(f"Extracting features from {self.app_path}")

        # Phase 1: Scan files for keyword matches
        self._scan_files_for_keywords()

        # Phase 2: Check dependencies from stack info
        self._check_dependencies()

        # Phase 3: Check routes and APIs (if available)
        self._check_routes_and_apis()

        # Phase 4: Calculate final confidence and detection status
        self._finalize_features()

        logger.info(f"Feature extraction complete: "
                     f"{sum(1 for f in self.features.values() if f.detected)} detected")

        return self._to_dict()

    def _scan_files_for_keywords(self):
        """Scan all source files for feature keywords."""
        # Precompile regex patterns for performance
        feature_patterns = {}
        for name, definition in FEATURE_DEFINITIONS.items():
            keywords = definition.get("keywords", [])
            file_patterns = definition.get("file_patterns", [])
            if keywords:
                # Create a combined regex for all keywords
                pattern = re.compile(
                    r'\b(' + '|'.join(re.escape(kw) for kw in keywords) + r')\b',
                    re.IGNORECASE
                )
                feature_patterns[name] = {
                    "keyword_pattern": pattern,
                    "file_patterns": [re.compile(fp, re.IGNORECASE) for fp in file_patterns],
                }

        for file_path in iter_source_files(self.app_path):
            try:
                content = file_path.read_text(errors="ignore")
                content_lower = content.lower()
                rel_path = str(file_path.relative_to(self.app_path))
                lines = content.split("\n")

                for name, patterns in feature_patterns.items():
                    # Check file name patterns first (fast rejection/promotion)
                    file_matches_pattern = any(
                        fp.match(file_path.name) for fp in patterns["file_patterns"]
                    )

                    # Find keyword matches
                    matches = patterns["keyword_pattern"].findall(content_lower)
                    unique_matches = list(set(m.lower() for m in matches))

                    if unique_matches or file_matches_pattern:
                        # Find line number of first match
                        line_number = None
                        context = None
                        if unique_matches:
                            for i, line in enumerate(lines):
                                if any(kw in line.lower() for kw in unique_matches):
                                    line_number = i + 1
                                    context = line.strip()[:200]
                                    break

                        # Calculate evidence confidence
                        evidence_confidence = self._calculate_keyword_confidence(
                            unique_matches, file_matches_pattern
                        )

                        evidence = FeatureEvidence(
                            file=rel_path,
                            matched_keywords=sorted(unique_matches) if unique_matches else ["file_pattern_match"],
                            confidence=evidence_confidence,
                            line_number=line_number,
                            context_snippet=context,
                            evidence_type="keyword_match",
                        )

                        self.features[name].evidence.append(evidence)

            except Exception as e:
                logger.debug(f"Error scanning {file_path}: {e}")
                continue

    def _check_dependencies(self):
        """Check if declared dependencies confirm features."""
        raw_deps = self.stack.get("raw_dependencies", [])
        if not raw_deps:
            return

        deps_lower = [d.lower() for d in raw_deps]

        for name, definition in FEATURE_DEFINITIONS.items():
            feature_deps = definition.get("dependencies", [])
            matched_deps = [
                dep for dep in feature_deps
                if any(dep.lower() in d for d in deps_lower)
            ]

            if matched_deps:
                evidence = FeatureEvidence(
                    file="pubspec.yaml / package.json / requirements.txt",
                    matched_keywords=matched_deps,
                    confidence=0.85,  # Dependency match is strong evidence
                    evidence_type="dependency",
                )
                self.features[name].evidence.append(evidence)
                self.features[name].dependencies.extend(matched_deps)

    def _check_routes_and_apis(self):
        """Check routes and APIs for feature evidence."""
        routes = self.stack.get("routes", [])
        apis = self.stack.get("api_endpoints", [])

        for name, definition in FEATURE_DEFINITIONS.items():
            keywords = [kw.lower() for kw in definition.get("keywords", [])]

            # Check routes
            for route in routes:
                route_path = (route.get("path") or route.get("route") or "").lower()
                route_name = (route.get("name", "")).lower()
                combined = route_path + " " + route_name

                matched = [kw for kw in keywords if kw in combined]
                if matched:
                    self.features[name].related_screens.append(
                        route_path or route_name
                    )
                    evidence = FeatureEvidence(
                        file=route.get("file", "unknown"),
                        matched_keywords=matched,
                        confidence=0.7,
                        evidence_type="route",
                    )
                    self.features[name].evidence.append(evidence)

            # Check APIs
            for api in apis:
                api_path = api.get("path", "").lower()
                api_method = api.get("method", "")

                matched = [kw for kw in keywords if kw in api_path]
                if matched:
                    self.features[name].related_apis.append(
                        f"{api_method} {api_path}"
                    )
                    evidence = FeatureEvidence(
                        file=api.get("file", "unknown"),
                        matched_keywords=matched,
                        confidence=0.75,
                        evidence_type="api",
                    )
                    self.features[name].evidence.append(evidence)

    def _calculate_keyword_confidence(
        self,
        matches: List[str],
        file_pattern_match: bool,
    ) -> float:
        """Calculate confidence for keyword-based evidence."""
        score = 0.0

        # More unique keywords = higher confidence
        unique_count = len(set(matches))
        if unique_count >= 5:
            score = 0.9
        elif unique_count >= 3:
            score = 0.7
        elif unique_count >= 2:
            score = 0.5
        elif unique_count == 1:
            score = 0.3

        # File pattern match boosts confidence
        if file_pattern_match:
            score = min(score + 0.2, 1.0)

        return score

    def _finalize_features(self):
        """Calculate final detection status and confidence for each feature."""
        for name, feature in self.features.items():
            definition = FEATURE_DEFINITIONS.get(name, {})
            evidence_list = feature.evidence

            if not evidence_list:
                feature.detected = False
                feature.confidence = 0.0
                feature.confidence_level = ConfidenceLevel.SPECULATIVE
                continue

            # Weight evidence by type
            weighted_score = 0.0
            total_weight = 0.0

            evidence_weights = {
                "dependency": 1.5,    # Dependencies are strong signals
                "keyword_match": 1.0,
                "route": 0.8,
                "api": 0.9,
                "config": 1.2,
            }

            for evidence in evidence_list:
                weight = evidence_weights.get(evidence.evidence_type, 1.0)
                weighted_score += evidence.confidence * weight
                total_weight += weight

            # Normalize
            if total_weight > 0:
                feature.confidence = min(weighted_score / total_weight, 1.0)
            else:
                feature.confidence = 0.0

            # Boost confidence based on evidence variety
            evidence_types = set(e.evidence_type for e in evidence_list)
            if len(evidence_types) >= 3:
                feature.confidence = min(feature.confidence + 0.15, 1.0)
            elif len(evidence_types) >= 2:
                feature.confidence = min(feature.confidence + 0.1, 1.0)

            # Set detection status
            feature.detected = feature.confidence >= 0.3
            feature.evidence_count = len(evidence_list)

            # Set confidence level
            if feature.confidence >= 0.8:
                feature.confidence_level = ConfidenceLevel.HIGH
            elif feature.confidence >= 0.5:
                feature.confidence_level = ConfidenceLevel.MEDIUM
            elif feature.confidence >= 0.3:
                feature.confidence_level = ConfidenceLevel.LOW
            else:
                feature.confidence_level = ConfidenceLevel.SPECULATIVE

            # Cap evidence list
            feature.evidence = feature.evidence[:20]

    def _to_dict(self) -> dict:
        """Convert features to dictionary format."""
        features_dict = {}
        for name, feature in self.features.items():
            features_dict[name] = feature.to_dict()

        # Summary
        detected = [f for f in self.features.values() if f.detected]
        high_confidence = [f for f in detected if f.confidence_level == ConfidenceLevel.HIGH]
        critical_risk = [f for f in detected if f.risk_level == "critical"]

        return {
            "features": features_dict,
            "summary": {
                "total_defined": len(self.features),
                "total_detected": len(detected),
                "high_confidence": len(high_confidence),
                "medium_confidence": len([f for f in detected if f.confidence_level == ConfidenceLevel.MEDIUM]),
                "low_confidence": len([f for f in detected if f.confidence_level == ConfidenceLevel.LOW]),
                "critical_risk_features": [f.name for f in critical_risk],
                "detected_features": [
                    {
                        "name": f.name,
                        "category": f.category.value,
                        "confidence": f.confidence,
                        "risk_level": f.risk_level,
                    }
                    for f in sorted(detected, key=lambda x: x.confidence, reverse=True)
                ],
            },
        }


# ─── Wrapper ────────────────────────────────────────

def extract_features(app_path: Path, stack_info: Optional[dict] = None) -> dict:
    """Main entry point. Returns structured feature map."""
    extractor = FeatureExtractor(Path(app_path), stack_info)
    return extractor.extract()


# ─── CLI ────────────────────────────────────────────

if __name__ == "__main__":
    import sys
    from pprint import pprint

    logging.basicConfig(level=logging.INFO, format="%(message)s")

    if len(sys.argv) < 2:
        print("Usage: python extract_features.py /path/to/app [stack_json]")
        sys.exit(1)

    app_path = Path(sys.argv[1])
    stack_info = json.loads(sys.argv[2]) if len(sys.argv) > 2 else {}

    result = extract_features(app_path, stack_info)
    pprint(result["summary"])
"""
scan_screens.py - Production-grade screen/page/component scanner.
Detects UI screens, pages, views, widgets, and components across
all major frameworks. Provides confidence scoring, auth detection,
and framework-specific heuristics.
"""

from pathlib import Path
from typing import List, Dict, Optional, Any
from dataclasses import dataclass, field
from enum import Enum
import re
import logging

from qa_ai.agents.file_walker import iter_source_files
from qa_ai.agents.constants import SOURCE_EXTENSIONS

logger = logging.getLogger(__name__)


# ─── Data Models ───────────────────────────────────────

class ScreenType(Enum):
    SCREEN = "screen"
    PAGE = "page"
    COMPONENT = "component"
    WIDGET = "widget"
    LAYOUT = "layout"
    DIALOG = "dialog"
    BOTTOM_SHEET = "bottom_sheet"
    TAB = "tab"
    DRAWER = "drawer"
    UNKNOWN = "unknown"


class AuthRequirement(Enum):
    REQUIRED = "required"
    OPTIONAL = "optional"
    NONE = "none"
    UNKNOWN = "unknown"


@dataclass
class Screen:
    """A single screen/page/component in the application."""
    name: str
    file_path: str
    screen_type: ScreenType = ScreenType.UNKNOWN
    route: Optional[str] = None
    route_name: Optional[str] = None
    auth_required: AuthRequirement = AuthRequirement.UNKNOWN
    line_number: Optional[int] = None
    parent_screen: Optional[str] = None
    children: List[str] = field(default_factory=list)
    has_form: bool = False
    has_list: bool = False
    has_navigation: bool = False
    state_management: Optional[str] = None
    imports: List[str] = field(default_factory=list)
    confidence: float = 0.0
    framework: Optional[str] = None

    def to_dict(self) -> dict:
        return {
            "name": self.name,
            "file": self.file_path,
            "type": self.screen_type.value,
            "path": self.route,
            "route": self.route_name or self.route,
            "auth_required": (
                True if self.auth_required == AuthRequirement.REQUIRED
                else False if self.auth_required == AuthRequirement.NONE
                else None
            ),
            "line": self.line_number,
            "parent": self.parent_screen,
            "children": self.children,
            "has_form": self.has_form,
            "has_list": self.has_list,
            "has_navigation": self.has_navigation,
            "state_management": self.state_management,
            "confidence": self.confidence,
            "framework": self.framework,
        }


# ─── Framework-Specific Constants ──────────────────────

# Keywords that indicate a file defines a screen/page
SCREEN_INDICATORS = {
    # Generic
    "screen": ScreenType.SCREEN,
    "page": ScreenType.PAGE,
    "view": ScreenType.SCREEN,
    "component": ScreenType.COMPONENT,
    "widget": ScreenType.WIDGET,
    "layout": ScreenType.LAYOUT,
    "dialog": ScreenType.DIALOG,
    "modal": ScreenType.DIALOG,
    "bottomsheet": ScreenType.BOTTOM_SHEET,
    "tab": ScreenType.TAB,
    "drawer": ScreenType.DRAWER,
    "panel": ScreenType.COMPONENT,
    "form": ScreenType.COMPONENT,
    "section": ScreenType.COMPONENT,
}

# Framework-specific class/function patterns that define screens
SCREEN_DEFINITION_PATTERNS = {
    "flutter": [
        r'class\s+(\w+)\s+extends\s+StatelessWidget',
        r'class\s+(\w+)\s+extends\s+StatefulWidget',
        r'class\s+(\w+)\s+extends\s+ConsumerWidget',
        r'class\s+(\w+)\s+extends\s+HookWidget',
        r'class\s+(\w+)\s+extends\s+ConsumerStatefulWidget',
    ],
    "react": [
        r'(?:export\s+)?(?:default\s+)?function\s+(\w+)\s*\([^)]*\)\s*\{',
        r'(?:export\s+)?const\s+(\w+)\s*[:=]\s*(?:\([^)]*\)|React\.FC)',
        r'class\s+(\w+)\s+extends\s+(?:React\.)?(?:Component|PureComponent)',
    ],
    "nextjs": [
        r'(?:export\s+)?(?:default\s+)?function\s+(\w+)\s*\([^)]*\)\s*\{',
        r'(?:export\s+)?const\s+(\w+)\s*[:=]\s*(?:\([^)]*\)|React\.FC)',
        r'export\s+default\s+function\s+(\w+)',
    ],
    "vue": [
        r'(?:export\s+)?default\s*\{',
        r'defineComponent\s*\(',
        r'<script\s+setup',
    ],
    "angular": [
        r'@Component\s*\(',
        r'class\s+(\w+)\s+implements\s+OnInit',
        r'export\s+class\s+(\w+Component)',
    ],
    "swiftui": [
        r'struct\s+(\w+)\s*:\s*View',
        r'struct\s+(\w+)\s*:\s*View\s*\{',
    ],
    "jetpack_compose": [
        r'@Composable\s*\n\s*fun\s+(\w+)',
        r'@Composable\s+fun\s+(\w+)\s*\(',
    ],
}

# Route extraction patterns per framework
ROUTE_PATTERNS = {
    "flutter": [
        (r"path\s*:\s*['\"]([^'\"]+)['\"]", "go_router"),
        (r"route\s*[:=]\s*['\"]([^'\"]+)['\"]", "named"),
        (r"@page\s*\(\s*['\"]([^'\"]+)['\"]", "auto_route"),
        (r"@MaterialRoute\s*\(\s*path\s*:\s*['\"]([^'\"]+)['\"]", "auto_route"),
    ],
    "react": [
        (r'path\s*[:=]\s*["\'`]([^"\'`]+)["\'`]', "react_router"),
        (r'element\s*[:=]\s*<(\w+)', "react_router"),
        (r'to\s*[:=]\s*["\'`]([^"\'`]+)["\'`]', "link"),
    ],
    "nextjs": [
        # File-system based routes are handled separately
        (r'useRouter\(\)', "next_router"),
        (r'router\.push\s*\(\s*["\'`]([^"\'`]+)["\'`]', "next_navigation"),
    ],
    "vue": [
        (r'path\s*:\s*["\'`]([^"\'`]+)["\'`]', "vue_router"),
        (r'name\s*:\s*["\'`]([^"\'`]+)["\'`]', "vue_router_name"),
    ],
    "angular": [
        (r'path\s*:\s*["\'`]([^"\'`]+)["\'`]', "angular_router"),
    ],
    "swiftui": [
        (r'NavigationLink\s*\(\s*destination\s*:\s*(\w+)', "navigation_link"),
        (r'\.navigationTitle\s*\(\s*"([^"]+)"', "title"),
    ],
}

# Auth detection keywords
AUTH_REQUIRED_KEYWORDS = [
    "authguard", "requiresauth", "requireauth", "authenticated",
    "protectedroute", "privateroute", "authrequired", "isauthorized",
    "canactivate", "auth_guard", "require_authentication",
    "redirectifnotauthenticated", "withauth", "authed",
]

AUTH_NONE_KEYWORDS = [
    "publicroute", "public_page", "guest", "unauthenticated",
    "login", "signup", "register", "signin", "sign_in",
    "createaccount", "forgotpassword", "resetpassword",
]

# Form detection patterns
FORM_PATTERNS = [
    r'Form\s*\(',
    r'<form',
    r'formKey',
    r'GlobalKey<FormState>',
    r'FormState',
    r'useForm\s*\(',
    r'react-hook-form',
    r'Formik',
    r'TextField\s*\(',
    r'TextFormField\s*\(',
    r'<input',
    r'<textarea',
    r'<select',
    r'TextInput\s*\(',
]

# List detection patterns
LIST_PATTERNS = [
    r'ListView\s*\(',
    r'List\.builder',
    r'RecyclerView',
    r'FlatList',
    r'SectionList',
    r'<ul',
    r'<ol',
    r'\.map\s*\(',
    r'forEach\s*\(',
    r'v-for',
    r'\*ngFor',
]

# Navigation detection patterns
NAVIGATION_PATTERNS = [
    r'Navigator\.',
    r'router\.',
    r'useRouter',
    r'useNavigate',
    r'navigate\s*\(',
    r'history\.',
    r'NavigationLink',
    r'Link\s+to=',
    r'routerLink',
    r'router-link',
    r'\.push\s*\(',
    r'\.replace\s*\(',
    r'\.go\s*\(',
    r'\.back\s*\(',
]


# ─── Main Scanner ────────────────────────────────────

class ScreenScanner:
    """Production-grade screen/page/component scanner."""

    def __init__(self, app_path: Path, stack_info: Optional[dict] = None):
        self.app_path = Path(app_path)
        self.stack = stack_info or {}
        self.framework = self.stack.get("framework", "unknown")
        self.language = self.stack.get("language", "unknown")
        self.screens: List[Screen] = []

    def scan_all(self) -> dict:
        """Scan all source files for screens, pages, and components."""
        logger.info(f"Scanning screens in {self.app_path} (framework: {self.framework})")

        for file_path in iter_source_files(self.app_path):
            try:
                screen = self._analyze_file(file_path)
                if screen and screen.confidence >= 0.3:  # Minimum confidence threshold
                    self.screens.append(screen)
            except Exception as e:
                logger.debug(f"Error scanning {file_path}: {e}")
                continue

        # Post-processing
        self._deduplicate()
        self._link_navigation()
        self._calculate_auth_stats()

        logger.info(f"Found {len(self.screens)} screens/pages/components")

        return {
            "screens": [s.to_dict() for s in self.screens],
            "total_screens": len(self.screens),
            "auth_protected_screens": len([
                s for s in self.screens
                if s.auth_required == AuthRequirement.REQUIRED
            ]),
            "unprotected_screens": len([
                s for s in self.screens
                if s.auth_required == AuthRequirement.NONE
            ]),
            "unknown_auth_screens": len([
                s for s in self.screens
                if s.auth_required == AuthRequirement.UNKNOWN
            ]),
            "components": len([
                s for s in self.screens
                if s.screen_type in (ScreenType.COMPONENT, ScreenType.WIDGET)
            ]),
        }

    def _analyze_file(self, file_path: Path) -> Optional[Screen]:
        """Analyze a single file and return a Screen if it defines one."""
        name_lower = file_path.name.lower()
        file_stem = file_path.stem

        # Quick rejection: file name must contain a screen indicator
        has_indicator = any(
            keyword in name_lower for keyword in SCREEN_INDICATORS
        )
        if not has_indicator:
            return None

        # Read content
        try:
            content = file_path.read_text(errors="ignore")
        except Exception as e:
            logger.debug("Failed to read file %s: %s", file_path, e)
            return None

        rel_path = str(file_path.relative_to(self.app_path))
        lines = content.split("\n")

        # Determine screen type
        screen_type = self._classify_screen_type(file_stem, content)

        # Extract screen name
        screen_name = self._extract_screen_name(file_stem, content, lines)
        if not screen_name:
            return None

        # Extract route
        route = self._extract_route(content, lines)
        route_name = self._extract_route_name(content, lines)

        # Determine auth requirement
        auth_required = self._determine_auth(content)

        # Detect features
        has_form = self._detect_pattern(content, FORM_PATTERNS)
        has_list = self._detect_pattern(content, LIST_PATTERNS)
        has_navigation = self._detect_pattern(content, NAVIGATION_PATTERNS)

        # Detect state management
        state_mgmt = self._detect_state_management(content)

        # Calculate confidence
        confidence = self._calculate_confidence(
            file_path, content, screen_type, route, has_indicator
        )

        return Screen(
            name=screen_name,
            file_path=rel_path,
            screen_type=screen_type,
            route=route,
            route_name=route_name,
            auth_required=auth_required,
            line_number=self._find_definition_line(lines),
            has_form=has_form,
            has_list=has_list,
            has_navigation=has_navigation,
            state_management=state_mgmt,
            confidence=confidence,
            framework=self.framework,
        )

    # ─── Classification ────────────────────────────────

    def _classify_screen_type(self, file_stem: str, content: str) -> ScreenType:
        """Classify what type of UI entity this file defines."""
        name_lower = file_stem.lower()

        # Direct keyword match
        for keyword, screen_type in SCREEN_INDICATORS.items():
            if keyword in name_lower:
                return screen_type

        # Framework-specific classification
        if self.framework == "flutter":
            if "extends StatefulWidget" in content or "extends StatelessWidget" in content:
                if "screen" in name_lower or "page" in name_lower:
                    return ScreenType.SCREEN
                return ScreenType.WIDGET

        elif self.framework in ("react", "nextjs"):
            if "export default" in content or "export {" in content:
                if "page" in name_lower:
                    return ScreenType.PAGE
                return ScreenType.COMPONENT

        return ScreenType.UNKNOWN

    def _extract_screen_name(self, file_stem: str, content: str, lines: List[str]) -> Optional[str]:
        """Extract the screen/component name from the file."""
        # Try framework-specific patterns
        patterns = SCREEN_DEFINITION_PATTERNS.get(self.framework, [])

        for pattern in patterns:
            match = re.search(pattern, content)
            if match:
                name = match.group(1)
                # Filter out generic names
                if name.lower() not in ("app", "main", "index", "default"):
                    return name

        # Fallback: look for any class definition
        class_match = re.search(r'class\s+(\w+)', content)
        if class_match:
            name = class_match.group(1)
            if name.lower() not in ("app", "main", "index"):
                return name

        # Fallback: look for exported function/const
        export_match = re.search(
            r'(?:export\s+(?:default\s+)?(?:function|const|class)\s+(\w+))',
            content
        )
        if export_match:
            return export_match.group(1)

        # Last resort: use file stem
        return file_stem.replace("_", " ").replace("-", " ").title().replace(" ", "")

    # ─── Route Extraction ──────────────────────────────

    def _extract_route(self, content: str, lines: List[str]) -> Optional[str]:
        """Extract the route/path for this screen."""
        patterns = ROUTE_PATTERNS.get(self.framework, [])

        for pattern, _ in patterns:
            match = re.search(pattern, content)
            if match:
                route = match.group(1)
                if route and not route.startswith(("http://", "https://")):
                    return self._normalize_route(route)

        # Next.js: derive route from file path
        if self.framework == "nextjs":
            return None  # Route derived from file location in scan_routes.py

        return None

    def _extract_route_name(self, content: str, lines: List[str]) -> Optional[str]:
        """Extract named route if available."""
        name_patterns = [
            r"name\s*:\s*['\"]([^'\"]+)['\"]",
            r"routeName\s*:\s*['\"]([^'\"]+)['\"]",
            r'pageName\s*:\s*["\'`]([^"\'`]+)["\'`]',
        ]

        for pattern in name_patterns:
            match = re.search(pattern, content)
            if match:
                return match.group(1)

        return None

    def _normalize_route(self, route: str) -> str:
        """Normalize route path."""
        route = route.strip()
        if not route.startswith("/"):
            route = "/" + route
        # Remove trailing slash unless it's the root
        if route != "/" and route.endswith("/"):
            route = route.rstrip("/")
        return route

    # ─── Auth Detection ────────────────────────────────

    def _determine_auth(self, content: str) -> AuthRequirement:
        """Determine if this screen requires authentication."""
        content_lower = content.lower()

        # Check auth required
        for keyword in AUTH_REQUIRED_KEYWORDS:
            if keyword.lower() in content_lower:
                return AuthRequirement.REQUIRED

        # Check auth not required
        for keyword in AUTH_NONE_KEYWORDS:
            if keyword.lower() in content_lower:
                return AuthRequirement.NONE

        # Framework-specific checks
        if self.framework == "nextjs":
            if "getServerSession" in content or "auth(" in content:
                return AuthRequirement.REQUIRED

        if self.framework in ("react", "vue"):
            if "useAuth" in content or "useSession" in content:
                return AuthRequirement.REQUIRED

        return AuthRequirement.UNKNOWN

    # ─── Feature Detection ─────────────────────────────

    def _detect_pattern(self, content: str, patterns: List[str]) -> bool:
        """Check if any pattern matches in content."""
        content_lower = content.lower()
        for pattern in patterns:
            if re.search(pattern, content, re.IGNORECASE):
                return True
        return False

    def _detect_state_management(self, content: str) -> Optional[str]:
        """Detect which state management solution is used."""
        detectors = {
            "riverpod": [r"riverpod", r"Provider\s*\(", r"ref\.", r"WidgetRef"],
            "bloc": [r"BlocBuilder", r"BlocProvider", r"BlocListener", r"flutter_bloc"],
            "provider": [r"Provider\.of", r"ChangeNotifierProvider", r"context\.watch"],
            "getx": [r"GetBuilder", r"GetX", r"Get\.to", r"get_storage"],
            "redux": [r"redux", r"StoreProvider", r"useSelector", r"useDispatch"],
            "mobx": [r"mobx", r"Observer\s*\(", r"observable", r"computed"],
            "zustand": [r"zustand", r"create\s*\(", r"useStore"],
            "jotai": [r"jotai", r"useAtom", r"atom\s*\("],
            "recoil": [r"recoil", r"useRecoilState", r"atom\s*\("],
            "pinia": [r"pinia", r"defineStore", r"useStore"],
            "vuex": [r"vuex", r"\$store", r"mapState"],
        }

        content_lower = content.lower()
        for mgmt, patterns in detectors.items():
            for pattern in patterns:
                if re.search(pattern, content, re.IGNORECASE):
                    return mgmt

        return None

    # ─── Confidence Scoring ────────────────────────────

    def _calculate_confidence(
        self,
        file_path: Path,
        content: str,
        screen_type: ScreenType,
        route: Optional[str],
        has_indicator: bool,
    ) -> float:
        """Calculate confidence that this file is a real screen/page."""
        score = 0.0

        # Base score from file name
        name_lower = file_path.name.lower()
        if "screen" in name_lower:
            score += 0.4
        elif "page" in name_lower:
            score += 0.35
        elif "view" in name_lower:
            score += 0.25
        elif "component" in name_lower:
            score += 0.15
        elif "widget" in name_lower:
            score += 0.2

        # Framework definition patterns
        if screen_type != ScreenType.UNKNOWN:
            score += 0.2

        # Route found
        if route:
            score += 0.15

        # Has class definition
        if re.search(r'class\s+\w+', content):
            score += 0.1

        # Has build/render function
        if re.search(r'(build|render|Widget build)\s*\(', content):
            score += 0.1

        # Has UI elements
        ui_indicators = ['<div', '<View', 'Container(', 'Column(', 'Row(', 'Scaffold(', '<template']
        if any(indicator in content for indicator in ui_indicators):
            score += 0.05

        return min(score, 1.0)

    # ─── Post-Processing ───────────────────────────────

    def _deduplicate(self):
        """Remove duplicate screens (same route, keep highest confidence)."""
        seen: Dict[str, Screen] = {}

        for screen in self.screens:
            key = screen.route or screen.name
            if key in seen:
                if screen.confidence > seen[key].confidence:
                    seen[key] = screen
            else:
                seen[key] = screen

        removed = len(self.screens) - len(seen)
        if removed:
            logger.debug(f"Deduplicated {removed} screens")
        self.screens = list(seen.values())

    def _link_navigation(self):
        """Link screens that navigate to each other."""
        route_to_screen = {
            s.route: s for s in self.screens if s.route
        }

        for screen in self.screens:
            if screen.has_navigation and screen.route:
                # Screens that navigate from here are potential children
                # This is a simplified heuristic — full navigation graph
                # is built by generate_app_map.py
                pass

    def _calculate_auth_stats(self):
        """Log auth protection statistics."""
        required = sum(1 for s in self.screens if s.auth_required == AuthRequirement.REQUIRED)
        none_req = sum(1 for s in self.screens if s.auth_required == AuthRequirement.NONE)
        unknown = sum(1 for s in self.screens if s.auth_required == AuthRequirement.UNKNOWN)

        logger.info(
            f"Auth stats: {required} protected, {none_req} public, {unknown} unknown"
        )

    # ─── Helpers ───────────────────────────────────────

    def _find_definition_line(self, lines: List[str]) -> Optional[int]:
        """Find the line number where the main class/function is defined."""
        for i, line in enumerate(lines):
            if re.search(
                r'(?:class\s+\w+|function\s+\w+|const\s+\w+\s*=)',
                line
            ):
                return i + 1
        return None


# ─── Wrapper ────────────────────────────────────────

def scan_screens(app_path: Path, stack_info: Optional[dict] = None) -> dict:
    """Main entry point. Returns structured screen map."""
    scanner = ScreenScanner(Path(app_path), stack_info)
    return scanner.scan_all()


# ─── CLI ────────────────────────────────────────────

if __name__ == "__main__":
    import sys
    import json
    from pprint import pprint

    logging.basicConfig(level=logging.INFO, format="%(message)s")

    if len(sys.argv) < 2:
        print("Usage: python scan_screens.py /path/to/app [stack_json]")
        sys.exit(1)

    app_path = Path(sys.argv[1])
    stack_info = json.loads(sys.argv[2]) if len(sys.argv) > 2 else {}

    result = scan_screens(app_path, stack_info)
    pprint(result)
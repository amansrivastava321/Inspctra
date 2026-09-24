"""
scan_routes.py - Framework-aware route/screen scanner.
Handles: Flutter (go_router, auto_route, named routes),
         React (react-router, Next.js pages/app router),
         Vue Router, Angular Router,
         FastAPI/Django/Flask routes.
"""

from pathlib import Path
from typing import Optional
from dataclasses import dataclass, field
from enum import Enum
import json
import logging
import re
import ast  # Python AST
import yaml

logger = logging.getLogger(__name__)


# ─── Data Models ───────────────────────────────────────

class RouteType(Enum):
    SCREEN = "screen"
    API = "api"
    REDIRECT = "redirect"
    GUARD = "guard"
    NESTED = "nested"


class AuthRequirement(Enum):
    NONE = "none"
    REQUIRED = "required"
    OPTIONAL = "optional"
    ADMIN = "admin"
    UNKNOWN = "unknown"


@dataclass
class Route:
    """A single route/screen/endpoint in the app."""
    path: str
    name: Optional[str] = None
    file_path: Optional[str] = None
    route_type: RouteType = RouteType.SCREEN
    auth_required: AuthRequirement = AuthRequirement.UNKNOWN
    roles: list = field(default_factory=list)
    parameters: list = field(default_factory=list)  # /user/:id, /billing/${planId}
    query_params: list = field(default_factory=list)
    parent_route: Optional[str] = None
    children: list = field(default_factory=list)
    line_number: Optional[int] = None
    is_protected: bool = False  # Has auth guard/middleware
    has_form: bool = False
    has_file_upload: bool = False
    related_apis: list = field(default_factory=list)  # APIs this screen calls
    
    def to_dict(self) -> dict:
        return {
            "path": self.path,
            "name": self.name,
            "file": self.file_path,
            "type": self.route_type.value,
            "auth": self.auth_required.value,
            "roles": self.roles,
            "params": self.parameters,
            "query": self.query_params,
            "parent": self.parent_route,
            "children": self.children,
            "line": self.line_number,
            "protected": self.is_protected,
        }


# ─── Framework Detectors ───────────────────────────────

class RouteScanner:
    """
    Main scanner. Detects the framework from StackInfo and delegates
    to the appropriate framework-specific parser.
    """
    
    def __init__(self, app_path: Path, stack_info: dict):
        self.app_path = app_path
        self.stack = stack_info
        self.routes: list[Route] = []
        self.api_routes: list[Route] = []
    
    def scan_all(self) -> dict:
        """Scan all routes and return structured output."""
        framework = self.stack.get("framework", "unknown")
        
        if framework == "flutter":
            self._scan_flutter_routes()
        elif framework in ("react", "nextjs", "vue", "angular", "svelte"):
            self._scan_js_routes(framework)
        elif framework in ("django", "fastapi", "flask"):
            self._scan_python_routes(framework)
        elif framework == "express":
            self._scan_express_routes()
        elif framework == "rails":
            self._scan_rails_routes()
        
        return {
            "routes": [r.to_dict() for r in self.routes],
            "api_routes": [r.to_dict() for r in self.api_routes],
            "total_screens": len(self.routes),
            "total_apis": len(self.api_routes),
            "auth_protected_screens": len([r for r in self.routes if r.is_protected]),
            "unprotected_screens": len([r for r in self.routes if not r.is_protected]),
        }
    
    # ─── Flutter Scanners ───────────────────────────
    
    def _scan_flutter_routes(self):
        """Scan Flutter routes: go_router, auto_route, named routes, onGenerateRoute."""
        router_lib = self.stack.get("router_library", "unknown")
        
        if router_lib == "go_router":
            self._scan_go_router()
        elif router_lib == "auto_route":
            self._scan_auto_route()
        else:
            self._scan_flutter_named_routes()
        
        # Also scan for Navigator.push calls (dynamic navigation)
        self._scan_flutter_navigator_calls()
    
    def _scan_go_router(self):
        """
        Parses GoRouter configuration.
        
        Examples:
            GoRoute(path: '/login', name: 'login', builder: ...)
            GoRoute(path: '/user/:id', name: 'user', builder: ...)
            ShellRoute(routes: [GoRoute(...)])
        """
        for dart_file in self.app_path.rglob("*.dart"):
            try:
                content = dart_file.read_text(errors="ignore")
                
                # Find GoRoute definitions
                # Pattern: GoRoute( ... path: '...'  ... )
                goroute_pattern = r'GoRoute\s*\((.*?)(?=\n\s*(?:GoRoute|ShellRoute|\]|\)\s*;))'
                
                for match in re.finditer(goroute_pattern, content, re.DOTALL):
                    block = match.group(1)
                    route = Route()
                    route.file_path = str(dart_file.relative_to(self.app_path))
                    route.route_type = RouteType.SCREEN
                    
                    # Extract path
                    path_match = re.search(r"path\s*:\s*['\"]([^'\"]+)['\"]", block)
                    if path_match:
                        route.path = path_match.group(1)
                        # Detect parameters: /user/:id or /user/${id}
                        route.parameters = re.findall(r'[:$]{(\w+)}|:(\w+)', block)
                        route.parameters = [p[0] or p[1] for p in route.parameters if p[0] or p[1]]
                    else:
                        continue  # No path, skip
                    
                    # Extract name
                    name_match = re.search(r"name\s*:\s*['\"]([^'\"]+)['\"]", block)
                    if name_match:
                        route.name = name_match.group(1)
                    
                    # Check for auth guard
                    if 'redirect:' in block and ('auth' in block.lower() or 'login' in block.lower()):
                        route.is_protected = True
                        route.auth_required = AuthRequirement.REQUIRED
                    
                    # Check if it's a redirect route
                    if 'redirect:' in block:
                        route.route_type = RouteType.REDIRECT
                    
                    self.routes.append(route)
                
                # Find ShellRoute for nested structure
                shell_pattern = r'ShellRoute\s*\(.*?routes\s*:\s*\[(.*?)\]'
                for shell_match in re.finditer(shell_pattern, content, re.DOTALL):
                    shell_block = shell_match.group(1)
                    # Routes inside ShellRoute are children
                    for child_route in self.routes:
                        if child_route.file_path == str(dart_file.relative_to(self.app_path)):
                            # Check if this route is inside shell_block
                            if child_route.path in shell_block:
                                child_route.parent_route = "shell"
                
                # Detect auth requirements from redirect logic
                redirect_pattern = r"redirect\s*:\s*\([^)]*\)\s*=>\s*['\"]([^'\"]+)['\"]"
                for redirect_match in re.finditer(redirect_pattern, content):
                    redirect_target = redirect_match.group(1)
                    if 'login' in redirect_target or 'auth' in redirect_target:
                        # The GoRoute above this redirect is protected
                        for route in reversed(self.routes):
                            if route.file_path == str(dart_file.relative_to(self.app_path)):
                                route.is_protected = True
                                route.auth_required = AuthRequirement.REQUIRED
                                break
                
            except Exception as e:
                logger.debug("Route scan error: %s", e)
                continue
    
    def _scan_auto_route(self):
        """Parse AutoRoute annotations."""
        for dart_file in self.app_path.rglob("*.dart"):
            try:
                content = dart_file.read_text(errors="ignore")
                
                # @RoutePage or @MaterialRoute or @CupertinoRoute
                route_patterns = [
                    r'@(?:RoutePage|MaterialRoute|CupertinoRoute|AdaptiveRoute)\s*\((.*?)\)',
                    r'@AutoRoute\s*\((.*?)\)',
                ]
                
                for pattern in route_patterns:
                    for match in re.finditer(pattern, content, re.DOTALL):
                        block = match.group(1)
                        route = Route()
                        route.file_path = str(dart_file.relative_to(self.app_path))
                        route.route_type = RouteType.SCREEN
                        
                        # Extract path
                        path_match = re.search(r"path\s*:\s*['\"]([^'\"]+)['\"]", block)
                        if path_match:
                            route.path = path_match.group(1)
                        
                        # Extract name
                        name_match = re.search(r"name\s*:\s*['\"]([^'\"]+)['\"]", block)
                        if name_match:
                            route.name = name_match.group(1)
                        
                        self.routes.append(route)
                        
            except Exception as e:
                logger.debug("Route scan error: %s", e)
                continue
    
    def _scan_flutter_named_routes(self):
        """Scan for MaterialApp/CupertinoApp routes: Map."""
        for dart_file in self.app_path.rglob("*.dart"):
            try:
                content = dart_file.read_text(errors="ignore")
                
                # MaterialApp(routes: { '/login': (context) => LoginScreen(), ... })
                routes_pattern = r"routes\s*:\s*\{([^}]+)\}"
                for match in re.finditer(routes_pattern, content, re.DOTALL):
                    routes_block = match.group(1)
                    
                    # Extract individual routes
                    route_entries = re.findall(
                        r"['\"](/[^'\"]+)['\"]\s*:\s*\([^)]*\)\s*=>\s*(\w+)",
                        routes_block
                    )
                    
                    for path, screen_name in route_entries:
                        route = Route(
                            path=path,
                            name=screen_name,
                            file_path=str(dart_file.relative_to(self.app_path)),
                            route_type=RouteType.SCREEN
                        )
                        self.routes.append(route)
                
                # onGenerateRoute
                if 'onGenerateRoute' in content:
                    route = Route(
                        path="/*",  # Wildcard - dynamic routing
                        name="onGenerateRoute",
                        file_path=str(dart_file.relative_to(self.app_path)),
                        route_type=RouteType.SCREEN
                    )
                    self.routes.append(route)
                    
            except Exception as e:
                logger.debug("Route scan error: %s", e)
                continue
    
    def _scan_flutter_navigator_calls(self):
        """Find Navigator.push calls for screens not in router."""
        for dart_file in self.app_path.rglob("*.dart"):
            try:
                content = dart_file.read_text(errors="ignore")
                
                # Navigator.push(context, MaterialPageRoute(builder: (_) => ScreenName()))
                navigator_pattern = r'Navigator\.(?:push|pushNamed|pushReplacement)\s*\([^,]*,\s*.*?(\w+)\s*\('
                for match in re.finditer(navigator_pattern, content):
                    screen_name = match.group(1)
                    # Check if this screen is already in routes
                    if not any(r.name == screen_name for r in self.routes):
                        route = Route(
                            path=f"?screen={screen_name}",
                            name=screen_name,
                            file_path=str(dart_file.relative_to(self.app_path)),
                            route_type=RouteType.SCREEN
                        )
                        self.routes.append(route)
                        
            except Exception as e:
                logger.debug("Route scan error: %s", e)
                continue
    
    # ─── JavaScript/TypeScript Scanners ──────────────
    
    def _scan_js_routes(self, framework: str):
        """Scan JavaScript/TypeScript routes based on framework."""
        if framework == "nextjs":
            self._scan_nextjs_routes()
        elif framework == "react":
            self._scan_react_router_routes()
        elif framework == "vue":
            self._scan_vue_router_routes()
        elif framework == "angular":
            self._scan_angular_routes()
    
    def _scan_nextjs_routes(self):
        """
        Next.js routes come from:
        1. pages/ directory structure
        2. app/ directory structure (App Router)
        """
        # Pages Router
        pages_dir = self.app_path / "pages"
        if pages_dir.exists():
            for file in pages_dir.rglob("*.{js,jsx,ts,tsx}"):
                relative = file.relative_to(pages_dir)
                path = "/" + str(relative.with_suffix("")).replace("\\", "/")
                
                # Dynamic routes: [id].tsx -> /:id
                path = re.sub(r'\[(\w+)\]', r':\1', path)
                # Catch-all: [...slug].tsx -> /:slug*
                path = re.sub(r'\[\.\.\.(\w+)\]', r':\1*', path)
                # Index files
                path = path.replace("/index", "/")
                if path == "":
                    path = "/"
                
                route = Route(
                    path=path,
                    name=relative.stem,
                    file_path=str(file.relative_to(self.app_path)),
                    route_type=RouteType.SCREEN
                )
                self.routes.append(route)
        
        # App Router
        app_dir = self.app_path / "app"
        if app_dir.exists():
            for file in app_dir.rglob("page.{js,jsx,ts,tsx}"):
                relative = file.relative_to(app_dir).parent
                path = "/" + str(relative).replace("\\", "/")
                path = re.sub(r'\[(\w+)\]', r':\1', path)
                
                if path == "/.":
                    path = "/"
                
                route = Route(
                    path=path,
                    file_path=str(file.relative_to(self.app_path)),
                    route_type=RouteType.SCREEN
                )
                
                # Check for auth in layout.tsx or middleware.ts
                layout_file = file.parent / "layout.tsx"
                if layout_file.exists():
                    layout_content = layout_file.read_text(errors="ignore")
                    if 'auth' in layout_content.lower() or 'redirect' in layout_content.lower():
                        route.is_protected = True
                        route.auth_required = AuthRequirement.REQUIRED
                
                self.routes.append(route)
    
    def _scan_react_router_routes(self):
        """Scan for react-router-dom Route components."""
        for js_file in self.app_path.rglob("*.{js,jsx,ts,tsx}"):
            try:
                content = js_file.read_text(errors="ignore")
                
                # <Route path="/dashboard" element={<Dashboard />} />
                route_pattern = r'<Route\s+(.*?)/?>'
                for match in re.finditer(route_pattern, content, re.DOTALL):
                    attrs = match.group(1)
                    
                    path_match = re.search(r'path\s*=\s*["\'`]([^"\'`]+)["\'`]', attrs)
                    if not path_match:
                        continue
                    
                    path = path_match.group(1)
                    route = Route(
                        path=path,
                        file_path=str(js_file.relative_to(self.app_path)),
                        route_type=RouteType.SCREEN
                    )
                    
                    # Check if protected (wrapped in ProtectedRoute or requires auth)
                    if 'ProtectedRoute' in content or 'requireAuth' in content:
                        route.is_protected = True
                        route.auth_required = AuthRequirement.REQUIRED
                    
                    self.routes.append(route)
                    
            except Exception as e:
                logger.debug("Route scan error: %s", e)
                continue
    
    def _scan_vue_router_routes(self):
        """Scan Vue Router configuration."""
        for js_file in self.app_path.rglob("*.{js,ts}"):
            try:
                content = js_file.read_text(errors="ignore")
                
                # Look for routes array
                if 'routes' not in content and 'createRouter' not in content:
                    continue
                
                # Extract route objects
                route_objects = re.findall(
                    r'\{\s*path\s*:\s*["\'`]([^"\'`]+)["\'`].*?(?:name\s*:\s*["\'`]([^"\'`]+)["\'`])?',
                    content,
                    re.DOTALL
                )
                
                for path, name in route_objects:
                    route = Route(
                        path=path,
                        name=name if name else None,
                        file_path=str(js_file.relative_to(self.app_path)),
                        route_type=RouteType.SCREEN
                    )
                    
                    # Check for meta: { requiresAuth: true }
                    if 'requiresAuth' in content or 'meta' in content and 'auth' in content:
                        route.is_protected = True
                        route.auth_required = AuthRequirement.REQUIRED
                    
                    self.routes.append(route)
                    
            except Exception as e:
                logger.debug("Route scan error: %s", e)
                continue
    
    def _scan_angular_routes(self):
        """Scan Angular routing modules."""
        for ts_file in self.app_path.rglob("*.ts"):
            try:
                content = ts_file.read_text(errors="ignore")
                
                if 'Routes' not in content and 'RouterModule' not in content:
                    continue
                
                # Extract route paths
                route_pattern = r'path\s*:\s*["\'`]([^"\'`]+)["\'`]'
                for match in re.finditer(route_pattern, content):
                    path = match.group(1)
                    route = Route(
                        path=path,
                        file_path=str(ts_file.relative_to(self.app_path)),
                        route_type=RouteType.SCREEN
                    )
                    
                    # Check for canActivate guard
                    if 'canActivate' in content:
                        route.is_protected = True
                        route.auth_required = AuthRequirement.REQUIRED
                    
                    self.routes.append(route)
                    
            except Exception as e:
                logger.debug("Route scan error: %s", e)
                continue
    
    # ─── Python Backend Scanners ─────────────────────
    
    def _scan_python_routes(self, framework: str):
        """Scan Python backend routes."""
        for py_file in self.app_path.rglob("*.py"):
            try:
                content = py_file.read_text(errors="ignore")
                
                if framework == "fastapi":
                    self._scan_fastapi_routes(py_file, content)
                elif framework == "django":
                    self._scan_django_routes(py_file, content)
                elif framework == "flask":
                    self._scan_flask_routes(py_file, content)
                    
            except Exception as e:
                logger.debug("Route scan error: %s", e)
                continue
    
    def _scan_fastapi_routes(self, file_path: Path, content: str):
        """Scan FastAPI route decorators."""
        # @app.get("/users")
        # @router.post("/users/{user_id}")
        decorator_pattern = r'@(?:app|router)\.(get|post|put|delete|patch|options|head)\s*\(\s*["\']([^"\']+)["\']'
        
        for match in re.finditer(decorator_pattern, content):
            method, path = match.group(1), match.group(2)
            
            route = Route(
                path=path,
                name=f"{method.upper()} {path}",
                file_path=str(file_path.relative_to(self.app_path)),
                route_type=RouteType.API
            )
            
            # Check for auth dependencies
            if 'Depends' in content and 'auth' in content.lower():
                route.is_protected = True
                route.auth_required = AuthRequirement.REQUIRED
            
            self.api_routes.append(route)
    
    def _scan_django_routes(self, file_path: Path, content: str):
        """Scan Django URL patterns."""
        # path('users/', views.user_list)
        # re_path(r'^users/(?P<id>\d+)/$', views.user_detail)
        url_pattern = r'(?:path|re_path|url)\s*\(\s*["\']([^"\']+)["\']'
        
        for match in re.finditer(url_pattern, content):
            path = match.group(1)
            
            route = Route(
                path=path,
                file_path=str(file_path.relative_to(self.app_path)),
                route_type=RouteType.API
            )
            self.api_routes.append(route)
    
    def _scan_flask_routes(self, file_path: Path, content: str):
        """Scan Flask route decorators."""
        # @app.route('/users')
        # @bp.route('/users/<int:user_id>')
        route_pattern = r'@\w+\.route\s*\(\s*["\']([^"\']+)["\']'
        
        for match in re.finditer(route_pattern, content):
            path = match.group(1)
            
            route = Route(
                path=path,
                file_path=str(file_path.relative_to(self.app_path)),
                route_type=RouteType.API
            )
            self.api_routes.append(route)
    
    # ─── Express Scanner ────────────────────────────
    
    def _scan_express_routes(self):
        """Scan Express.js routes."""
        for js_file in self.app_path.rglob("*.{js,ts}"):
            try:
                content = js_file.read_text(errors="ignore")
                
                # app.get('/users', handler)
                # router.post('/users/:id', handler)
                express_pattern = r'(?:app|router)\.(get|post|put|delete|patch|use)\s*\(\s*["\'`]([^"\'`]+)["\'`]'
                
                for match in re.finditer(express_pattern, content):
                    method, path = match.group(1), match.group(2)
                    
                    route = Route(
                        path=path,
                        name=f"{method.upper()} {path}",
                        file_path=str(js_file.relative_to(self.app_path)),
                        route_type=RouteType.API
                    )
                    
                    # Check for auth middleware
                    if 'auth' in content.lower() or 'jwt' in content.lower():
                        route.is_protected = True
                        route.auth_required = AuthRequirement.REQUIRED
                    
                    self.api_routes.append(route)
                    
            except Exception as e:
                logger.debug("Route scan error: %s", e)
                continue
    
    # ─── Rails Scanner ──────────────────────────────
    
    def _scan_rails_routes(self):
        """Scan Rails routes.rb."""
        routes_file = self.app_path / "config" / "routes.rb"
        if not routes_file.exists():
            return
        
        try:
            content = routes_file.read_text(errors="ignore")
            
            # get '/users', to: 'users#index'
            # resources :users
            # namespace :api do ... end
            
            # Extract explicit routes
            explicit_routes = re.findall(
                r'(get|post|put|patch|delete|match)\s+[\'"]([^\'"]+)[\'"]',
                content
            )
            
            for method, path in explicit_routes:
                route = Route(
                    path=path,
                    name=f"{method.upper()} {path}",
                    file_path="config/routes.rb",
                    route_type=RouteType.API
                )
                self.api_routes.append(route)
            
            # Extract resources
            resources = re.findall(r'resources\s+:(\w+)', content)
            for resource in resources:
                # RESTful routes for a resource
                for action in ['index', 'show', 'create', 'update', 'destroy']:
                    path = f"/{resource}"
                    if action in ['show', 'update', 'destroy']:
                        path += "/:id"
                    
                    route = Route(
                        path=path,
                        name=f"{action} {resource}",
                        file_path="config/routes.rb",
                        route_type=RouteType.API
                    )
                    self.api_routes.append(route)
                    
        except Exception as e:
            logger.debug("Route scan error: %s", e)


# ─── Simple Wrapper ─────────────────────────────────

def scan_routes(app_path: Path, stack_info: dict = None) -> dict:
    """
    Main entry point. Scans all routes from the app.
    
    Args:
        app_path: Path to the app directory
        stack_info: Output from detect_stack.py (optional, used for framework detection)
    
    Returns:
        dict with routes, api_routes, and summary
    """
    scanner = RouteScanner(app_path, stack_info or {})
    return scanner.scan_all()


# ─── CLI ────────────────────────────────────────────

if __name__ == "__main__":
    import sys
    from pprint import pprint
    
    if len(sys.argv) < 2:
        print("Usage: python scan_routes.py /path/to/app [stack_json]")
        sys.exit(1)
    
    app_path = Path(sys.argv[1])
    stack_info = {}
    
    if len(sys.argv) > 2:
        stack_info = json.loads(sys.argv[2])
    
    result = scan_routes(app_path, stack_info)
    pprint(result)
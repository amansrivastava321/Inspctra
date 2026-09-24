"""
constants.py - Discovery Agent configuration constants.
Controls which files and directories are scanned or excluded.
"""

# ─── Directory Exclusions ──────────────────────────────
# Any path containing these directory names will be skipped entirely.

EXCLUDED_DIRS = {
    # Version control
    ".git",
    ".svn",
    ".hg",
    
    # IDEs and editors
    ".idea",
    ".vscode",
    ".vs",
    ".eclipse",
    
    # Python
    "__pycache__",
    ".pytest_cache",
    ".mypy_cache",
    ".ruff_cache",
    ".tox",
    ".eggs",
    "*.egg-info",
    
    # Dart / Flutter
    ".dart_tool",
    ".flutter-plugins",
    ".flutter-plugins-dependencies",
    
    # Node.js
    "node_modules",
    ".npm",
    ".yarn",
    
    # Build outputs
    "build",
    "dist",
    "out",
    "target",
    "bin",
    "obj",
    
    # Next.js
    ".next",
    ".turbo",
    
    # Android
    ".gradle",
    
    # iOS / macOS
    "Pods",
    "DerivedData",
    "Carthage",
    
    # Virtual environments
    "venv",
    ".venv",
    "env",
    ".env",
    "virtualenv",
    
    # Our own output
    "artifacts",
    "reports",
    "coverage",
    "evidence",
    
    # Docker
    ".docker",
    
    # Terraform
    ".terraform",
    
    # Miscellaneous
    ".cache",
    ".sass-cache",
    "tmp",
    "temp",
    "logs",
}


# ─── File Suffix Exclusions ────────────────────────────
# Files ending with these suffixes are skipped.

EXCLUDED_FILE_SUFFIXES = {
    # Images
    ".png",
    ".jpg",
    ".jpeg",
    ".gif",
    ".svg",
    ".ico",
    ".webp",
    ".bmp",
    ".tiff",
    
    # Fonts
    ".ttf",
    ".otf",
    ".woff",
    ".woff2",
    ".eot",
    
    # Documents
    ".pdf",
    ".doc",
    ".docx",
    ".xls",
    ".xlsx",
    ".ppt",
    ".pptx",
    ".md",
    ".rst",
    ".txt",
    ".csv",
    
    # Archives
    ".zip",
    ".tar",
    ".gz",
    ".bz2",
    ".7z",
    ".rar",
    
    # Media
    ".mp4",
    ".mp3",
    ".wav",
    ".avi",
    ".mov",
    ".mkv",
    ".flac",
    
    # Lock files (exact match handled in file_walker.py)
    ".lock",
    
    # Binary / compiled
    ".pyc",
    ".pyo",
    ".class",
    ".o",
    ".so",
    ".dylib",
    ".dll",
    ".exe",
    ".bin",
    ".dat",
    
    # Database
    ".db",
    ".sqlite",
    ".sqlite3",
    
    # Certificates / keys
    ".pem",
    ".key",
    ".crt",
    ".cer",
    ".p12",
    ".pfx",
    
    # Generated bundles
    ".min.js",
    ".min.css",
}


# ─── Generated File Patterns ───────────────────────────
# Files containing these patterns anywhere in their name are skipped.
# This catches generated code that has source extensions.

EXCLUDED_FILE_PATTERNS = [
    # Minified / bundled
    ".min.",
    ".bundle.",
    ".chunk.",
    
    # Dart generated
    ".g.dart",
    ".freezed.dart",
    ".gr.dart",
    ".pb.dart",
    ".pbenum.dart",
    ".pbjson.dart",
    ".pbserver.dart",
    
    # Protobuf generated (other languages)
    ".pb.go",
    "_pb2.py",
    "_pb2_grpc.py",
    ".pb.cc",
    ".pb.h",
    
    # GraphQL generated
    ".graphql.dart",
    ".gql.dart",
    
    # General generated markers
    ".generated.",
    ".g.cs",
    ".designer.cs",
    ".auto.",
    
    # TypeScript declaration files (generated)
    ".d.ts",
    
    # Other generated
    "_generated.",
    ".gen.",
]


# ─── Source Extensions ─────────────────────────────────
# Only files with these extensions are scanned for routes, APIs, and code quality.

SOURCE_EXTENSIONS = {
    # Python
    ".py",
    ".pyi",   # Python type stubs
    
    # JavaScript / TypeScript
    ".js",
    ".jsx",
    ".ts",
    ".tsx",
    ".mjs",
    ".cjs",
    
    # Dart
    ".dart",
    
    # Java / JVM
    ".java",
    ".kt",
    ".kts",
    ".scala",
    ".groovy",
    
    # Swift / Apple
    ".swift",
    ".m",     # Objective-C
    ".h",     # Objective-C header
    ".mm",    # Objective-C++
    
    # Go
    ".go",
    
    # Rust
    ".rs",
    
    # Ruby
    ".rb",
    ".rake",
    ".gemspec",
    
    # PHP
    ".php",
    ".phtml",
    
    # C# / .NET
    ".cs",
    ".vb",
    ".fs",
    
    # C / C++
    ".c",
    ".cpp",
    ".cc",
    ".cxx",
    ".h",
    ".hpp",
    ".hxx",
    
    # Shell / Config (limited - only when they contain code patterns)
    ".sh",
    ".bash",
    ".zsh",
}


# ─── Important Config Files (never excluded) ───────────
# Even if these match exclusion patterns, they are always scanned.
# Currently used by file_walker.py for dotfile exceptions.

IMPORTANT_CONFIG_FILES = {
    ".env",
    ".env.local",
    ".env.development",
    ".env.staging",
    ".env.production",
    ".env.example",
    ".eslintrc",
    ".eslintrc.js",
    ".eslintrc.json",
    ".prettierrc",
    ".prettierrc.js",
    ".prettierrc.json",
    ".babelrc",
    ".babelrc.js",
    ".browserslistrc",
    ".dockerignore",
    ".gitignore",
    ".gitattributes",
    ".editorconfig",
    ".nvmrc",
    ".node-version",
    ".ruby-version",
    ".python-version",
}


# ─── File Size Limits ──────────────────────────────────

MAX_FILE_SIZE_BYTES = 5 * 1024 * 1024  # 5 MB
MAX_FILES_TO_SCAN = 50000


# ─── Binary Detection ──────────────────────────────────

BINARY_CHECK_BYTES = 512  # Read first 512 bytes to detect null bytes
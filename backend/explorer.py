from collections import Counter
from pathlib import Path


LANGUAGE_EXTENSIONS = {
    ".py": "Python",
    ".js": "JavaScript",
    ".ts": "TypeScript",
    ".tsx": "TypeScript",
    ".jsx": "JavaScript",
    ".java": "Java",
    ".cpp": "C++",
    ".c": "C",
    ".go": "Go",
    ".rs": "Rust",
    ".md": "Markdown",
    ".rst": "reStructuredText",
    ".html": "HTML",
    ".css": "CSS",
    ".sql": "SQL",
}


IGNORED_DIRECTORIES = {
    ".git",
    "node_modules",
    "__pycache__",
    ".venv",
}


def scan_repository(repository_path: Path) -> list[Path]:
    """Return all files in a repository, excluding obvious noise directories."""
    files = []

    for path in repository_path.rglob("*"):
        if not path.is_file():
            continue

        if any(part in IGNORED_DIRECTORIES for part in path.parts):
            continue

        files.append(path)

    return files


def get_file_info(file_path: Path, repository_path: Path) -> dict:
    """Return basic metadata for a single file."""
    relative_path = file_path.relative_to(repository_path)
    extension = file_path.suffix.lower()
    size_bytes = file_path.stat().st_size

    try:
        line_count = len(file_path.read_text(encoding="utf-8").splitlines())
    except (UnicodeDecodeError, OSError):
        line_count = None

    return {
        "path": str(relative_path),
        "extension": extension,
        "size_bytes": size_bytes,
        "line_count": line_count,
    }


def detect_language(file_path: Path) -> str | None:
    """Detect a file's language from its extension."""
    return LANGUAGE_EXTENSIONS.get(file_path.suffix.lower())


def classify_file(file_path: Path) -> str:
    """Classify a file using simple path and filename rules."""
    name = file_path.name.lower()
    path = str(file_path).lower()
    extension = file_path.suffix.lower()

    if "test" in name or "tests" in path or "spec" in name:
        return "test"

    if extension in {".md", ".rst"} or "/docs/" in path or "\\docs\\" in path:
        return "docs"

    if name in {
        "package.json",
        "pyproject.toml",
        "requirements.txt",
        "package-lock.json",
        "poetry.lock",
        "uv.lock",
    }:
        return "dependency"

    if (
        extension in {".json", ".yml", ".yaml", ".toml", ".ini"}
        or name in {"dockerfile", ".env.example"}
    ):
        return "config"

    return "source"


def build_file_inventory(repository_path: Path) -> list[dict]:
    """Build a structured inventory of all files in a repository."""
    files = scan_repository(repository_path)

    inventory = []

    for file_path in files:
        info = get_file_info(file_path, repository_path)

        inventory.append(
            {
                **info,
                "language": detect_language(file_path),
                "category": classify_file(file_path),
            }
        )

    return inventory


def build_repository_summary(repository_path: Path) -> dict:
    """Build a repository-level summary from the file inventory."""
    inventory = build_file_inventory(repository_path)

    language_counts = Counter(
        item["language"]
        for item in inventory
        if item["language"] is not None
    )

    category_counts = Counter(item["category"] for item in inventory)

    notable_names = {
        "readme",
        "readme.md",
        "readme.rst",
        "license",
        "license.md",
        "license.txt",
    }

    notable_files = [
        item["path"]
        for item in inventory
        if Path(item["path"]).name.lower() in notable_names
    ]

    return {
        "total_files": len(inventory),
        "languages": dict(language_counts),
        "categories": dict(category_counts),
        "notable_files": sorted(notable_files),
    }


def print_repository_summary(repository_path: Path) -> None:
    """Print a human-readable repository summary."""
    summary = build_repository_summary(repository_path)

    print(f"Repository: {repository_path.name}")
    print(f"Total files: {summary['total_files']}")

    print("\nLanguages:")
    if summary["languages"]:
        for language, count in summary["languages"].items():
            print(f"  - {language}: {count}")
    else:
        print("  - None detected")

    print("\nCategories:")
    for category, count in summary["categories"].items():
        print(f"  - {category}: {count}")

    print("\nNotable files:")
    if summary["notable_files"]:
        for file_path in summary["notable_files"]:
            print(f"  - {file_path}")
    else:
        print("  - None")
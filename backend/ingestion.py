from pathlib import Path
from collections import Counter

from git import Repo


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
    ".html": "HTML",
    ".css": "CSS",
}


def clone_repository(repo_url: str, destination: Path) -> Path:
    """Clone a GitHub repository into the destination directory."""
    destination.parent.mkdir(parents=True, exist_ok=True)

    try:
        Repo.clone_from(repo_url, destination)
    except Exception as exc:
        raise RuntimeError(
            f"Could not clone repository from '{repo_url}'. "
            "Please check the URL and make sure the repository is reachable."
        ) from exc

    return destination


def analyze_repository(repository_path: Path) -> dict:
    """Return basic facts about a cloned repository."""
    files = [
        path
        for path in repository_path.rglob("*")
        if path.is_file() and ".git" not in path.parts
    ]

    language_counts = Counter()

    for file in files:
        language = LANGUAGE_EXTENSIONS.get(file.suffix.lower())
        if language:
            language_counts[language] += 1

    top_level_folders = sorted(
        path.name
        for path in repository_path.iterdir()
        if path.is_dir() and path.name != ".git"
    )

    return {
        "file_count": len(files),
        "languages": dict(language_counts),
        "top_level_folders": top_level_folders,
    }


def print_repository_facts(repository_path: Path) -> None:
    """Print basic facts about a cloned repository."""
    facts = analyze_repository(repository_path)

    print(f"Repository: {repository_path.name}")
    print(f"Total files: {facts['file_count']}")

    print("Languages:")
    if facts["languages"]:
        for language, count in facts["languages"].items():
            print(f"  - {language}: {count} file(s)")
    else:
        print("  - None detected")

    print("Top-level folders:")
    if facts["top_level_folders"]:
        for folder in facts["top_level_folders"]:
            print(f"  - {folder}")
    else:
        print("  - None")
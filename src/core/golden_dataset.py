# -*- coding: utf-8 -*-
"""
Golden dataset loader — persistent JSON-based dataset with version management.

Usage:
    from src.core.golden_dataset import load_golden_dataset, get_repo_by_id

    dataset = load_golden_dataset()
    print(dataset.version)           # "1.0.0"
    print(len(dataset.repos))        # 10
    langchain = dataset.get_by_id("standard_large_python")
    large_repos = dataset.get_by_category("standard")
    edge_repos = dataset.get_by_category("edge")
    py_repos = dataset.filter_by_language("Python")
"""

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional


_GOLDEN_DATASET_PATH = Path(__file__).parent.parent / "data" / "golden_dataset.json"


@dataclass
class GoldenRepo:
    """A single golden dataset repo entry."""

    id: str
    category: str
    full_name: str
    html_url: str
    stargazers_count: int
    forks_count: int
    watchers_count: int
    open_issues_count: int
    language: str
    description: str
    topics: List[str]
    updated_at: str
    owner_login: str
    is_fork: bool
    is_archived: bool
    readme: Optional[str]

    def to_api_response(self) -> Dict[str, Any]:
        """Convert to GitHub API response format."""
        return {
            "full_name": self.full_name,
            "html_url": self.html_url,
            "stargazers_count": self.stargazers_count,
            "forks_count": self.forks_count,
            "watchers_count": self.watchers_count,
            "open_issues_count": self.open_issues_count,
            "language": self.language,
            "description": self.description,
            "topics": self.topics,
            "updated_at": self.updated_at,
            "owner": {"login": self.owner_login},
            "fork": self.is_fork,
            "archived": self.is_archived,
            "readme": self.readme,
        }


@dataclass
class GoldenDataset:
    """Golden dataset with version management and filtering."""

    version: str
    description: str
    repos: List[GoldenRepo] = field(default_factory=list)

    def get_by_id(self, repo_id: str) -> Optional[GoldenRepo]:
        """Get a repo by its unique ID."""
        for repo in self.repos:
            if repo.id == repo_id:
                return repo
        return None

    def get_by_category(self, category: str) -> List[GoldenRepo]:
        """Get all repos in a category (e.g., 'standard', 'edge')."""
        return [r for r in self.repos if r.category == category]

    def filter_by_language(self, language: str) -> List[GoldenRepo]:
        """Filter repos by programming language."""
        return [r for r in self.repos if r.language.lower() == language.lower()]

    def get_all_ids(self) -> List[str]:
        """Return all repo IDs."""
        return [r.id for r in self.repos]

    def stats(self) -> Dict[str, Any]:
        """Dataset statistics."""
        categories = {}
        languages = {}
        for repo in self.repos:
            categories[repo.category] = categories.get(repo.category, 0) + 1
            languages[repo.language] = languages.get(repo.language, 0) + 1
        return {
            "version": self.version,
            "total_repos": len(self.repos),
            "categories": categories,
            "languages": languages,
            "has_readme": sum(1 for r in self.repos if r.readme),
            "no_readme": sum(1 for r in self.repos if not r.readme),
            "archived": sum(1 for r in self.repos if r.is_archived),
            "forks": sum(1 for r in self.repos if r.is_fork),
        }

    def add_repo(self, repo: GoldenRepo) -> None:
        """Add a repo to the dataset. Replaces existing repo with same ID."""
        for i, existing in enumerate(self.repos):
            if existing.id == repo.id:
                self.repos[i] = repo
                return
        self.repos.append(repo)

    def update_repo(self, repo_id: str, **fields: Any) -> bool:
        """Update fields of an existing repo by ID. Returns True if updated."""
        for repo in self.repos:
            if repo.id == repo_id:
                for key, value in fields.items():
                    if hasattr(repo, key):
                        setattr(repo, key, value)
                return True
        return False

    def remove_repo(self, repo_id: str) -> bool:
        """Remove a repo by ID. Returns True if removed."""
        original_len = len(self.repos)
        self.repos = [r for r in self.repos if r.id != repo_id]
        return len(self.repos) < original_len

    def save_to_file(self, path: str) -> None:
        """Save dataset to JSON file."""
        data = {
            "version": self.version,
            "description": self.description,
            "repos": [
                {
                    "id": r.id,
                    "category": r.category,
                    "full_name": r.full_name,
                    "html_url": r.html_url,
                    "stargazers_count": r.stargazers_count,
                    "forks_count": r.forks_count,
                    "watchers_count": r.watchers_count,
                    "open_issues_count": r.open_issues_count,
                    "language": r.language,
                    "description": r.description,
                    "topics": r.topics,
                    "updated_at": r.updated_at,
                    "owner": {"login": r.owner_login},
                    "fork": r.is_fork,
                    "archived": r.is_archived,
                    "readme": r.readme,
                }
                for r in self.repos
            ],
        }
        output_path = Path(path)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        with open(output_path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)

    def merge_dataset(self, other: "GoldenDataset", overwrite: bool = True) -> int:
        """Merge another dataset into this one. Returns count of added/updated repos."""
        count = 0
        for repo in other.repos:
            existing_ids = {r.id for r in self.repos}
            if repo.id in existing_ids:
                if overwrite:
                    for i, r in enumerate(self.repos):
                        if r.id == repo.id:
                            self.repos[i] = repo
                            count += 1
                            break
            else:
                self.repos.append(repo)
                count += 1
        return count


def load_golden_dataset(path: Optional[str] = None) -> GoldenDataset:
    """
    Load golden dataset from JSON file.

    Args:
        path: Optional path to JSON file. Defaults to src/data/golden_dataset.json.

    Returns:
        Loaded GoldenDataset.

    Raises:
        FileNotFoundError: If dataset file not found.
        json.JSONDecodeError: If file is not valid JSON.
    """
    dataset_path = Path(path) if path else _GOLDEN_DATASET_PATH

    if not dataset_path.exists():
        raise FileNotFoundError(f"Golden dataset not found: {dataset_path}")

    with open(dataset_path, "r", encoding="utf-8") as f:
        data = json.load(f)

    repos = []
    for repo_data in data.get("repos", []):
        repos.append(GoldenRepo(
            id=repo_data["id"],
            category=repo_data.get("category", "standard"),
            full_name=repo_data["full_name"],
            html_url=repo_data["html_url"],
            stargazers_count=repo_data["stargazers_count"],
            forks_count=repo_data["forks_count"],
            watchers_count=repo_data.get("watchers_count", 0),
            open_issues_count=repo_data["open_issues_count"],
            language=repo_data["language"],
            description=repo_data.get("description", ""),
            topics=repo_data.get("topics", []),
            updated_at=repo_data["updated_at"],
            owner_login=repo_data["owner"]["login"],
            is_fork=repo_data.get("fork", False),
            is_archived=repo_data.get("archived", False),
            readme=repo_data.get("readme"),
        ))

    return GoldenDataset(
        version=data.get("version", "unknown"),
        description=data.get("description", ""),
        repos=repos,
    )


def get_repo_by_id(repo_id: str, path: Optional[str] = None) -> Optional[GoldenRepo]:
    """Convenience function to get a single repo by ID."""
    dataset = load_golden_dataset(path)
    return dataset.get_by_id(repo_id)

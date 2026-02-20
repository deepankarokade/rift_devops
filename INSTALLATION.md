# 📦 Package Installation Guide

## Prerequisites

- **Python**: 3.7 or newer
- **pip**: 19.0 or newer (upgrade with `python -m pip install --upgrade pip`)
- **Git**: Must be installed and available on PATH (required by GitPython)

---

## Required Packages

| Package | Version | Used By | Purpose |
|---------|---------|---------|---------|
| `gitpython` | `>=3.1.0` | `github_client.py`, `repo_cloner.py` | Git operations (clone, commit, push, branch) |
| `requests` | `>=2.28.0` | `ci_provider.py` | GitHub Actions REST API calls |

---

## Installation

### Install all at once

```bash
pip install gitpython requests
```

### Or use the requirements file

```bash
pip install -r requirements.txt
```

---

## Standard Library Modules (no install needed)

These are built into Python — listed here for reference only:

| Module | Used By |
|--------|---------|
| `subprocess` | `docker_sandbox.py` |
| `logging` | All modules |
| `os` | `docker_sandbox.py`, `repo_cloner.py` |
| `re` | `branching_naming.py` |

---

## Verify Installation

```bash
python -c "import git; print('GitPython:', git.__version__)"
python -c "import requests; print('Requests:', requests.__version__)"
```

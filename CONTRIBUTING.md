# Contributor Guidelines

Welcome! This guide helps you set up the project locally for development and contributions. It also explains the coding standards used in the project along with the CI checks

## Local Setup

This project uses **uv** for Python packaging and virtual environments. Python is pinned to **3.12.10** in `pyproject.toml`.


### Step 1: Clone the Repository
Clone the repository and navigate to the project directory.

```bash
cd RAG-Module
```

### Step 2: Install uv
If uv is not already installed, install it via the official installer.

```bash
curl -LsSf https://astral.sh/uv/install.sh | sh
# Restart your terminal or run: source ~/.zshrc
```

### Step 3: Install the Required Python Version
Use uv to install and manage Python 3.12.10.

```bash
uv python install 3.12.10
```

### Step 4: Recreate the Virtual Environment
From the project root (where `pyproject.toml` and `uv.lock` are located), recreate the environment from the lockfile.

```bash
# Create .venv and install dependencies strictly from uv.lock
uv sync --frozen
```

**Notes:**
- `uv sync` creates a local `.venv/` directory by default and installs dependencies from `uv.lock`.
- If `--frozen` fails due to a stale lockfile, run `uv sync -p 3.12.10` (without `--frozen`) to resolve and update.

### Step 5: Activate the Environment (Optional)
Activate the virtual environment to use it directly.

```bash
source .venv/bin/activate
python -V  # Should output: Python 3.12.10
```

### Step 6: Run the Application

When running the FastAPI APIs locally always run with

```bash
uv run python app.py
```

instead of 

```bash
python3 app.py
```

This will make sure that regardless of whether you have activated the .venv environment or not uv will use the right versions when setting up the


For more help, check the [uv documentation](https://docs.astral.sh/uv/)

## CI Checks

### Environment Check

- Located in `.github/workflows/uv-env-check.yml`

- This GitHub actions check runs to check whether there are any conflicts between the lockfile and pyproject.toml. If it fails 

### Type check for Python 

## Installing New Dependencies to the Project (Python)

If you need to add a new Python dependency, **do not run `pip install` directly**.

We use `uv` to manage environments and lockfiles so that installs are reproducible in local development, CI, and containers.

### Follow This Process:

#### 1. Add the Dependency
Use `uv add` instead of `pip install`. This ensures both `pyproject.toml` and `uv.lock` are updated together.

```bash
uv add "package-name>=x.y,<x.(y+1)"
```

- Use a bounded version range (`>=` + `<`) to avoid uncontrolled upgrades.


#### 2. Re-sync Your Environment
After adding, re-sync to refresh your local `.venv`:

```bash
uv sync --reinstall
```

#### 3. Run Checks Locally
Make sure type checks, linter, and tests pass:

```bash
uv run pyright
uv run ruff check .
uv run pytest
```

#### 4. Commit Both Files
Always commit both `pyproject.toml` and `uv.lock`. If only one is updated, CI will fail (`uv sync --frozen` check).

```bash
git add pyproject.toml uv.lock
git commit -m "added package-name dependency"
```

#### 5. Open a PR
CI will validate that the lockfile and environment are consistent. If you forgot to update the lockfile, the PR will fail with a clear error.

---

### Important Notes

- **Never edit `uv.lock` manually.** It is controlled by `uv`.
- **Never use `uv pip install` for permanent deps** — it only changes your local venv. Use `uv add` instead.
- If you remove a dependency, run:

```bash
uv remove package-name
uv sync --reinstall
git add pyproject.toml uv.lock
git commit -m "removed package-name"
```

## Coding Standards

## PR evaluation criteria

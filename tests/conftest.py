"""Pytest configuration for test discovery and imports."""

import sys
from pathlib import Path

# Add the project root to Python path so tests can import from src
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

# Add src directory to Python path for direct module imports
src_dir = project_root / "src"
sys.path.insert(0, str(src_dir))

# Add models directory (sibling to src) for backward compatibility
models_dir = project_root / "models"
if models_dir.exists():
    sys.path.insert(0, str(models_dir.parent))

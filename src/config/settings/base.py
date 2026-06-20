from pathlib import Path
from typing import Literal

EnvType = Literal["PROD", "DEV", "TEST"]

# Resolves to the repo root regardless of CWD:
# base.py lives at src/config/settings/base.py → parents[3] = repo root
_REPO_ROOT = Path(__file__).resolve().parents[3]

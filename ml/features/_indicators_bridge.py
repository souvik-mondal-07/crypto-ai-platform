"""Reuse of the Phase 10 indicator math (backend/app/services/indicators.py).

That module is pure Python with no third-party imports, so it is loaded by file
path. This avoids (a) duplicating RSI/MACD/Bollinger/ATR logic inside ``ml`` and
(b) importing ``app.services``, whose package ``__init__`` pulls in MongoDB,
FastAPI and provider clients that the ML code (and training CLI) must not need.
"""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path
from types import ModuleType

from ml.config.model_config import REPO_ROOT

_MODULE_NAME = "_phase10_indicators"
_PATH = REPO_ROOT / "backend" / "app" / "services" / "indicators.py"


def load_indicators() -> ModuleType:
    cached = sys.modules.get(_MODULE_NAME)
    if cached is not None:
        return cached
    path = Path(_PATH)
    if not path.is_file():
        raise ImportError(f"Phase 10 indicator module not found at {path}")
    spec = importlib.util.spec_from_file_location(_MODULE_NAME, path)
    if spec is None or spec.loader is None:  # pragma: no cover
        raise ImportError(f"Cannot load indicator module from {path}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[_MODULE_NAME] = module
    try:
        spec.loader.exec_module(module)
    except Exception:
        sys.modules.pop(_MODULE_NAME, None)
        raise
    return module

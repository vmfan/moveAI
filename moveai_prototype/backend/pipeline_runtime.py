"""Caches loaded models across requests and serializes pipeline runs
(IMPLEMENTATION_ROADMAP.md Build 10).

`models.py`'s `detect_furniture`/`segment_detections`/`estimate_metric_depth`
each call `from_pretrained` fresh, then pass the model/processor into
`release_memory()`, which only `del`s *local* references and empties the
accelerator cache -- it does not destroy an object a cache elsewhere still
holds a strong reference to. That means a cache placed in front of
`from_pretrained` survives `release_memory()` unchanged, so this module
installs that cache by monkey-patching the handful of `from_pretrained`-style
entry points `models.py` actually calls, rather than editing `models.py`
itself (the roadmap's own preference). The patch targets shared class/module
attributes, so it only needs to run once per process, at import time.

MPS/CUDA are not safe for concurrent inference from multiple threads, so
every pipeline run is submitted to a single-worker `ThreadPoolExecutor`
rather than called directly -- one worker both serializes model access and
gives callers a plain blocking function to call.
"""

from __future__ import annotations

import sys
import threading
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from typing import Callable

BACKEND_DIR = Path(__file__).resolve().parent
APP_DIR = BACKEND_DIR.parent
if str(APP_DIR) not in sys.path:
    sys.path.insert(0, str(APP_DIR))

from transformers import (  # noqa: E402
    AutoModelForZeroShotObjectDetection,
    AutoProcessor,
    Sam2Model,
    Sam2Processor,
)

import depth_pro  # noqa: E402
import pipeline  # noqa: E402
from config import PipelineConfig  # noqa: E402
from pipeline import PipelineResult  # noqa: E402


def _default_key(args: tuple, kwargs: dict) -> tuple:
    return (args, tuple(sorted(kwargs.items())))


def _install_cache(
    obj: object,
    attr_name: str,
    key_fn: Callable[[tuple, dict], object] = _default_key,
) -> None:
    """Wraps `obj.attr_name` in a keyed cache, in place.

    Keyed by `key_fn(args, kwargs)`, so a repeated call with equivalent
    arguments (the common case -- every request uses the same model id,
    checkpoint, device, and precision) returns the same loaded object
    instead of reloading from disk. `key_fn` defaults to hashing the raw
    call arguments, but callers whose arguments include an unhashable object
    (e.g. a dataclass config) must supply one that extracts a hashable
    fingerprint instead.
    """
    original: Callable = getattr(obj, attr_name)
    lock = threading.Lock()
    cache: dict[object, object] = {}

    def cached(*args, **kwargs):
        key = key_fn(args, kwargs)
        with lock:
            if key not in cache:
                cache[key] = original(*args, **kwargs)
            return cache[key]

    setattr(obj, attr_name, cached)


def _depth_pro_key(args: tuple, kwargs: dict) -> tuple:
    """`create_model_and_transforms(config=DepthProConfig(...), device=...,
    precision=...)` -- `DepthProConfig` is an unhashable dataclass (it holds
    a nested `DepthProEncoderConfig`), so key on its `checkpoint_uri` field
    (the only part that varies here) plus device/precision instead of the
    raw config object."""
    config = kwargs.get("config") if "config" in kwargs else (args[0] if args else None)
    return (
        getattr(config, "checkpoint_uri", None),
        str(kwargs.get("device")),
        str(kwargs.get("precision")),
    )


_PATCHED = False
_patch_lock = threading.Lock()


def _install_model_caching() -> None:
    global _PATCHED
    with _patch_lock:
        if _PATCHED:
            return
        _install_cache(AutoProcessor, "from_pretrained")
        _install_cache(AutoModelForZeroShotObjectDetection, "from_pretrained")
        _install_cache(Sam2Processor, "from_pretrained")
        _install_cache(Sam2Model, "from_pretrained")
        _install_cache(depth_pro, "create_model_and_transforms", key_fn=_depth_pro_key)
        _PATCHED = True


_install_model_caching()

_executor = ThreadPoolExecutor(max_workers=1)


def run_pipeline_locked(
    image,
    furniture_classes: list[str],
    config: PipelineConfig,
    progress=None,
) -> PipelineResult:
    """Blocking wrapper around `pipeline.run_pipeline`, serialized through
    the single-worker executor above so concurrent capture requests never
    touch MPS/CUDA at the same time."""
    future = _executor.submit(
        pipeline.run_pipeline, image, furniture_classes, config, progress
    )
    return future.result()

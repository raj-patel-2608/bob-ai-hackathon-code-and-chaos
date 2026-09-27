"""GPU-first device placement with CPU fallback."""
from __future__ import annotations

import logging

log = logging.getLogger("model_service.device")


def cuda_available() -> bool:
    try:
        import torch
        return torch.cuda.is_available()
    except Exception:                                     # torch missing or broken driver
        return False


def free_vram_mb() -> int:
    import torch
    free, _total = torch.cuda.mem_get_info()
    return int(free / 2**20)


def resolve_device(policy: str, min_free_vram_mb: int = 0) -> tuple[str, str]:
    """Returns (device, reason). policy: auto | cuda | cpu."""
    if policy == "cpu":
        return "cpu", "configured"
    if not cuda_available():
        return "cpu", "no CUDA GPU available"
    if policy == "auto":
        free = free_vram_mb()
        if free < min_free_vram_mb:
            return "cpu", f"only {free} MB GPU memory free (< {min_free_vram_mb} MB)"
    return "cuda", "GPU available"


def is_gpu_error(exc: BaseException) -> bool:
    """CUDA out-of-memory or other CUDA runtime failure: worth retrying on CPU."""
    name = exc.__class__.__name__
    text = str(exc).lower()
    return name == "OutOfMemoryError" or "cuda" in text or "cublas" in text or "out of memory" in text


def release_gpu_memory() -> None:
    try:
        import torch
        if torch.cuda.is_available():
            torch.cuda.empty_cache()
    except Exception:
        pass


def gpu_memory() -> dict | None:
    if not cuda_available():
        return None
    import torch
    free, total = torch.cuda.mem_get_info()
    return {"device": torch.cuda.get_device_name(0), "free_mb": int(free / 2**20), "total_mb": int(total / 2**20),
            "allocated_mb": int(torch.cuda.memory_allocated() / 2**20)}

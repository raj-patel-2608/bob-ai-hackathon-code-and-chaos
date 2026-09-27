"""CrimeFIR environment checks, used by scripts/setup.ps1 and scripts/setup.sh.

  <any python>        doctor.py reqs <requirements.txt>   installed packages match the pinned requirements?
  <model_service py>  doctor.py gpu                        NVIDIA GPU visible to PyTorch?
  <model_service py>  doctor.py models [--download]        Laya + Granite Embedding in the Hugging Face cache?
  <model_service py>  doctor.py watsonx [--ping]           src/.env credentials valid? (--ping sends a 1-token request)

Exit code 0 = everything OK, 1 = something missing / failing, 2 = usage error.
The `reqs` command uses only the standard library, so it works in a fresh virtual environment.
"""
from __future__ import annotations

import os
import re
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
MODEL_SERVICE = REPO / "src" / "model_service"


COLOUR = sys.stdout.isatty() and not os.environ.get("NO_COLOR")


def say(status: str, what: str, detail: str = "") -> None:
    colour = {"OK": "\033[32m", "MISSING": "\033[33m", "FAIL": "\033[31m", "INFO": "\033[36m"}.get(status, "") if COLOUR else ""
    reset = "\033[0m" if COLOUR else ""
    print(f"  {colour}{status:<8}{reset} {what}{('  ' + detail) if detail else ''}", flush=True)


# ----------------------------------------------------------------------------- python requirements

def _norm(name: str) -> str:
    return re.sub(r"[-_.]+", "-", name).lower()


def cmd_reqs(path: str) -> int:
    from importlib import metadata

    installed = {_norm(d.metadata["Name"]): d.version for d in metadata.distributions() if d.metadata["Name"]}
    missing = []
    for line in Path(path).read_text(encoding="utf-8").splitlines():
        line = line.split("#", 1)[0].strip()
        if not line or line.startswith("-"):
            continue
        m = re.match(r"^([A-Za-z0-9_.\-]+)(\[[^\]]*\])?\s*(==\s*([^\s;]+))?", line)
        if not m:
            continue
        name, wanted = _norm(m.group(1)), m.group(4)
        have = installed.get(name)
        # torch: the CPU build (2.11.0+cpu) satisfies a CUDA pin (2.11.0+cu128) and vice versa
        if have is None or (wanted and have.split("+")[0] != wanted.split("+")[0]):
            missing.append(f"{m.group(1)} (need {wanted or 'any'}, have {have or 'not installed'})")
    if missing:
        print(f"{len(missing)} package(s) missing or outdated:")
        for item in missing:
            print(f"    - {item}")
        return 1
    print("all requirements installed")
    return 0


# ----------------------------------------------------------------------------- GPU

def cmd_gpu() -> int:
    try:
        import torch
    except ImportError:
        say("MISSING", "PyTorch", "install the model service requirements first")
        return 1
    if torch.cuda.is_available():
        free, total = torch.cuda.mem_get_info()
        say("OK", "GPU", f"{torch.cuda.get_device_name(0)} · {total // 2**20} MB VRAM ({free // 2**20} MB free) · torch {torch.__version__}")
        return 0
    say("INFO", "GPU", f"not available to PyTorch ({torch.__version__}); models will run on CPU (slower, still works)")
    return 1


# ----------------------------------------------------------------------------- models

def _config() -> dict:
    import yaml
    return yaml.safe_load((MODEL_SERVICE / "models.yaml").read_text(encoding="utf-8"))


def _laya_patterns(sub: str | None) -> list[str]:
    prefix = f"{sub}/" if sub else ""        # the same files laya.load() fetches
    return [prefix + n for n in ("rl_agent_config.json", "model.safetensors", "tokenizer/*", "encoder/*")]


def _cached(repo: str, patterns: list[str] | None, must_have: list[str]) -> Path | None:
    from huggingface_hub import snapshot_download
    try:
        root = Path(snapshot_download(repo, allow_patterns=patterns, local_files_only=True))
    except Exception:
        return None
    return root if all((root / f).exists() for f in must_have) else None


def _size(path: Path) -> str:
    total = sum(f.stat().st_size for f in path.rglob("*") if f.is_file())
    return f"{total / 2**30:.2f} GB" if total > 2**30 else f"{total / 2**20:.0f} MB"


def cmd_models(download: bool) -> int:
    cfg = _config()
    dec, emb = cfg["decision"], cfg["embedding"]
    sub = dec.get("checkpoint")
    checks = [
        ("Decision model (Laya)", dec["model"] + (f" / {sub}" if sub else ""), "~1.7 GB",
         lambda: _cached(dec["model"], _laya_patterns(sub),
                         [f"{sub + '/' if sub else ''}model.safetensors", f"{sub + '/' if sub else ''}rl_agent_config.json"]),
         lambda: __import__("huggingface_hub").snapshot_download(dec["model"], allow_patterns=_laya_patterns(sub))),
        ("Embedding model (IBM Granite Embedding)", emb["model"], "~65 MB",
         lambda: _cached(emb["model"], None, ["modules.json", "config.json"]),
         lambda: __import__("sentence_transformers").SentenceTransformer(emb["model"], device="cpu")),
    ]
    ok = True
    for label, repo, size, check, fetch in checks:
        found = check()
        if found:
            say("OK", label, f"{repo} · {_size(found)} in {found.parent.parent}")
            continue
        if not download:
            say("MISSING", label, f"{repo} ({size} download)")
            ok = False
            continue
        say("INFO", label, f"downloading {repo} ({size}) ...")
        try:
            fetch()
            found = check()
            say("OK" if found else "FAIL", label, f"{repo} · {_size(found)}" if found else "download finished but files not found")
            ok &= bool(found)
        except Exception as exc:
            say("FAIL", label, f"{exc.__class__.__name__}: {exc}")
            ok = False
    gen = cfg.get("generator", {})
    say("INFO", "LLM (IBM Granite on watsonx.ai)", f"remote, nothing to download · candidates: {', '.join(gen.get('model_candidates', []))}")
    return 0 if ok else 1


# ----------------------------------------------------------------------------- watsonx

PLACEHOLDERS = {"", "your_ibm_cloud_api_key", "your_watsonx_project_id"}


def _env() -> dict:
    values = {}
    env_file = REPO / "src" / ".env"
    if env_file.exists():
        for line in env_file.read_text(encoding="utf-8").splitlines():
            if "=" in line and not line.lstrip().startswith("#"):
                k, v = line.split("=", 1)
                values[k.strip()] = v.strip().strip('"').strip("'")
    return values


def cmd_watsonx(ping: bool) -> int:
    env = _env()
    key, project = env.get("WATSONX_API_KEY", ""), env.get("WATSONX_PROJECT_ID", "")
    url = env.get("WATSONX_URL") or "https://us-south.ml.cloud.ibm.com"
    if key in PLACEHOLDERS or project in PLACEHOLDERS:
        say("MISSING", "watsonx credentials", "WATSONX_API_KEY / WATSONX_PROJECT_ID not set in src/.env (optional)")
        return 1
    sys.path.insert(0, str(MODEL_SERVICE))
    from app.providers.base import ProviderUnavailable
    from app.providers.watsonx_generator import WatsonxGenerator

    gen = WatsonxGenerator(_config().get("generator", {}), key, project, url)
    try:
        gen.load()                                   # IAM token + model list: checks the key and the region
    except ProviderUnavailable as exc:
        say("FAIL", "watsonx.ai", str(exc))
        return 1
    except Exception as exc:
        say("FAIL", "watsonx.ai", f"{exc.__class__.__name__}: {exc}")
        return 1
    say("OK", "IBM Cloud API key + region", f"{url} · model {gen.model_id} available")
    if ping:
        try:
            out = gen.generate("Reply with OK.", "OK?", None, 1)   # checks the project id; ~20 tokens
            say("OK", "watsonx.ai project", f"test request answered ({sum(out['usage'].values())} tokens)")
        except Exception as exc:
            say("FAIL", "watsonx.ai project", f"{exc}".split("\n")[0][:300])
            return 1
    return 0


def main(argv: list[str]) -> int:
    os.environ.setdefault("HF_HUB_DISABLE_SYMLINKS_WARNING", "1")
    if not argv:
        print(__doc__)
        return 2
    cmd, rest = argv[0], argv[1:]
    if cmd == "reqs" and rest:
        return cmd_reqs(rest[0])
    if cmd == "gpu":
        return cmd_gpu()
    if cmd == "models":
        return cmd_models("--download" in rest)
    if cmd == "watsonx":
        return cmd_watsonx("--ping" in rest)
    print(__doc__)
    return 2


if __name__ == "__main__":
    if os.name == "nt":
        os.system("")                                # enable ANSI colours in Windows consoles
    sys.exit(main(sys.argv[1:]))

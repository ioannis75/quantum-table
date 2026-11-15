"""Configuration: .env loading (values are never printed), clock, versions."""
import os
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

ROOT = Path(__file__).resolve().parent
KEYS = ["ANTHROPIC_API_KEY", "OUMI_API_KEY", "OUMI_PROJECT_ID", "OUMI_DEPLOYMENT_ID",
        "FAL_KEY", "IBM_QUANTUM_TOKEN", "DISCORD_WEBHOOK_URL", "SERVICE_MARGIN_PCT", "PORT"]


def load_env(path: Path | None = None) -> None:
    path = path or ROOT / ".env"
    if not path.exists():
        return
    for line in path.read_text().splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        k, v = line.split("=", 1)
        k, v = k.strip(), v.strip().strip('"').strip("'")
        if v and k not in os.environ:
            os.environ[k] = v


load_env()


def has(key: str) -> bool:
    return bool(os.environ.get(key, "").strip())


def athens_now() -> datetime:
    return datetime.now(ZoneInfo("Europe/Athens"))


def key_status() -> dict:
    """Which keys are present (booleans only, never values)."""
    return {k: has(k) for k in KEYS if k not in ("PORT", "SERVICE_MARGIN_PCT")}


def versions() -> dict:
    import qiskit, qiskit_aer
    v = {"qiskit": qiskit.__version__, "qiskit_aer": qiskit_aer.__version__}
    try:
        import qiskit_ibm_runtime
        v["qiskit_ibm_runtime"] = qiskit_ibm_runtime.__version__
    except Exception:
        pass
    return v


DB_PATH = ROOT / "data" / "quantum_table.db"

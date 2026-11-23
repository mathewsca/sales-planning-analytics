"""Configuração central via variáveis de ambiente (12-factor)."""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def _env(name: str, default: str) -> str:
    return os.getenv(name, default)


@dataclass(frozen=True)
class Settings:
    database_url: str = field(
        default_factory=lambda: _env(
            "WAREHOUSE_URL", "postgresql+psycopg://analytics:analytics@localhost:5433/warehouse"
        )
    )
    mlflow_tracking_uri: str = field(
        default_factory=lambda: _env("MLFLOW_TRACKING_URI", "http://localhost:5000")
    )
    experiment_name: str = field(default_factory=lambda: _env("MLFLOW_EXPERIMENT", "sales-forecast"))
    model_name: str = field(default_factory=lambda: _env("MODEL_NAME", "sales-forecast-lgbm"))
    data_dir: Path = field(default_factory=lambda: Path(_env("DATA_DIR", str(ROOT / "data"))))
    generator_config: Path = field(
        default_factory=lambda: Path(_env("GENERATOR_CONFIG", str(ROOT / "config" / "generator.yaml")))
    )

    @property
    def public_dir(self) -> Path:
        """Snapshot versionado dos dados públicos (IBGE e feriados)."""
        return self.data_dir / "public"

    @property
    def landing_dir(self) -> Path:
        return self.data_dir / "landing"

    @property
    def truth_dir(self) -> Path:
        """Verdade do gerador (oráculo). Nunca vai para o warehouse nem para o git."""
        return self.data_dir / "ground_truth"


settings = Settings()

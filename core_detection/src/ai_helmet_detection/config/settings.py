from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path


@dataclass(frozen=True)
class PreprocessingConfig:
    ssim_threshold: float = 0.5
    blur_threshold: float = 100.0
    clahe_clip_limit: float = 2.0
    clahe_tile_grid_size: tuple[int, int] = (8, 8)


@dataclass(frozen=True)
class TrackingConfig:
    model_path: str = "yolov8n.pt"
    tracker_config: str = "botsort.yaml"
    confidence_threshold: float = 0.25
    iou_threshold: float = 0.45
    supported_class_names: tuple[str, ...] = field(default_factory=lambda: ("helmet", "other hat", "no helmet"))


@dataclass(frozen=True)
class AlertValidationConfig:
    window_size: int = 30
    alert_threshold: float = 0.8
    cooldown_seconds: float = 10.0
    evidence_dir: Path = Path("outputs/evidence")
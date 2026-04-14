from __future__ import annotations

from collections import defaultdict, deque
import csv
from dataclasses import dataclass
from datetime import datetime, timezone
import json
from pathlib import Path

import cv2
import numpy as np

from ai_helmet_detection.rule_engine import HelmetViolation, PersonValidationResult


@dataclass(frozen=True)
class OfficialAlert:
    frame_index: int
    track_id: int
    event_time: str
    source_time_seconds: float
    violation_ratio: float
    evidence_path: Path
    metadata_path: Path
    csv_path: Path
    subject_box: tuple[float, float, float, float]


class ViolationValidator:
    def __init__(
        self,
        window_size: int = 30,
        alert_threshold: float = 0.8,
        cooldown_seconds: float = 10.0,
        evidence_dir: str | Path = "outputs/evidence",
    ) -> None:
        self.window_size = window_size
        self.alert_threshold = alert_threshold
        self.cooldown_seconds = cooldown_seconds
        self.evidence_dir = Path(evidence_dir)
        self.evidence_dir.mkdir(parents=True, exist_ok=True)
        self.metadata_path = self.evidence_dir / "alerts.jsonl"
        self.csv_path = self.evidence_dir / "alerts.csv"
        self._buffers: dict[int, deque[bool]] = defaultdict(lambda: deque(maxlen=self.window_size))
        self._last_alert_times: dict[int, datetime] = {}

    def update(
        self,
        frame_index: int,
        frame: np.ndarray,
        violations: list[HelmetViolation],
        event_time: datetime | None = None,
        source_time_seconds: float = 0.0,
    ) -> list[OfficialAlert]:
        visible_ids: set[int] = set()
        alerts: list[OfficialAlert] = []
        alert_time = event_time or datetime.now(timezone.utc)
        event_time_iso = alert_time.isoformat()

        for violation in violations:
            if violation.track_id is None:
                continue

            track_id = violation.track_id
            visible_ids.add(track_id)
            self._buffers[track_id].append(bool(violation.violation))

            if self._should_trigger_alert(track_id, alert_time):
                evidence_path = self._save_evidence(frame, frame_index, violation)
                ratio = sum(self._buffers[track_id]) / len(self._buffers[track_id])
                alert = OfficialAlert(
                    frame_index=frame_index,
                    track_id=track_id,
                    event_time=event_time_iso,
                    source_time_seconds=source_time_seconds,
                    violation_ratio=ratio,
                    evidence_path=evidence_path,
                    metadata_path=self.metadata_path,
                    csv_path=self.csv_path,
                    subject_box=violation.subject_box,
                )
                self._append_metadata(alert)
                self._append_csv(alert)
                alerts.append(alert)
                self._last_alert_times[track_id] = alert_time

        self._reset_missing_tracks(visible_ids)
        return alerts

    def _should_trigger_alert(self, track_id: int, alert_time: datetime) -> bool:
        last_alert_time = self._last_alert_times.get(track_id)
        if last_alert_time is not None:
            elapsed_seconds = (alert_time - last_alert_time).total_seconds()
            if elapsed_seconds < self.cooldown_seconds:
                return False

        track_buffer = self._buffers[track_id]
        if len(track_buffer) < self.window_size:
            return False

        violation_ratio = sum(track_buffer) / len(track_buffer)
        return violation_ratio > self.alert_threshold

    def _save_evidence(
        self,
        frame: np.ndarray,
        frame_index: int,
        violation: HelmetViolation,
    ) -> Path:
        x1, y1, x2, y2 = violation.subject_box
        frame_height, frame_width = frame.shape[:2]
        left = max(int(x1), 0)
        top = max(int(y1), 0)
        right = min(int(x2), frame_width)
        bottom = min(int(y2), frame_height)

        cropped_person = frame[top:bottom, left:right]
        if cropped_person.size == 0:
            cropped_person = frame.copy()

        evidence_path = self.evidence_dir / f"track_{violation.track_id}_frame_{frame_index:05d}.jpg"
        cv2.imwrite(str(evidence_path), cropped_person)
        return evidence_path

    def _reset_missing_tracks(self, visible_ids: set[int]) -> None:
        missing_ids = set(self._buffers) - visible_ids
        for track_id in missing_ids:
            self._buffers.pop(track_id, None)
            self._last_alert_times.pop(track_id, None)

    def _append_metadata(self, alert: OfficialAlert) -> None:
        record = {
            "frame_index": alert.frame_index,
            "track_id": alert.track_id,
            "event_time": alert.event_time,
            "source_time_seconds": alert.source_time_seconds,
            "violation_ratio": alert.violation_ratio,
            "evidence_path": str(alert.evidence_path),
            "subject_box": [float(value) for value in alert.subject_box],
        }
        with self.metadata_path.open("a", encoding="utf-8") as metadata_file:
            metadata_file.write(json.dumps(record) + "\n")

    def _append_csv(self, alert: OfficialAlert) -> None:
        file_exists = self.csv_path.exists()
        with self.csv_path.open("a", encoding="utf-8", newline="") as csv_file:
            writer = csv.writer(csv_file)
            if not file_exists:
                writer.writerow([
                    "frame_index",
                    "track_id",
                    "event_time",
                    "source_time_seconds",
                    "violation_ratio",
                    "evidence_path",
                    "subject_box",
                ])
            writer.writerow([
                alert.frame_index,
                alert.track_id,
                alert.event_time,
                f"{alert.source_time_seconds:.6f}",
                f"{alert.violation_ratio:.6f}",
                str(alert.evidence_path),
                list(float(value) for value in alert.subject_box),
            ])


class TrackViolationValidator:
    def __init__(self, window_size: int = 30, required_hits: int = 24) -> None:
        self.window_size = window_size
        self.required_hits = required_hits
        # Independent sliding window per track_id so N workers create N temporal streams.
        self._histories: dict[int, deque[bool]] = defaultdict(lambda: deque(maxlen=self.window_size))

    def update_tracks(self, potential_by_track: dict[int, bool]) -> dict[int, float]:
        visible_ids = set(potential_by_track)
        confirmed_ratios: dict[int, float] = {}

        for track_id, potential_violation in potential_by_track.items():
            history = self._histories[track_id]
            history.append(potential_violation)
            if len(history) == self.window_size:
                hit_count = sum(history)
                if hit_count >= self.required_hits:
                    confirmed_ratios[track_id] = hit_count / self.window_size

        missing_ids = set(self._histories) - visible_ids
        for track_id in missing_ids:
            self._histories.pop(track_id, None)

        return confirmed_ratios

    def update_results(self, results: list[PersonValidationResult]) -> dict[int, float]:
        return self.update_tracks({result.track_id: result.potential_violation for result in results})
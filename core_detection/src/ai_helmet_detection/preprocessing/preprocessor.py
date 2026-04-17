from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Iterator, Optional, Tuple, Union
from urllib.parse import urlparse

import cv2
import numpy as np



FrameSource = Union[str, int, Path, np.ndarray]


@dataclass(frozen=True)
class PreprocessingResult:
    original_frame: np.ndarray
    processed_frame: np.ndarray
    blur_score: float
    inference_allowed: bool


class Preprocessor:
    def __init__(
        self,
        ssim_threshold: float = 0.5,
        blur_threshold: float = 100.0,
        clahe_clip_limit: float = 2.0,
        clahe_tile_grid_size: Tuple[int, int] = (8, 8),
    ) -> None:
        self.ssim_threshold = ssim_threshold
        self.blur_threshold = blur_threshold
        self.clahe = cv2.createCLAHE(
            clipLimit=clahe_clip_limit,
            tileGridSize=clahe_tile_grid_size,
        )

    def is_blurred(self, frame: np.ndarray, threshold: float = 100.0) -> bool:
        gray_frame = self._to_grayscale(frame)
        laplacian_variance = cv2.Laplacian(gray_frame, cv2.CV_64F).var()
        return float(laplacian_variance) < float(threshold)

    def is_glitch(
        self,
        current_frame: np.ndarray,
        prev_frame: Optional[np.ndarray],
        threshold: float = 0.5,
    ) -> bool:
        if prev_frame is None:
            return False

        score = self._compute_ssim(current_frame, prev_frame)
        return score < float(threshold)

    def preprocess_frame(
        self,
        frame: np.ndarray,
        prev_frame: Optional[np.ndarray] = None,
    ) -> Tuple[str, np.ndarray, dict[str, float]]:
        blur_score = self._laplacian_variance(frame)
        is_blurred = self.is_blurred(frame, threshold=self.blur_threshold)
        ssim_score = self._compute_ssim(frame, prev_frame)
        is_glitch = self.is_glitch(frame, prev_frame, threshold=self.ssim_threshold)

        frame_metrics = {
            "ssim": ssim_score,
            "laplacian_variance": blur_score,
        }

        if is_blurred or is_glitch:
            return "Skip", frame, frame_metrics

        return "Process", self.apply_clahe(frame), frame_metrics

    def process_frame(
        self,
        frame: np.ndarray,
        previous_frame: Optional[np.ndarray] = None,
    ) -> Tuple[bool, np.ndarray, dict[str, float]]:
        status, processed_frame, frame_metrics = self.preprocess_frame(frame, previous_frame)
        return status != "Skip", processed_frame, frame_metrics

    def process_input(
        self,
        source: FrameSource,
    ) -> Iterator[Tuple[np.ndarray, dict[str, float]]]:
        if isinstance(source, np.ndarray):
            keep_frame, processed_frame, frame_metrics = self.process_frame(source)
            if keep_frame:
                yield processed_frame, frame_metrics
            return

        if isinstance(source, int):
            yield from self._process_capture(source)
            return

        if isinstance(source, Path):
            source = str(source)

        if self._is_stream_source(source):
            yield from self._process_capture(source)
            return

        source_path = Path(source)

        if source_path.exists() and self._is_image_file(source_path):
            frame = cv2.imread(str(source_path))
            if frame is None:
                raise ValueError(f"Unable to read image: {source}")

            keep_frame, processed_frame, frame_metrics = self.process_frame(frame)
            if keep_frame:
                yield processed_frame, frame_metrics
            return

        if not source_path.exists():
            raise FileNotFoundError(f"Input source not found: {source}")

        yield from self._process_capture(str(source_path))

    def check_ssim(
        self,
        current_frame: np.ndarray,
        previous_frame: Optional[np.ndarray],
    ) -> Tuple[bool, float]:
        score = self._compute_ssim(current_frame, previous_frame)
        return score >= self.ssim_threshold, score

    def detect_blur(self, frame: np.ndarray) -> Tuple[bool, float]:
        laplacian_variance = self._laplacian_variance(frame)
        return laplacian_variance >= self.blur_threshold, float(laplacian_variance)

    def apply_clahe(self, frame: np.ndarray) -> np.ndarray:
        lab_frame = cv2.cvtColor(frame, cv2.COLOR_BGR2LAB)
        l_channel, a_channel, b_channel = cv2.split(lab_frame)
        enhanced_l_channel = self.clahe.apply(l_channel)
        enhanced_lab_frame = cv2.merge((enhanced_l_channel, a_channel, b_channel))
        return cv2.cvtColor(enhanced_lab_frame, cv2.COLOR_LAB2BGR)

    def _compute_ssim(
        self,
        current_frame: np.ndarray,
        previous_frame: Optional[np.ndarray],
    ) -> float:
        if previous_frame is None:
            return 1.0

        current_gray = self._to_grayscale(current_frame)
        previous_gray = self._to_grayscale(previous_frame)

        if current_gray.shape != previous_gray.shape:
            return 0.0

        # Sử dụng thuật toán MSE siêu nhẹ thay cho SSIM cấu trúc
        curr_small = cv2.resize(current_gray, (64, 48))
        prev_small = cv2.resize(previous_gray, (64, 48))
        
        err = cv2.norm(curr_small, prev_small, cv2.NORM_L2)
        mse = (err * err) / float(64 * 48)
        
        # Chuyển đổi MSE thành thang đo SSIM giả lập (Tỷ lệ nghịch)
        # Giới hạn MSE từ 0 đến khoảng 2000+. MSE càng cao -> Khác biệt càng lớn (SSIM gần 0)
        max_error = 1500.0
        pseudo_ssim = max(0.0, 1.0 - (mse / max_error))
        
        return float(pseudo_ssim)

    def _laplacian_variance(self, frame: np.ndarray) -> float:
        gray_frame = self._to_grayscale(frame)
        return float(cv2.Laplacian(gray_frame, cv2.CV_64F).var())

    def _process_capture(
        self,
        source: Union[str, int],
    ) -> Iterator[Tuple[np.ndarray, dict[str, float]]]:
        capture = cv2.VideoCapture(source)
        if not capture.isOpened():
            raise ValueError(f"Unable to open video source: {source}")

        previous_frame: Optional[np.ndarray] = None
        try:
            while True:
                has_frame, frame = capture.read()
                if not has_frame:
                    break

                keep_frame, processed_frame, frame_metrics = self.process_frame(frame, previous_frame)
                previous_frame = frame

                if keep_frame:
                    yield processed_frame, frame_metrics
        finally:
            capture.release()

    @staticmethod
    def _is_image_file(source_path: Path) -> bool:
        return source_path.suffix.lower() in {
            ".bmp",
            ".jpeg",
            ".jpg",
            ".png",
            ".tif",
            ".tiff",
            ".webp",
        }

    @staticmethod
    def _is_stream_source(source: str) -> bool:
        parsed_source = urlparse(source)
        return parsed_source.scheme.lower() in {
            "http",
            "https",
            "rtmp",
            "rtsp",
            "rtp",
            "tcp",
            "udp",
        }

    @staticmethod
    def _to_grayscale(frame: np.ndarray) -> np.ndarray:
        if frame is None or frame.size == 0:
            raise ValueError("Input frame must be a non-empty numpy array.")

        if frame.ndim == 2:
            return frame

        if frame.ndim == 3:
            return cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)

        raise ValueError("Input frame must be a 2D grayscale or 3D BGR image.")


class FramePreprocessor:
    def __init__(
        self,
        blur_threshold: float = 60.0,
        clahe_clip_limit: float = 2.0,
        clahe_tile_grid_size: Tuple[int, int] = (8, 8),
    ) -> None:
        self.blur_threshold = blur_threshold
        self.clahe = cv2.createCLAHE(
            clipLimit=clahe_clip_limit,
            tileGridSize=clahe_tile_grid_size,
        )

    def process_frame(self, frame: np.ndarray) -> PreprocessingResult:
        original_frame = frame.copy()
        processed_frame = self.apply_clahe_lab(frame)
        blur_score = self.compute_blur_score(processed_frame)
        inference_allowed = blur_score >= self.blur_threshold
        return PreprocessingResult(
            original_frame=original_frame,
            processed_frame=processed_frame,
            blur_score=blur_score,
            inference_allowed=inference_allowed,
        )

    def apply_clahe_lab(self, frame: np.ndarray) -> np.ndarray:
        lab_frame = cv2.cvtColor(frame, cv2.COLOR_BGR2LAB)
        l_channel, a_channel, b_channel = cv2.split(lab_frame)
        enhanced_l_channel = self.clahe.apply(l_channel)
        enhanced_lab_frame = cv2.merge((enhanced_l_channel, a_channel, b_channel))
        return cv2.cvtColor(enhanced_lab_frame, cv2.COLOR_LAB2BGR)

    @staticmethod
    def compute_blur_score(frame: np.ndarray) -> float:
        gray_frame = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        return float(cv2.Laplacian(gray_frame, cv2.CV_64F).var())


class PreProcessor(Preprocessor):
    pass
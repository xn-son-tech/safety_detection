from __future__ import annotations

from dataclasses import dataclass
from typing import Optional, Tuple

import cv2
import numpy as np


@dataclass(frozen=True)
class PreprocessOutput:
	should_process: bool
	cleaned_frame: np.ndarray
	is_blurred: bool
	is_glitch: bool
	blur_score: float
	ssim_score: float


class Preprocessor:
	def __init__(
		self,
		blur_threshold: float = 100.0,
		ssim_threshold: float = 0.5,
		clahe_clip_limit: float = 5.0,
		clahe_tile_grid_size: Tuple[int, int] = (8, 8),
		ssim_check_interval: int = 2,
		ssim_resize_shape: Tuple[int, int] = (320, 180),
		ssim_win_size: int = 7,
		# Step 1 – Gamma Correction: gamma > 1.0 darkens mid-tones so a white helmet
		# stands out more against a bright background before CLAHE runs.
		gamma: float = 1.5,
		# Step 2 – Edge Reinforcement: strength of the Unsharp Mask applied after CLAHE.
		# Set to 0.0 to disable.
		unsharp_amount: float = 0.5,
		# Step 3 – Adaptive ROI: mean-brightness threshold (0–255) above which the
		# head-ROI CLAHE switches to the high-brightness clipLimit.
		brightness_threshold: float = 200.0,
		high_brightness_clip_limit: float = 8.0,
	) -> None:
		self.blur_threshold = blur_threshold
		self.ssim_threshold = ssim_threshold
		self.ssim_check_interval = max(int(ssim_check_interval), 1)
		self.ssim_resize_shape = (
			max(int(ssim_resize_shape[0]), 32),
			max(int(ssim_resize_shape[1]), 32),
		)
		self.ssim_win_size = max(int(ssim_win_size), 3)
		self._frame_index = 0
		self.gamma = gamma
		self.unsharp_amount = unsharp_amount
		self.brightness_threshold = brightness_threshold
		self.clahe = cv2.createCLAHE(
			clipLimit=clahe_clip_limit,
			tileGridSize=clahe_tile_grid_size,
		)
		# Pre-built high-brightness CLAHE for adaptive head-ROI processing (Step 3).
		self._clahe_high_brightness = cv2.createCLAHE(
			clipLimit=high_brightness_clip_limit,
			tileGridSize=clahe_tile_grid_size,
		)

	@staticmethod
	def _to_gray(frame: np.ndarray) -> np.ndarray:
		if frame is None or frame.size == 0:
			raise ValueError("Input frame must be a non-empty numpy array.")
		if frame.ndim == 2:
			return frame
		if frame.ndim == 3:
			return cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
		raise ValueError("Input frame must be a 2D grayscale or 3D BGR image.")

	@staticmethod
	def _apply_gamma(frame: np.ndarray, gamma: float) -> np.ndarray:
		"""Apply gamma correction via a precomputed LUT.

		gamma > 1.0 darkens mid-tones and highlights, making a white helmet's
		silhouette more distinct against an over-exposed background.
		"""
		lut = np.array(
			[((i / 255.0) ** gamma) * 255 for i in range(256)], dtype=np.uint8
		)
		return cv2.LUT(frame, lut)

	@staticmethod
	def _apply_unsharp_mask(
		frame: np.ndarray, amount: float = 0.5, blur_ksize: int = 5
	) -> np.ndarray:
		"""Unsharp masking: Result = frame + (frame - blurred) * amount.

		Reinforces helmet boundary edges after CLAHE without introducing
		colour artefacts (operates in BGR space, all channels equally).
		"""
		blurred = cv2.GaussianBlur(frame, (blur_ksize, blur_ksize), 0)
		return cv2.addWeighted(frame, 1.0 + amount, blurred, -amount, 0)

	def apply_clahe(self, frame: np.ndarray) -> np.ndarray:
		# Step 1: Gamma correction – darken mid-tones/highlights so the white helmet
		# edges emerge from the bright background before local contrast is boosted.
		gamma_corrected = self._apply_gamma(frame, self.gamma)

		# Step 2: Adaptive histogram equalisation on LAB L-channel.
		# Stronger clipLimit helps helmet edges emerge in high-glare scenes.
		lab_frame = cv2.cvtColor(gamma_corrected, cv2.COLOR_BGR2LAB)
		l_channel, a_channel, b_channel = cv2.split(lab_frame)
		enhanced_l = self.clahe.apply(l_channel)
		enhanced_lab = cv2.merge((enhanced_l, a_channel, b_channel))
		clahe_result = cv2.cvtColor(enhanced_lab, cv2.COLOR_LAB2BGR)

		# Step 2 continued – Unsharp masking: burns helmet edges after CLAHE.
		# Formula: Result = frame + (frame - blurred) * amount
		if self.unsharp_amount > 0.0:
			clahe_result = self._apply_unsharp_mask(clahe_result, self.unsharp_amount)

		return clahe_result

	def apply_clahe_to_region(
		self,
		region_frame: np.ndarray,
		debug_label: str = "Head ROI",
	) -> tuple[np.ndarray, float]:
		"""Apply adaptive-strength CLAHE to a specific region (e.g., a head ROI crop).

		Step 3 – Adaptive Thresholding (Internal):
		  If the mean brightness of the region exceeds `brightness_threshold`,
		  the stronger `_clahe_high_brightness` object is used to force local
		  contrast in the over-exposed area.

		Step 4 – Verification:
		  Always prints the Brightness Mean so exposure levels can be monitored.

		Args:
			region_frame: BGR crop of the region to enhance.
			debug_label:  Label shown in the debug print (e.g. "Person ID=3").

		Returns:
			Tuple of (enhanced_region, brightness_mean).
		"""
		gray = self._to_gray(region_frame)
		brightness_mean = float(gray.mean())

		if brightness_mean > self.brightness_threshold:
			active_clahe = self._clahe_high_brightness
			mode_label = "HIGH → boosted CLAHE"
		else:
			active_clahe = self.clahe
			mode_label = "NORMAL"

		# Step 4: debug print for live exposure monitoring.
		print(
			f"[Preprocessor] {debug_label} Brightness Mean: {brightness_mean:.1f} "
			f"(threshold: {self.brightness_threshold:.0f}, mode: {mode_label})"
		)

		lab_frame = cv2.cvtColor(region_frame, cv2.COLOR_BGR2LAB)
		l_channel, a_channel, b_channel = cv2.split(lab_frame)
		enhanced_l = active_clahe.apply(l_channel)
		enhanced_lab = cv2.merge((enhanced_l, a_channel, b_channel))
		return cv2.cvtColor(enhanced_lab, cv2.COLOR_LAB2BGR), brightness_mean

	def blur_score(self, frame: np.ndarray) -> float:
		gray = self._to_gray(frame)
		return float(cv2.Laplacian(gray, cv2.CV_64F).var())

	def is_blurred(self, frame: np.ndarray, threshold: float = 100.0) -> bool:
		return self.blur_score(frame) < float(threshold)

	def is_glitch(
		self,
		current_frame: np.ndarray,
		prev_frame: Optional[np.ndarray],
		threshold: float = 0.5,
	) -> tuple[bool, float]:
		if prev_frame is None:
			return False, 1.0

		current_gray = self._to_gray(current_frame)
		prev_gray = self._to_gray(prev_frame)
		if current_gray.shape != prev_gray.shape:
			return True, 0.0

		# Downsample before MSE to avoid allocating large intermediate buffers on
		# full-resolution webcam frames. cv2.resize expects (width, height).
		current_small = cv2.resize(
			current_gray,
			self.ssim_resize_shape,
			interpolation=cv2.INTER_AREA,
		)
		prev_small = cv2.resize(
			prev_gray,
			self.ssim_resize_shape,
			interpolation=cv2.INTER_AREA,
		)

		# OpenCV Mean Squared Error (MSE) runs natively in C
		diff = cv2.subtract(current_small, prev_small)
		err = np.sum(diff.astype(np.float32)**2) / float(current_small.shape[0] * current_small.shape[1])
		
		# Set an MSE threshold equivalent to old SSIM tearing detection
		mse_threshold = 2000.0 if self.ssim_threshold < 0.5 else 1000.0

		# Convert error to a similarity-like score (0 to 1) for backwards compatibility
		score = 1.0 / (1.0 + err / 1000.0)

		# Release temporary arrays promptly to reduce memory pressure in long runs.
		del current_small
		del prev_small
		return (err > mse_threshold), score

	def process(self, frame: np.ndarray, prev_frame: Optional[np.ndarray]) -> PreprocessOutput:
		self._frame_index += 1
		current_blur_score = self.blur_score(frame)
		detected_blur = current_blur_score < self.blur_threshold

		detected_glitch = False
		ssim_score = 1.0
		# Only run SSIM every N frames to keep CPU/memory usage bounded.
		if self._frame_index % self.ssim_check_interval == 0:
			detected_glitch, ssim_score = self.is_glitch(frame, prev_frame, threshold=self.ssim_threshold)

		cleaned = self.apply_clahe(frame)
		should_process = not detected_blur and not detected_glitch
		return PreprocessOutput(
			should_process=should_process,
			cleaned_frame=cleaned,
			is_blurred=detected_blur,
			is_glitch=detected_glitch,
			blur_score=current_blur_score,
			ssim_score=ssim_score,
		)


class PreProcessor(Preprocessor):
	pass


__all__ = ["PreprocessOutput", "PreProcessor", "Preprocessor"]

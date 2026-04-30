import time
from collections import deque


class PostureAssessment:
    """
    Converts noisy frame-level posture metrics into stable posture states.
    """

    def __init__(self, config=None):
        posture_config = (config or {}).get("posture", {})
        self.thresholds = posture_config.get("thresholds", {})
        self.quality_min_visibility = posture_config.get("quality_min_visibility", 0.55)
        self.smoothing_window = posture_config.get("smoothing_window", 12)
        self.calibration_seconds = posture_config.get("calibration_seconds", 3.0)
        self.sustain_seconds = posture_config.get("sustain_seconds", 2.0)

        self.history = {}
        self.baseline_samples = []
        self.baseline = {}
        self.started_at = time.monotonic()
        self.bad_since = None

    def reset_calibration(self):
        self.history.clear()
        self.baseline_samples.clear()
        self.baseline.clear()
        self.started_at = time.monotonic()
        self.bad_since = None

    def _smooth_metric(self, name, value):
        if value is None:
            return None
        window = self.history.setdefault(name, deque(maxlen=self.smoothing_window))
        window.append(float(value))
        return sum(window) / len(window)

    def _smooth(self, metrics):
        smoothed = {}
        for key, value in metrics.items():
            if isinstance(value, (int, float)):
                smoothed[key] = self._smooth_metric(key, value)
            else:
                smoothed[key] = value
        return smoothed

    def _threshold(self, name, default):
        return float(self.thresholds.get(name, default))

    def _update_baseline(self, metrics):
        if time.monotonic() - self.started_at > self.calibration_seconds:
            if not self.baseline and self.baseline_samples:
                keys = (
                    "forward_head_angle",
                    "forward_head_offset_norm",
                    "head_lateral_offset_norm",
                    "forward_head_projection_norm",
                    "neck_compaction_norm",
                    "shoulder_height_delta_norm",
                )
                for key in keys:
                    vals = [sample[key] for sample in self.baseline_samples if sample.get(key) is not None]
                    if vals:
                        self.baseline[key] = sum(vals) / len(vals)
            return

        self.baseline_samples.append(dict(metrics))

    def _deviation(self, metrics, key):
        value = metrics.get(key)
        if value is None:
            return None
        return value - self.baseline.get(key, 0.0)

    def assess(self, metrics):
        if not metrics:
            self.bad_since = None
            return {
                "metrics": {},
                "issues": [],
                "status": "no_pose",
                "score": 0,
                "calibrating": False,
                "sustained_bad": False,
            }

        smoothed = self._smooth(metrics)
        quality_ok = smoothed.get("landmark_min_visibility", 1.0) >= self.quality_min_visibility
        self._update_baseline(smoothed)
        calibrating = time.monotonic() - self.started_at <= self.calibration_seconds

        enriched = dict(smoothed)
        enriched["forward_head_angle_deviation"] = self._deviation(smoothed, "forward_head_angle")
        enriched["forward_head_offset_deviation"] = self._deviation(smoothed, "forward_head_offset_norm")
        enriched["head_lateral_offset_deviation"] = self._deviation(smoothed, "head_lateral_offset_norm")
        enriched["forward_head_projection_deviation"] = self._deviation(smoothed, "forward_head_projection_norm")
        enriched["neck_compaction_deviation"] = self._deviation(smoothed, "neck_compaction_norm")
        enriched["shoulder_height_delta_deviation"] = self._deviation(smoothed, "shoulder_height_delta_norm")

        if not quality_ok:
            self.bad_since = None
            return {
                "metrics": enriched,
                "issues": [],
                "status": "low_confidence",
                "score": 0,
                "calibrating": calibrating,
                "sustained_bad": False,
            }

        issues = self._issues(enriched)
        score = sum(issue["severity"] for issue in issues)
        status = "critical" if score >= 4 else "warning" if score else "good"

        now = time.monotonic()
        if status in ("warning", "critical") and not calibrating:
            if self.bad_since is None:
                self.bad_since = now
        else:
            self.bad_since = None

        sustained_bad = self.bad_since is not None and now - self.bad_since >= self.sustain_seconds

        return {
            "metrics": enriched,
            "issues": issues,
            "status": status,
            "score": score,
            "calibrating": calibrating,
            "sustained_bad": sustained_bad,
        }

    def _issues(self, metrics):
        issues = []

        shoulder_abs = abs(metrics.get("shoulder_slope", 0.0))
        shoulder_height_abs = abs(
            metrics.get("shoulder_height_delta_deviation")
            if metrics.get("shoulder_height_delta_deviation") is not None
            else metrics.get("shoulder_height_delta_norm", 0.0)
        )
        shoulder_balance_score = max(
            shoulder_abs / max(self._threshold("shoulder_slope_critical", 6.0), 1e-6),
            shoulder_height_abs / max(self._threshold("shoulder_height_delta_critical", 0.08), 1e-6),
        )
        self._append_issue(
            issues,
            shoulder_balance_score,
            0.6,
            1.0,
            "Relax shoulders and keep them level",
            "shoulder_balance",
        )

        head_tilt_abs = abs(metrics.get("head_tilt", 0.0))
        self._append_issue(
            issues,
            head_tilt_abs,
            self._threshold("head_tilt_warning", 5.0),
            self._threshold("head_tilt_critical", 10.0),
            "Keep your head upright",
            "head_tilt",
        )

        lateral = abs(metrics.get("head_lateral_offset_deviation") or metrics.get("head_lateral_offset_norm", 0.0))
        self._append_issue(
            issues,
            lateral,
            self._threshold("head_lateral_offset_warning", 0.08),
            self._threshold("head_lateral_offset_critical", 0.14),
            "Center your head over your shoulders",
            "head_lateral_offset_norm",
        )

        forward_angle = metrics.get("forward_head_angle_deviation")
        if forward_angle is None:
            forward_angle = metrics.get("forward_head_angle", 0.0)
        forward_angle_risk = max(0.0, abs(forward_angle))
        forward_offset = metrics.get("forward_head_offset_deviation")
        forward_offset_risk = 0.0 if forward_offset is None else max(0.0, -forward_offset)
        projection = metrics.get("forward_head_projection_deviation")
        projection_risk = 0.0 if projection is None else max(0.0, abs(projection))
        neck_compaction = metrics.get("neck_compaction_deviation")
        neck_compaction_risk = 0.0 if neck_compaction is None else max(0.0, -neck_compaction)

        forward_head_score = max(
            forward_angle_risk / max(self._threshold("forward_head_warning", 10.0), 1e-6),
            forward_offset_risk / max(self._threshold("forward_head_offset_warning", 0.08), 1e-6),
            projection_risk / max(self._threshold("forward_head_projection_warning", 0.08), 1e-6),
            neck_compaction_risk / max(self._threshold("neck_compaction_warning", 0.05), 1e-6),
        )
        self._append_issue(
            issues,
            forward_head_score,
            1.0,
            2.0,
            "Sit tall and pull your head straight back",
            "forward_head_posture",
        )

        return issues

    def _append_issue(self, issues, value, warning, critical, message, metric):
        if value >= critical:
            issues.append({"message": message, "metric": metric, "value": value, "severity": 2})
        elif value >= warning:
            issues.append({"message": message, "metric": metric, "value": value, "severity": 1})

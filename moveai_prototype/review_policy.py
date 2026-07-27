"""DESIGN.md SS5b review-state policy -- turns the signals captured at
measurement time (Build 4) into one of the three named states. Pure logic,
no db/Streamlit imports, mirroring pricing.py/priors.py.

SS5b's interrupt-rule sentence names only shell ratio, border truncation, and
implausible dimension as customer-confirm triggers ("the customer cannot
assess whether a measurement is geometrically sound"). The roadmap's Build 5
line separately lists point count and axis-aligned fallback as signals to
act on. Reconciled by routing the geometric-soundness signals -- ones a
customer has no basis to judge -- to staff_escalate instead of a customer
prompt, and reserving customer_confirm for signals a plain-language question
can resolve ("is this really a sofa?", "is this ~2.1 m long?").

MIN_DETECTION_CONFIDENCE and MIN_POINT_COUNT are uncalibrated placeholders
(DESIGN.md Calibration section), not measured thresholds.

Precedence: staff_escalate > customer_confirm > auto_accept.
"""

from __future__ import annotations

from dataclasses import dataclass

import priors


MIN_DETECTION_CONFIDENCE = 0.35
MIN_POINT_COUNT = 200


@dataclass(frozen=True)
class ReviewDecision:
    state: str
    reason: str | None
    signals: tuple[str, ...]
    shell_ratio: float | None
    implausible_dimension: bool


def classify(
    *,
    label: str,
    detection_confidence: float | None,
    point_count: int | None,
    used_axis_aligned_fallback: bool,
    mask_touches_border: bool,
    width_m: float | None,
    height_m: float | None,
    depth_m: float | None,
    measurement_error: str | None = None,
) -> ReviewDecision:
    """Classify one measured item into auto_accept / customer_confirm /
    staff_escalate, recording every signal that fired so the caller can
    store it on the row rather than recompute it at display time.
    """
    if measurement_error is not None:
        return ReviewDecision(
            state="staff_escalate",
            reason=f"Measurement failed: {measurement_error}",
            signals=("measurement_failed",),
            shell_ratio=None,
            implausible_dimension=False,
        )

    dimension_flags = {}
    for axis, value in (("width_m", width_m), ("height_m", height_m), ("depth_m", depth_m)):
        if value is not None:
            dimension_flags[axis] = priors.flag_implausible_dimension(label, axis, value)

    implausible_dimension = any(
        flag.has_prior and flag.flagged for flag in dimension_flags.values()
    )
    implausible_reasons = [
        flag.reason
        for flag in dimension_flags.values()
        if flag.has_prior and flag.flagged and flag.reason
    ]

    expected_depth = priors.expected_depth_m(label)
    shell_ratio = (
        depth_m / expected_depth if depth_m is not None and expected_depth else None
    )
    # A shell ratio well below 1.0 means the fitted depth is much shallower
    # than the class-expected depth -- a front-facing shell, not a real
    # measurement. No threshold fires today since expected_depth_m() is a
    # stub (Build 3 scope) and always returns None.
    shell_flagged = shell_ratio is not None and shell_ratio < 0.5

    escalate_signals = []
    if used_axis_aligned_fallback:
        escalate_signals.append("used_axis_aligned_fallback")
    if point_count is not None and point_count < MIN_POINT_COUNT:
        escalate_signals.append("low_point_count")

    if escalate_signals:
        return ReviewDecision(
            state="staff_escalate",
            reason=(
                "Geometric fit could not be fully trusted "
                f"({', '.join(escalate_signals)}); needs staff review."
            ),
            signals=tuple(escalate_signals),
            shell_ratio=shell_ratio,
            implausible_dimension=implausible_dimension,
        )

    confirm_signals = []
    if mask_touches_border:
        confirm_signals.append("mask_touches_border")
    if detection_confidence is not None and detection_confidence < MIN_DETECTION_CONFIDENCE:
        confirm_signals.append("low_detection_confidence")
    if shell_flagged:
        confirm_signals.append("shell_ratio")
    if implausible_dimension:
        confirm_signals.append("implausible_dimension")

    if confirm_signals:
        if "shell_ratio" in confirm_signals or "implausible_dimension" in confirm_signals:
            reason = "; ".join(implausible_reasons) or "Dimension looked atypical for this item type."
        elif "mask_touches_border" in confirm_signals:
            reason = "This item's photo edge was cropped -- please confirm the size looks right."
        else:
            reason = "We weren't fully confident this detection is correct -- please confirm."
        return ReviewDecision(
            state="customer_confirm",
            reason=reason,
            signals=tuple(confirm_signals),
            shell_ratio=shell_ratio,
            implausible_dimension=implausible_dimension,
        )

    return ReviewDecision(
        state="auto_accept",
        reason=None,
        signals=(),
        shell_ratio=shell_ratio,
        implausible_dimension=implausible_dimension,
    )

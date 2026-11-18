"""BƯỚC 4 — Cửa chặn: quyết định Release / Hold / Rework.   ★

Test:  pytest tests/test_gate.py -q
"""
from ..common import ERROR, WARN


def decide(issues, image_stems, cfg, reviewed=frozenset()):
    stem_set = set(image_stems)
    reviewed_set = set(reviewed)
    n_images = len(stem_set)
    hold_thr = cfg["gate"]["warn_ratio_hold"]

    n_errors = sum(1 for i in issues if i.severity == ERROR)
    warn_imgs = {
        i.image
        for i in issues
        if i.severity == WARN and i.image in stem_set and i.image not in reviewed_set
    }
    n_warn_images = len(warn_imgs)
    raw_ratio = (n_warn_images / n_images) if n_images > 0 else 0.0
    warn_ratio = round(raw_ratio, 4)

    if n_errors > 0:
        decision = "Rework"
        reasons = [
            f"Còn {n_errors} lỗi bắt buộc (severity ERROR) chưa được khắc phục -> Rework (chặn xuất dữ liệu)."
        ]
    elif n_images > 0 and raw_ratio >= hold_thr:
        decision = "Hold"
        reasons = [
            f"Còn {n_warn_images}/{n_images} ảnh ({warn_ratio * 100:.1f}%) có cảnh báo chưa duyệt >= ngưỡng Hold {hold_thr * 100:.1f}% -> Hold."
        ]
    else:
        decision = "Release"
        reasons = [
            f"Không còn lỗi bắt buộc (0 ERROR) và tỉ lệ ảnh cảnh báo chưa duyệt {n_warn_images}/{n_images} ({warn_ratio * 100:.1f}%) < ngưỡng {hold_thr * 100:.1f}% -> Release."
        ]

    return {
        "decision": decision,
        "n_errors": n_errors,
        "n_warn_images": n_warn_images,
        "n_images": n_images,
        "warn_ratio": warn_ratio,
        "reasons": reasons,
    }

"""CHECK 2 — Dòng nhãn YOLO: sai định dạng, ID lớp lạ, box tràn ảnh, box rỗng, box lặp.   (Script 2 trong slide)   ★★

Test:  pytest tests/test_label_format.py -q
"""
from ..common import ERROR, WARN, Issue, iou_xywh, parse_yolo_line


def run(ds, cfg):
    c = cfg["label_format"]
    tol = c["overflow_tol"]
    min_px = c["min_box_px"]
    max_frac = c["max_box_frac"]
    dup_iou = c["dup_box_iou"]
    n_classes = len(ds.classes)

    issues = []
    for lf in ds.label_files():
        stem = lf.stem
        lines = ds.read_label_lines(stem)
        if not lines:
            continue
        size = ds.image_size(stem)
        seen = []

        for line_no, text in lines:
            try:
                cls_id, cx, cy, w, h = parse_yolo_line(text)
            except ValueError as e:
                issues.append(
                    Issue("label_format", ERROR, "BAD_FORMAT", stem, f"sai định dạng: {e}", line=line_no)
                )
                continue

            if not (0 <= cls_id < n_classes):
                issues.append(
                    Issue(
                        "label_format",
                        ERROR,
                        "BAD_CLASS_ID",
                        stem,
                        f"id lớp {cls_id} ngoài 0..{n_classes - 1}",
                        line=line_no,
                        extra={"class_id": cls_id},
                    )
                )
                continue

            if w <= 0 or h <= 0:
                issues.append(
                    Issue(
                        "label_format",
                        ERROR,
                        "BOX_ZERO",
                        stem,
                        f"kích thước box <= 0 (w={w}, h={h})",
                        line=line_no,
                    )
                )
                continue

            x1, y1, x2, y2 = cx - w / 2.0, cy - h / 2.0, cx + w / 2.0, cy + h / 2.0
            overflow = max(0.0, -x1, -y1, x2 - 1.0, y2 - 1.0)
            if overflow > tol:
                issues.append(
                    Issue(
                        "label_format",
                        ERROR,
                        "BOX_OUT_OF_IMAGE",
                        stem,
                        f"box tràn ngoài ảnh {overflow:.4f}",
                        line=line_no,
                        extra={"overflow": round(overflow, 6)},
                    )
                )

            box = (cx, cy, w, h)
            if any(pc == cls_id and iou_xywh(pb, box) > dup_iou for pc, pb in seen):
                issues.append(
                    Issue(
                        "label_format",
                        ERROR,
                        "DUP_BOX",
                        stem,
                        f"box lặp cùng lớp {cls_id} với dòng trước",
                        line=line_no,
                    )
                )
            seen.append((cls_id, box))

            if size is not None:
                W, H = size
                short_side = min(w * W, h * H)
                if short_side < min_px:
                    issues.append(
                        Issue(
                            "label_format",
                            WARN,
                            "BOX_TINY",
                            stem,
                            f"cạnh ngắn {short_side:.1f}px < {min_px}px",
                            line=line_no,
                            extra={"min_px": round(short_side, 2)},
                        )
                    )

            area_frac = w * h
            if area_frac > max_frac:
                issues.append(
                    Issue(
                        "label_format",
                        WARN,
                        "BOX_HUGE",
                        stem,
                        f"diện tích box {area_frac:.3f} > {max_frac}",
                        line=line_no,
                        extra={"area_frac": round(area_frac, 4)},
                    )
                )

    return issues

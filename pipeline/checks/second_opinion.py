"""CHECK 6 — Ý kiến thứ hai: so nhãn với một model LỚN HƠN (yolo26l).   ★★★

Test:  pytest tests/test_second_opinion.py -q
"""
from ..common import WARN, Issue, iou_xywh, parse_yolo_line
from ..model_cache import get_preds


def run(ds, cfg, preds=None):
    if preds is None:
        preds = get_preds(ds, cfg, "checker")

    c = cfg["second_opinion"]
    conf_thr = c["conf"]
    min_area_px = c["min_area_px"]
    fp_conf = c["fp_conf"]
    iou_missing = c["iou_missing"]
    iou_match = c["iou_match"]
    iou_loose = c["iou_loose"]
    classes = ds.classes
    n_classes = len(classes)

    def cname(cid: int) -> str:
        return classes[cid] if 0 <= cid < n_classes else str(cid)

    issues = []
    for p in ds.image_files():
        stem = p.stem
        if stem not in preds:
            continue
        raw_lines = ds.read_label_lines(stem)
        if raw_lines is None:
            continue
        size = ds.image_size(stem)
        if size is None:
            continue
        W, H = size

        labeled = []  # (line_no, cls_id, (cx, cy, w, h))
        for line_no, text in raw_lines:
            try:
                cls_id, cx, cy, w, h = parse_yolo_line(text)
            except ValueError:
                continue
            if 0 <= cls_id < n_classes and w > 0 and h > 0:
                labeled.append((line_no, cls_id, (cx, cy, w, h)))

        img_preds = preds[stem] or []

        # 1. Kiểm theo dự đoán của model: MISSING / LOOSE_BOX / WRONG_CLASS
        for r in img_preds:
            p_cls = int(r[0])
            p_conf = float(r[1])
            px, py, pw, ph = float(r[2]), float(r[3]), float(r[4]), float(r[5])
            if p_conf < conf_thr:
                continue
            area_px = (pw * W) * (ph * H)
            if area_px < min_area_px:
                continue

            p_box = (px, py, pw, ph)
            cands = []
            for line_no, l_cls, l_box in labeled:
                v = iou_xywh(p_box, l_box)
                if v >= iou_missing:
                    cands.append((line_no, l_cls, v))

            if not cands:
                issues.append(
                    Issue(
                        "second_opinion",
                        WARN,
                        "POSSIBLE_MISSING",
                        stem,
                        f"model thấy {cname(p_cls)} (conf={p_conf:.2f}) nhưng nhãn không có box khớp",
                        extra={"pred_cls": p_cls, "conf": round(p_conf, 4)},
                    )
                )
                continue

            same = [v for _, l_cls, v in cands if l_cls == p_cls]
            if same:
                best_same = max(same)
                if best_same < iou_loose:
                    issues.append(
                        Issue(
                            "second_opinion",
                            WARN,
                            "POSSIBLE_LOOSE_BOX",
                            stem,
                            f"box {cname(p_cls)} lệch/lỏng so với model (IoU={best_same:.2f} < {iou_loose})",
                            extra={"pred_cls": p_cls, "conf": round(p_conf, 4), "iou": round(best_same, 4)},
                        )
                    )
                continue

            best_other = max(cands, key=lambda item: item[2])
            if best_other[2] >= iou_match:
                issues.append(
                    Issue(
                        "second_opinion",
                        WARN,
                        "POSSIBLE_WRONG_CLASS",
                        stem,
                        f"nghi nhầm lớp: nhãn {cname(best_other[1])}, model đoán {cname(p_cls)} (conf={p_conf:.2f}, IoU={best_other[2]:.2f})",
                        extra={
                            "label_cls": best_other[1],
                            "pred_cls": p_cls,
                            "conf": round(p_conf, 4),
                            "iou": round(best_other[2], 4),
                        },
                    )
                )

        # 2. Kiểm theo nhãn: POSSIBLE_FALSE_POS (dùng fp_conf, không lọc diện tích)
        fp_preds = [
            (float(r[2]), float(r[3]), float(r[4]), float(r[5]))
            for r in img_preds
            if float(r[1]) >= fp_conf
        ]
        for line_no, l_cls, l_box in labeled:
            best_iou = max((iou_xywh(l_box, pb) for pb in fp_preds), default=0.0)
            if best_iou < iou_missing:
                issues.append(
                    Issue(
                        "second_opinion",
                        WARN,
                        "POSSIBLE_FALSE_POS",
                        stem,
                        f"nhãn {cname(l_cls)} dòng {line_no} không khớp dự đoán nào của model (max IoU={best_iou:.2f})",
                        line=line_no,
                        extra={"label_cls": l_cls, "max_iou": round(best_iou, 4)},
                    )
                )

    return issues

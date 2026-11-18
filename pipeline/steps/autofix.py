"""BƯỚC 2/4 — Sửa tự động những lỗi bắt buộc mà máy sửa được AN TOÀN.   ★★

Test:  pytest tests/test_autofix.py -q
"""
from collections import defaultdict

import yaml

from ..common import ERROR, parse_yolo_line

DROP_CODES = {"BAD_FORMAT", "BAD_CLASS_ID", "BOX_ZERO", "DUP_BOX"}
REMOVE_IMAGE_CODES = {"LEAK_TEST", "CORRUPT_IMAGE", "BAD_SIZE"}


def _is_remove_image(code: str) -> bool:
    return code in REMOVE_IMAGE_CODES or code.startswith("DUP_IMAGE_")


def fix(ds, issues, cfg):
    fixes = []
    err_issues = [i for i in issues if i.severity == ERROR]
    if not err_issues:
        return fixes

    # 1. Xoá ảnh lỗi nặng ở cửa vào (trùng, rò rỉ, hỏng, quá nhỏ)
    remove_stems = sorted({i.image for i in err_issues if _is_remove_image(i.code)})
    removed = set(remove_stems)
    for stem in remove_stems:
        img_p = ds.image_path(stem)
        lbl_p = ds.label_path(stem)
        existed = False
        if img_p is not None and img_p.exists():
            img_p.unlink()
            existed = True
        if lbl_p.exists():
            lbl_p.unlink()
            existed = True
        if existed:
            fixes.append(
                {
                    "image": stem,
                    "line": "",
                    "action": "remove_image",
                    "before": stem,
                    "after": "(đã xoá)",
                }
            )

    # 2. Chuẩn hoá tên lớp trong data.yaml
    if any(i.code == "BAD_CLASS_NAME" for i in err_issues):
        yaml_p = ds.yaml_path
        data = yaml.safe_load(yaml_p.read_text(encoding="utf-8")) if yaml_p.exists() else {}
        if not isinstance(data, dict):
            data = {}
        before_names = data.get("names")
        target_classes = list(cfg["classes"])
        new_names = target_classes if isinstance(before_names, list) else {i: n for i, n in enumerate(target_classes)}
        data["names"] = new_names
        yaml_p.write_text(yaml.safe_dump(data, allow_unicode=True, sort_keys=False), encoding="utf-8")
        fixes.append(
            {
                "image": "data.yaml",
                "line": "",
                "action": "rename_classes",
                "before": str(before_names),
                "after": str(new_names),
            }
        )

    # 3. Ảnh thiếu file nhãn -> không tạo file rỗng, chuyển người gán
    missing_stems = sorted(
        {i.image for i in err_issues if i.code == "MISSING_LABEL_FILE" and i.image not in removed}
    )
    for stem in missing_stems:
        fixes.append(
            {
                "image": stem,
                "line": "",
                "action": "needs_label",
                "before": "(không có file)",
                "after": "chuyển người gán",
            }
        )

    # 4. Sửa theo dòng nhãn (gom theo file để giữ nguyên số dòng gốc)
    drops_by_img: dict[str, set[int]] = defaultdict(set)
    clips_by_img: dict[str, set[int]] = defaultdict(set)
    for i in err_issues:
        if i.image in removed or i.line is None:
            continue
        if i.code in DROP_CODES:
            drops_by_img[i.image].add(int(i.line))
        elif i.code == "BOX_OUT_OF_IMAGE":
            clips_by_img[i.image].add(int(i.line))

    touched_stems = sorted(set(drops_by_img) | set(clips_by_img))
    for stem in touched_stems:
        lp = ds.label_path(stem)
        if not lp.exists():
            continue
        raw_lines = lp.read_text(encoding="utf-8", errors="replace").splitlines()
        drop_set = drops_by_img[stem]
        clip_set = clips_by_img[stem] - drop_set  # xoá dòng thắng cắt box

        new_lines = []
        changed = False
        for line_no, orig in enumerate(raw_lines, 1):
            if line_no in drop_set:
                changed = True
                fixes.append(
                    {
                        "image": stem,
                        "line": line_no,
                        "action": "drop_line",
                        "before": orig,
                        "after": "(đã xoá)",
                    }
                )
                continue

            if line_no in clip_set:
                try:
                    c, cx, cy, w, h = parse_yolo_line(orig)
                except ValueError:
                    changed = True
                    fixes.append(
                        {
                            "image": stem,
                            "line": line_no,
                            "action": "drop_line",
                            "before": orig,
                            "after": "(đã xoá)",
                        }
                    )
                    continue
                x1, y1, x2, y2 = cx - w / 2.0, cy - h / 2.0, cx + w / 2.0, cy + h / 2.0
                nx1 = max(0.0, min(1.0, x1))
                ny1 = max(0.0, min(1.0, y1))
                nx2 = max(0.0, min(1.0, x2))
                ny2 = max(0.0, min(1.0, y2))
                nw, nh = nx2 - nx1, ny2 - ny1
                changed = True
                if nw <= 0.0 or nh <= 0.0:
                    fixes.append(
                        {
                            "image": stem,
                            "line": line_no,
                            "action": "drop_line",
                            "before": orig,
                            "after": "(đã xoá: ngoài ảnh)",
                        }
                    )
                    continue
                ncx, ncy = (nx1 + nx2) / 2.0, (ny1 + ny2) / 2.0
                fixed_ln = f"{c} {ncx:.6f} {ncy:.6f} {nw:.6f} {nh:.6f}"
                new_lines.append(fixed_ln)
                fixes.append(
                    {
                        "image": stem,
                        "line": line_no,
                        "action": "clip_box",
                        "before": orig,
                        "after": fixed_ln,
                    }
                )
                continue

            new_lines.append(orig)

        if changed:
            content = "\n".join(new_lines) + ("\n" if new_lines else "")
            lp.write_text(content, encoding="utf-8")

    return fixes

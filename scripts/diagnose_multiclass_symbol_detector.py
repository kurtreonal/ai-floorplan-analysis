"""Bounded per-entry head/preprocessing diagnosis on original training tiles."""
import argparse
import json
import os
from pathlib import Path
import sys

os.environ["YOLO_OFFLINE"] = "true"
os.environ["YOLO_AUTOINSTALL"] = "false"
sys.path.insert(0, str(Path(__file__).resolve().parents[1]/"backend"))
import numpy as np
from PIL import Image, ImageDraw
import torch
from ultralytics import YOLO
from probe_symbol_detector_dev import iou, digest


def inspect(dataset, checkpoint, base, output):
    if output.exists():
        raise FileExistsError("Diagnostic versions are immutable")
    manifest = json.loads((dataset/"manifest.json").read_text())
    trained, previous = YOLO(str(checkpoint)).model.eval(), YOLO(str(base)).model.eval()
    if len(trained.names) != 56 or len(previous.names) != 56:
        raise ValueError("Expected identical numeric 56-entry heads")
    output.mkdir(parents=True)
    entries = []
    contact = Image.new("RGB", (4*280, 14*300), "white")
    pen = ImageDraw.Draw(contact)
    with torch.inference_mode():
        for cls in manifest["classes"]:
            row = next(r for r in manifest["images"] if r["class_id"] == cls["id"] and not r.get("augmentation"))
            path = dataset/"images/train"/f"{row['record_id']}.png"
            if digest(path) != row["image_sha256"]:
                raise ValueError("Diagnostic tile changed")
            image = Image.open(path).convert("RGB")
            tensor = torch.from_numpy(np.asarray(image.resize((320, 320))).copy()).permute(2,0,1).unsqueeze(0).float()/255
            left, top = row["tile_origin"]
            box = [row["source_box"][i]-(left if i%2 == 0 else top) for i in range(4)]
            measurements = []
            for model in (previous, trained):
                raw = model(tensor)[0][0].cpu()  # decoded xywh + all 56 scores, before argmax/NMS
                if raw.shape[0] != 60:
                    raise ValueError("Unexpected raw detector output")
                boxes = raw[:4].T.numpy()*(256/320)
                matches = [j for j,(x,y,w,h) in enumerate(boxes)
                           if iou(box, [x-w/2,y-h/2,x+w/2,y+h/2]) >= .5]
                expected_scores = raw[4+cls["id"]]
                best = max((float(expected_scores[j]) for j in matches), default=0)
                measurements.append({"expected_class_max_anywhere": float(expected_scores.max()),
                    "expected_class_max_iou_0_5": best,
                    "decoded_locations_iou_0_5": len(matches),
                    "best_class_overall": int(raw[4:].amax(dim=1).argmax())})
            change = sum(float((a[-1].weight[cls['id']]-b[-1].weight[cls['id']]).abs().sum())
                         for a,b in zip(trained.model[-1].cv3, previous.model[-1].cv3))
            entries.append({"class_id": cls["id"], "legend_entry": cls["legend_entry"],
                "record_id": row["record_id"], "tile_sha256": row["image_sha256"],
                "source_sha256": row["source_sha256"], "expected_local_box": box,
                "before": measurements[0], "after": measurements[1], "class_head_weight_change_l1": change})
            preview = image.copy()
            ImageDraw.Draw(preview).rectangle(box, outline="red", width=2)
            x, y = (cls['id']%4)*280, (cls['id']//4)*300
            contact.paste(preview, (x,y+40))
            pen.text((x,y), f"{cls['id']} {cls['legend_entry']} n={cls['samples']}", fill="black")
            pen.text((x,y+15), f"expected score/IoU: {measurements[1]['expected_class_max_iou_0_5']:.3f}", fill="black")
    contact.save(output/"all-56-training-examples.jpg", quality=90)
    result = {"schema": "ved-56-entry-raw-head-diagnostic-v1", "checkpoint_sha256": digest(checkpoint),
              "base_sha256": digest(base), "dataset_sha256": digest(dataset/"manifest.json"),
              "purpose": "pipeline/zero-output diagnosis on training examples; not accuracy",
              "entries": entries}
    (output/"diagnosis.json").write_text(json.dumps(result, indent=2))
    return {"entries": len(entries), "heads_updated": sum(r["class_head_weight_change_l1"]>0 for r in entries),
            "expected_class_and_iou_score_ge_0_5": sum(r["after"]["expected_class_max_iou_0_5"] >= .5 for r in entries)}


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ("dataset", "checkpoint", "base", "output"):
        parser.add_argument(f"--{name}", type=Path, required=True)
    args = parser.parse_args()
    print(json.dumps(inspect(args.dataset, args.checkpoint, args.base, args.output)))

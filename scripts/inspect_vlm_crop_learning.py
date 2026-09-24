"""Offline, read-only audit of the twelve-example crop learning check."""
import argparse
import html
import json
import re
from pathlib import Path

import torch
from peft import PeftModel
from transformers import AutoModelForVision2Seq, AutoProcessor

from train_vlm_symbol_crops import batch, offline, validate_manifest


def normalize(value):
    return re.sub(r"[^a-z0-9]+", " ", value.casefold()).strip()


def inspect(manifest_path, model_path, adapter_path, output):
    root = manifest_path.parent
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    validate_manifest(manifest, root)
    records = [r for r in manifest["records"] if r["split"] == "train"]
    if len(records) != 12:
        raise ValueError("Expected the fixed twelve-example diagnostic")
    torch.set_num_threads(4)
    processor = AutoProcessor.from_pretrained(model_path, local_files_only=True, trust_remote_code=False)
    processor.image_processor.do_image_splitting = False
    base = AutoModelForVision2Seq.from_pretrained(
        model_path, local_files_only=True, trust_remote_code=False,
        torch_dtype=torch.float32, attn_implementation="eager")
    base.eval()
    results = []
    with torch.no_grad():
        for record in records:
            inputs, prefix = batch(processor, record, root)
            if not any(key.startswith("pixel_values") for key in inputs):
                raise ValueError("Image pixels missing from model inputs")
            answer_ids = base.generate(**prefix, max_new_tokens=32, do_sample=False)
            answer = processor.decode(answer_ids[0, prefix["input_ids"].shape[1]:], skip_special_tokens=True).strip()
            results.append({"id": record["id"], "image": record["image"],
                            "sheet_id": record["sheet_id"], "group": record["group"],
                            "legend_entry": record["legend_entry"], "expected": record["label"],
                            "base_raw": answer, "base_normalized": normalize(answer),
                            "supervised_tokens": int((inputs["labels"] != -100).sum()),
                            "image_shape": list(inputs["pixel_values"].shape)})
    adapted = PeftModel.from_pretrained(base, adapter_path, local_files_only=True)
    adapted.eval()
    with torch.no_grad():
        for result, record in zip(results, records):
            _, prefix = batch(processor, record, root)
            answer_ids = adapted.generate(**prefix, max_new_tokens=32, do_sample=False)
            answer = processor.decode(answer_ids[0, prefix["input_ids"].shape[1]:], skip_special_tokens=True).strip()
            result["adapter_raw"] = answer
            result["adapter_normalized"] = normalize(answer)
            result["expected_normalized"] = normalize(record["label"])
            result["normalized_match"] = result["adapter_normalized"] == result["expected_normalized"]
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps({"results": results}, indent=2), encoding="utf-8")
    rows = []
    for result in results:
        cells = [f'<img src="{html.escape(result["image"])}" width="160">',
                 result["id"], result["sheet_id"], result["legend_entry"],
                 result["expected"], result["base_raw"], result["adapter_raw"],
                 result["adapter_normalized"]]
        rows.append("<tr>" + "".join(f"<td>{html.escape(str(c)) if i else c}</td>" for i, c in enumerate(cells)) + "</tr>")
    page = ("<!doctype html><meta charset='utf-8'><title>Private crop audit</title>"
            "<style>body{font:14px sans-serif}table{border-collapse:collapse}"
            "td,th{border:1px solid #aaa;padding:7px}img{image-rendering:pixelated}</style>"
            "<h1>Private 12-crop audit</h1><table><tr>"
            + "".join(f"<th>{h}</th>" for h in ("Crop", "ID", "Sheet", "Legend", "Expected", "Base raw", "Adapter raw", "Adapter normalized"))
            + "</tr>" + "".join(rows) + "</table>")
    output.with_suffix(".html").write_text(page, encoding="utf-8")
    return results


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--model", type=Path, required=True)
    parser.add_argument("--adapter", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    with offline():
        records = inspect(args.manifest, args.model, args.adapter, args.output)
    print(json.dumps({"samples": len(records), "normalized_matches": sum(r["normalized_match"] for r in records)}))

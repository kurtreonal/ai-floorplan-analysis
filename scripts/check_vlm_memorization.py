"""Bounded offline two-class memorization check; never a generalization score."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import socket
import time

for key in ("HF_HUB_OFFLINE", "TRANSFORMERS_OFFLINE", "HF_HUB_DISABLE_TELEMETRY"):
    os.environ[key] = "1"
os.environ["WANDB_DISABLED"] = "true"

import psutil
import torch
from peft import LoraConfig, get_peft_model, PeftModel
from transformers import AutoModelForVision2Seq, AutoProcessor

from train_vlm_symbol_crops import batch, offline, parameter_hash, validate_manifest


SAMPLES = {
    "DOME": ("8e65b3fac7edb9ead64f3d1d", "b21fe5f7e0cdeaa6f5e93d5e", "f27650a3a8cc8c0ffec5c028"),
    "PULL": ("1421451ddf2e1217c0833e17", "0fa577e32ac65b7d915452e0", "5017b5d998527690aa8b230c"),
}


def run(manifest_path, model_path, output, steps):
    if not 1 <= steps <= 120:
        raise ValueError("Step budget exceeded")
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    root = manifest_path.parent
    validate_manifest(manifest, root)
    by_id = {r["id"]: r for r in manifest["records"]}
    records = []
    for class_id, ids in SAMPLES.items():
        for sample_id in ids:
            source = by_id[sample_id]
            if source["split"] != "train":
                raise ValueError("Memorization check cannot use validation data")
            records.append({**source, "label": class_id, "source_label": source["label"]})
    if len({r["source_sha256"] for r in records}) == 0:
        raise ValueError("Missing source identity")
    output.mkdir(parents=True, exist_ok=False)
    torch.set_num_threads(4)
    torch.manual_seed(42)
    processor = AutoProcessor.from_pretrained(model_path, local_files_only=True, trust_remote_code=False)
    processor.image_processor.do_image_splitting = False
    base = AutoModelForVision2Seq.from_pretrained(
        model_path, local_files_only=True, trust_remote_code=False,
        torch_dtype=torch.float32, attn_implementation="eager")
    model = get_peft_model(base, LoraConfig(
        r=8, lora_alpha=16, lora_dropout=0.0, bias="none",
        target_modules=r".*text_model.*\.(q_proj|v_proj)", task_type="CAUSAL_LM"))
    before_base, before_adapter = parameter_hash(model, False), parameter_hash(model, True)
    optimizer = torch.optim.AdamW([p for p in model.parameters() if p.requires_grad], lr=2e-4)
    started = time.monotonic()
    snapshots, losses = [], []

    def guard():
        if time.monotonic() - started > 900 or psutil.Process().memory_info().rss > 6 * 1024**3:
            raise RuntimeError("Memorization resource budget exceeded")

    def evaluate(step):
        model.eval()
        predictions = []
        with torch.no_grad():
            for record in records:
                guard()
                inputs, prefix = batch(processor, record, root)
                generated = model.generate(**prefix, max_new_tokens=8, do_sample=False)
                answer = processor.decode(generated[0, prefix["input_ids"].shape[1]:], skip_special_tokens=True).strip()
                predictions.append({"id": record["id"], "expected_id": record["label"],
                                    "raw": answer, "loss": model(**inputs).loss.item()})
        snapshots.append({"step": step, "matches": sum(p["raw"] == p["expected_id"] for p in predictions),
                          "predictions": predictions})

    evaluate(0)
    gradient_norm = None
    image_delta = None
    for step in range(steps):
        guard()
        model.train()
        record = records[step % len(records)]
        inputs, _ = batch(processor, record, root)
        if step == 0:
            other, _ = batch(processor, records[3], root)
            if "pixel_values" not in inputs or "pixel_values" not in other:
                raise ValueError("Images omitted from processor inputs")
            image_delta = float((inputs["pixel_values"] - other["pixel_values"]).abs().mean())
            if image_delta <= 0:
                raise ValueError("Distinct crops produced identical image tensors")
        optimizer.zero_grad(set_to_none=True)
        loss = model(**inputs).loss
        if not torch.isfinite(loss):
            raise ValueError("Non-finite loss")
        loss.backward()
        if step == 0:
            gradient_norm = float(sum(p.grad.abs().sum().item() for p in model.parameters()
                                      if p.requires_grad and p.grad is not None))
            if gradient_norm <= 0:
                raise ValueError("No LoRA gradient")
        torch.nn.utils.clip_grad_norm_(model.parameters(), 1)
        optimizer.step()
        losses.append(float(loss.detach()))
        if (step + 1) % 30 == 0 or step + 1 == steps:
            evaluate(step + 1)
            print(json.dumps({"step": step + 1, "matches": snapshots[-1]["matches"],
                              "loss": losses[-1]}), flush=True)
    report = {
        "kind": "pipeline_memorization_only", "status": "inactive_experiment",
        "manifest_sha256": hashlib.sha256(manifest_path.read_bytes()).hexdigest(),
        "model": str(model_path), "samples": records, "steps": steps,
        "image_tensor_mean_absolute_difference": image_delta,
        "first_step_lora_gradient_l1": gradient_norm,
        "base_unchanged": before_base == parameter_hash(model, False),
        "adapter_changed": before_adapter != parameter_hash(model, True),
        "snapshots": snapshots, "losses": losses, "elapsed_seconds": time.monotonic() - started,
        "limitations": ["Training-sample memorization only", "No project-separated or held-out score",
                        "No full-page localization or detection metric", "No live model activation"],
    }
    model.save_pretrained(output / "adapter", safe_serialization=True)
    (output / "report.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
    return {"steps": steps, "initial": snapshots[0]["matches"], "final": snapshots[-1]["matches"],
            "gradient_l1": gradient_norm}


def verify_existing(manifest_path, model_path, output):
    report = json.loads((output / "report.json").read_text(encoding="utf-8"))
    if report["manifest_sha256"] != hashlib.sha256(manifest_path.read_bytes()).hexdigest():
        raise ValueError("Memorization manifest version changed")
    processor = AutoProcessor.from_pretrained(model_path, local_files_only=True, trust_remote_code=False)
    processor.image_processor.do_image_splitting = False
    base = AutoModelForVision2Seq.from_pretrained(
        model_path, local_files_only=True, trust_remote_code=False,
        torch_dtype=torch.float32, attn_implementation="eager")
    model = PeftModel.from_pretrained(base, output / "adapter", local_files_only=True)
    model.eval()
    results = []
    with torch.no_grad():
        for record in report["samples"]:
            _, prefix = batch(processor, record, manifest_path.parent)
            generated = model.generate(**prefix, max_new_tokens=8, do_sample=False)
            answer = processor.decode(generated[0, prefix["input_ids"].shape[1]:], skip_special_tokens=True).strip()
            results.append({"id": record["id"], "expected_id": record["label"], "raw": answer,
                            "exact": answer == record["label"]})
    return {"matches": sum(r["exact"] for r in results), "samples": len(results), "results": results}


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--model", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--steps", type=int, default=90)
    parser.add_argument("--verify-existing", action="store_true")
    args = parser.parse_args()
    with offline():
        print(json.dumps(verify_existing(args.manifest, args.model, args.output)
                         if args.verify_existing else
                         run(args.manifest, args.model, args.output, args.steps)))

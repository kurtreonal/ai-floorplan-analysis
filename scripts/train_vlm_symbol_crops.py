"""Bounded real CPU LoRA experiment; never activate or claim full-plan quality."""
import argparse
import gc
from contextlib import contextmanager
import hashlib
import importlib.metadata
import json
import os
from pathlib import Path
import random
import socket
import time

for key in ("HF_HUB_OFFLINE", "TRANSFORMERS_OFFLINE", "HF_HUB_DISABLE_TELEMETRY"):
    os.environ[key] = "1"
os.environ["WANDB_DISABLED"] = "true"

import psutil
import torch
from PIL import Image
from peft import LoraConfig, get_peft_model, PeftModel
from transformers import AutoProcessor, AutoModelForVision2Seq

from prepare_vlm_symbol_crops import sha, resolve_legend, valid_box

PROMPT = "Identify the electrical symbol in this reviewed crop. Reply only with its drawing legend label."


@contextmanager
def offline():
    original = socket.socket.connect
    def deny(*args, **kwargs):
        raise RuntimeError("Network prohibited during private training")
    socket.socket.connect = deny
    try:
        yield
    finally:
        socket.socket.connect = original


def parameter_hash(model, trainable):
    digest = hashlib.sha256()
    for name, tensor in model.named_parameters():
        if tensor.requires_grad == trainable:
            digest.update(name.encode())
            digest.update(tensor.detach().cpu().contiguous().numpy().tobytes())
    return digest.hexdigest()


def validate_manifest(manifest, root):
    if manifest.get("schema") != "ved-reviewed-symbol-crops-v1":
        raise ValueError("Unsupported dataset")
    if manifest.get("task") != "symbol_crop_classification" or not manifest.get("authorization"):
        raise ValueError("Task/authorization missing")
    if manifest.get("technical_exclusions_sha256"):
        exclusion_path = root / "source-technical-exclusions.json"
        if sha(exclusion_path) != manifest["technical_exclusions_sha256"]:
            raise ValueError("Technical exclusion snapshot integrity failed")
        exclusions = json.loads(exclusion_path.read_text(encoding="utf-8"))
        excluded_ids = {item["record_id"] for item in exclusions["proposals"]}
        if (exclusions.get("review_export_sha256") != manifest.get("review_sha256")
                or any(r["id"] in excluded_ids for r in manifest["records"])):
            raise ValueError("Technical exclusions not enforced")
    for filename, key in (("source-review.json", "review_sha256"),
                          ("source-references.json", "reference_sha256")):
        if sha(root / filename) != manifest.get(key):
            raise ValueError("Source snapshot integrity failed")
    review = json.loads((root / "source-review.json").read_text(encoding="utf-8"))
    refs = json.loads((root / "source-references.json").read_text(encoding="utf-8"))
    sheets = {sheet["id"]: sheet for sheet in review["sheets"]}
    approval = None
    if manifest.get("approval_sha256"):
        if sha(root / "source-approval.json") != manifest["approval_sha256"]:
            raise ValueError("Approval snapshot integrity failed")
        approval = json.loads((root / "source-approval.json").read_text(encoding="utf-8"))
        if approval != manifest["authorization"] or approval.get("review_sha256") != manifest["review_sha256"]:
            raise ValueError("Approval does not bind this dataset version")
    identifiers = set()
    groups, hashes = {}, {}
    for record in manifest["records"]:
        if record["id"] in identifiers:
            raise ValueError("Duplicate sample identity")
        identifiers.add(record["id"])
        sheet = sheets[record["sheet_id"]]
        if approval is not None and sheet.get("group") not in approval["approved_groups"]:
            raise ValueError("Source outside approved groups")
        originals = [a for a in sheet["annotations"] if a["id"] == record["annotation_id"]]
        if len(originals) != 1 or originals[0] != record["original_annotation"]:
            raise ValueError("Annotation provenance mismatch")
        entry, evidence = resolve_legend(originals[0], sheet, refs["legend_catalog"])
        if (entry is None or record["label"] != entry["label"]
                or record["legend_entry"] != entry["legend_entry"]
                or record["mapping_evidence"] != evidence):
            raise ValueError("Legend target mismatch")
        box = valid_box(originals[0], sheet["width"], sheet["height"])
        if box is None or list(box) != list(record["bbox"]):
            raise ValueError("Crop provenance mismatch")
        decision = review.get("decisions", {}).get(sheet["id"], {}).get("decision")
        if decision in {"exclude", "rescan_needed"} or sheet.get("split") in {"sealed_test", "test"}:
            raise ValueError("Excluded source")
        split = record["split"]
        if split not in {"train", "development_validation"}:
            raise ValueError("Protected or unknown split")
        for seen, key in ((groups, record["group"]), (hashes, record["source_sha256"]),
                          (hashes, record["image_sha256"])):
            if key in seen and seen[key] != split:
                raise ValueError("Split leakage")
            seen[key] = split
        image = (root / record["image"]).resolve()
        if not image.is_relative_to(root.resolve()) or sha(image) != record["image_sha256"]:
            raise ValueError("Image integrity failed")
        if record["original_annotation"].get("review_state") not in {"corrected", "manually_added", "user_reviewed"}:
            raise ValueError("Unreviewed target")


def batch(processor, record, root):
    with Image.open(root / record["image"]) as source:
        image = source.convert("RGB")
    messages = [{"role": "user", "content": [{"type": "image"}, {"type": "text", "text": PROMPT}]}]
    prompt = processor.apply_chat_template(messages, add_generation_prompt=True)
    full = processor.apply_chat_template(messages + [
        {"role": "assistant", "content": [{"type": "text", "text": record["label"]}]}],
        add_generation_prompt=False)
    inputs = processor(text=full, images=[image], return_tensors="pt")
    prefix = processor(text=prompt, images=[image], return_tensors="pt")
    length = prefix["input_ids"].shape[1]
    if not torch.equal(inputs["input_ids"][:, :length], prefix["input_ids"]):
        raise ValueError("Assistant prefix masking mismatch")
    labels = inputs["input_ids"].clone()
    labels[:, :length] = -100
    if (labels != -100).sum() == 0 or labels.shape[1] > 1024:
        raise ValueError("Empty or oversized target")
    inputs["labels"] = labels
    return inputs, prefix


def run(args):
    if not 1 <= args.steps <= 500:
        raise ValueError("Step budget exceeded")
    manifest = json.loads(args.manifest.read_text(encoding="utf-8"))
    root = args.manifest.parent
    validate_manifest(manifest, root)
    # Historical workspace-group splits are useful for debugging but are not
    # project-verified model-selection evidence. Keep the diagnostic output
    # while explicitly fencing it from reported generalization accuracy.
    from audit_vlm_crop_evaluation import audit
    evaluation_audit = audit(manifest)
    train = [r for r in manifest["records"] if r["split"] == "train"]
    validation = [r for r in manifest["records"] if r["split"] == "development_validation"]
    if not train or not validation:
        raise ValueError("Training and development records required")
    acquisition = json.loads((args.model / "acquisition.json").read_text(encoding="utf-8"))
    for filename, digest in acquisition["files"].items():
        if sha(args.model / filename) != digest:
            raise ValueError("Base model integrity failed")
    args.output.mkdir(parents=True, exist_ok=False)
    torch.set_num_threads(4)
    torch.manual_seed(42)
    random.Random(42).shuffle(train)
    started = time.monotonic()
    peak = 0

    def budget():
        nonlocal peak
        peak = max(peak, psutil.Process().memory_info().rss)
        if peak > 6 * 1024**3 or psutil.virtual_memory().available < 768 * 1024**2:
            raise RuntimeError("RAM safety limit reached")
        if time.monotonic() - started > 1800:
            raise RuntimeError("30-minute run budget reached")

    processor = AutoProcessor.from_pretrained(args.model, local_files_only=True, trust_remote_code=False)
    processor.image_processor.do_image_splitting = False
    base = AutoModelForVision2Seq.from_pretrained(
        args.model, local_files_only=True, trust_remote_code=False,
        torch_dtype=torch.float32, attn_implementation="eager")
    model = get_peft_model(base, LoraConfig(
        r=8, lora_alpha=16, lora_dropout=0.0, bias="none",
        target_modules=r".*text_model.*\.(q_proj|v_proj)", task_type="CAUSAL_LM"))
    before_base = parameter_hash(model, False)
    before_adapter = parameter_hash(model, True)
    sample = validation[:args.validation_limit]

    def evaluate():
        model.eval()
        losses, exact, results = [], 0, []
        with torch.no_grad():
            for record in sample:
                budget()
                inputs, prefix = batch(processor, record, root)
                losses.append(model(**inputs).loss.item())
                generated = model.generate(**prefix, max_new_tokens=32, do_sample=False)
                answer = processor.decode(generated[0, prefix["input_ids"].shape[1]:], skip_special_tokens=True).strip()
                match = answer.casefold() == record["label"].strip().casefold()
                exact += int(match)
                results.append({"id": record["id"], "prediction": answer, "exact": match})
        return {"samples": len(sample), "mean_loss": sum(losses)/len(losses),
                "exact_matches": exact, "exact_match_accuracy": exact/len(sample), "results": results}

    initial = evaluate()
    optimizer = torch.optim.AdamW([p for p in model.parameters() if p.requires_grad], lr=2e-4)
    history = []
    model.train()
    for step in range(args.steps):
        budget()
        inputs, _ = batch(processor, train[step % len(train)], root)
        optimizer.zero_grad(set_to_none=True)
        loss = model(**inputs).loss
        if not torch.isfinite(loss):
            raise ValueError("Non-finite training loss")
        loss.backward()
        torch.nn.utils.clip_grad_norm_(model.parameters(), 1.0)
        optimizer.step()
        history.append(loss.item())
        if step == 0 or (step + 1) % 10 == 0:
            print(json.dumps({"step": step+1, "loss": loss.item()}), flush=True)
    final = evaluate()
    unchanged_base = before_base == parameter_hash(model, False)
    changed_adapter = before_adapter != parameter_hash(model, True)
    if not unchanged_base or not changed_adapter:
        raise ValueError("Parameter update isolation failed")
    model.save_pretrained(args.output / "adapter", safe_serialization=True)
    processor.save_pretrained(args.output / "processor")
    # Reload adapter into the original frozen base and verify actual inference.
    del optimizer, model, base, inputs, loss
    gc.collect()
    reloaded_base = AutoModelForVision2Seq.from_pretrained(
        args.model, local_files_only=True, trust_remote_code=False,
        torch_dtype=torch.float32, attn_implementation="eager")
    reloaded = PeftModel.from_pretrained(reloaded_base, args.output / "adapter", local_files_only=True)
    reloaded.eval()
    _, prefix = batch(processor, sample[0], root)
    with torch.no_grad():
        reloaded.generate(**prefix, max_new_tokens=2, do_sample=False)
    report = {
        "status": "inactive_experimental_adapter", "task": manifest["task"],
        "base": acquisition, "manifest_sha256": sha(args.manifest), "seed": 42,
        "steps": args.steps, "device": "cpu", "learning_rate": 2e-4, "rank": 8,
        "train_records": len(train), "validation_records": len(validation),
        "before": initial, "after": final, "training_losses": history,
        "evaluation_audit": evaluation_audit,
        "frozen_base_unchanged": unchanged_base, "adapter_changed": changed_adapter,
        "adapter_reload_inference": True, "peak_rss_bytes": peak,
        "elapsed_seconds": time.monotonic()-started,
        "versions": {p: importlib.metadata.version(p) for p in ("torch", "transformers", "peft", "accelerate")},
        "unsupported_metrics": ["project-separated crop accuracy", "full-plan detection precision/recall", "wall accuracy", "wiring accuracy", "sealed-test quality"],
        "limitations": manifest["limitations"],
        "validation_unseen_label_samples": sum(r["label"] not in {t["label"] for t in train} for r in sample),
        "adapter_files": {p.name: sha(p) for p in (args.output / "adapter").iterdir() if p.is_file()},
    }
    with (args.output / "report.json").open("x") as stream:
        json.dump(report, stream, indent=2)
    print(json.dumps({k: report[k] for k in ("status", "steps", "adapter_changed", "frozen_base_unchanged", "elapsed_seconds")}), flush=True)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--model", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--steps", type=int, default=50)
    parser.add_argument("--validation-limit", type=int, choices=range(1, 101), default=8)
    args = parser.parse_args()
    with offline():
        run(args)

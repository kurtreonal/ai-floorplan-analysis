"""Controlled public-only acquisition; no private data is read by this command."""
import hashlib
import json
import os
from pathlib import Path
import shutil
import urllib.request

os.environ["HF_HUB_DISABLE_TELEMETRY"] = "1"
os.environ["HF_HUB_DISABLE_XET"] = "1"
from huggingface_hub import snapshot_download

MODEL = "HuggingFaceTB/SmolVLM-256M-Instruct"
REVISION = "7e3e67edbbed1bf9888184d9df282b700a323964"
DEST = Path(__file__).resolve().parents[1] / "models/vlm/smolvlm-256m"


def main():
    metadata_url = f"https://huggingface.co/api/models/{MODEL}/revision/{REVISION}?blobs=true"
    with urllib.request.urlopen(metadata_url, timeout=30) as response:
        metadata = json.load(response)
    if metadata["sha"] != REVISION or metadata["cardData"]["license"] != "apache-2.0":
        raise ValueError("Model identity/license mismatch")
    files = [f for f in metadata["siblings"] if "/" not in f["rfilename"]
             and f["rfilename"].endswith((".json", ".txt", ".md", ".safetensors"))]
    size = sum(f.get("size", 0) for f in files)
    disk = shutil.disk_usage(DEST.parent)
    if size > 2 * 1024**3 or disk.free - size < disk.total * .2:
        raise ValueError("Acquisition exceeds storage budget")
    snapshot_download(MODEL, revision=REVISION, local_dir=DEST,
                      allow_patterns=[f["rfilename"] for f in files], max_workers=2,
                      token=False)
    hashes = {}
    for file in files:
        path = DEST / file["rfilename"]
        with path.open("rb") as stream:
            digest = hashlib.file_digest(stream, "sha256").hexdigest()
        expected = file.get("lfs", {}).get("sha256")
        if expected and expected != digest:
            raise ValueError("Artifact hash mismatch")
        hashes[file["rfilename"]] = digest
    manifest = {"model": MODEL, "revision": REVISION, "license": "apache-2.0",
                "files": hashes, "purpose": "inactive supervised crop-classification experiment"}
    with (DEST / "acquisition.json").open("x") as stream:
        json.dump(manifest, stream, indent=2)
    print(json.dumps({"acquired": MODEL, "revision": REVISION, "verified_files": len(hashes)}))


if __name__ == "__main__":
    main()

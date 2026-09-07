# U1 Hardware, Privacy, and Runtime Baseline

- Ticket: U1
- Measurement date: 2026-09-07 (Asia/Manila)
- Status: BLOCKED pending target inference/training-machine measurement and
  explicit approval of the numeric operating budgets below
- Application baseline: `81ecd83` (PRE12 published, L1 implemented)
- Model selected or downloaded: no

This document is a sanitized requirements record. It intentionally excludes
usernames, device identifiers, absolute private paths, source filenames,
private hashes, credentials, and drawing contents.

## Measured development machine

| Resource | Measured result | U1 interpretation |
|---|---|---|
| Operating system | Windows 11 Home Single Language, 64-bit, build 22631 | Supported for application development only |
| CPU | Intel Celeron N4500, 2 physical and 2 logical cores | Insufficient for the planned VLM bake-off or training |
| Physical RAM | 4,091,207,680 bytes | Insufficient for the planned VLM bake-off or training |
| Available RAM at inspection | 408,600,576 bytes | Transient measurement; no model workload was started |
| GPU | Intel UHD integrated graphics | No supported discrete model-training accelerator established |
| GPU memory | Windows reported 1,073,741,824 adapter bytes | Integrated/shared reporting; dedicated VRAM is unavailable and must not be represented as CUDA VRAM |
| NVIDIA/CUDA | `nvidia-smi` unavailable | No NVIDIA driver/CUDA capability established |
| Local fixed-disk free space | 12,059,586,560 bytes | Insufficient for pinned VLM artifacts and training scratch space |
| Python | 3.13.7 in the system and backend environments | Existing application runtime only; model environment remains separate |
| WSL | Unavailable or not configured | Not approved or required for this machine |
| Docker | Unavailable | Not approved or required for this machine |

The measured laptop remains a development/control machine. It is not approved
for local VLM inference, model acquisition, or adapter training. A separate
VED-controlled target machine must be measured before U1 can pass. U6 and U10
must not substitute guessed specifications or cloud rental.

## Approved privacy boundary

The user approved establishing a separate local private AI workspace on
2026-09-07. The absolute path is retained only in local operational state. The
verified root is outside the repository's OneDrive hierarchy, supports local
read/write/delete operations, has no explicit broad `Everyone` write rule, and
contains separate areas for corpus, derivatives, diagnostics, models, adapters,
manifests, sealed test evidence, and training runs.

The existing private corpus remains in its original location. U1 did not move,
copy, rename, rewrite, or delete it. A later migration requires a separately
verified manifest and explicit authorization; it must never be inferred from
the existence of the new directory.

Local-only means:

- no hosted inference, remote fallback, remote annotation, or automatic model
  download;
- no drawing, crop, OCR text, prompt, candidate, label, metric, or model
  diagnostic sent to telemetry or an external service;
- loopback binding by default for any future gateway;
- network-disabled inference after controlled, separately authorized public
  model acquisition;
- private artifacts excluded from Git and from synchronized repository paths;
- safe public errors containing no private path, source text, model internals,
  prompt, or stack trace.

The repository is under a directory named `OneDrive`. No running or installed
OneDrive client was detected during U1 inspection, but that does not prove that
historical synchronization, backup, or another endpoint never received the
files. The earlier Roboflow visibility and declared-license concern remains a
human/external-service issue; U1 performs no hosted-service mutation.

## Proposed operating budgets requiring explicit approval

These are conservative U1 requirements, not measured throughput claims and not
an approved model selection.

| Area | Proposed limit or objective |
|---|---|
| Uploaded file | Existing 25 MiB maximum; JPEG/JPG, PNG, or PDF only |
| Document inventory | At most 50 source pages inventoried per job; every page receives an explicit outcome |
| Plan pages interpreted | At most 20 included plan pages per job |
| Decoded evidence page | At most 60 megapixels and 10,000 pixels on either edge before allocation |
| K1/reference image | Existing maximum 4,096 pixels per edge |
| Overview image | At most 2,048 pixels on the longest edge |
| Tile | 1,536 x 1,536 pixels with 256-pixel overlap |
| Tiles | At most 96 per page and 8 images per model request |
| Model-request pixels | At most 24 megapixels across all images in one request |
| Generated output | At most 16,384 tokens and 256 KiB before strict U2 validation |
| Inference concurrency | One active model request per device/process |
| Worker concurrency | One active floor-plan job until measured evidence supports more |
| Queue | At most four waiting model requests per gateway process |
| Model initialization timeout | 300 seconds |
| Model request timeout | 300 seconds |
| Page processing timeout | 30 minutes |
| Whole-job timeout | 120 minutes |
| Latency objective | Median at most 5 minutes and p95 at most 10 minutes per supported page on the future measured target |
| Base-model storage | At most 50 GiB per pinned candidate |
| Adapter/checkpoint storage | At most 20 GiB per experiment/release family |
| Corpus plus derivatives | 200 GiB planned capacity |
| Training scratch | 300 GiB planned capacity, with at least 20% free-space reserve |

U2 may impose tighter entity/string/array bounds. U6 may recommend lower limits
after real measurements, but it must not silently increase these limits without
a new approval.

## Proposed retention policy requiring explicit approval

- Immutable consented source data: retained until explicit VED-authorized
  deletion; never deleted automatically by a processing or training job.
- Sealed-test membership and approval evidence: retained until superseded by an
  independently approved test release and explicit archival/deletion decision.
- Approved gold, release manifests, and active/rollback artifacts: retained
  through release retirement and rollback closeout.
- Protected raw prompt/model diagnostics: maximum 30 days unless attached to an
  active incident or approval record.
- Failed run-owned temporary derivatives: eligible for explicit cleanup after
  7 days, only from the recorded run directory and never from original storage.
- Production uploads: never become training data solely because retention is
  permitted; purpose-specific consent, split assignment, completeness, and
  independent approval remain mandatory.

## Licensing and acquisition policy

- Only publicly obtainable artifacts with a recorded model card, revision,
  license, permitted VED use, and verified hashes may be evaluated.
- Controlled acquisition is a separate U6 action after U1/U5 gates pass; no
  application import or processing request may download a model.
- `trust_remote_code` is denied unless its exact pinned code is reviewed and a
  separate justification is recorded.
- Ultralytics remains installed as the legacy path. Its AGPL/commercial-license
  status must be resolved before commercial production use.
- Possessing PEC/reference material or an export that declares a public license
  does not establish training or redistribution permission.

## Gate status

| Acceptance criterion | Status | Evidence |
|---|---|---|
| Development-machine OS/CPU/RAM/GPU/VRAM/CUDA/disk measured without guessing | PASS | Read-only Windows inventory; unavailable CUDA/dedicated-VRAM information is stated explicitly |
| Intended inference/training target measured | BLOCKED | Separate VED-controlled machine has been authorized in principle but not supplied or measured |
| Local-only privacy boundary defined and locally created outside OneDrive | PASS | Read/write/delete probe passed; no existing corpus was moved |
| Page/tile/context/output/concurrency/timeout/latency/storage budgets approved | BLOCKED | Numeric proposal above awaits explicit user approval |
| Retention policy approved | BLOCKED | Proposed policy above awaits explicit user approval |
| Model/license acquisition policy defined | PASS | Policy above permits only controlled, pinned, reviewed acquisition in a later ticket |
| No model selection, download, dependency, API, schema, or runtime change | PASS | Repository and environment audit found no VLM artifact or U runtime change |

U2 must not start until every U1 blocker is resolved, U1 is verified and
published, and the ticket report records the actual target-machine inventory.

## Device-transfer checkpoint exception

On 2026-09-07 the user authorized a feature-branch WIP commit and push so the
new device can resume this unfinished ticket. The user also authorized physical
transfer of database, private files and credentials outside Git. This is not a
U1 completion release or approval of the unresolved numeric/retention budgets.
The new device must measure its own resources and finish the remaining gates.
No incomplete-U1 merge into main is part of this checkpoint.

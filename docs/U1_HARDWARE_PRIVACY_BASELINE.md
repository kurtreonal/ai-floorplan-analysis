# U1 Hardware, Privacy, and Runtime Baseline

- Ticket: U1
- Measurement date: 2026-09-07 (Asia/Manila)
- Status: PASS
- Application baseline: `81ecd83` (PRE12 published, L1 implemented)
- Model selected or downloaded: no

This document is a sanitized requirements record. It intentionally excludes
usernames, device identifiers, absolute private paths, source filenames,
private hashes, credentials, and drawing contents.

## Measured development machine

| Resource | Measured result | U1 interpretation |
|---|---|---|
| Operating system | Windows 11 Home Single Language, 64-bit, version 10.0.26200/build 26200 | Approved native-Windows target |
| CPU | AMD Ryzen 7 7435HS, 8 physical and 16 logical cores | Approved for bounded U6 measurement; not a performance claim |
| Physical RAM | 16,989,728,768 bytes (about 15.8 GiB) | Approved with single-worker limits |
| Available RAM at inspection | 5,376,929,792 bytes (about 5.01 GiB) | Transient measurement; no model workload was started |
| GPU | NVIDIA GeForce RTX 3050 Laptop GPU | Approved for measured candidate evaluation only |
| Dedicated GPU memory | 4,096 MiB | U6/U10 must stop if a candidate or training configuration cannot fit honestly |
| NVIDIA/CUDA | Driver 566.07; `nvidia-smi` reports CUDA 12.7 | Runtime compatibility still must be proven in the isolated U6 environment |
| Local fixed disk | 480,338,317,312 bytes total; 189,087,903,744 bytes free (about 176.1 GiB) | Fits only the approved bounded storage allocation below |
| Python | CPython 3.11 and 3.13 available | Any model environment remains separate; U6 must choose a compatible interpreter without changing the application environment |
| WSL | Not installed | Not authorized or required for this target |
| Docker | Unavailable | Not authorized or required for this target |

The measured laptop is the approved native-Windows target for bounded local
evaluation and, only if later resource gates pass, adapter training. This is
not a claim that a qualifying model or training configuration will fit. U6 and
U10 must report a resource failure and stop dependent work rather than use
cloud rental, another host, WSL, Docker, or unapproved system changes.

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

The restored repository and private workspace are both outside the user's
OneDrive hierarchy. The private workspace ACL grants access to the current
Windows user and `SYSTEM`; this is a local observation, not proof that historical
copies never reached another endpoint. The earlier Roboflow visibility and
declared-license concern remains a human/external-service issue; U1 performs no
hosted-service mutation.

Device encryption was being disabled during inspection. The user explicitly
approved a temporary exception on 2026-09-07 and intends to re-enable it later.
The exception ends before U3 may ingest any additional real source data or U6
may acquire model artifacts, whichever comes first. Existing private material
remains at risk until encryption is restored; ACLs and local-only operation do
not replace full-disk encryption.

## Approved operating budgets

The user approved these limits on 2026-09-07. They are safety bounds and
objectives, not measured throughput claims or an approved model selection.

| Area | Approved limit or objective |
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
| Latency objective | Median at most 5 minutes and p95 at most 10 minutes per supported page on the measured target |
| Base-model storage | At most 20 GiB total; retain only one evaluation candidate at a time unless a later approval changes the aggregate cap |
| Adapter/checkpoint storage | At most 10 GiB total |
| Corpus plus derivatives | At most 20 GiB total |
| Training scratch | At most 30 GiB total |
| Aggregate new private AI storage | At most 80 GiB, while maintaining at least 20% of the fixed disk's capacity free |

U2 may impose tighter entity/string/array bounds. U6 may recommend lower limits
after real measurements, but it must not silently increase these limits without
a new approval.

## Approved retention policy

The user approved this policy on 2026-09-07.

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
| Intended inference/training target measured | PASS | The restored native-Windows target is measured above; later tickets retain independent fit and performance gates |
| Local-only privacy boundary defined and locally created outside OneDrive | PASS | Read/write/delete probe passed; no existing corpus was moved |
| Page/tile/context/output/concurrency/timeout/latency/storage budgets approved | PASS | User approved the bounded policy recorded above on 2026-09-07 |
| Retention policy approved | PASS | User approved the policy recorded above on 2026-09-07 |
| Model/license acquisition policy defined | PASS | Policy above permits only controlled, pinned, reviewed acquisition in a later ticket |
| No model selection, download, dependency, API, schema, or runtime change | PASS | Repository and environment audit found no VLM artifact or U runtime change |

U2 may start after this passing U1 baseline is verified and published. The
device-encryption exception remains a hard gate before additional U3 real-data
intake or U6 model acquisition.

## Device-transfer checkpoint exception

On 2026-09-07 the user authorized a feature-branch WIP commit and push so the
new device could resume this unfinished ticket. The user also authorized
physical transfer of database, private files and credentials outside Git. This
was not a U1 completion release. The restored device has now been measured and
the user has approved the operating and retention policy recorded above. The
checkpoint commit remains part of the final U1 publication history.

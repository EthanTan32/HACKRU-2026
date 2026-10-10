# FrameTrace implementation and validation report

The application was updated in place. Existing models, extracted CSVs, SQLite indexes, uploads, and diagnostic artifacts were preserved. Do not deploy the old classifier against the new features: inference rejects its incompatible feature/preprocessing contract.

## 1. Files changed

| File (relative to FrameTrace) | Change |
|---|---|
| backend/app/detectors/flow.py | Forward/backward tracking, confidence filtering, RANSAC camera compensation, local temporal acceleration, raw segments, contributing-point overlay. |
| backend/app/detectors/face.py (new) | MediaPipe face tracking, pose-normalized stable geometry, expressions, local facial flow, confidence, overlay. |
| backend/app/detectors/depth.py | Adjacent low-rate depth pairs, texture/occlusion masking, proportional sample-count requirement, robust scale/offset fit. |
| backend/app/preprocessing.py (new) | Shared per-analyzer profiles, analyzer versions, face model/reference hashes. |
| backend/app/anomaly_calibration.py (new) | Optional empirical real-validation reference scores and flags, separate from AI probability. |
| backend/app/video.py | Higher standalone sampling defaults, decoder timestamps with monotonic FPS fallback; no timestamp rounding. |
| backend/app/config.py | Updated standalone sampling defaults. |
| backend/app/pipeline.py | Six analyzers, separate profiles, reusable analyzer cache, overlays, raw segment results, extraction contract. |
| backend/app/features.py | Facial and improved motion features; available, insufficient, unavailable indicators. |
| backend/app/classifier.py | Complete preprocessing compatibility checks; abstention below three usable analyzers; uncertain probability band. |
| backend/app/main.py | Safe allowlist includes new evidence overlays. |
| backend/genbuster_pipeline.py | Generator labels from directories; deterministic balanced sampling distributed across generators; exact manifest selection; versioned per-analyzer caches and feature history. |
| backend/extract_dataset.py | Legacy CSV extractor now exports preprocessing signatures. |
| backend/train_classifier.py | Calibrated logistic/RF/XGBoost comparisons, per-analyzer ablations, generator holdout, metrics, existing model overwrite protection. |
| backend/calibrate_anomalies.py (new) | Fits reference distributions using cached real validation segments. |
| backend/validate_motion.py (new) | Independent balanced exploratory motion validation, excludes original feature CSV clips. |
| backend/requirements.txt | Use OpenCV contrib, compatible with MediaPipe; avoids selecting OpenCV 5. |
| backend/requirements-training.txt | Adds XGBoost. |
| backend/requirements-face.txt (new) | Optional MediaPipe dependency. |
| backend/tests/test_pipeline.py | Six-analyzer contract. |
| backend/tests/test_motion_face.py (new) | Eleven controlled motion, geometry, reliability, and calibration tests (19 total suite cases). |
| frontend/src/App.tsx | Sixth card, raw metrics/evidence details, separate per-analyzer segment plots. |
| frontend/src/api.ts | Segment schema. |
| frontend/src/vite-env.d.ts (new) | Fixes existing ImportMeta.env build typing error. |
| docs/IMPLEMENTATION_REPORT.md (new) | This report and commands. |

Generated artifacts: frontend/dist production build; docs/validation/motion_validation_v4.json; docs/validation/face_smoke_v1.json; backend/data/models/face_landmarker.task. The project .venv now contains core, training, and MediaPipe dependencies. No existing trained model was replaced.

## 2. Mathematical changes

Old flow used p90(||(v2-v1)-median(v2-v1)||), divided by 40, then clipped to [0,1]. This was a velocity difference, not acceleration; it removed translation only, depended on image size, and mapped normal camera/foreground changes to 1.000. At 1 FPS, correspondence failures and large motion were especially problematic.

New flow:

1. Track Shi-Tomasi corners through adjacent frames using pyramidal Lucas-Kanade. Reject failed tracks, high photometric error, out-of-bounds points, and forward/backward errors above 1.5 pixels. Require at least 24 reliable tracks and dominant-model support of 35%.
2. Fit a full affine camera transform with RANSAC independently for both frame intervals. This represents pan, translation, rotation, zoom, and affine perspective approximations; arbitrary projective camera motion is still a limitation.
3. For each interval compute camera-compensated velocity v=(q-T(p))/(dt*image_diagonal), in image diagonals per second.
4. Compute acceleration a=(v2-v1)/((dt1+dt2)/2), in image diagonals per second squared.
5. Subtract the median acceleration of the eight nearest tracked neighbors. Smooth independently moving foreground regions and locally smooth parallax can move/accelerate without receiving large deformation residuals. Record p90 of remaining norms, raw acceleration, track counts, forward/backward error, and confidence.
6. Reject temporal intervals longer than 0.35 seconds rather than claiming continuity from sparse tracks.
7. Without reference calibration, return raw measurements with a null anomaly index and no threshold flags. With at least 30 trusted real-validation segments, use the empirical CDF (rank+0.5)/(N+1). Flag values exceeding the 99th percentile only with confidence >=0.5. These are diagnostic percentiles, never AI probabilities. The validation reference may require many more independent clips to be stable; 30 is an implementation minimum, not evidence of statistical adequacy.

Overlays color the tracked points by their contribution to local acceleration residual. Colors are relative visualization intensities and are not labels. The optical_flow_evidence preview corresponds to the highest raw-residual triplet; the older dense-flow color preview remains available for comparison.

Depth previously used every third frame, making comparisons three seconds apart at 1 FPS. It now compares all adjacent frames of its dedicated 2 FPS stream. Forward/backward consistency has a small displacement-dependent allowance; textureless pixels remain excluded. The validity requirement scales with resolution. Four iterations of robust weighted least squares fit positive monocular depth scale and offset; degenerate depth ranges and unreliable comparisons remain insufficient evidence.

## 3. Facial features

MediaPipe VIDEO mode supplies landmarks, blendshapes, and facial transformation matrices. See the [official Python guide](https://ai.google.dev/edge/mediapipe/solutions/vision/face_landmarker/python).

Correspondence uses temporary spatial association, with ambiguous assignments rejected. There are no embeddings, names, identity databases, or persistent identity vectors. Stable landmark geometry is centered and scale-normalized; a 3D orthogonal Procrustes fit removes rigid pose. Eye and mouth interior points are excluded from the stable-shape error. Eye aperture and mouth opening are retained as raw expression covariates rather than directly triggering anomalies. Head rotation is measured from rotation matrices. Large inter-frame pose changes, small/blurred crops, ambiguous associations, and poor facial-flow agreement reduce evidence or reject observations.

Exported features: median stable-shape residual, median landmark/optical-flow residual normalized by face width, median eye aperture, median mouth opening, valid observation count, tracking confidence. Segments also contain pose change and valid landmark-track counts. The current implementation extracts blendshapes but does not use them in the classifier. Stable relative geometry is represented by normalized point configurations rather than a separate catalog of landmark-pair distances.

## 4. Dependencies and compatible environment

The current Python 3.14 project environment passes the core tests and MediaPipe integration check. Full requirements-models.txt installation failed because no Python 3.14 Windows PaddlePaddle wheel was available. Use a separate Python 3.13 environment for the full OCR/depth/face pipeline; verify pip installation succeeds before extraction. This setup does not delete the existing .venv.

From PowerShell:

```powershell
Set-Location 'C:\path\to\HACKRU-2026\FrameTrace\backend'
# Install Python 3.13 first if py -3.13 is unavailable:
winget install --id Python.Python.3.13 --exact
py -3.13 -m venv .venv313
& .\.venv313\Scripts\python.exe -m pip install -r requirements.txt -r requirements-training.txt -r requirements-models.txt -r requirements-face.txt
& .\.venv313\Scripts\python.exe -m pip check
$python = (Resolve-Path .\.venv313\Scripts\python.exe).Path
$dataset = 'C:\path\to\GenBuster-200K\train'
$env:ENABLE_OCR = '1'
$env:ENABLE_DEPTH = '1'
$env:ENABLE_FACE = '1'
& .\.venv313\Scripts\python.exe .\download_face_model.py
$env:FACE_MODEL_PATH = (Resolve-Path .\data\models\face_landmarker.task).Path
Remove-Item Env:CLASSIFIER_PATH -ErrorAction SilentlyContinue
Remove-Item Env:ANOMALY_REFERENCE_PATH -ErrorAction SilentlyContinue
```

Depth and OCR checkpoints download on first use. Default profiles: flow/face 8 FPS at width 640; depth/background/color 2 FPS at width 384; OCR 2 FPS at width 1280 (the text detector itself processes alternate sampled frames). OCR uses high-resolution full-frame recognition, including PaddleOCR text-region processing; a custom crop-only preprocessing stage was not added. Each stream retains a bounded sample list, rather than all decoded native frames. Long 180-second clips can still use substantial memory at 640 pixels: streaming-window processing of motion/face is a remaining optimization.

Per-analyzer environment controls include OPTICAL_FLOW_FPS, OPTICAL_FLOW_WIDTH, FACIAL_CONSISTENCY_FPS, FACIAL_CONSISTENCY_WIDTH, DEPTH_CONSISTENCY_FPS, DEPTH_CONSISTENCY_WIDTH, TEXT_CONSISTENCY_FPS, TEXT_CONSISTENCY_WIDTH. Extraction and backend inference must share them. Legacy CLI --sample-fps/--frame-width/--max-frames override every stream; use these only for explicit experiments, and reproduce their contract at inference.

## 5. Reprocess exactly the original 100 clips

The original CSV is the manifest and preserves its existing train/val/test assignments. Generator labels are inferred from fake subdirectories. The original source IDs were per-file paths: they do NOT establish that near-duplicates or related source footage are separated.

```powershell
& $python .\genbuster_pipeline.py index --root $dataset --db .\data\genbuster_original100_v4.sqlite3 --metadata-csv .\..\docs\original100_manifest.csv
& $python .\genbuster_pipeline.py extract --db .\data\genbuster_original100_v4.sqlite3 --manifest .\..\docs\original100_manifest.csv
& $python .\genbuster_pipeline.py export --db .\data\genbuster_original100_v4.sqlite3 --out .\data\genbuster_original100_v4.csv
& $python .\train_classifier.py .\data\genbuster_original100_v4.csv --output .\data\classifier_original100_v4.joblib
```

This is a reproduction, not independent validation. It may be too small to support reliable calibrated probabilities. The commands have been documented, not executed for full six-analyzer extraction in this session.

## 6. Balanced 1,000 and 10,000 clip experiments

Each fresh experiment database makes --limit the TOTAL selected count, including previously completed selected clips; resuming does not accidentally select an additional N. Selection interleaves labels and uses a deterministic SHA256 ordering (seed 42), distributing selection across fake generators. Exact class balance requires enough clips of both classes and successful decoding; failures are reported and must be resolved or reported rather than silently relabeled.

```powershell
foreach ($n in @(1000, 10000)) {
    $db = ".\data\genbuster_${n}_v4.sqlite3"
    $csv = ".\data\genbuster_${n}_v4.csv"
    $model = ".\data\classifier_${n}_v4.joblib"
    & $python .\genbuster_pipeline.py index --root $dataset --db $db
    & $python .\genbuster_pipeline.py extract --db $db --limit $n
    & $python .\genbuster_pipeline.py export --db $db --out $csv
    & $python .\train_classifier.py $csv --output $model
}
```

When available, add --metadata-csv 'C:\path\source_metadata.csv' to BOTH index commands before extraction. CSV columns: video_path,source_id, optional generator,split. All derivatives and near-duplicates must share source_id. Cross-split source conflicts are rejected. Without that metadata, splitting is deterministic per file and near-duplicate leakage is not ruled out. Automatic perceptual deduplication was not implemented; therefore these runs must not be called source-safe independent evaluations until grouping is established.

Strict generator-held-out evaluation on a sufficiently diverse experiment:

```powershell
& $python .\train_classifier.py .\data\genbuster_1000_v4.csv --held-out-generator hunyuanvideo --output .\data\classifier_1000_holdout_hunyuan_v4.joblib
```

Held-out generator source groups move entirely to test. Familiar fake test groups move to train; real test groups remain. Every resulting split must still contain both labels, otherwise training fails clearly. A 100-video reproduction containing only one generator cannot support this experiment.

Every trained model's .metrics.json contains accuracy, balanced accuracy, precision, recall, AUROC, false-positive rate and confusion matrix for all three calibrated baselines. XGBoost is the predefined deployed candidate; test performance does not select the model. Six ablations train and calibrate models excluding each analyzer, including its missing-evidence features. No fixed analyzer weights are used. Ablations use the same XGBoost hyperparameters as the full baseline.

Optional reference-percentile calibration, separate from classifier probability calibration:

```powershell
& $python .\calibrate_anomalies.py --db .\data\genbuster_1000_v4.sqlite3 --output .\data\anomaly_reference_1000_v4.json
$env:ANOMALY_REFERENCE_PATH = (Resolve-Path .\data\anomaly_reference_1000_v4.json).Path
& $python .\genbuster_pipeline.py extract --db .\data\genbuster_1000_v4.sqlite3 --limit 1000
& $python .\genbuster_pipeline.py export --db .\data\genbuster_1000_v4.sqlite3 --out .\data\genbuster_1000_v4_calibrated.csv
& $python .\train_classifier.py .\data\genbuster_1000_v4_calibrated.csv --output .\data\classifier_1000_v4_calibrated.joblib
```

Analyzer raw caches are reused during this pass. Keep reference/model files paired and use the same ANOMALY_REFERENCE_PATH during inference. Reference fitting pools segments, so long clips contribute more observations; future validation should evaluate clip-weighted reference estimation. Do not pool caches from incompatible extraction configurations into one reference: use a fresh experiment database for each configuration.

## 7. Restart backend and frontend

In a backend PowerShell terminal (set the same analyzer flags/profiles used for training):

```powershell
Set-Location 'C:\path\to\HACKRU-2026\FrameTrace\backend'
$env:ENABLE_OCR = '1'
$env:ENABLE_DEPTH = '1'
$env:ENABLE_FACE = '1'
& .\.venv313\Scripts\python.exe .\download_face_model.py
$env:FACE_MODEL_PATH = (Resolve-Path .\data\models\face_landmarker.task).Path
$env:CLASSIFIER_PATH = (Resolve-Path .\data\classifier_original100_v4.joblib).Path
# Only set ANOMALY_REFERENCE_PATH if that exact classifier used it during extraction.
& .\.venv313\Scripts\python.exe -m uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
```

Ctrl+C stops an existing server. A model must first be successfully trained at the specified path. For diagnostics before training, omit CLASSIFIER_PATH.

In another PowerShell terminal:

```powershell
Set-Location 'C:\path\to\HACKRU-2026\FrameTrace\frontend'
$env:PATH = 'C:\Program Files\nodejs;' + $env:PATH
npm.cmd ci
npm.cmd run dev -- --host 127.0.0.1
```

## 8. Verification and remaining limitations

- Backend: 19 passed. One third-party Starlette/httpx deprecation warning.
- Frontend: TypeScript and Vite production build passed. Vite reports a bundle-size warning.
- Dependency check: no broken requirements after MediaPipe installation and OpenCV 4 pinning.
- Real upload face smoke: 40 valid observations, median shape residual 0.00215, median local-flow residual 0.00407, track acceptance confidence 1.0. This is integration evidence, not an accuracy evaluation.
- Independent exploratory motion dataset: 20 real + 20 fake clips, deterministic seed 20261010, excluding all clips listed in the original CSV. 40/40 usable. Raw local-deformation AUROC 0.17; raw acceleration AUROC 0.1125. Higher residuals generally occurred in REAL footage. This refutes the assumption that these motion magnitudes should be monotonic AI likelihood. It does not establish improved full-system accuracy or false-positive rate. Full report: docs/validation/motion_validation_v4.json.
- Synthetic tests exercise pan/rotation/zoom, independently moving foreground, coherent local acceleration, discontinuities, geometric warp, pose-normalized face geometry with expression-point changes, depth scale/offset, textureless evidence rejection, sparse/blank unreliable sequences, and empirical calibration. They are geometric stand-ins; they do not replace labeled videos of walking, speaking, smiling/blinking, severe blur/occlusion, or head turns.
- The face model was exercised on real video, but no labeled real/generated facial accuracy evaluation was performed.
- Dense pretrained flow was not added: no demonstrated benefit was available to justify its dependency/runtime cost.
- Full OCR/depth inference and 100/1,000/10,000 six-analyzer retraining were NOT run because PaddlePaddle is unavailable for this Python 3.14 environment. Probability improvements and deployment readiness remain unverified.
- Facial geometry residuals are sensitive to landmark model jitter; very fast head turns are rejected. The spatial face association can reset around crossings and re-entry; no identity recognition is used to resolve them.
- RANSAC assumes a useful dominant affine scene component; complex perspective, crowded scenes, scene cuts, texture loss, and rolling shutter can limit evidence. Neighbor residuals can still rise at foreground boundaries and with real articulated deformation.
- Classifier abstention currently uses fewer than three usable analyzers and a policy probability band (0.35,0.65), not a learned uncertainty model or confidence interval. Report coverage and conditional error rates on independent data before relying on this policy.
- Generator holdout is a supported evaluation mode, not a completed generator-generalization result.

Reproduce checks:

```powershell
Set-Location 'C:\path\to\HACKRU-2026\FrameTrace\backend'
& .\.venv\Scripts\python.exe -m pytest -q
& .\.venv\Scripts\python.exe -m pip check
Set-Location ..\frontend
$env:PATH = 'C:\Program Files\nodejs;' + $env:PATH
npm.cmd run build
```

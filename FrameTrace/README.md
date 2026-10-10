# FrameTrace: AI-generated video diagnostics

FrameTrace is a React + FastAPI application with six temporal video analyzers and an optional supervised classifier trained on labeled camera-recorded (`real`, label 0) and generated (`fake`, label 1) footage.

| Analyzer | Measurement | Optional dependency |
|---|---|---|
| Text consistency | Tracked OCR character stability | PaddleOCR/PaddlePaddle |
| Background motion | Dominant-scene geometric coherence | None |
| Depth consistency | Motion-aligned relative depth | PyTorch/Transformers |
| Optical flow | Camera-compensated, locally normalized trajectory acceleration | None |
| Gamma/saturation | Aligned brightness and color residuals | None |
| Facial consistency | Pose-normalized landmark geometry and local facial flow | MediaPipe and face landmarker model |

**The application runs in diagnostics mode without a trained classifier.** Optional analyzers report unavailable evidence until enabled. Measurements and anomaly indices are not probabilities of AI generation. Improved classifier accuracy and full six-analyzer retraining have not been demonstrated. See the [implementation and validation report](docs/IMPLEMENTATION_REPORT.md) and [architecture](docs/ARCHITECTURE.md).

## Requirements

- Python **3.13 recommended** for the full optional stack. PaddlePaddle could not install in the original Python 3.14 Windows environment. Wheel availability varies by operating system.
- Node.js **20 or newer**, with 22 recommended, and npm. The checked-in lockfile includes Tailwind dependencies requiring Node 20+.
- Internet access for dependency installation and model downloads. FFmpeg on PATH is useful for broader codec support.

All commands start from this repository's `FrameTrace` directory. Source, manifests, frontend lockfile, tests, and model download instructions are included. Virtual environments, dependencies, datasets, uploads, trained models, and runtime caches are generated locally and excluded from Git.

## Start on Windows PowerShell

Backend terminal:

```powershell
cd backend
py -3.13 -m venv .venv
& .\.venv\Scripts\python.exe -m pip install --upgrade pip
& .\.venv\Scripts\python.exe -m pip install -r requirements.txt -r requirements-training.txt
$env:ENABLE_OCR = '0'
$env:ENABLE_DEPTH = '0'
$env:ENABLE_FACE = '0'
Remove-Item Env:CLASSIFIER_PATH -ErrorAction SilentlyContinue
& .\.venv\Scripts\python.exe -m uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
```

Frontend terminal, starting from `FrameTrace`:

```powershell
cd frontend
npm.cmd ci
npm.cmd run dev -- --host 127.0.0.1
```

## Start on macOS or Linux

Backend terminal:

```sh
cd backend
python3.13 -m venv .venv
.venv/bin/python -m pip install --upgrade pip
.venv/bin/python -m pip install -r requirements.txt -r requirements-training.txt
export ENABLE_OCR=0 ENABLE_DEPTH=0 ENABLE_FACE=0
unset CLASSIFIER_PATH
.venv/bin/python -m uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
```

Frontend terminal, starting from `FrameTrace`:

```sh
cd frontend
npm ci
npm run dev -- --host 127.0.0.1
```

Open <http://localhost:5173>. API documentation is at <http://localhost:8000/docs>. Uploads are limited to 100 MB and 30 seconds. Stop either server with Ctrl+C. The local development server uses an in-process job queue; production hosting requires additional infrastructure.

## Enable OCR, depth, and facial consistency

Stop the backend and run these commands from `backend`. Install `requirements-models.txt` for OCR/depth and `requirements-face.txt` for facial consistency. You can enable these independently. OCR/depth checkpoints download on first use; face has an explicit downloader.

Windows PowerShell:

```powershell
& .\.venv\Scripts\python.exe -m pip install -r requirements-models.txt -r requirements-face.txt
& .\.venv\Scripts\python.exe download_face_model.py
& .\.venv\Scripts\python.exe -m pip check
$env:ENABLE_OCR = '1'
$env:ENABLE_DEPTH = '1'
$env:ENABLE_FACE = '1'
$env:FACE_MODEL_PATH = (Resolve-Path .\data\models\face_landmarker.task).Path
& .\.venv\Scripts\python.exe -m uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
```

macOS/Linux:

```sh
.venv/bin/python -m pip install -r requirements-models.txt -r requirements-face.txt
.venv/bin/python download_face_model.py
.venv/bin/python -m pip check
export ENABLE_OCR=1 ENABLE_DEPTH=1 ENABLE_FACE=1
export FACE_MODEL_PATH="$PWD/data/models/face_landmarker.task"
.venv/bin/python -m uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
```

The downloader stores `backend/data/models/face_landmarker.task` and verifies its checksum. No classifier or training dataset is required to inspect detector measurements. Full optional-stack setup is provided; a six-analyzer accuracy evaluation remains unfinished.

## Configuration

[.env.example](.env.example) lists settings. **Python does not automatically load `.env` files.** Set variables in the shell that starts extraction, training, or the backend. Restart after changing settings. For a different frontend API address, set `VITE_API_URL` in the frontend shell before starting/building Vite.

Default analyzer profiles: optical flow/face 8 FPS at width 640; depth/background/color 2 FPS at width 384; OCR 2 FPS at width 1280. Per-analyzer variables such as `OPTICAL_FLOW_FPS` and `OPTICAL_FLOW_WIDTH` override these profiles. Extraction and inference must share the exact feature/preprocessing contract, including enabled analyzers, profile settings, model configuration, face-model path/hash, and any anomaly-reference file.

## Dataset extraction and optional classifier training

Obtain and extract the dataset separately. Arrange it as `real/` and `fake/`, with generator subdirectories where available. Related clips should share a `source_id` in metadata; automatic near-duplicate grouping is not implemented. The [example metadata](docs/example_metadata.csv) shows the format.

From `backend`, using the environment above:

```sh
python genbuster_pipeline.py index --root /absolute/path/to/dataset --metadata-csv ../docs/your_metadata.csv
python genbuster_pipeline.py extract --limit 1000
python genbuster_pipeline.py export --out data/genbuster_features.csv
python train_classifier.py data/genbuster_features.csv --output data/classifier.joblib
```

Replace `python` with `.venv/bin/python` on macOS/Linux or `& .\.venv\Scripts\python.exe` in PowerShell. Use your actual dataset and metadata paths. Enable OCR/depth before extraction; enable face for a six-analyzer experiment. For a core-only smoke test, `extract --allow-disabled-models --limit 100` marks disabled features unavailable. `--limit` caps the selected dataset, including already completed selected clips when resuming. Completed work with the same contract is reused.

Training compares calibrated logistic regression, random forest, and XGBoost and writes test metrics plus analyzer ablations. No compatible pretrained classifier is bundled. See the [implementation report](docs/IMPLEMENTATION_REPORT.md) for exact reproduction, larger balanced experiments, reference calibration, and generator holdout commands.

To load a **trusted** classifier, reproduce its exact training contract in the backend environment, then set its path before starting the server:

```powershell
$env:CLASSIFIER_PATH = (Resolve-Path .\data\classifier.joblib).Path
```

```sh
export CLASSIFIER_PATH="$PWD/data/classifier.joblib"
```

Joblib files can execute code during loading; use models you trained or trust. An incompatible artifact returns `model_unavailable` with an explanation. Fewer than three usable analyzers yields `insufficient_evidence`; probabilities between 0.35 and 0.65 yield `uncertain`. These policies require independent evaluation. Omit `CLASSIFIER_PATH` for diagnostics mode.

## Verify a checkout

Windows PowerShell, starting from `FrameTrace`:

```powershell
cd backend
& .\.venv\Scripts\python.exe -m pytest -q
& .\.venv\Scripts\python.exe -m pip check
cd ..\frontend
npm.cmd run build
```

macOS/Linux, starting from `FrameTrace`:

```sh
cd backend
.venv/bin/python -m pytest -q
.venv/bin/python -m pip check
cd ../frontend
npm run build
```

Tests exercise the API, extraction/training contracts, synthetic motion/geometry, appearance/depth checks, and calibration. Passing verifies software behavior; it does not establish accuracy on unseen videos.

## Project layout and API

```text
frontend/                       React upload, reports, evidence plots and previews
backend/app/                    FastAPI, six detectors, features and classifier
backend/genbuster_pipeline.py   index / extract / export / stats
backend/train_classifier.py     calibrated baselines, ablations and holdout metrics
backend/calibrate_anomalies.py  optional real-validation reference distributions
backend/download_face_model.py  face model download and checksum check
backend/tests/                  API, pipeline, geometry and training tests
docs/                           architecture, report and sample metadata
```

Endpoints: `POST /api/videos`, `GET /api/videos/{id}/status`, `GET /api/videos/{id}/results`, `GET /api/videos/{id}/media`, `GET /api/videos/{id}/artifacts/{name}`, `DELETE /api/videos/{id}`, and `GET /api/health`.

# FrameTrace architecture

FastAPI receives short videos, extracts six sets of diagnostic measurements, and serves a React/TypeScript evidence dashboard. A trained classifier is optional: the application runs in diagnostics mode with no model file.

## Sampling and evidence

`app/preprocessing.py` defines shared training/inference profiles and analyzer versions. Motion and faces use 8 FPS at width 640; depth, background and appearance use 2 FPS at width 384; OCR uses width 1280. Each sample stream is bounded. Decoder timestamps are retained with a monotonic nominal-FPS fallback. Classifier inference checks the complete extraction contract against the saved model.

The six modules retain separate status, metrics, events and optional segment/overlay data:

- Text: PaddleOCR and approximate region tracking; requires optional OCR dependencies.
- Background: tracked features and RANSAC homography; parallax can confound it.
- Depth: optional Depth Anything V2 Small, dense correspondence masks and robust positive scale/offset alignment on adjacent low-rate frames.
- Flow: forward/backward KLT checks, RANSAC affine camera compensation, elapsed-time/diagonal normalized acceleration and deviation from nearby motion. Raw measurements are separate from optional real-validation empirical percentiles.
- Appearance: motion-aligned gamma and saturation residuals. Diagnostic filters provide views of pixels rather than evidence of generation.
- Face: optional MediaPipe Face Landmarker, temporary spatial associations, pose-normalized stable geometry, eye/mouth expression covariates and local flow. No identity embeddings or recognition database.

## Training

`genbuster_pipeline.py` indexes dataset metadata in SQLite, selects deterministic balanced experiments, and caches versioned per-analyzer results. Source-group metadata is required to establish source-safe splits; automatic near-duplicate discovery is not implemented. Generator-held-out mode is supported.

`train_classifier.py` compares logistic regression, Random Forest and XGBoost. Models learn from raw metrics and explicit missing-evidence indicators. A separate validation split calibrates probabilities; test metrics and six analyzer ablations are reported. XGBoost is the predefined deployment candidate. Fewer than three usable analyzers causes abstention; probabilities in (0.35,0.65) receive an uncertain label.

## Validation status

The backend suite passed 19 tests and the frontend production build passed. A 40-clip independent motion exploration found that higher raw residuals tended to occur in real footage; these measurements cannot be assumed to increase with AI likelihood. Full six-analyzer classifier retraining and generalization improvements are not established.

See [setup](../README.md) and [implementation report](IMPLEMENTATION_REPORT.md) for mathematical details, experiment commands, and limitations. Runtime data, uploads, checkpoints and models are generated locally and ignored by Git.

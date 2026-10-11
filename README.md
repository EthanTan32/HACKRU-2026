# HACKRU-2026

# HACKRU-2026
<<<<<<< Updated upstream
yo
=======

FrameTrace video forensics is available in [FrameTrace](FrameTrace/README.md), including backend/frontend setup, optional model downloads, tests, and classifier training instructions.
yo


## Inspiration

As generative video models (Sora, Omni, etc.) become more and more realistic, the boundary between recorded reality and generated content becomes thinner and thinner. Today's AI's don't just deepfake and they rarely make the same telltale mistakes they once did. Modern generative models are used for propoganda, trick juries with fake evidence, and for scamming.

Most AI detectors rely on proprietary black-boxes which output probalistic guesses without a verifiable decision trail. 

VerityAI is our response: VerityAI is a multi-stage verification platform that combines frame-by-frame visual analysis, spacial tracking, and transparency so users don't have to rely on a superficial 'vibe-check.'


## What it does

VerityAI starts with a binary level where a function scans the video header for signed credentials and checks them with the Coalition for Content Provenance and Authenticity standards.

The next layer down, VerityAI uses multiple strategies to identify suspicious points and anomolies before classifying each video.
- Dense optical flow algorithms is used to uncover tearing, warping, and other suspicious artifacts
- A monocular depth model (from Depth Anything) is used to reconstruct 3D space to detect suspcious volutes and geometric inconsistencies
- Colors and brightness are analyzed for suspcious fluctuations across frames and poor tracking with shadows. 
- Facial landmarks are tracked through MediaPipe to detect inconsistencies in anatomy. 

## How we built it

VerityAI is structured into 3 parts: a web platform, a diagnostic console, and a deep-learning backend. 
- VerityAI Web Platform is build with Next.js, React, TypeScript, and Tailwind CSS. It also features an interactive WebGL GUI powered by Three.js and beautiful UI elements with DaisyUI.
- VerityAI's diagnostic console is powered by Vite and Recharts to show detected anomalies in real-time while rendering diagnostics and timelines for transparency.
- VertiyAI's neural backend leverages quick C2PA metadata checks for confirmed human/AI content before analysing suspicious videos.
    - Computer vision through OpenCV, NumPU, SciPuy, and FFmpeg handles video processing and frame-by-fram analysis.
    - Deep learning through XGBoost and Scikit correlates anomaly metrics against datasets for accurate classification.

## Challenges we ran into

Metadata stripping: social media platforms strip C2PA metadata during compression which demands even more accuracy out of VerityAI

Motion confusion: 

## Accomplishments that we're proud of

Transparency: Rather than giving a user a percentage with no explanation, VerityAI records evidence and anomalies like impossible motions in the optical flow vector fields, impossible volumes through the depth map, and incorrect shadows by checking gamma values. 

Pipelining: Connected complex computer vision analysis with C2PA  validation, bridging header authentication and physics-based deep learning into a fast, cohesive verification pipeline.

High quality design: Created a polished and modern webpage using Next.js, Tailwind, and Three.js to make complex digital analysis accessible for non-technical users.

## What we learned

We learned to process metadata headers for cryptographic signatures to verify with C2PA. 

Working with training data taught us the complexity of diffusion models and how they generate frames out of layered noise then stretched between frames via optical flow. 

## What's next for VerityAI

Browser Extension for Live Verification: Bringing VerityAI’s C2PA and scan heuristics directly to users browsing through social media feeds for real-time alerts of altered or generated content.

Continuous Audio-Visual Sync: Detecting deepfakes by identifying desyncs between the video and audio through precise facial landmark systems and audio processing.
>>>>>>> Stashed changes


FrameTrace video forensics is available in [FrameTrace](FrameTrace/README.md), including backend/frontend setup, optional model downloads, tests, and classifier training instructions.
yo

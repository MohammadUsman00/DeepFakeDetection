## Architecture (placeholder)

This document will be filled as implementation progresses.

### Explainability note (Grad-CAM)
Grad-CAM is intentionally generated only for the **Top-K most suspicious frames (K=5)** to keep CPU runtime and storage usage bounded. Generating heatmaps for every sampled frame would significantly increase latency on a typical laptop.


# Experimental evidence and limits

The notebooks retain historical YOLOv8 console outputs, but this public repository does not distribute the exact dataset export, trained checkpoint, validation split manifest, or run artefacts needed to independently reproduce those measurements.

For that reason, this repository intentionally makes no public claim for mAP, precision, recall, F1, or agronomic accuracy. A reproducible report must record, at minimum:

- the immutable dataset version and split;
- the base checkpoint and final weight checksum;
- Ultralytics, PyTorch, CUDA, and Python versions;
- training command and random seed;
- validation metrics exported from the matching run.

`neural_network/train_v2.py` provides the public training entry point once a permitted local dataset export and weights are available. The CI workflow exercises deterministic application logic only; it does not train a model or run private weights.

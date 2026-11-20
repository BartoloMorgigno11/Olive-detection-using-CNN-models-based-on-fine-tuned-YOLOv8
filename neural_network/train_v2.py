"""Train the reproducible Olive Detection v2 model on the local Roboflow export."""

from __future__ import annotations

import argparse
from pathlib import Path

from ultralytics import YOLO
import yaml


ROOT = Path(__file__).resolve().parent
DEFAULT_DATASET = ROOT / "olive-v2.yaml"
DEFAULT_OUTPUT = ROOT / "runs"
DEFAULT_MODEL = ROOT / "models" / "yolov8n.pt"
RESOLVED_DATASET = ROOT / ".olive-v2.resolved.yaml"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data", type=Path, default=DEFAULT_DATASET)
    parser.add_argument("--model", type=Path, default=DEFAULT_MODEL, help="Local Ultralytics checkpoint to fine-tune.")
    parser.add_argument("--epochs", type=int, default=80)
    parser.add_argument("--batch", type=int, default=16)
    parser.add_argument("--imgsz", type=int, default=640)
    parser.add_argument(
        "--device",
        default=None,
        help="CUDA device index (for example '0') or 'cpu'; omitted = let Ultralytics choose.",
    )
    parser.add_argument("--project", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--name", default="olive-v2")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    if not args.data.is_file():
        raise FileNotFoundError(f"Dataset configuration not found: {args.data}")
    if not args.model.is_file():
        raise FileNotFoundError(
            f"Base checkpoint not found: {args.model}. Download yolov8n.pt into "
            "neural_network/models before training."
        )

    dataset_config = yaml.safe_load(args.data.read_text(encoding="utf-8"))
    dataset_root = Path(dataset_config["path"])
    if not dataset_root.is_absolute():
        dataset_config["path"] = str((args.data.parent / dataset_root).resolve())
    RESOLVED_DATASET.write_text(yaml.safe_dump(dataset_config, sort_keys=False), encoding="utf-8")

    try:
        model = YOLO(str(args.model))
        model.train(
            data=str(RESOLVED_DATASET),
            epochs=args.epochs,
            batch=args.batch,
            imgsz=args.imgsz,
            device=args.device,
            project=str(args.project),
            name=args.name,
            patience=15,
            seed=42,
            pretrained=True,
        )
    finally:
        RESOLVED_DATASET.unlink(missing_ok=True)


if __name__ == "__main__":
    main()

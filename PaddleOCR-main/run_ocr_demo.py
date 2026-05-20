from __future__ import annotations

import argparse
from pathlib import Path
from typing import Iterable

from paddleocr import PaddleOCR


DEFAULT_IMAGE = Path("docs/images/ppocrv4_en.jpg")
DEFAULT_OUTPUT_DIR = Path("ocr_demo_output")


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Run a local PaddleOCR demo on a sample image and print the result."
    )
    parser.add_argument(
        "--image",
        type=Path,
        default=DEFAULT_IMAGE,
        help=f"Input image path. Defaults to {DEFAULT_IMAGE.as_posix()}",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=DEFAULT_OUTPUT_DIR,
        help=f"Directory for saved OCR artifacts. Defaults to {DEFAULT_OUTPUT_DIR.as_posix()}",
    )
    parser.add_argument(
        "--engine",
        choices=("paddle", "transformers"),
        default="paddle",
        help="Inference engine to use.",
    )
    return parser


def _print_header(title: str) -> None:
    print()
    print(title)
    print("=" * len(title))


def _print_result_summary(result: Iterable[object]) -> None:
    for index, item in enumerate(result, start=1):
        print(f"\nResult {index}:")
        if hasattr(item, "print"):
            item.print()
        else:
            print(item)


def main() -> int:
    parser = _build_parser()
    args = parser.parse_args()

    image_path = args.image.resolve()
    output_dir = args.output_dir.resolve()

    if not image_path.exists():
        parser.error(f"Image not found: {image_path}")

    output_dir.mkdir(parents=True, exist_ok=True)

    _print_header("PaddleOCR local demo")
    print(f"Image:   {image_path}")
    print(f"Engine:  {args.engine}")
    print(f"Output:  {output_dir}")

    _print_header("What OCR does here")
    print("1. Load the image from disk.")
    print("2. Detect text regions in the image.")
    print("3. Recognize the text inside each region.")
    print("4. Save the annotated image and JSON result.")

    ocr = PaddleOCR(engine=args.engine)
    result = ocr.predict(str(image_path))

    _print_header("OCR output")
    _print_result_summary(result)

    for index, item in enumerate(result, start=1):
        image_output_dir = output_dir / f"result_{index}"
        image_output_dir.mkdir(parents=True, exist_ok=True)
        if hasattr(item, "save_to_img"):
            item.save_to_img(str(image_output_dir))
        if hasattr(item, "save_to_json"):
            item.save_to_json(str(output_dir / f"result_{index}.json"))

    _print_header("Done")
    print(f"Saved OCR artifacts to: {output_dir}")
    print("Open the saved PNG to see the text boxes and recognized text.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
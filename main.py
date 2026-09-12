from argparse import ArgumentParser
from pathlib import Path

from anpr import read_plate
from detection import detect_vehicles
from reports import print_report
from tracking import track_vehicles


def parse_args():
    parser = ArgumentParser(description="Intelligent traffic monitoring")
    parser.add_argument("video", type=Path, help="Path to the traffic video")
    parser.add_argument(
        "--plate-image",
        type=Path,
        help="Optional path to a number-plate image for OCR",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("output"),
        help="Directory for generated detection and tracking files",
    )
    parser.add_argument(
        "--confidence",
        type=float,
        default=0.25,
        help="Minimum YOLO confidence score",
    )
    parser.add_argument(
        "--road-roi",
        nargs=4,
        type=int,
        metavar=("X1", "Y1", "X2", "Y2"),
        help="Road region in pixels: left top right bottom; defaults to the full frame",
    )
    return parser.parse_args()


def main():
    args = parse_args()

    if not args.video.is_file():
        raise FileNotFoundError(f"Video not found: {args.video}")

    args.output.mkdir(parents=True, exist_ok=True)

    print(f"Processing video: {args.video}")
    detect_vehicles(args.video, args.output, args.confidence)
    traffic_data = track_vehicles(
        args.video,
        args.output,
        args.confidence,
        tuple(args.road_roi) if args.road_roi else None,
    )

    plate_results = []
    if args.plate_image:
        if not args.plate_image.is_file():
            raise FileNotFoundError(f"Plate image not found: {args.plate_image}")
        plate_results = read_plate(args.plate_image)

    print_report(traffic_data, plate_results)


if __name__ == "__main__":
    main()

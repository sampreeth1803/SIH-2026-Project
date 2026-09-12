from pathlib import Path

def read_plate(image_path: Path):
    import easyocr

    reader = easyocr.Reader(["en"])
    return reader.readtext(str(image_path))

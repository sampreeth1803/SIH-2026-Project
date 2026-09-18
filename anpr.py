from pathlib import Path
from privacy import normalize_plate

def read_plate(image_path: Path):
    import easyocr

    reader = easyocr.Reader(["en"])
    return reader.readtext(str(image_path))

def best_plate_candidate(image_path: Path) -> dict | None:
    candidates=[]
    for _box,text,confidence in read_plate(image_path):
        normalized=normalize_plate(text)
        if 4 <= len(normalized) <= 14 and any(char.isdigit() for char in normalized): candidates.append({"text":normalized,"confidence":round(float(confidence),3)})
    return max(candidates,key=lambda item:item["confidence"],default=None)

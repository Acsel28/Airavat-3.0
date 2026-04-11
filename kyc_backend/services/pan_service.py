import re
from utils.ocr import extract_text_google_vision

def extract_pan_details(text):
    lines = [line.strip() for line in text.split("\n") if line.strip()]

    pan_number = None
    name = None
    father_name = None

    for i, line in enumerate(lines):

        # 🔹 PAN Number (keep your logic, slightly stricter)
        pan_match = re.search(r"\b[A-Z]{5}[0-9]{4}[A-Z]\b", line)
        if pan_match:
            pan_number = pan_match.group()

        # 🔹 Name (line AFTER "Name")
        if "Name" in line and "Father" not in line:
            if i + 1 < len(lines):
                name = lines[i + 1]

        # 🔹 Father's Name (line AFTER "Father's Name")
        if "Father's Name" in line:
            if i + 1 < len(lines):
                father_name = lines[i + 1]
    return {
        "pan_number": pan_number,
        "name": name,
        "father_name": father_name
    }


def process_pan(file_bytes):
    text = extract_text_google_vision(file_bytes)

    details = extract_pan_details(text)
    return details


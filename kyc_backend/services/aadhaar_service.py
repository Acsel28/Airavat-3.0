import re
from utils.ocr import extract_text_google_vision

def extract_aadhaar_details(text):
    lines = [line.strip() for line in text.split("\n") if line.strip()]

    aadhaar_pattern = r"\d{4}\s?\d{4}\s?\d{4}"
    aadhaar = re.findall(aadhaar_pattern, text)

    name = None
    dob = None
    dob_line_index = None

    # Step 1: Find DOB line
    for i, line in enumerate(lines):
        if "dob" in line.lower():
            dob_line_index = i

            # Extract DOB from same line
            match = re.search(r"\d{2}[/\-]\d{2}[/\-]\d{4}", line)
            if match:
                dob = match.group()

            break

    # Step 2: Extract Name using "To"
    for i, line in enumerate(lines):
        if line.lower().startswith("to"):
            if i + 1 < len(lines):
                name = lines[i + 1]
                break

    # Step 3: If not found, use line above DOB
    if not name and dob_line_index is not None:
        if dob_line_index > 0:
            name = lines[dob_line_index - 1]

    # Step 4: Fallback (your previous logic)
    if not name:
        blacklist = ["government", "india", "authority", "uidai"]
        for line in lines:
            if (
                len(line.split()) >= 2 and
                not any(char.isdigit() for char in line) and
                not any(word in line.lower() for word in blacklist)
            ):
                name = line
                break

    return {
        "name": name,
        "aadhaar_number": aadhaar[0] if aadhaar else None,
        "dob": dob
    }


def mask_aadhaar(aadhaar):
    if aadhaar:
        return "XXXX XXXX " + aadhaar[-4:]
    return None


def process_aadhaar(file_bytes):
    text = extract_text_google_vision(file_bytes)

    details = extract_aadhaar_details(text)

    # if details["aadhaar_number"]:
    #     details["aadhaar_number"] = mask_aadhaar(details["aadhaar_number"])

    return details
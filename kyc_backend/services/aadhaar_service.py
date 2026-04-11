import re
from utils.ocr import extract_text_google_vision


def extract_aadhaar_details(text):
    lines = [line.strip() for line in text.split("\n") if line.strip()]

    aadhaar_pattern = r"\d{4}\s?\d{4}\s?\d{4}"
    aadhaar = re.findall(aadhaar_pattern, text)

    name = None
    dob = None
    gender = None
    phone = None
    dob_line_index = None

    # -------------------------------
    # ✅ PHONE NUMBER
    # -------------------------------
    phone_match = re.findall(r"\b[6-9]\d{9}\b", text)
    if phone_match:
        phone = phone_match[0]

    # -------------------------------
    # ✅ GENDER
    # -------------------------------
    for line in lines:
        if "male" in line.lower():
            gender = "Male"
            break
        elif "female" in line.lower():
            gender = "Female"
            break

    # -------------------------------
    # ✅ DOB + INDEX
    # -------------------------------
    for i, line in enumerate(lines):
        if "dob" in line.lower():
            dob_line_index = i

            match = re.search(r"\d{2}[/\-]\d{2}[/\-]\d{4}", line)
            if match:
                dob = match.group()

            break

    # -------------------------------
    # ✅ NAME EXTRACTION (SMART)
    # -------------------------------

    def clean_line(line):
        return re.sub(r"[^A-Za-z\s]", "", line).strip()

    def is_valid_name_candidate(line):
        blacklist = ["government", "india", "authority", "uidai", "aadhaar"]
        words = line.split()

        return (
            2 <= len(words) <= 4 and
            all(word.isalpha() for word in words) and
            not any(word.lower() in blacklist for word in words)
        )

    def score_name_candidate(line, index, dob_index):
        score = 0
        words = line.split()

        # Length score
        if 2 <= len(words) <= 4:
            score += 2

        # Uppercase bonus
        if line.isupper():
            score += 2

        # Near DOB bonus
        if dob_index is not None:
            distance = abs(index - dob_index)
            if distance <= 2:
                score += 3
            elif distance <= 5:
                score += 1

        # No digits bonus
        if not any(char.isdigit() for char in line):
            score += 2

        return score

    best_score = -1

    for i, line in enumerate(lines):
        cleaned = clean_line(line)

        if is_valid_name_candidate(cleaned):
            score = score_name_candidate(cleaned, i, dob_line_index)

            if score > best_score:
                best_score = score
                name = cleaned

    # -------------------------------
    # ✅ FALLBACK (VERY IMPORTANT)
    # -------------------------------
    if not name and dob_line_index is not None:
        if dob_line_index > 0:
            name = clean_line(lines[dob_line_index - 1])

    # -------------------------------
    # ✅ FINAL OUTPUT
    # -------------------------------
    return {
        "name": name,
        "aadhaar_number": aadhaar[0] if aadhaar else None,
        "dob": dob,
        "gender": gender,
        "mobile": phone
    }


def mask_aadhaar(aadhaar):
    if aadhaar:
        return "XXXX XXXX " + aadhaar[-4:]
    return None


def process_aadhaar(file_bytes):
    text = extract_text_google_vision(file_bytes)

    details = extract_aadhaar_details(text)

    return details
from google.cloud import vision

def extract_text_google_vision(file_bytes):
    client = vision.ImageAnnotatorClient()

    image = vision.Image(content=file_bytes)

    response = client.document_text_detection(image=image)

    if response.text_annotations:
        return response.text_annotations[0].description
    return ""
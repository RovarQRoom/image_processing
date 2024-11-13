from flask import Flask, jsonify, request
from flask_cors import CORS
from werkzeug.utils import secure_filename
import os
import cv2
from passporteye import read_mrz
from datetime import datetime
from appwrite_module import get_storage
from appwrite.input_file import InputFile
from appwrite.id import ID
import logging
import numpy as np

app = Flask(__name__)
CORS(app)
storage = get_storage()
app.logger.setLevel(logging.INFO)

# Use Flask's instance path to construct the path to the uploads directory
UPLOAD_FOLDER = os.path.join("", "static/uploads")
# Ensure the upload folder exists
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

# Assuming you have the haarcascade file in the same directory as your app
HAARCASCADE_PATH = "haarcascade_frontalface_default.xml"


def extract_face(filepath, expand_margin=0.7):
    try:
        img = cv2.imread(filepath)
        gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
        face_cascade = cv2.CascadeClassifier(HAARCASCADE_PATH)
        faces = face_cascade.detectMultiScale(gray, 1.3, 5)

        if len(faces) == 0:
            return None  # No face detected

        # Expand the detected face area
        x, y, w, h = faces[0]
        expand_w = int(w * expand_margin)
        expand_h = int(h * expand_margin)

        # Make sure the expanded area does not go out of image bounds
        x_expanded = max(x - expand_w, 0)
        y_expanded = max(y - expand_h, 0)
        w_expanded = min(w + 2 * expand_w, img.shape[1] - x_expanded)
        h_expanded = min(h + 2 * expand_h, img.shape[0] - y_expanded)

        # Extract the whole frame of the face picture in the passport
        face = img[y_expanded:y_expanded+h_expanded, x_expanded:x_expanded+w_expanded]
        face_filepath = filepath.rsplit(".", 1)[0] + "_face.jpg"
        cv2.imwrite(face_filepath, face)
        return face_filepath.replace("\\", "/")
    except Exception as e:
        app.logger.info(f"Error in extract_face: {e}")
        return None



@app.route("/api/data", methods=["GET"])
def get_data():
    data = {"message": "Hello from Python backend!"}
    return jsonify(data)


@app.route("/api/process_passport", methods=["POST"])
def process_passport():
    try:
        # Check if the part 'file' is present
        if "file" not in request.files:
            return jsonify({"error": "No file part"}), 400
        file = request.files["file"]
        if file.filename == "":
            return jsonify({"error": "No selected file"}), 400
        
        # Save the uploaded file
        filename = secure_filename(file.filename)
        filepath = os.path.join(UPLOAD_FOLDER, filename)
        file.save(filepath)
        app.logger.info(f"Saved file to {filepath}")
        
        # Process the MRZ
        mrz_data = read_mrz(filepath)
        if mrz_data is None:
            # Open the saved image and process it
            image = cv2.imread(filepath)
            gray_image = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
            _, thresh_image = cv2.threshold(gray_image, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
            processed_filepath = os.path.join(UPLOAD_FOLDER, 'processed_' + filename)
            cv2.imwrite(processed_filepath, thresh_image)
            mrz_data = read_mrz(processed_filepath)
            
        mrz_dict = mrz_data.to_dict()
        print(mrz_dict)
        # Correct and format data from MRZ
        personal_number = mrz_dict.get("personal_number", "").replace("<", "")
        surname = mrz_dict.get("surname", "").lstrip("Q")
        names = mrz_dict.get("names", "").replace("X", "")
        country_correction = {"ITR": "IRQ"}  # Example of country code correction
        corrected_country = country_correction.get(mrz_dict.get("country"), mrz_dict.get("country"))
        
        # Format dates
        dob = datetime.strptime(mrz_dict.get("date_of_birth", "000000"), "%y%m%d").strftime("%Y-%m-%d")
        exp_date = datetime.strptime(mrz_dict.get("expiration_date", "000000"), "%y%m%d").strftime("%Y-%m-%d")

        # Process the face image and store it
        app.logger.info(f"Calling extract_face with filepath {filepath}")
        face_filename = extract_face(filepath)
        app.logger.info(f"Face filename: {face_filename}")
        # Assuming `storage.create_file` and `ID.unique` work as expected.
        result = storage.create_file('6602a873de0e9ff815f0', ID.unique(), InputFile.from_path(face_filename or filepath))
        file_url = f"https://cloud.appwrite.io/v1/storage/buckets/6602a873de0e9ff815f0/files/{result['$id']}/view?project=6602a79975c04c55b0a3"

        # Assemble the data
        extracted_data = {
            "passport_number": mrz_dict.get("number"),
            "country": corrected_country,
            "surname": surname,
            "names": names,
            "nationality": mrz_dict.get("nationality"),
            "date_of_birth": dob,
            "sex": mrz_dict.get("sex"),
            "expiration_date": exp_date,
            "personal_number": personal_number,
            "face_image_url": file_url
        }

        return jsonify(extracted_data)
    except Exception as e:
        return jsonify({"error": str(e)}), 500


if __name__ == "__main__":
    app.run(port=5000, debug=True)
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
UPLOAD_FOLDER = os.path.join("/tmp", "uploads")
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
        
        # Clean and format the names
        names = mrz_dict.get("names", "").replace("<", " ").strip()
        # Remove any extra spaces between words
        names = " ".join(filter(None, names.split()))
        
        surname = mrz_dict.get("surname", "").replace("<", "").strip()
        
        # Handle date parsing with proper century detection
        def parse_mrz_date(date_str):
            try:
                year = int(date_str[:2])
                month = int(date_str[2:4])
                day = int(date_str[4:6])
                
                # Determine century (19xx or 20xx)
                if year > 30:  # Assuming dates before 1930 are unlikely
                    year += 1900
                else:
                    year += 2000
                    
                return f"{year}-{month:02d}-{day:02d}"
            except:
                return None

        dob_str = mrz_dict.get("date_of_birth", "")
        exp_str = mrz_dict.get("expiration_date", "")
        
        dob = parse_mrz_date(dob_str) if dob_str else None
        exp_date = parse_mrz_date(exp_str) if exp_str else None

        # Process the face image and store it
        app.logger.info(f"Calling extract_face with filepath {filepath}")
        face_filename = extract_face(filepath)
        app.logger.info(f"Face filename: {face_filename}")
        
        result = storage.create_file('6602a873de0e9ff815f0', ID.unique(), InputFile.from_path(face_filename or filepath))
        file_url = f"https://cloud.appwrite.io/v1/storage/buckets/6602a873de0e9ff815f0/files/{result['$id']}/view?project=6602a79975c04c55b0a3"

        # Assemble the data
        extracted_data = {
            "passport_number": mrz_dict.get("number", "").strip(),
            "country": mrz_dict.get("country", "").strip(),
            "surname": surname,
            "names": names,
            "nationality": mrz_dict.get("nationality", "").strip(),
            "date_of_birth": dob,
            "sex": mrz_dict.get("sex", "").strip(),
            "expiration_date": exp_date,
            "personal_number": mrz_dict.get("personal_number", "").replace("<", "").strip(),
            "face_image_url": file_url
        }

        return jsonify(extracted_data)
    except Exception as e:
        app.logger.error(f"Error processing passport: {str(e)}")
        return jsonify({"error": str(e)}), 500


@app.route("/api/process_multiple_passports", methods=["POST"])
def process_multiple_passports():
    try:
        # Check if any files were sent
        if "files" not in request.files:
            return jsonify({"error": "No files part"}), 400
        
        files = request.files.getlist("files")
        
        # Check if any files were selected
        if not files or files[0].filename == "":
            return jsonify({"error": "No selected files"}), 400
            
        # Limit the number of files
        if len(files) > 15:
            return jsonify({"error": "Maximum 15 files allowed"}), 400
            
        results = []
        
        for file in files:
            try:
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
                
                if mrz_data is None:
                    results.append({
                        "filename": filename,
                        "error": "Could not read MRZ data from image"
                    })
                    continue
                    
                mrz_dict = mrz_data.to_dict()
                
                # Clean and format the names
                names = mrz_dict.get("names", "").replace("<", " ").strip()
                names = " ".join(filter(None, names.split()))
                surname = mrz_dict.get("surname", "").replace("<", "").strip()
                
                # Handle date parsing with proper century detection
                def parse_mrz_date(date_str):
                    try:
                        year = int(date_str[:2])
                        month = int(date_str[2:4])
                        day = int(date_str[4:6])
                        
                        # Determine century (19xx or 20xx)
                        if year > 30:  # Assuming dates before 1930 are unlikely
                            year += 1900
                        else:
                            year += 2000
                            
                        return f"{year}-{month:02d}-{day:02d}"
                    except:
                        return None

                dob_str = mrz_dict.get("date_of_birth", "")
                exp_str = mrz_dict.get("expiration_date", "")
                
                dob = parse_mrz_date(dob_str) if dob_str else None
                exp_date = parse_mrz_date(exp_str) if exp_str else None

                # Process the face image and store it
                face_filename = extract_face(filepath)
                
                result = storage.create_file('6602a873de0e9ff815f0', ID.unique(), InputFile.from_path(face_filename or filepath))
                file_url = f"https://cloud.appwrite.io/v1/storage/buckets/6602a873de0e9ff815f0/files/{result['$id']}/view?project=6602a79975c04c55b0a3"

                # Assemble the data
                extracted_data = {
                    "filename": filename,
                    "passport_number": mrz_dict.get("number", "").strip(),
                    "country": mrz_dict.get("country", "").strip(),
                    "surname": surname,
                    "names": names,
                    "nationality": mrz_dict.get("nationality", "").strip(),
                    "date_of_birth": dob,
                    "sex": mrz_dict.get("sex", "").strip(),
                    "expiration_date": exp_date,
                    "personal_number": mrz_dict.get("personal_number", "").replace("<", "").strip(),
                    "face_image_url": file_url
                }
                
                results.append(extracted_data)
                
            except Exception as e:
                results.append({
                    "filename": filename,
                    "error": str(e)
                })
                continue
                
        return jsonify({
            "total_processed": len(files),
            "successful": len([r for r in results if "error" not in r]),
            "failed": len([r for r in results if "error" in r]),
            "results": results
        })
        
    except Exception as e:
        app.logger.error(f"Error processing multiple passports: {str(e)}")
        return jsonify({"error": str(e)}), 500


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)
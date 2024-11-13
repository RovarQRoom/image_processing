# Use an official Python runtime as a parent image
FROM python:3.11-slim

# Set the working directory in the container
WORKDIR /app

# Install system dependencies required for OpenCV and dlib (used by PassportEye)
RUN apt-get update --fix-missing
RUN apt-get install -y --no-install-recommends 
RUN apt-get install -y --no-install-recommends cmake
RUN apt-get install -y --no-install-recommends --fix-missing build-essential
RUN apt-get install -y --no-install-recommends libopenblas-dev
RUN apt-get install -y --no-install-recommends liblapack-dev
RUN apt-get install -y --no-install-recommends libjpeg-dev 
RUN apt-get install -y --no-install-recommends libpng-dev 
RUN apt-get install -y --no-install-recommends libtiff-dev 
RUN apt-get install -y --no-install-recommends libavcodec-dev 
RUN apt-get install -y --no-install-recommends libavformat-dev 
RUN apt-get install -y --no-install-recommends libswscale-dev 
RUN apt-get install -y --no-install-recommends libv4l-dev 
RUN apt-get install -y --no-install-recommends libxvidcore-dev 
RUN apt-get install -y --no-install-recommends libx264-dev 
RUN apt-get install -y --no-install-recommends libpng-tools 
RUN apt-get install -y --no-install-recommends libtiff5-dev 
RUN apt-get install -y --no-install-recommends gfortran 
RUN apt-get install -y --no-install-recommends openssl 
RUN apt-get install -y --no-install-recommends libssl-dev 
RUN apt-get install -y --no-install-recommends libffi-dev
RUN apt-get install -y --no-install-recommends tesseract-ocr
RUN apt-get install -y --no-install-recommends tesseract-ocr-eng
RUN apt-get install -y --no-install-recommends libtesseract-dev
RUN apt-get clean && \
    rm -rf /var/lib/apt/lists/*


# Upgrade pip, setuptools, and wheel
RUN pip install --upgrade pip setuptools wheel

# Copy the current directory contents into the container at /app
COPY . /app

# Install any needed packages specified in a requirements.txt
# Ensure you have Flask, Flask-CORS, opencv-python-headless, passporteye, appwrite in your requirements.txt
RUN pip install -r requirements.txt

# Make port 5000 available to the world outside this container
EXPOSE 5000

# Define environment variable
ENV UPLOAD_FOLDER /app/static/uploads
ENV HAARCASCADE_PATH /app/haarcascade_frontalface_default.xml

# Create the directory for uploads
RUN mkdir -p ${UPLOAD_FOLDER}

# Run app.py when the container launches
CMD ["flask", "run", "--host","0.0.0.0"]

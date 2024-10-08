import os
import logging
import shutil
from flask import Flask, jsonify, request
from flask_cors import CORS
from werkzeug.utils import secure_filename
from utils import query_rag
from rag_pipeline import RAGPipeline

app = Flask(__name__)
logging.basicConfig(level=logging.INFO)

CORS(
    app,
    resources={
        r"/*": {"origins": ["*", "http://localhost:5173", "http://127.0.0.1:5000"]}
    },
)

UPLOAD_FOLDER = "./uploads"
app.config["UPLOAD_FOLDER"] = UPLOAD_FOLDER

jd_path = os.path.join(UPLOAD_FOLDER, "jd")
pdfs_path = os.path.join(UPLOAD_FOLDER, "pdfs")
os.makedirs(jd_path, exist_ok=True)
os.makedirs(pdfs_path, exist_ok=True)

ALLOWED_EXTENSIONS = {"pdf"}


def allowed_file(filename):
    return "." in filename and filename.rsplit(".", 1)[1].lower() in ALLOWED_EXTENSIONS


@app.route("/api/upload", methods=["POST"])
def upload_resumes():
    """
    Uploads job description and resumes as part of a multi-part form-data request.
    """
    if "resumes" not in request.files or "job_description" not in request.form:
        return jsonify({"error": "Resumes and job description are required."}), 400

    job_description = request.form["job_description"]
    uploaded_files = request.files.getlist("resumes")

    if not uploaded_files:
        return jsonify({"error": "No resumes uploaded."}), 400

    saved_files = []
    for file in uploaded_files:
        if file and allowed_file(file.filename):
            filename = secure_filename(file.filename)
            file.save(os.path.join(pdfs_path, filename))
            saved_files.append(filename)

    with open(os.path.join(jd_path, "job_description.txt"), "w") as jd_file:
        jd_file.write(job_description)

    rag_pipeline = RAGPipeline(
        document_type="pdf",
        data_path=r"uploads\pdfs",
        database_path="chroma",
    )
    rag_pipeline.run_pipeline()

    return jsonify(
        {
            "message": "Resumes and job description received successfully.",
            "saved_files": saved_files,
            "job_description": job_description,
        }
    ), 200


@app.route("/api/reset", methods=["POST"])
def reset_uploads():
    """
    Resets the uploaded files by deleting them from the server.
    """
    try:
        for folder in [jd_path, pdfs_path]:
            for filename in os.listdir(folder):
                file_path = os.path.join(folder, filename)
                if os.path.isfile(file_path):
                    os.remove(file_path)

        if os.path.exists("chroma"):
            shutil.rmtree("chroma")

        return jsonify({"message": "Uploads reset successfully."}), 200

    except Exception as e:
        logging.error(f"Error resetting uploads: {e}")
        return jsonify({"error": "Failed to reset uploads."}), 500


@app.route("/api/predict", methods=["POST"])
def predict():
    """
    Endpoint to query the RAG pipeline for answers based on job descriptions and resumes.
    """
    try:
        data = request.json
        if not data or "job_description" not in data or "question" not in data:
            logging.error("Invalid input: Missing job_description or question field.")
            return jsonify({"error": "Job description and question are required."}), 400

        question = data["question"]

        with open(r"uploads\jd\job_description.txt", "r") as jd_file:
            job_description = jd_file.read()
        print(job_description)
        response = query_rag(job_description=job_description, question=question)

        return jsonify({"answer": response}), 200

    except Exception as e:
        logging.error(f"Error in /api/predict: {e}")
        return jsonify(
            {"error": "An error occurred while processing your request."}
        ), 500


if __name__ == "__main__":
    app.run(debug=True)

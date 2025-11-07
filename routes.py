from flask import Blueprint, render_template, request, send_from_directory, jsonify, current_app
import os
import pandas as pd
from utils.ai_pdf_generator import (
    generate_two_pdfs_hybrid,
    get_ai_resources,
)
from utils.sanitize import sanitize_filename
from dotenv import load_dotenv

load_dotenv()

routes = Blueprint("routes", __name__)

# 📂 Çıktı klasörü
UPLOAD_FOLDER = "outputs"
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

# 🌐 Render ortamına uyumlu URL ve port
SERVER_IP = os.getenv("SERVER_IP", "0.0.0.0")
PORT = os.getenv("PORT", "10000")  # Render genelde kendi portunu atar


CSV_URL = "https://drive.google.com/uc?id=1EU6wifU-cdpeSHjKdl2jvxzLD26Lq-bs&export=download"

_cached_df = None

def get_data():
    global _cached_df
    if _cached_df is None:
        print("Veri Google Drive'dan yükleniyor...")
        _cached_df = pd.read_csv(
            CSV_URL,
            low_memory=False
        )
        print("Veri başarıyla yüklendi.")
    return _cached_df



# --- Sayfa rotaları ---
@routes.route("/")
def index():
    return render_template("pages/index.html")

@routes.route("/about")
def about():
    return render_template("pages/about.html")

@routes.route("/faq")
def faq():
    return render_template("pages/faq.html")

@routes.route("/chatbot")
def chatbot():
    return render_template("pages/chatbot.html")


# --- PDF Üretimi ---
@routes.route("/generate", methods=["POST"])
def generate():
    if request.is_json:
        user_input = request.json.get("topic", "").strip()
    else:
        user_input = request.form.get("topic", "").strip()

    if not user_input:
        return jsonify({"error": "Konu girilmedi."}), 400

    safe_topic = sanitize_filename(user_input)
    df = get_data()

    try:
        generate_two_pdfs_hybrid(user_input, df, output_dir=UPLOAD_FOLDER)
    except Exception as e:
        return jsonify({"error": f"PDF oluşturma hatası: {str(e)}"}), 500

    resource_pdf = f"{safe_topic}_resources.pdf"
    timeline_pdf = f"{safe_topic}_roadmap.pdf"

    base_url = request.host_url.rstrip("/")
    if request.is_json:
        return jsonify({
            "resource_url": f"{base_url}/download/{resource_pdf}",
            "roadmap_url": f"{base_url}/download/{timeline_pdf}"
        })
    else:
        return render_template(
            "pages/results.html",
            resource_pdf=resource_pdf,
            timeline_pdf=timeline_pdf
        )


# --- Dosya indirme ---
@routes.route("/download/<filename>")
def download_file(filename):
    file_path = os.path.join(UPLOAD_FOLDER, filename)
    if not os.path.exists(file_path):
        return jsonify({"error": "Dosya bulunamadı."}), 404
    return send_from_directory(UPLOAD_FOLDER, filename, as_attachment=True)


# --- Kaynak önerileri ---
@routes.route("/resources", methods=["GET", "POST"])
def resources():
    if request.method == "POST":
        if request.is_json:
            user_input = request.json.get("topic", "").strip()
        else:
            user_input = request.form.get("topic", "").strip()

        if not user_input:
            return jsonify({"error": "Konu boş olamaz."}), 400

        raw_response = get_ai_resources(user_input)

        if request.is_json:
            return jsonify(raw_response)

        else:
            return render_template(
                "pages/resources.html",
                topic=user_input,
                resources=raw_response,
                error=None
            )

    # GET isteği
    return render_template("pages/resources.html", resources=None, error=None)

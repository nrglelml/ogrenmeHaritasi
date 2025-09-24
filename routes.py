from flask import Blueprint, render_template, request, send_from_directory, jsonify
import os
import pandas as pd
from utils.ai_pdf_generator import (
    generate_two_pdfs_hybrid,
    get_ai_resources,
    parse_ai_resources
)
from utils.sanitize import sanitize_filename
from dotenv import load_dotenv


load_dotenv()


SERVER_IP = os.getenv("SERVER_IP", "127.0.0.1")
PORT = os.getenv("PORT", "5000")

routes = Blueprint('routes', __name__)
UPLOAD_FOLDER = "outputs"

df_with_skills = pd.read_csv("data/df_with_skills.csv", low_memory=False)

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

@routes.route("/generate", methods=["POST"])
def generate():
    if request.is_json:
        user_input = request.json.get("topic")
    else:
        user_input = request.form.get("topic")

    if not user_input:
        return jsonify({"error": "Konu girilmedi."}), 400

    safe_topic = sanitize_filename(user_input)
    generate_two_pdfs_hybrid(user_input, df_with_skills, output_dir=UPLOAD_FOLDER)

    resource_pdf = f"{safe_topic}_resources.pdf"
    timeline_pdf = f"{safe_topic}_roadmap.pdf"

    if request.is_json:
        return jsonify({
            "resource_url": f"http://{SERVER_IP}:{PORT}/download/{resource_pdf}",
            "roadmap_url": f"http://{SERVER_IP}:{PORT}/download/{timeline_pdf}"
        })
    else:
        return render_template(
            "pages/results.html",
            resource_pdf=resource_pdf,
            timeline_pdf=timeline_pdf
        )

@routes.route("/download/<filename>")
def download_file(filename):
    return send_from_directory(UPLOAD_FOLDER, filename, as_attachment=True)



@routes.route("/resources", methods=["GET", "POST"])
def resources():
    if request.method == "POST":
        # POST isteği için JSON verisi bekleniyorsa request.get_json() kullanın
        data = request.get_json()
        if not data or 'topic' not in data:
            return jsonify({"error": "Lütfen bir konu giriniz."}), 400

        user_input = data.get("topic").strip()
        if not user_input:
            return jsonify({"error": "Lütfen bir konu giriniz."}), 400

        raw_response = get_ai_resources(user_input)
        resources_dict = parse_ai_resources(raw_response)

        # Bu satır, mobil uygulamanızın beklediği JSON yanıtını döndürür
        return jsonify(resources_dict)

    return render_template("pages/resources.html", resources=None, error=None)

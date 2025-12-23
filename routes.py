from flask import Blueprint, render_template, request, send_from_directory, jsonify, current_app
import os
import pandas as pd
from utils.ai_pdf_generator import (
    generate_two_pdfs_hybrid,
    get_ai_resources,
)
from utils.sanitize import sanitize_filename
from dotenv import load_dotenv
import io
import requests
import re

load_dotenv()

routes = Blueprint("routes", __name__)

# Çıktı klasörü
UPLOAD_FOLDER = "outputs"
os.makedirs(UPLOAD_FOLDER, exist_ok=True)


SERVER_IP = os.getenv("SERVER_IP", "0.0.0.0")
PORT = os.getenv("PORT", "10000")

FILE_ID = "1EU6wifU-cdpeSHjKdl2jvxzLD26Lq-bs"
BASE_URL = "https://drive.google.com/uc?export=download"

_cached_df = None


def get_data():
    global _cached_df

    if _cached_df is None:
        print("--------------------------------------------------")
        print("BAĞLANTI BAŞLATILIYOR (HTML PARSING MODU)...")

        try:
            session = requests.Session()
            response = session.get(BASE_URL, params={'id': FILE_ID}, stream=True)


            if "text/html" in response.headers.get('Content-Type', ''):
                print("⚠️ Virüs tarama uyarısı algılandı. Form verileri çözümleniyor...")


                html_content = ""
                for chunk in response.iter_content(chunk_size=1024):
                    if chunk:
                        html_content += chunk.decode('utf-8', errors='ignore')
                    if len(html_content) > 10000:  # İlk 10kb yeterli
                        break


                action_match = re.search(r'action="([^"]+)"', html_content)
                if action_match:
                    target_url = action_match.group(1).replace("&amp;", "&")
                    print(f"Hedef URL bulundu: {target_url[:30]}...")


                    confirm_match = re.search(r'name="confirm" value="([^"]+)"', html_content)
                    confirm_val = confirm_match.group(1) if confirm_match else "t"


                    uuid_match = re.search(r'name="uuid" value="([^"]+)"', html_content)
                    uuid_val = uuid_match.group(1) if uuid_match else None


                    params = {'id': FILE_ID, 'confirm': confirm_val}
                    if uuid_val:
                        params['uuid'] = uuid_val
                        print(f"UUID Anahtarı: {uuid_val}")


                    response = session.get(target_url, params=params, stream=True)
                else:
                    print("HATA: HTML içindeki indirme linki bulunamadı.")

            # 2. İNDİRME VE PANDAS (RAM ÜZERİNDEN)
            if "text/csv" in response.headers.get('Content-Type', '') or response.status_code == 200:
                print("✅ Veri akışı yakalandı. Pandas ile okunuyor (Diske yazılmıyor)...")

                req_cols = ["skills", "problem_id", "correct"]


                response.raw.decode_content = True

                _cached_df = pd.read_csv(
                    response.raw,
                    usecols=req_cols,
                    dtype={'skills': str, 'problem_id': str},
                    low_memory=True
                )

                print(f"BAŞARILI! Veri belleğe yüklendi. Satır: {len(_cached_df)}")
            else:
                print("KRİTİK HATA: Google Drive hala dosya vermedi. Yanıt tipi:", response.headers.get('Content-Type'))

                _cached_df = pd.DataFrame()

        except Exception as e:
            print(f"HATA OLUŞTU: {e}")
            _cached_df = pd.DataFrame()

        print("--------------------------------------------------")

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
        duration = request.json.get("duration", "").strip()
    else:
        user_input = request.form.get("topic", "").strip()
        duration = request.form.get("duration", "").strip()

    if not duration:
        duration = None

    if not user_input:
        return jsonify({"error": "Konu girilmedi."}), 400

    safe_topic = sanitize_filename(user_input)
    df = get_data()

    try:

        generate_two_pdfs_hybrid(user_input, df, output_dir=UPLOAD_FOLDER, duration=duration)
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
            timeline_pdf=timeline_pdf,
            topic=user_input  # Başlıkta göstermek için
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
            if request.is_json:
                return jsonify({"error": "Konu boş olamaz."}), 400
            else:
                return render_template("pages/resources.html", error="Lütfen bir konu girin.")


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


    return render_template("pages/resources.html", resources=None, error=None)
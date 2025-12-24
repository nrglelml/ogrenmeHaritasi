from flask import Blueprint, render_template, request, send_from_directory, jsonify
import os
import pandas as pd
from openai import OpenAI
from utils.ai_pdf_generator import generate_two_pdfs_hybrid, get_ai_resources
from utils.sanitize import sanitize_filename
from dotenv import load_dotenv
import requests
import re
import gc

load_dotenv()

routes = Blueprint("routes", __name__)

# Çıktı klasörü
UPLOAD_FOLDER = "outputs"
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

FILE_ID = "1EU6wifU-cdpeSHjKdl2jvxzLD26Lq-bs"
DRIVE_URL = "https://drive.google.com/uc?export=download"

client = OpenAI(
    base_url="https://api.groq.com/openai/v1",
    api_key=os.getenv("GROQ_API_KEY")
)
AI_MODEL = "llama-3.3-70b-versatile"


def get_english_term(text):
    """ 'Python Programlama' -> 'Python' çevirisi yapar """
    try:
        response = client.chat.completions.create(
            model=AI_MODEL,
            messages=[{"role": "system", "content": "Translate to English technical term. Only output the word."},
                      {"role": "user", "content": text}],
            temperature=0.1
        )
        return response.choices[0].message.content.strip().replace('"', '').replace('.', '')
    except:
        return text


def smart_search_stream(topic):
    """
    ULTRA-LITE HİBRİT ARAMA:
    Render Free Tier (512MB RAM) için özel optimize edilmiştir.
    Asla 1.1GB veriyi yüklemez, küçük parçalarla 'tadım testi' yapar.
    """
    print(f" [WEB] Veri Seti Taranıyor (Ultra-Lite Mod): '{topic}'...")
    eng_term = get_english_term(topic)
    search_terms = [topic, eng_term]

    try:
        session = requests.Session()
        response = session.get(DRIVE_URL, params={'id': FILE_ID}, stream=True)


        if "text/html" in response.headers.get('Content-Type', ''):
            html = ""
            for chunk in response.iter_content(chunk_size=1024):
                if chunk: html += chunk.decode('utf-8', errors='ignore')
                if len(html) > 10000: break

            confirm_match = re.search(r'name="confirm" value="([^"]+)"', html)
            confirm = confirm_match.group(1) if confirm_match else "t"

            uuid_match = re.search(r'name="uuid" value="([^"]+)"', html)
            params = {'id': FILE_ID, 'confirm': confirm}
            if uuid_match:
                params['uuid'] = uuid_match.group(1)

            response = session.get("https://drive.usercontent.google.com/download", params=params, stream=True)


        response.raw.decode_content = True


        chunk_iterator = pd.read_csv(
            response.raw,
            chunksize=2000,
            usecols=["skills", "problem_id", "correct"],
            dtype=str,
            low_memory=True
        )

        found_data = []
        total_found = 0
        total_scanned = 0
        MAX_SCAN_LIMIT = 100000

        for chunk in chunk_iterator:
            pattern = '|'.join([re.escape(t) for t in search_terms if t])
            matches = chunk[chunk['skills'].str.contains(pattern, case=False, na=False)]

            total_scanned += len(chunk)

            if not matches.empty:
                found_data.append(matches)
                total_found += len(matches)


                if total_found > 100:
                    print(" Yeterli veri örneği bulundu, arama tamamlandı.")
                    break


            if total_scanned >= MAX_SCAN_LIMIT:
                print(f"    {MAX_SCAN_LIMIT} satır tarandı, veri bulunamadı. RAM koruması için durduruluyor.")
                break


            gc.collect()

        if found_data:
            return pd.concat(found_data)

        return pd.DataFrame()

    except Exception as e:
        print(f" Arama Sırasında RAM/Bağlantı Hatası (AI Devreye Girecek): {e}")

        return pd.DataFrame()


# --- Sayfa Rotaları ---
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
    # 1. İstek Tipi Kontrolü
    if request.is_json:
        data = request.json
        user_input = data.get("topic", "").strip()
        duration = data.get("duration", "").strip()
        source = data.get("source", "web")
    else:
        user_input = request.form.get("topic", "").strip()
        duration = request.form.get("duration", "").strip()
        source = request.form.get("source", "web")

    if not user_input:
        return jsonify({"error": "Konu girilmedi."}), 400


    df_filtered = pd.DataFrame()

    if source == 'mobile':
        print(f"🚀 [MOBİL] Hız Modu: '{user_input}' için veri taraması atlanıyor.")
    else:
        # Web isteği ise akıllı arama yap
        # Hata yakalama bloğu ekleyelim ki sunucu 500 vermesin
        try:
            df_filtered = smart_search_stream(user_input)
        except Exception as e:
            print(f"Kritik Arama Hatası (Atlanıyor): {e}")
            df_filtered = pd.DataFrame()


    try:
        safe_topic = generate_two_pdfs_hybrid(user_input, df_filtered, output_dir=UPLOAD_FOLDER, duration=duration)
    except Exception as e:
        print(f"PDF Oluşturma Hatası: {e}")
        return jsonify({"error": "PDF oluşturulamadı, lütfen tekrar deneyin."}), 500


    base_url = request.host_url.rstrip("/")

    if request.is_json:
        return jsonify({
            "resource_url": f"{base_url}/download/{safe_topic}_resources.pdf",
            "roadmap_url": f"{base_url}/download/{safe_topic}_roadmap.pdf"
        })
    else:
        return render_template(
            "pages/results.html",
            topic=user_input,
            resource_pdf=f"{safe_topic}_resources.pdf",
            timeline_pdf=f"{safe_topic}_roadmap.pdf"
        )


# --- İndirme Rotası ---
@routes.route("/download/<filename>")
def download_file(filename):
    file_path = os.path.join(UPLOAD_FOLDER, filename)
    if not os.path.exists(file_path):
        return jsonify({"error": "Dosya bulunamadı."}), 404
    return send_from_directory(UPLOAD_FOLDER, filename, as_attachment=True)


# --- Kaynak Önerileri ---
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
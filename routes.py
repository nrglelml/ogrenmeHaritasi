from flask import Blueprint, render_template, request, send_from_directory, jsonify, current_app
import os
import pandas as pd
from openai import OpenAI

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


"""def get_data():
    global _cached_df

    if _cached_df is None:
        print("--------------------------------------------------")
        print("BAĞLANTI BAŞLATILIYOR (HTML PARSING MODU)...")

        try:
            session = requests.Session()
            response = session.get(BASE_URL, params={'id': FILE_ID}, stream=True)


            if "text/html" in response.headers.get('Content-Type', ''):
                print(" Virüs tarama uyarısı algılandı. Form verileri çözümleniyor...")


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
                print(" Veri akışı yakalandı. Pandas ile okunuyor (Diske yazılmıyor)...")

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

    return _cached_df """

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
    HİBRİT MOTOR: RAM dostu arama.
    1.1 GB veriyi yüklemez, sadece ilgili kısmı bulana kadar tarar.
    """
    FILE_ID = "1EU6wifU-cdpeSHjKdl2jvxzLD26Lq-bs"
    URL = "https://drive.google.com/uc?export=download"

    # 1. Dil Çevirisi (Veri seti İngilizce)
    eng_term = get_english_term(topic)
    search_terms = [topic, eng_term]
    print(f" Hibrit Arama Başladı: {search_terms}")

    try:
        session = requests.Session()
        response = session.get(URL, params={'id': FILE_ID}, stream=True)

        # --- Google Drive Virüs Engelini Aşma ---
        if "text/html" in response.headers.get('Content-Type', ''):
            html = ""
            for chunk in response.iter_content(chunk_size=1024):
                if chunk: html += chunk.decode('utf-8', errors='ignore')
                if len(html) > 10000: break

            confirm_match = re.search(r'name="confirm" value="([^"]+)"', html)
            confirm = confirm_match.group(1) if confirm_match else "t"

            # uuid parametresini de yakalayalım (Loglarda görmüştük)
            uuid_match = re.search(r'name="uuid" value="([^"]+)"', html)
            params = {'id': FILE_ID, 'confirm': confirm}
            if uuid_match:
                params['uuid'] = uuid_match.group(1)

            response = session.get("https://drive.usercontent.google.com/download", params=params, stream=True)

        # --- RAM DOSTU OKUMA (Chunking) ---
        response.raw.decode_content = True
        chunk_iterator = pd.read_csv(
            response.raw,
            chunksize=10000,  # Her seferde sadece 10bin satır (RAM şişmez)
            usecols=["skills", "problem_id", "correct"],  # Sadece gereken sütunlar
            dtype=str,  # Hız için string oku
            low_memory=True
        )

        found_data = []

        for chunk in chunk_iterator:
            # Regex ile arama (Hızlı)
            pattern = '|'.join([re.escape(t) for t in search_terms if t])
            matches = chunk[chunk['skills'].str.contains(pattern, case=False, na=False)]

            if not matches.empty:
                found_data.append(matches)
                print(f"   -> {len(matches)} veri bulundu!")

                .
                if sum([len(d) for d in found_data]) > 100:
                    print("   ⚡ Yeterli örneklem alındı, arama sonlandırılıyor.")
                    break

        if found_data:
            return pd.concat(found_data)

        return pd.DataFrame()

    except Exception as e:
        print(f" Veri Okuma Hatası (AI Devreye Girecek): {e}")
        return pd.DataFrame()

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
        data = request.json
        user_input = data.get("topic", "").strip()
        duration = data.get("duration", "").strip()
    else:
        user_input = request.form.get("topic", "").strip()
        duration = request.form.get("duration", "").strip()

    if not user_input:
        return jsonify({"error": "Konu girilmedi."}), 400


    df_filtered = smart_search_stream(user_input)


    try:
        safe_topic = generate_two_pdfs_hybrid(user_input, df_filtered, output_dir=UPLOAD_FOLDER, duration=duration)
    except Exception as e:
        return jsonify({"error": str(e)}), 500

    # ... (URL dönüş kodları aynı) ...
    base_url = request.host_url.rstrip("/")
    if request.is_json:
        return jsonify({
            "resource_url": f"{base_url}/download/{safe_topic}_resources.pdf",
            "roadmap_url": f"{base_url}/download/{safe_topic}_roadmap.pdf"
        })
    else:
        return render_template("pages/results.html", topic=user_input, resource_pdf=f"{safe_topic}_resources.pdf",
                               timeline_pdf=f"{safe_topic}_roadmap.pdf")



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
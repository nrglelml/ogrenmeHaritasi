from flask import Blueprint, render_template, request, send_from_directory, jsonify
import os
import pandas as pd
from openai import OpenAI
from utils.ai_pdf_generator import generate_two_pdfs_hybrid, get_ai_resources
from dotenv import load_dotenv
import requests
import re
import csv
import io
import time

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

USER_TOPIC_MAP = {
    "matematik": ["8.NS.A.2-1", "7.EE.B.4a-1", "6.NS.B.3-3"],
    "sayılar": ["8.NS.A.2-1", "6.NS.B.3-3", "8.NS.A.2-2"],
    "oran orantı": ["7.RP.A.1", "7.RP.A.2", "7.RP.A.3"], # Genişletildi
    "oran": ["7.RP.A.1"],
    "orantı": ["7.RP.A.2"],
    "denklem çözme": ["6.EE.B.7", "7.EE.B.4a-1", "8.EE.C.7"],
    "denklemler": ["6.EE.B.7", "8.EE.C.7"],
    "fonksiyonlar": ["8.F.B.5", "8.F.A.1"],
    "veri": ["8.SP.A.1"],
    "geometri": ["8.G.A.3-1", "8.G.A.1"],
    "ifadeler": ["7.EE.A.2"],
    "üslü sayılar": ["8.EE.A.1"],
    "kareköklü sayılar": ["8.EE.A.2"],
    "olasılık": ["7.SP.C.5"]
}
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
    HİBRİT ARAMA MOTORU (Harita Destekli):
    1. Önce USER_TOPIC_MAP'e bakar (Nokta Atışı).
    2. Bulamazsa İngilizce çeviri ile arar.
    3. Maksimum 8 saniye çalışır (Timeout Koruması).
    """
    print(f"[WEB] Veri Seti Taranıyor: '{topic}'...")

    topic_lower = topic.lower().strip()
    search_terms = []

    # 1. HARİTA KONTROLÜ (Öncelikli)
    if topic_lower in USER_TOPIC_MAP:
        search_terms = USER_TOPIC_MAP[topic_lower]
        print(f" Harita Eşleşmesi: {topic} -> {search_terms}")
    else:
        # 2. ÇEVİRİ KONTROLÜ (Yedek)
        eng_term = get_english_term(topic)
        search_terms = [t.lower() for t in [topic, eng_term] if t]
        print(f"  Haritada yok, Kelime Bazlı Arama: {search_terms}")

    start_time = time.time()

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
        text_stream = io.TextIOWrapper(response.raw, encoding='utf-8')

        reader = csv.DictReader(text_stream)

        found_rows = []
        limit = 0

        for i, row in enumerate(reader):
            if time.time() - start_time > 8:
                print(" Süre doldu. Arama güvenli şekilde durduruluyor.")
                break


            row_content = (str(row.get('skills', '')) + " " + str(row.get('problem_id', ''))).lower()


            if any(term.lower() in row_content for term in search_terms):
                found_rows.append({
                    "skills": row.get('skills'),
                    "problem_id": row.get('problem_id'),
                    "correct": row.get('correct')
                })
                limit += 1

                if limit >= 50:
                    print(f"Yeterli veri ({limit} satır) bulundu.")
                    break

        if found_rows:
            return pd.DataFrame(found_rows)

        print("Veri bulunamadı (Harita/Çeviri eşleşmedi).")
        return pd.DataFrame()

    except Exception as e:
        print(f"Arama Hatası: {e}")
        return pd.DataFrame()


# --- Endpointler ---

@routes.route("/")
def index(): return render_template("pages/index.html")


@routes.route("/about")
def about(): return render_template("pages/about.html")


@routes.route("/faq")
def faq(): return render_template("pages/faq.html")


@routes.route("/chatbot")
def chatbot(): return render_template("pages/chatbot.html")


@routes.route("/generate", methods=["POST"])
def generate():
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
        print(f"[MOBİL] Hız Modu: '{user_input}' için veri taraması atlanıyor.")
    else:
        try:
            df_filtered = smart_search_stream(user_input)
        except Exception as e:
            print(f"Kritik Hata (Atlanıyor): {e}")
            df_filtered = pd.DataFrame()

    try:

        safe_topic = generate_two_pdfs_hybrid(user_input, df_filtered, output_dir=UPLOAD_FOLDER, duration=duration)
    except Exception as e:
        print(f"PDF ERROR: {e}")
        return jsonify({"error": "PDF oluşturulamadı, sistem yoğun."}), 500

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


@routes.route("/download/<filename>")
def download_file(filename):
    file_path = os.path.join(UPLOAD_FOLDER, filename)
    if not os.path.exists(file_path):
        return jsonify({"error": "Dosya bulunamadı."}), 404
    return send_from_directory(UPLOAD_FOLDER, filename, as_attachment=True)


@routes.route("/resources", methods=["GET", "POST"])
def resources():
    if request.method == "POST":
        user_input = request.json.get("topic", "").strip() if request.is_json else request.form.get("topic", "").strip()

        if not user_input:
            return jsonify({"error": "Konu boş olamaz."}) if request.is_json else render_template(
                "pages/resources.html", error="Lütfen bir konu girin.")

        raw_response = get_ai_resources(user_input)
        return jsonify(raw_response) if request.is_json else render_template("pages/resources.html", topic=user_input,
                                                                             resources=raw_response)

    return render_template("pages/resources.html", resources=None, error=None)
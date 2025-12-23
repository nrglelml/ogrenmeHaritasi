import os
import re
import json
import wikipedia
import requests
import matplotlib

matplotlib.use('Agg')
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
import numpy as np

from openai import OpenAI
from weasyprint import HTML
from weasyprint.text.fonts import FontConfiguration
from jinja2 import Template
from datetime import datetime
from .sanitize import sanitize_filename
from dotenv import load_dotenv
import textwrap

load_dotenv()


client = OpenAI(
    base_url="https://api.groq.com/openai/v1",
    api_key=os.getenv("GROQ_API_KEY")
)


AI_MODEL = "llama-3.3-70b-versatile"


def get_ai_learning_plan_and_steps(topic, problems=None, guidance=None, duration=None):
    # Context mesajını oluştur
    if problems and guidance:
        # Sorun ID'lerini stringe çevir
        problems_str = ", ".join(map(str, problems))
        guidance_str = " ".join(guidance)
        context_msg = f"ÖĞRENCİ ANALİZİ (Bunu plana yansıt): {guidance_str}. Öğrencinin en çok hata yaptığı soru ID'leri: {problems_str}."
    else:
        context_msg = "Öğrenci hakkında geçmiş veri yok, genel bir plan oluştur."

    # --- PROMPT AYARLARI ---
    # Duration varsa ona göre, yoksa seviye bazlı
    if duration:
        prompt_instruction = f"""
        Konu: {topic}
        Hedef Süre: {duration}
        {context_msg}

        GÖREV:
        1. HTML formatında, {duration} süresine uygun, haftalara/aylara bölünmüş detaylı bir eğitim planı tablosu oluştur.
        2. Ayrıca Timeline grafiği için 10-15 adım başlığı listele.
        """
    else:
        prompt_instruction = f"""
        Konu: {topic}
        Hedef: Sıfırdan Uzmanlığa (Süre sınırı yok)
        {context_msg}

        GÖREV:
        1. HTML formatında Başlangıç, Orta, İleri seviye detaylı bir eğitim müfredatı tablosu oluştur.
        2. Ayrıca Timeline grafiği için 8-12 adım başlığı listele.
        """

    full_prompt = f"""
    {prompt_instruction}

    Lütfen cevabını ŞU FORMATTA ver:
    ===PLAN===
    (Buraya HTML kodları)
    ===STEPS===
    Adım 1
    Adım 2
    ...
    """

    try:
        response = client.chat.completions.create(
            model=AI_MODEL,  # llama-3.3-70b-versatile
            messages=[
                {
                    "role": "system",
                    "content": (
                        "Sen Türkçe konuşan profesyonel bir eğitim asistanısın. "
                        "1. SADECE TÜRKÇE yaz. Asla Çince, Korece, Rusça karakter kullanma. "
                        "2. İngilizce terim kullanabilirsin (örneğin 'Linear Regression') ama açıklamalar Türkçe olmalı. "
                        "3. Cevabın eğitici, teşvik edici ve net olsun."
                    )
                },
                {"role": "user", "content": full_prompt}
            ],
            temperature=0.3,  # <-- BURASI KRİTİK: Halüsinasyonu önlemek için düşük tutuyoruz
            max_tokens=4000
        )

        content = response.choices[0].message.content

        # Basit temizlik (Eğer model yine de hata yaparsa diye)
        # Sadece Türkçe, İngilizce ve noktalama işaretlerini tutan bir filtre yazabiliriz ama
        # temperature=0.3 genellikle yeterlidir.

        plan_match = re.search(r"===PLAN===\s*(.*?)\s*===STEPS===", content, re.S)
        steps_match = re.search(r"===STEPS===\s*(.*)", content, re.S)

        plan_html = plan_match.group(1).strip() if plan_match else "<p>Plan oluşturulamadı.</p>"

        if steps_match:
            steps_text = steps_match.group(1).strip().split("\n")
            steps = [s.strip().lstrip("-").lstrip("0123456789.").strip() for s in steps_text if s.strip()]
        else:
            steps = []

        return plan_html, steps

    except Exception as e:
        print(f"AI Hatası: {e}")
        return f"<p>Beklenmedik bir hata oluştu: {e}</p>", []



def export_resources_pdf(topic, ai_plan_html, filename, duration=None):
    subtitle = f"Hedef Süre: {duration}" if duration else "Çalışma Tipi: Kendi Hızında (Detaylı Müfredat)"

    html_template = """
    <html>
    <head>
        <style>
            @page {
                margin: 2cm;
                @bottom-center {
                    content: "Sayfa " counter(page);
                }
            }
            body { 
                font-family: 'Helvetica', 'Arial', sans-serif; 
                padding: 0; 
                line-height: 1.6; 
                color: #333; 
                font-size: 12pt;
            }
            h1 { 
                color: #2c3e50; 
                border-bottom: 3px solid #3498db; 
                padding-bottom: 15px; 
                text-transform: uppercase;
                letter-spacing: 1px;
            }
            h2 { 
                color: #e67e22; 
                margin-top: 30px; 
                border-left: 5px solid #e67e22;
                padding-left: 10px;
            }
            h3 { color: #2980b9; margin-top: 20px; }
            p { margin-bottom: 15px; text-align: justify; }

            
            a {
                color: #2980b9;
                text-decoration: none;
                font-weight: bold;
                border-bottom: 1px dotted #2980b9;
            }

           
            table {
                width: 100%;
                border-collapse: collapse;
                margin: 20px 0;
                font-size: 11pt;
            }
            th, td {
                padding: 12px;
                border: 1px solid #ddd;
                text-align: left;
                vertical-align: top;
            }
            th {
                background-color: #f2f2f2;
                color: #2c3e50;
                font-weight: bold;
            }
            tr:nth-child(even) { background-color: #f9f9f9; }

            .meta { 
                background-color: #f8f9fa; 
                padding: 15px; 
                border-radius: 5px; 
                border-left: 4px solid #2ecc71;
                margin-bottom: 30px;
                font-size: 0.95em;
            }
            .highlight {
                background-color: #fff3cd;
                padding: 2px 5px;
                border-radius: 3px;
            }
        </style>
    </head>
    <body>
        <h1>Öğrenme Planı: {{ topic }}</h1>
        <div class="meta">
            <p><strong>Tarih:</strong> {{ date }}</p>
            <p><strong>{{ subtitle }}</strong></p>
        </div>

        <div class="content">
            {{ ai_plan | safe }}
        </div>

        <hr style="margin-top:50px; border:0; border-top:1px solid #eee;">
        <p style="text-align:center; font-size:10pt; color:#999;">
            Bu plan yapay zeka tarafından kişiye özel oluşturulmuştur.
        </p>
    </body>
    </html>
    """

    template = Template(html_template)
    rendered_html = template.render(
        topic=topic,
        subtitle=subtitle,
        date=datetime.today().strftime("%d.%m.%Y"),  # Tarih formatını güncelledim
        ai_plan=ai_plan_html
    )

    try:
        font_config = FontConfiguration()
        # WeasyPrint linkleri PDF'de otomatik olarak tıklanabilir yapar
        HTML(string=rendered_html).write_pdf(filename, font_config=font_config)
    except Exception as e:
        print(f"PDF oluşturma hatası: {e}")


def generate_two_pdfs_hybrid(user_input, df_with_skills, output_dir="outputs", duration=None):
    safe_topic = sanitize_filename(user_input)
    if not os.path.exists(output_dir):
        os.makedirs(output_dir)

    # --- 1. VERİ SETİ ANALİZİ (Jupyter Mantığına Göre) ---
    problems = None
    guidance = []

    # Görüntüden teyit ettiğimiz kesin sütun adı: 'skills'
    target_col = "skills"

    # Sütun var mı kontrol et
    if target_col in df_with_skills.columns:
        print(f"DEBUG: '{target_col}' sütunu bulundu, arama yapılıyor...")

        # Kullanıcı girdisini (örn: "Denklem") skills içinde ara
        # case=False: Büyük küçük harf duyarsız
        # na=False: Boş satırları atla
        mask = df_with_skills[target_col].astype(str).str.contains(user_input, case=False, na=False)
        df_topic = df_with_skills[mask]

        if not df_topic.empty:
            print(f"DEBUG: '{user_input}' için {len(df_topic)} kayıt bulundu.")

            # Başarı analizi (correct sütunu 0 veya 1)
            if "correct" in df_topic.columns and "problem_id" in df_topic.columns:
                # En zorlanılan 5 soru
                difficulty = df_topic.groupby("problem_id")["correct"].mean().reset_index()
                hardest = difficulty.sort_values(by="correct", ascending=True).head(5)
                problems = hardest["problem_id"].tolist()

                # Genel Ortalamaya Göre Tavsiye
                avg_score = df_topic["correct"].mean()
                print(f"DEBUG: Başarı Ortalaması: {avg_score}")

                if avg_score < 0.40:
                    guidance.append(
                        f"Veri Analizi: '{user_input}' konusunda başarı oranı düşük (%{int(avg_score * 100)}).")
                    guidance.append("Öneri: Konuyu en temelden almalı, basit tanımlara odaklanmalısın.")
                elif avg_score < 0.70:
                    guidance.append(
                        f"Veri Analizi: '{user_input}' konusunda orta seviyedesin (%{int(avg_score * 100)}).")
                    guidance.append("Öneri: Bol bol pratik yaparak işlem hatalarını gidermelisin.")
                else:
                    guidance.append(f"Veri Analizi: '{user_input}' konusunda gayet iyisin (%{int(avg_score * 100)}).")
                    guidance.append("Öneri: Kendini zorlamak için ileri düzey sorulara geçebilirsin.")
        else:
            print(f"DEBUG: '{user_input}' kelimesi veri setinde bulunamadı.")
    else:
        print(f"DEBUG: '{target_col}' sütunu DataFrame içinde yok! Mevcut sütunlar: {df_with_skills.columns}")

    # --- 2. AI İLE PLAN OLUŞTURMA (Garip Karakter Fix) ---
    ai_plan_html, steps = get_ai_learning_plan_and_steps(user_input, problems, guidance, duration)

    # PDF çıktılarını al
    export_resources_pdf(user_input, ai_plan_html, os.path.join(output_dir, f"{safe_topic}_resources.pdf"), duration)

    if steps:
        create_timeline_pdf(steps, os.path.join(output_dir, f"{safe_topic}_roadmap.pdf"))

    return safe_topic



# --- Timeline PDF ---
def create_timeline_pdf(steps, filename):
    try:
        num_steps = len(steps)


        fig_height = max(8, num_steps * 1.2)
        fig, ax = plt.subplots(figsize=(8, fig_height))
        ax.axis('off')

        y_positions = np.linspace(num_steps, 0, num_steps)

        x_positions = np.sin(np.linspace(0, num_steps, num_steps) * 1.5) * 2

        ax.plot(x_positions, y_positions, color='#bdc3c7', linewidth=4, linestyle='--', zorder=1, alpha=0.5)

        colors = ['#e74c3c', '#3498db', '#9b59b6', '#2ecc71', '#f1c40f', '#34495e']

        for i, (x, y, text) in enumerate(zip(x_positions, y_positions, steps)):

            color = colors[i % len(colors)]


            circle = mpatches.Circle((x, y), 0.3, color=color, zorder=3)
            ax.add_patch(circle)


            ax.text(x, y, str(i + 1), color='white', ha='center', va='center',
                    fontsize=10, fontweight='bold', zorder=4)


            text_offset_x = 0.6 if x >= 0 else -0.6
            ha_align = 'left' if x >= 0 else 'right'


            wrapped_text = "\n".join(textwrap.wrap(text, width=25))


            ax.text(x + text_offset_x, y, wrapped_text,
                    ha=ha_align, va='center', fontsize=11, color='#2c3e50', weight='bold',
                    bbox=dict(boxstyle="round,pad=0.4", fc="white", ec=color, lw=1.5, alpha=0.9),
                    zorder=5)


        ax.set_xlim(-5, 5)
        ax.set_ylim(-1, num_steps + 1)


        os.makedirs(os.path.dirname(filename), exist_ok=True)


        plt.savefig(filename, bbox_inches='tight', dpi=150)
        plt.close()

    except Exception as e:
        print(f"Timeline PDF hatası: {e}")






def get_wikipedia_summary(user_input, lang="en"):
    wikipedia.set_lang(lang)
    try:
        wikipedia.set_user_agent("LearningPlanProject/1.0")
    except AttributeError:
        pass

    try:
        summary = wikipedia.summary(user_input, sentences=3)
        page = wikipedia.page(user_input)
        return {"title": page.title, "summary": summary, "url": page.url}
    except (requests.exceptions.ConnectionError, requests.exceptions.ReadTimeout) as e:
        print(f"Wiki Bağlantı Hatası: {e}")
        return {"error": "Wikipedia'ya bağlanılamadı."}
    except wikipedia.exceptions.DisambiguationError as e:
        return {"error": f"Çok anlamlı: {e.options[:3]}"}
    except wikipedia.exceptions.PageError:
        return {"error": "Sayfa bulunamadı."}
    except Exception as e:
        return {"error": f"Hata: {str(e)}"}



def get_ai_resources(topic):
    results = {}

    # 1. Wikipedia
    wiki_data = get_wikipedia_summary(topic)
    if "error" not in wiki_data:
        results["Wikipedia"] = [wiki_data]


    prompt = f"""
    Sen uzman bir eğitim asistanısın. Kullanıcı "{topic}" konusunu öğrenmek istiyor.
    Bu konu için en iyi ve en güncel kaynakları öner.

    Kurallar:
    1. Cevabı SADECE geçerli bir JSON formatında ver.
    2. Linklerin (url) çalışacağından emin ol.
    3. Kategoriler: "Videos", "Articles", "Books", "Courses".
    4. Her kaynak objesi şunları içermeli: "title", "url", "desc" (Türkçe açıklama).

    İstenen JSON Yapısı:
    {{
        "Videos": [ {{"title": "...", "url": "...", "desc": "..."}} ],
        "Articles": [],
        "Books": [],
        "Courses": []
    }}
    """

    try:
        response = client.chat.completions.create(
            model=AI_MODEL,  # Llama-3 modeli
            response_format={"type": "json_object"},  # Groq da JSON modunu destekler
            messages=[
                {"role": "system", "content": "Sen JSON çıktısı veren bir asistansın."},
                {"role": "user", "content": prompt}
            ],
            temperature=0.3
        )

        content = response.choices[0].message.content
        ai_data = json.loads(content)
        results.update(ai_data)

    except Exception as e:
        print(f"Groq Hatası: {e}")
        # Hata durumunda kullanıcı boş sayfa görmesin diye manuel link ekleyebiliriz
        results["Hata"] = [
            {"title": "Bağlantı Sorunu", "url": "#", "desc": "Yapay zeka yanıt veremedi, lütfen tekrar deneyin."}]

    return results
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
import pandas as pd
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
    # KİŞİSELLEŞTİRME MESAJI OLUŞTURMA
    # Eğer veri setinden (routes.py'den) veri geldiyse burası dolar
    personalization_note = ""
    if problems and len(problems) > 0:
        personalization_note = (
            f"DİKKAT - ÖĞRENCİ VERİSİ MEVCUT: Bu öğrenci analizlerimize göre şu problem tiplerinde zorlanıyor: {', '.join(map(str, problems[:5]))}. "
            "Lütfen hazırlayacağın planda bu zayıf noktaları güçlendirecek pratiklere EKSTRA ağırlık ver. "
            "Öğrencinin başarı ortalaması analiz edildi ve seviyesi buna göre belirlendi."
        )
    else:
        personalization_note = "Öğrenci hakkında geçmiş veri yok. Bu yüzden konuyu sıfırdan alan, herkes için uygun en kapsamlı rehberi hazırla."

    # PROMPT AYARLARI (Detaylı PDF İçin)
    style_guide = """
    ÇIKTI FORMATI: Sadece HTML kodu.
    İÇERİK ZORUNLULUKLARI:
    1. 'Kaynak Önerileri' bölümü MUTLAKA olacak (<a> etiketli linkler).
    2. 'Günlük Rutin' bölümü MUTLAKA olacak.
    3. Tablolar CSS ile stillendirilmiş olacak.
    """

    if duration:
        scenario = f"Kullanıcı '{topic}' konusunu '{duration}' sürede bitirmek istiyor. {duration} süresine uygun haftalık/aylık detaylı tablo oluştur."
    else:
        scenario = f"Kullanıcı '{topic}' konusunu A'dan Z'ye öğrenmek istiyor. Seviye bazlı (Başlangıç-Orta-İleri) detaylı tablo oluştur."

    full_prompt = f"""
    Sen uzman bir eğitim koçusun. Konu: {topic}.

    {personalization_note}

    {scenario}

    {style_guide}

    Cevabın en altına ===STEPS=== ekleyip yol haritası adımlarını listele.
    """

    # ... (AI çağırma ve PDF oluşturma kısımları aynı, önceki cevaptaki zengin prompt yapısını kullanıyor) ...
    # Buradaki kodun kalanı önceki cevaptaki "generate_two_pdfs_hybrid" ile aynıdır.
    # ÖNEMLİ OLAN: personalization_note kısmını eklememizdi.

    # Kodu kısaltmak için tekrar yazmıyorum, önceki cevaptaki logic aynen geçerli.
    # Sadece full_prompt içine personalization_note eklediğinden emin ol.

    try:
        response = client.chat.completions.create(
            model=AI_MODEL,
            messages=[{"role": "user", "content": full_prompt}],
            temperature=0.5
        )
        content = response.choices[0].message.content
        # ... Regex işlemleri aynı ...
        plan_match = re.search(r"(.*?)===STEPS===", content, re.S)
        steps_match = re.search(r"===STEPS===\s*(.*)", content, re.S)

        plan_html = plan_match.group(1).strip() if plan_match else content.replace("===STEPS===", "")
        steps = steps_match.group(1).strip().split("\n") if steps_match else []

        return plan_html, steps
    except Exception as e:
        return f"<p>Hata: {e}</p>", []



def export_resources_pdf(topic, ai_plan_html, filename, duration=None):
    subtitle = f"Hedef Süre: {duration}" if duration else "Kapsamlı Öğrenme Rehberi"

    html_template = """
    <html>
    <head>
        <style>
            @page { margin: 2cm; }
            body { font-family: 'Helvetica', sans-serif; line-height: 1.6; color: #333; }
            h1 { color: #2c3e50; border-bottom: 2px solid #3498db; padding-bottom: 10px; }
            h3 { color: #e67e22; margin-top: 25px; border-left: 5px solid #e67e22; padding-left: 10px; }
            table { width: 100%; border-collapse: collapse; margin-top: 15px; font-size: 0.9em; }
            th, td { border: 1px solid #ddd; padding: 12px; text-align: left; }
            th { background-color: #f2f2f2; color: #2c3e50; }
            tr:nth-child(even) { background-color: #f9f9f9; }
            a { color: #2980b9; text-decoration: none; font-weight: bold; }
            ul { margin-top: 0; }
            .meta { font-size: 0.8em; color: #777; margin-bottom: 30px; }
        </style>
    </head>
    <body>
        <h1>Öğrenme Planı: {{ topic }}</h1>
        <div class="meta">
            <strong>Tarih:</strong> {{ date }} <br>
            <strong>Program Türü:</strong> {{ subtitle }}
        </div>

        {{ ai_plan | safe }}

    </body>
    </html>
    """

    template = Template(html_template)
    rendered_html = template.render(
        topic=topic,
        subtitle=subtitle,
        date=datetime.today().strftime("%d.%m.%Y"),
        ai_plan=ai_plan_html
    )

    try:
        font_config = FontConfiguration()
        HTML(string=rendered_html).write_pdf(filename, font_config=font_config)
    except Exception as e:
        print(f"PDF oluşturma hatası: {e}")


def generate_two_pdfs_hybrid(user_input, df_with_skills, output_dir="outputs", duration=None):
    safe_topic = sanitize_filename(user_input)
    if not os.path.exists(output_dir): os.makedirs(output_dir)

    problems = []
    # VERİ ANALİZİ (Hibrit Kısım)
    if not df_with_skills.empty:
        try:
            # Correct sütununu sayıya çevir
            df_with_skills["correct"] = pd.to_numeric(df_with_skills["correct"], errors='coerce')
            # En çok yanlış yapılan problem ID'lerini bul
            difficulty = df_with_skills.groupby("problem_id")["correct"].mean()
            problems = difficulty.sort_values().head(5).index.tolist()
            print(f" Veri Analizi Sonucu: Öğrenci {problems} konularında zayıf.")
        except:
            pass

    # Analiz sonuçlarını (problems) AI'ya gönder
    ai_plan_html, steps = get_ai_learning_plan_and_steps(user_input, problems, None, duration)

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
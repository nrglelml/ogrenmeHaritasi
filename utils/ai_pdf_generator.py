import os
from .sanitize import sanitize_filename
from openai import OpenAI
from weasyprint import HTML
from weasyprint.text.fonts import FontConfiguration
from jinja2 import Template
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
import numpy as np
import re
import wikipedia
from datetime import datetime
from dotenv import load_dotenv
load_dotenv()


client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))


# --- AI'dan Plan + Timeline Adımları Alma ---
def get_ai_learning_plan_and_steps(topic, problems=None, guidance=None):
    if problems and guidance:
        problems_str = ", ".join(map(str, problems))
        guidance_str = ", ".join(guidance)
    else:
        problems_str = "Yok"
        guidance_str = "Yok"

    prompt = f"""
    Kullanıcı '{topic}' konusunda öğrenme planı istiyor.
    Zorlandığı sorular: {problems_str}.
    Çalışma tavsiyeleri: {guidance_str}.

    1. HTML formatında "Konuya Giriş", "Nasıl Çalışmalı?", "Günlük Çalışma Rutini", "Kaynak Önerileri" başlıklarıyla detaylı bir öğrenme planı oluştur.
    2. Ayrıca 5 adımlık bir "Yol Haritası" listesi oluştur. Bu listede sadece adım başlıklarını ver, numara ekleme.

    Cevabın şu formatta olsun:
    ===PLAN===
    [HTML burada]
    ===STEPS===
    Adım 1 başlığı
    Adım 2 başlığı
    ...
    Adım 5 başlığı
    """
    response = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[
            {"role": "system", "content": "Sen deneyimli bir eğitim koçusun."},
            {"role": "user", "content": prompt}
        ],
        temperature=0.7
    )

    content = response.choices[0].message.content
    plan_match = re.search(r"===PLAN===\n(.*?)\n===STEPS===", content, re.S)
    steps_match = re.search(r"===STEPS===\n(.*)", content, re.S)

    plan_html = plan_match.group(1).strip() if plan_match else ""
    steps_text = steps_match.group(1).strip().split("\n") if steps_match else []
    steps = [s.strip() for s in steps_text if s.strip()]

    return plan_html, steps

# --- Kaynak PDF ---
def export_resources_pdf(topic, ai_plan_html, filename):
    html_template = """
    <html>
    <head>
        <style>
            body { font-family: Arial, sans-serif; padding: 20px; line-height: 1.6; }
            h1 { color: #2c3e50; }
            h2 { color: #34495e; }
        </style>
    </head>
    <body>
        <h1>Öğrenme Planı: {{ topic }}</h1>
        <p><strong>Tarih:</strong> {{ date }}</p>
        <div>{{ ai_plan | safe }}</div>
    </body>
    </html>
    """
    template = Template(html_template)
    rendered_html = template.render(
        topic=topic,
        date=datetime.today().strftime("%Y-%m-%d"),
        ai_plan=ai_plan_html
    )
    font_config = FontConfiguration()
    HTML(string=rendered_html).write_pdf(filename, font_config=font_config)

# --- Timeline PDF ---
def create_timeline_pdf(steps, filename):
    fig, ax = plt.subplots(figsize=(10, 5))
    ax.axis('off')

    x = np.linspace(0, 10, 500)
    y = np.sin(x) * 0.5
    ax.plot(x, y, color='black', linewidth=4)

    colors = ['#FF4B4B', '#1ABC9C', '#9B59B6', '#E67E22', '#3498DB']
    step_x = np.linspace(0.5, 9.5, len(steps))

    for i, (sx, text) in enumerate(zip(step_x, steps)):
        sy = np.sin(sx) * 0.5
        circle = mpatches.Circle((sx, sy), 0.3, color=colors[i % len(colors)], zorder=3)
        ax.add_patch(circle)
        ax.text(sx, sy, str(i+1), color='white', ha='center', va='center', fontsize=12, fontweight='bold')
        ax.text(sx, sy-0.8, text, ha='center', va='top', fontsize=10, wrap=True)

    plt.savefig(filename, bbox_inches='tight')
    plt.close()

# --- Hibrit Sistem ---
def generate_two_pdfs_hybrid(user_input, df_with_skills, output_dir="outputs"):
    safe_topic = sanitize_filename(user_input)

    if "skills" in df_with_skills.columns and user_input in df_with_skills["skills"].unique():
        df_topic = df_with_skills[df_with_skills["skills"] == user_input]
        difficulty = df_topic.groupby("problem_id")["correct"].mean().reset_index()
        difficulty = difficulty.sort_values(by="correct").head(5)

        problems = difficulty["problem_id"].tolist()
        guidance = []
        for rate in difficulty["correct"]:
            if rate < 0.3:
                guidance.append("Temel kavramları tekrar edin.")
            elif rate < 0.6:
                guidance.append("Daha fazla pratik yapın.")
            else:
                guidance.append("Tekrar çözerek pekiştirin.")

        ai_plan_html, steps = get_ai_learning_plan_and_steps(user_input, problems, guidance)
    else:
        ai_plan_html, steps = get_ai_learning_plan_and_steps(user_input)

    export_resources_pdf(safe_topic, ai_plan_html, os.path.join(output_dir, f"{safe_topic}_resources.pdf"))
    if steps:
        create_timeline_pdf(steps, os.path.join(output_dir, f"{safe_topic}_roadmap.pdf"))


def get_wikipedia_summary(user_input, lang="en"):
    wikipedia.set_lang(lang)
    try:
        summary = wikipedia.summary(user_input, sentences=3)
        page = wikipedia.page(user_input)
        return {
            "title": page.title,
            "summary": summary,
            "url": page.url
        }
    except wikipedia.exceptions.DisambiguationError as e:
        return {"error": f"Çok anlamlı konu, lütfen daha net yazın. Örnekler: {e.options[:3]}"}
    except wikipedia.exceptions.PageError:
        return {"error": "Bu konuda Wikipedia sayfası bulunamadı."}

def get_ai_resources(topic):
    results = {}

    # 1. Wikipedia
    wiki = get_wikipedia_summary(topic)
    results["Wikipedia"] = wiki

    # 2. YouTube (isteğe bağlı: youtube-search-python)
    results["Videos"] = [
        f"https://www.youtube.com/results?search_query={topic}+introduction"
    ]

    # 3. Books
    results["Books"] = [
        f"https://www.google.com/search?q={topic}+book"
    ]

    # 4. arXiv (isteğe bağlı)
    results["Articles"] = [
        f"https://arxiv.org/search/?query={topic}&searchtype=all"
    ]

    # 5. Wikibooks/Wikiversity
    results["Wikibooks"] = [
        f"https://en.wikibooks.org/wiki/{topic.replace(' ', '_')}"
    ]

    return results



def parse_ai_resources(raw_text):
    sections = {}
    current_section = None
    for line in raw_text.splitlines():
        line = line.strip()
        if line.startswith("===") and line.endswith("==="):
            current_section = line.strip("= ")
            sections[current_section] = []
        elif line and current_section:
            sections[current_section].append(line)
    return sections

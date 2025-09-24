AI Destekli Kişisel Öğrenme Platformu – Flask Backend

Bu Flask tabanlı uygulama, kullanıcıların belirttiği konulara göre yapay zeka destekli kişiselleştirilmiş öğrenme planı ve kaynak önerisi sunar. Kullanıcılar oluşturulan planları PDF olarak indirebilir ve eğitim süreçlerini optimize edebilir.

 Özellikler

Konu girdisine göre AI destekli öğrenme planı ve kaynak önerisi üretimi

PDF olarak indirilebilir plan (Resources & Roadmap)

Chatbot ile öğrenme planı başlatma

Web & Mobil API desteği

 .env ile IP yapılandırması

️ Kurulum Adımları
1. Bu repoyu klonla:
git clone https://github.com/<kullanici-adi>/ogrenmeHaritasi.git
cd ogrenmeHaritasi

2. Sanal ortam oluştur:
python -m venv .venv
source .venv/bin/activate  # macOS/Linux
.venv\Scripts\activate     # Windows

3. Gereksinimleri yükle:
pip install -r requirements.txt

📦 Kullanılan Ana Paketler
Flask
Flask-Cors
openai
python-dotenv
pandas
reportlab

⚙️ .env Ayarları

Projenin kök dizinine .env dosyası oluştur ve içine şu satırları ekle:

OPENAI_API_KEY=sk-xxxxxxxxxxxxxxxxxxxxxxxx
SERVER_IP=192.168.x.x
PORT=5000


Not: SERVER_IP, hem web hem de mobil uygulamanın erişmesi için gereklidir. Mobil cihazın erişebileceği lokal IP olmalıdır.

▶️ Sunucuyu Başlat
python app.py


Sunucu şu adreslerde çalışır:

Web: http://127.0.0.1:5000

Lokal Ağ: http://192.168.x.x:5000
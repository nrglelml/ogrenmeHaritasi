from flask import Flask
from routes import routes
import os
from flask_cors import CORS
from dotenv import load_dotenv

load_dotenv()

app = Flask(__name__)
CORS(app)
app.register_blueprint(routes)

if __name__ == "__main__":

    os.makedirs("outputs", exist_ok=True)


    port = int(os.environ.get("PORT", 10000))

    print(f"🚀 Server running on port {port} (Render ready)")
    app.run(host="0.0.0.0", port=port, debug=False)

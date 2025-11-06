from flask import Flask
from routes import routes
import os

app = Flask(__name__)
app.register_blueprint(routes)

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 10000))  # Render'ın atadığı port
    app.run(host="0.0.0.0", port=port)

# mathan-ai-engine
from flask import Flask
import requests

app = Flask(__name__)

@app.route("/")
def home():
    return "Mathan AI Market Engine Running"

@app.route("/market")
def market():
    data = {
        "engine": "AERO VEL VG",
        "market": "NIFTY",
        "trend": "Checking",
        "signal": "Waiting",
        "status": "AI Engine Active"
    }
    return data

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)
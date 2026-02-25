from flask import Flask,jsonify
import requests

app = Flask(__name__)

NSE_URL = "https://www.nseindia.com/api/option-chain-indices?symbol=NIFTY"

headers = {
    "User-Agent":"Mozilla/5.0",
    "Accept-Language":"en-US,en;q=0.9"
}

def get_market_data():
    session = requests.Session()
    session.get("https://www.nseindia.com",headers=headers)
    response=session.get(NSE_URL,headers=headers)
    data=response.json()

    ce_oi=0
    pe_oi=0

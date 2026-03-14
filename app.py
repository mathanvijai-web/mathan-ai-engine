from flask import Flask,request,jsonify
from flask_cors import CORS
import requests,os,json

app=Flask(__name__)
CORS(app,resources={r"/*":{"origins":"*"}})

DHAN_BASE="https://api.dhan.co"
CLIENT_ID="2603124705"

def dhan_hdrs(t):
    return{"access-token":t,"client-id":CLIENT_ID,"Content-Type":"application/json","Accept":"application/json"}

NSE_HDRS={
    "User-Agent":"Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
    "Accept":"*/*","Accept-Language":"en-US,en;q=0.9",
    "Referer":"https://www.nseindia.com/option-chain"
}

@app.route("/")
def home():
    return jsonify({"status":"MATHAN AI BACKEND RUNNING","version":"V10"})

@app.route("/api/connect",methods=["POST","OPTIONS"])
def connect():
    if request.method=="OPTIONS":return jsonify({"status":True}),200
    token=(request.json or{}).get("token","")
    if len(token)<50:return jsonify({"status":False,"message":"Token too short"}),400
    # Accept if JWT format valid
    if token.startswith("eyJ") and len(token)>100:
        return jsonify({"status":True,"message":"Token accepted!"})
    return jsonify({"status":False,"message":"Invalid token format"}),401

@app.route("/api/oi",methods=["POST","OPTIONS"])
def get_oi():
    if request.method=="OPTIONS":return jsonify({"status":True}),200
    d=request.json or{}
    index=d.get("index","NIFTY")
    expiry=d.get("expiry","")

    # METHOD 1: NSE Option Chain (no auth needed!)
    try:
        sym="NIFTY" if index=="NIFTY" else "SENSEX"
        # First hit NSE homepage to get cookies
        s=requests.Session()
        s.get("https://www.nseindia.com",headers=NSE_HDRS,timeout=8)
        r=s.get(f"https://www.nseindia.com/api/option-chain-indices?symbol={sym}",
                headers=NSE_HDRS,timeout=12)
        if r.status_code==200:
            raw=r.json()
            records=raw.get("records",{})
            data=records.get("data",[])
            exp_dates=records.get("expiryDates",[])
            # Use first expiry if not specified
            target_exp=expiry if expiry in exp_dates else (exp_dates[0] if exp_dates else "")
            tC=tP=mxC=mxP=mxCS=mxPS=ceLTP=peLTP=0
            spot=records.get("underlyingValue",0)
            for row in data:
                if target_exp and row.get("expiryDate","")!=target_exp:continue
                st=row.get("strikePrice",0)
                ce=row.get("CE",{})
                pe=row.get("PE",{})
                ceOI=ce.get("openInterest",0) or 0
                peOI=pe.get("openInterest",0) or 0
                ceLtp=ce.get("lastPrice",0) or 0
                peLtp=pe.get("lastPrice",0) or 0
                tC+=ceOI;tP+=peOI
                if ceOI>mxC:mxC=ceOI;mxCS=st
                if peOI>mxP:mxP=peOI;mxPS=st
                # Get ATM premiums
                atm=round(spot/50)*50 if index=="NIFTY" else round(spot/100)*100
                if abs(st-atm)<(51 if index=="NIFTY" else 101):
                    if ceLtp:ceLTP=ceLtp
                    if peLtp:peLTP=peLtp
            if tC>0:
                return jsonify({"status":True,"source":"NSE","data":{
                    "totalCallOI":tC,"totalPutOI":tP,
                    "pcr":round(tP/tC,2),
                    "resistance":mxCS,"resistanceOI":mxC,
                    "support":mxPS,"supportOI":mxP,
                    "atmCEpremium":ceLTP,"atmPEpremium":peLTP,
                    "spotPrice":spot,"expiryDates":exp_dates[:6],
                    "strikeCount":len(set(r.get("strikePrice",0) for r in data))
                }})
    except Exception as e:
        print(f"NSE OI error: {e}")

    # METHOD 2: Dhan Option Chain (fallback)
    token=d.get("token","")
    if token and len(token)>50:
        try:
            scrip=13 if index=="NIFTY" else 21
            for url in [f"{DHAN_BASE}/v2/optionchain",f"{DHAN_BASE}/optionchain"]:
                r=requests.post(url,headers=dhan_hdrs(token),
                    json={"UnderlyingScrip":scrip,"UnderlyingSegment":"IDX_I","ExpiryDate":expiry},
                    timeout=12)
                if r.status_code==200:
                    raw=r.json()
                    strikes=raw if isinstance(raw,list) else raw.get("data",raw.get("oc",[]))
                    if not strikes:continue
                    tC=tP=mxC=mxP=mxCS=mxPS=ceLTP=peLTP=0
                    for row in strikes:
                        st=row.get("strikePrice",0)
                        ceOI=(row.get("callOI") or(row.get("CE")or{}).get("openInterest",0) or 0)
                        peOI=(row.get("putOI") or(row.get("PE")or{}).get("openInterest",0) or 0)
                        ceLtp=(row.get("callLTP") or(row.get("CE")or{}).get("lastPrice",0) or 0)
                        peLtp=(row.get("putLTP") or(row.get("PE")or{}).get("lastPrice",0) or 0)
                        tC+=ceOI;tP+=peOI
                        if ceOI>mxC:mxC=ceOI;mxCS=st
                        if peOI>mxP:mxP=peOI;mxPS=st
                        if ceLtp and not ceLTP:ceLTP=ceLtp
                        if peLtp and not peLTP:peLTP=peLtp
                    if tC>0:
                        return jsonify({"status":True,"source":"DHAN","data":{
                            "totalCallOI":tC,"totalPutOI":tP,
                            "pcr":round(tP/tC,2),
                            "resistance":mxCS,"support":mxPS,
                            "atmCEpremium":ceLTP,"atmPEpremium":peLTP,
                            "strikeCount":len(strikes)
                        }})
        except Exception as e:
            print(f"Dhan OI error: {e}")

    return jsonify({"status":False,"message":"Both NSE and Dhan OI failed"}),400

@app.route("/api/spot",methods=["POST","OPTIONS"])
def spot():
    if request.method=="OPTIONS":return jsonify({"status":True}),200
    token=(request.json or{}).get("token","")
    # Try NSE spot first
    try:
        s=requests.Session()
        s.get("https://www.nseindia.com",headers=NSE_HDRS,timeout=6)
        r=s.get("https://www.nseindia.com/api/option-chain-indices?symbol=NIFTY",
                headers=NSE_HDRS,timeout=10)
        if r.status_code==200:
            spot=r.json().get("records",{}).get("underlyingValue",0)
            if spot>0:
                return jsonify({"status":True,"source":"NSE","data":{"nifty":spot}})
    except Exception as e:
        print(f"NSE spot error: {e}")
    # Dhan fallback
    if token and len(token)>50:
        try:
            r=requests.post(f"{DHAN_BASE}/marketfeed/ltp",headers=dhan_hdrs(token),
                json={"NSE_INDEX":["NIFTY 50"],"BSE_INDEX":["SENSEX"]},timeout=10)
            if r.status_code==200:
                data=r.json().get("data",{})
                result={}
                nse=data.get("NSE_INDEX",{})
                bse=data.get("BSE_INDEX",{})
                if "NIFTY 50" in nse:result["nifty"]=nse["NIFTY 50"].get("last_price",0)
                if "SENSEX" in bse:result["sensex"]=bse["SENSEX"].get("last_price",0)
                if result:return jsonify({"status":True,"source":"DHAN","data":result})
        except Exception as e:
            print(f"Dhan spot error: {e}")
    return jsonify({"status":False,"message":"Spot fetch failed"}),400

if __name__=="__main__":
    port=int(os.environ.get("PORT",5000))
    app.run(host="0.0.0.0",port=port)

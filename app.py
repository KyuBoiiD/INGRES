import os
import json
import time
import gspread
import pandas as pd
import google.generativeai as genai

from flask import Flask, render_template, request, jsonify
from pandasql import sqldf
from datetime import date
from google.oauth2.service_account import Credentials
from google.api_core import exceptions

# -------------------------------------------------
# APP SETUP
# -------------------------------------------------
app = Flask(__name__)

# -------------------------------------------------
# ENVIRONMENT VARIABLES (Vercel compatible)
# -------------------------------------------------
SHEET_NAME = "Ingres_Explorer_DB"
WORKSHEET_NAME = "Records"

GEMINI_KEY = os.environ.get("GEMINI_API_KEY")
GOOGLE_CREDS_JSON = os.environ.get("GOOGLE_CREDENTIALS_JSON")

if not GEMINI_KEY:
    raise RuntimeError("GEMINI_API_KEY is not set")

if not GOOGLE_CREDS_JSON:
    raise RuntimeError("GOOGLE_CREDENTIALS_JSON is not set")

genai.configure(api_key=GEMINI_KEY)

# -------------------------------------------------
# GOOGLE SHEETS CONNECTION (NO FILE SYSTEM)
# -------------------------------------------------
def get_worksheet():
    try:
        creds_dict = json.loads(GOOGLE_CREDS_JSON)

        creds = Credentials.from_service_account_info(
            creds_dict,
            scopes=["https://www.googleapis.com/auth/spreadsheets"]
        )

        gc = gspread.authorize(creds)
        sh = gc.open(SHEET_NAME)
        return sh.worksheet(WORKSHEET_NAME)

    except Exception as e:
        print("Google Sheets Error:", e)
        return None

# -------------------------------------------------
# DATA FETCH
# -------------------------------------------------
def load_dataframe():
    ws = get_worksheet()
    if not ws:
        return pd.DataFrame()

    data = ws.get_all_records()
    return pd.DataFrame(data)

# -------------------------------------------------
# GEMINI QUERY WITH FAILOVER
# -------------------------------------------------
def run_gemini(prompt):
    models = [
        "models/gemini-2.5-flash",
        "models/gemini-2.5-flash-lite"
    ]

    for model_name in models:
        try:
            model = genai.GenerativeModel(model_name)
            response = model.generate_content(prompt)
            return response.text
        except exceptions.ResourceExhausted:
            print(f"{model_name} exhausted, switching...")
            time.sleep(1)
        except Exception as e:
            print("Gemini Error:", e)

    return "❌ Gemini models unavailable right now."

# -------------------------------------------------
# ROUTES
# -------------------------------------------------
@app.route("/")
def home():
    return render_template("index.html")

@app.route("/query", methods=["POST"])
def query():
    user_query = request.json.get("query", "").strip()
    if not user_query:
        return jsonify({"error": "Empty query"}), 400

    df = load_dataframe()
    if df.empty:
        return jsonify({"error": "Database unavailable"}), 500

    try:
        sql_prompt = f"""
You are an expert SQL generator.
Table name: df
Columns: {', '.join(df.columns)}

User question:
{user_query}

Return ONLY a valid SQL query.
"""

        sql_query = run_gemini(sql_prompt)
        result_df = sqldf(sql_query, {"df": df})

        return jsonify({
            "sql": sql_query,
            "rows": result_df.to_dict(orient="records")
        })

    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route("/health")
def health():
    return jsonify({
        "status": "ok",
        "date": str(date.today())
    })

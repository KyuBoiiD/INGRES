import os
import json
import time
import gspread
import pandas as pd
import google.generativeai as genai
from flask import Flask, render_template, request, jsonify
from pandasql import sqldf
from dotenv import load_dotenv
from datetime import date
from google.api_core import exceptions

# --- CONFIGURATION ---
load_dotenv()
app = Flask(__name__)

SHEET_NAME = "Ingres_Explorer_DB"
WORKSHEET_NAME = "Records"
GEMINI_KEY = os.getenv("GEMINI_API_KEY")

# --- GEMINI MODEL FAILOVER CONFIG ---
GEMINI_MODELS = [
    "gemini-2.5-flash",
    "gemini-2.5-flash-lite"
]

CURRENT_MODEL_INDEX = 0
MODEL_COOLDOWN_SECONDS = 60
last_model_failure_time = {}

# --- DATABASE CONNECTION ---
def get_worksheet():
    try:
        if not os.path.exists('credentials.json'):
            return None
        gc = gspread.service_account(filename='credentials.json')
        return gc.open(SHEET_NAME).worksheet(WORKSHEET_NAME)
    except:
        return None

def fetch_data():
    sheet = get_worksheet()
    if sheet:
        return pd.DataFrame(sheet.get_all_records())
    return None

# --- MODEL SELECTION HELPERS ---
def is_model_available(model_name):
    last_fail = last_model_failure_time.get(model_name)
    if not last_fail:
        return True
    return (time.time() - last_fail) > MODEL_COOLDOWN_SECONDS

def select_best_model():
    global CURRENT_MODEL_INDEX
    for i, model in enumerate(GEMINI_MODELS):
        if is_model_available(model):
            CURRENT_MODEL_INDEX = i
            return model
    return GEMINI_MODELS[CURRENT_MODEL_INDEX]

# --- AI LOGIC (AUTO FAILOVER ENABLED) ---
def get_ai_decision(user_input, columns):
    if not GEMINI_KEY:
        return {"error": "API Key missing."}

    genai.configure(api_key=GEMINI_KEY)

    prompt = f"""
    You are a database assistant. Columns: {columns}. Input: "{user_input}". Today: {date.today()}.
    Return ONLY JSON (no markdown):
    1. QUERY: {{ "action": "query", "sql": "SELECT * FROM df..." }}
    2. DELETE: {{ "action": "delete", "id_value": "..." }}
    3. UPDATE: {{ "action": "update", "id_value": "...", "column_name": "...", "new_value": "..." }}
    4. INSERT: {{ "action": "insert", "record_data": {{...}} }}
    """

    for _ in range(len(GEMINI_MODELS)):
        model_name = select_best_model()

        try:
            print(f"🤖 Using Gemini model: {model_name}")
            model = genai.GenerativeModel(model_name)
            response = model.generate_content(prompt)

            clean_text = response.text.replace("```json", "").replace("```", "").strip()
            return json.loads(clean_text)

        except exceptions.ResourceExhausted:
            print(f"⚠️ {model_name} quota exhausted. Switching model...")
            last_model_failure_time[model_name] = time.time()
            time.sleep(2)
            continue

        except Exception as e:
            return {"error": f"AI Error: {str(e)}"}

    return {"error": "All AI models are currently rate-limited. Please wait 1 minute."}

# --- WEB ROUTES ---
@app.route('/')
def home():
    return render_template('index.html')

@app.route('/api/chat', methods=['POST'])
def chat():
    user_input = request.json.get('message')
    df = fetch_data()

    if df is None:
        return jsonify({"response": "❌ Error: DB Connection Failed."})

    decision = get_ai_decision(user_input, list(df.columns))

    if "error" in decision:
        return jsonify({"response": f"⚠️ {decision['error']}"})

    action = decision.get("action")
    ws = get_worksheet()

    try:
        if action == "query":
            sql = decision.get("sql").replace("Records", "df").replace("records", "df")
            result = sqldf(sql, locals())

            if result.empty:
                return jsonify({"response": "No records found."})

            return jsonify({
                "response": "Here is what I found:",
                "table": result.to_html(classes='data-table', index=False)
            })

        elif action == "delete":
            id_val = str(decision.get("id_value"))
            cell = ws.find(id_val)
            ws.delete_rows(cell.row)
            return jsonify({"response": f"✅ Deleted ID {id_val}"})

        elif action == "update":
            id_val = str(decision.get("id_value"))
            col = decision.get("column_name")
            val = decision.get("new_value")

            cell = ws.find(id_val)
            headers = ws.row_values(1)
            ws.update_cell(cell.row, headers.index(col) + 1, val)

            return jsonify({"response": f"✅ Updated {col} for ID {id_val}"})

        elif action == "insert":
            data = decision.get("record_data")
            ws.append_row([data.get(col, "") for col in df.columns])
            return jsonify({"response": "✅ Added record!"})

    except Exception as e:
        return jsonify({"response": f"❌ Execution Error: {str(e)}"})

    return jsonify({"response": "🤷 I didn't understand."})

# --- LAUNCH ---
if __name__ == '__main__':
    print("🚀 Launching Clean Slate App with Gemini Auto-Failover")
    app.run(debug=True)

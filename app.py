import streamlit as st
import pandas as pd
import requests
from datetime import datetime
import os

# --- הגדרות ---
DB_FILE = 'food_db_usda_en.csv'
LOG_FILE = 'daily_log_usda_en.csv'
# מפתח ציבורי של ממשל ארה"ב
USDA_API_KEY = "DEMO_KEY"

# --- מילון משקלים ממוצעים (למקרה שבוחרים 'יחידות') ---
AVERAGE_WEIGHTS = {
    'apple': 180, 'banana': 120, 'orange': 150, 'pear': 160,
    'egg': 60, 'bread': 30, 'pita': 100, 'roll': 90,
    'date': 10, 'almond': 1.2, 'walnut': 5, 'cashew': 1.5,
    'cucumber': 100, 'tomato': 120, 'pepper': 150, 'carrot': 100,
    'chicken breast': 150, 'rice': 150, 'pasta': 150,
    'yogurt': 150, 'milk': 200, 'coffee': 200,
    'oil': 15, 'sugar': 5, 'honey': 8
}

def load_data():
    if not os.path.exists(DB_FILE):
        pd.DataFrame(columns=['name', 'calories', 'protein', 'sugar']).to_csv(DB_FILE, index=False)
    if not os.path.exists(LOG_FILE):
        pd.DataFrame(columns=['date', 'time', 'food', 'amount', 'unit', 'calories', 'protein', 'sugar']).to_csv(LOG_FILE, index=False)
    return pd.read_csv(DB_FILE), pd.read_csv(LOG_FILE)

def fetch_from_usda(query):
    """שאיבת נתונים ממשרד החקלאות האמריקאי (מקבל אנגלית בלבד)"""
    # חיפוש במאגר המדויק (SR Legacy / Foundation)
    url = f"https://api.nal.usda.gov/fdc/v1/foods/search?api_key={USDA_API_KEY}&query={query}&dataType=SR%20Legacy,Foundation&pageSize=3"
    
    try:
        response = requests.get(url, timeout=10)
        data = response.json()
        
        if not data.get('foods'):
            return None
            
        # לוקח את התוצאה הראשונה
        food = data['foods'][0]
        nutrients = food['foodNutrients']
        
        cal, prot, sugar = 0, 0, 0
        
        for n in nutrients:
            name = n.get('nutrientName', '').lower()
            val = n.get('value', 0)
            if 'energy' in name: cal = val
            elif 'protein' in name: prot = val
            elif 'sugar' in name: sugar = val
            
        return {'calories': cal, 'protein': prot, 'sugar': sugar}
        
    except:
        return None

def save_new_food(name, nutrients):
    df = pd.read_csv(DB_FILE)
    new_row = {'name': name, 'calories': nutrients['calories'], 'protein': nutrients['protein'], 'sugar': nutrients['sugar']}
    df = pd.concat([df, pd.DataFrame([new_row])], ignore_index=True)
    df.to_csv(DB_FILE, index=False)

def get_weight(food_name):
    """ניחוש משקל ליחידה"""
    food_name = food_name.lower()
    for k, v in AVERAGE_WEIGHTS.items():
        if k in food_name: return v
    return 100 # ברירת מחדל

# --- ממשק משתמש ---
st.set_page_config(page_title="Calorie Tracker", page_icon="🇺🇸", layout="centered")
st.markdown("<h1 style='text-align: center;'>מעקב תזונה (באנגלית)</h1>", unsafe_allow_html=True)

db_df, log_df = load_data()

# --- סיכום יומי ---
today = datetime.now().strftime("%Y-%m-%d")
day_log = log_df[log_df['date'] == today]

c1, c2, c3 = st.columns(3)
c1.metric("קלוריות", f"{day_log['calories'].sum():,.0f}")
c2.metric("חלבון (g)", f"{day_log['protein'].sum():,.1f}")
c3.metric("סוכר (g)", f"{day_log['sugar'].sum():,.1f}")

st.divider()

# --- טופס ---
with st.form("english_form"):
    c_name, c_amt, c_unit = st.columns([2,1,1])
    
    name = c_name.text_input("Product Name (English Only)", placeholder="e.g. Apple, Egg, Bread")
    amount = c_amt.number_input("Amount", 1.0, step=0.5)
    unit = c_unit.selectbox("Unit", ["Units", "Grams"])
    
    submit = st.form_submit_button("Search USDA & Add")
    
    if submit and name:
        # 1. חיפוש מקומי
        exists = db_df[db_df['name'] == name]
        nutrients = None
        
        if not exists.empty:
            row = exists.iloc[0]
            nutrients = {'calories': row['calories'], 'protein': row['protein'], 'sugar': row['sugar']}
            st.success(f"Loaded from memory: {name}")
        else:
            # 2. חיפוש בארה"ב
            with st.spinner("Searching USDA Database..."):
                nutrients = fetch_from_usda(name)
                if nutrients:
                    save_new_food(name, nutrients)
                    st.info("Found in USDA Database!")
                else:
                    st.error("Not found. Try a simpler name (e.g. 'Apple' instead of 'Red Apple')")
        
        # 3. חישוב ושמירה
        if nutrients:
            weight = 100
            if unit == "Units":
                weight = get_weight(name)
                if weight == 100: st.warning(f"Unknown weight for '{name}', assuming 100g per unit.")
            
            grams = amount if unit == "Grams" else amount * weight
            factor = grams / 100.0
            
            new_entry = {
                'date': datetime.now().strftime("%Y-%m-%d"),
                'time': datetime.now().strftime("%H:%M"),
                'food': name,
                'amount': amount,
                'unit': unit,
                'calories': round(nutrients['calories'] * factor),
                'protein': round(nutrients['protein'] * factor, 1),
                'sugar': round(nutrients['sugar'] * factor, 1)
            }
            
            log_df = pd.read_csv(LOG_FILE)
            log_df = pd.concat([log_df, pd.DataFrame([new_entry])], ignore_index=True)
            log_df.to_csv(LOG_FILE, index=False)
            st.rerun()

# --- טבלה ---
if not day_log.empty:
    st.markdown("### Daily Log")
    st.dataframe(day_log[['time', 'food', 'amount', 'unit', 'calories', 'protein', 'sugar']], use_container_width=True)

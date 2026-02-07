import streamlit as st
import pandas as pd
import requests
from datetime import datetime
import os

# --- הגדרות קבצים ---
LOG_FILE = 'daily_log.csv'     # יומן אכילה

# --- פונקציות עזר (Logic) ---

def load_data():
    """טעינת נתונים או יצירת קבצים אם אינם קיימים"""
    if not os.path.exists(LOG_FILE):
        pd.DataFrame(columns=['date', 'time', 'food', 'amount', 'unit', 'calories', 'protein', 'carbs']).to_csv(LOG_FILE, index=False)
    
    return pd.read_csv(LOG_FILE)

def fetch_nutrients_nutritionix(query):
    """
    חיפוש נתונים מ-Nutritionix API (מאגר מקצועי ודיוק).
    מחזיר ערכים ל-100 גרם.
    """
    url = f"https://www.nutritionix.com/api/v2/search/instant?query={query}"
    headers = {
        'x-app-id': 'b9db0e10',
        'x-app-key': '1839914e6d91b097184cc25f1c13f6fa'
    }
    try:
        response = requests.get(url, headers=headers, timeout=5)
        data = response.json()
        if data.get('common') or data.get('branded'):
            # עדיפות: common foods
            items = data.get('common', []) or data.get('branded', [])
            if items:
                product = items[0]
                # Nutritionix נותן נתונים ל-100g כברירת מחדל
                return {
                    'calories': product.get('nf_calories', 0),
                    'protein': product.get('nf_total_protein', 0),
                    'carbs': product.get('nf_total_carbohydrate', 0),
                    'name': product.get('food_name', query)
                }
    except Exception as e:
        st.warning(f"שגיאה בחיפוש: {str(e)}")
        return None
    return None

def log_meal(food_name, amount, unit, nutrients):
    """רישום הארוחה ביומן"""
    if unit == 'גרם':
        factor = amount / 100
    else:  # יחידות
        factor = 1  # מניחים שיחידה אחת = 100 גרם
    
    total_cal = nutrients['calories'] * factor
    total_prot = nutrients['protein'] * factor
    total_carbs = nutrients['carbs'] * factor
    
    new_entry = {
        'date': datetime.now().strftime("%Y-%m-%d"),
        'time': datetime.now().strftime("%H:%M"),
        'food': food_name,
        'amount': amount,
        'unit': unit,
        'calories': round(total_cal, 1),
        'protein': round(total_prot, 1),
        'carbs': round(total_carbs, 1)
    }
    
    log_df = load_data()
    log_df = pd.concat([log_df, pd.DataFrame([new_entry])], ignore_index=True)
    log_df.to_csv(LOG_FILE, index=False)

# --- ממשק משתמש (UI) ---

st.set_page_config(page_title="ניהול קלוריות", page_icon="🍎", layout="centered")

# כותרת מותאמת אישית
st.markdown("<h1 style='text-align: center;'>מעקב תזונה יומי</h1>", unsafe_allow_html=True)

# טעינת נתונים
log_df = load_data()

# סינון להיום בלבד
today = datetime.now().strftime("%Y-%m-%d")
today_log = log_df[log_df['date'] == today]

# --- מטריקות בזמן אמת ---
col1, col2, col3 = st.columns(3)
total_cals = today_log['calories'].sum()
total_prot = today_log['protein'].sum()
total_carbs = today_log['carbs'].sum()

# יעד
TARGET_CALORIES = st.sidebar.number_input("יעד קלורי יומי", value=2000)

delta_cal = TARGET_CALORIES - total_cals

col1.metric("קלוריות", f"{total_cals:,.0f}", f"{delta_cal:,.0f} נותר", delta_color="normal")
col2.metric("חלבון (g)", f"{total_prot:,.1f}")
col3.metric("פחמימות (g)", f"{total_carbs:,.1f}")

st.progress(min(total_cals / TARGET_CALORIES, 1.0))

st.markdown("---")

# --- טופס הזנה ---
st.subheader("מה אכלת?")

with st.form("eat_form"):
    col_input, col_amount, col_unit = st.columns([2, 1, 1])
    
    food_input = col_input.text_input("שם המאכל/משקה") 
    amount_input = col_amount.number_input("כמות", min_value=1.0, value=100.0)
    unit_input = col_unit.selectbox("יחידה", ["גרם", "יחידות"])
    
    submitted = st.form_submit_button("הוסף ליומן")

    if submitted and food_input:
        with st.spinner('מחפש נתונים מ-Nutritionix...'):
            nutrients = fetch_nutrients_nutritionix(food_input)
            
            if nutrients and nutrients['calories'] > 0:
                st.success(f"✅ נמצא: {nutrients['name']}")
                log_meal(food_input, amount_input, unit_input, nutrients)
                st.rerun()
            else:
                st.error("❌ לא נמצא מוצר כזה. נסה שם באנגלית או שם כללי יותר.")

# --- היסטוריה יומית ---
if not today_log.empty:
    st.subheader("היסטוריה להיום")
    st.dataframe(today_log[['time', 'food', 'amount', 'calories', 'protein', 'carbs']], use_container_width=True)
else:
    st.info("📝 עדיין לא הוספת מאום היום")

import streamlit as st
import pandas as pd
import requests
from datetime import datetime
import os

# --- הגדרות קבצים ---
DB_FILE = 'food_database.csv'  # בסיס נתונים של מוצרים שכבר חיפשנו
LOG_FILE = 'daily_log.csv'     # יומן אכילה

# --- פונקציות עזר (Logic) ---

def load_data():
    """טעינת נתונים או יצירת קבצים אם אינם קיימים"""
    if not os.path.exists(DB_FILE):
        pd.DataFrame(columns=['name', 'calories', 'protein', 'sugar']).to_csv(DB_FILE, index=False)
    if not os.path.exists(LOG_FILE):
        pd.DataFrame(columns=['date', 'time', 'food', 'amount', 'unit', 'calories', 'protein', 'sugar']).to_csv(LOG_FILE, index=False)
    
    return pd.read_csv(DB_FILE), pd.read_csv(LOG_FILE)

def fetch_nutrients(query):
    """
    חיפוש נתונים באינטרנט (OpenFoodFacts API).
    מחזיר ערכים ל-100 גרם.
    """
    url = f"https://world.openfoodfacts.org/cgi/search.pl?search_terms={query}&search_simple=1&action=process&json=1"
    try:
        response = requests.get(url, timeout=5)
        data = response.json()
        if data['products']:
            product = data['products'][0] # לוקח את התוצאה הראשונה
            nutriments = product.get('nutriments', {})
            
            return {
                'calories': nutriments.get('energy-kcal_100g', 0),
                'protein': nutriments.get('proteins_100g', 0),
                'sugar': nutriments.get('sugars_100g', 0)
            }
    except Exception as e:
        return None
    return None

def save_new_food(name, nutrients):
    """שמירת מוצר חדש לבסיס הנתונים לשימוש עתידי"""
    df = pd.read_csv(DB_FILE)
    new_row = {'name': name, 'calories': nutrients['calories'], 'protein': nutrients['protein'], 'sugar': nutrients['sugar']}
    # שימוש ב-concat במקום append
    df = pd.concat([df, pd.DataFrame([new_row])], ignore_index=True)
    df.to_csv(DB_FILE, index=False)

def log_meal(food_name, amount, unit, nutrients):
    """רישום הארוחה ביומן"""
    factor = amount / 100 if unit == 'גרם' else amount # הנחה: יחידה = 100 גרם (אפשר לשכלל)
    
    total_cal = nutrients['calories'] * factor
    total_prot = nutrients['protein'] * factor
    total_sug = nutrients['sugar'] * factor
    
    new_entry = {
        'date': datetime.now().strftime("%Y-%m-%d"),
        'time': datetime.now().strftime("%H:%M"),
        'food': food_name,
        'amount': amount,
        'unit': unit,
        'calories': round(total_cal, 1),
        'protein': round(total_prot, 1),
        'sugar': round(total_sug, 1)
    }
    
    log_df = pd.read_csv(LOG_FILE)
    log_df = pd.concat([log_df, pd.DataFrame([new_entry])], ignore_index=True)
    log_df.to_csv(LOG_FILE, index=False)

# --- ממשק משתמש (UI) ---

st.set_page_config(page_title="ניהול קלוריות", page_icon="🍎", layout="centered")

# כותרת מותאמת אישית
st.markdown("<h1 style='text-align: center;'>מעקב תזונה יומי</h1>", unsafe_allow_html=True)

# טעינת נתונים
db_df, log_df = load_data()

# סינון להיום בלבד
today = datetime.now().strftime("%Y-%m-%d")
today_log = log_df[log_df['date'] == today]

# --- מטריקות בזמן אמת ---
col1, col2, col3 = st.columns(3)
total_cals = today_log['calories'].sum()
total_prot = today_log['protein'].sum()
total_sugar = today_log['sugar'].sum()

# יעד (מותאם לגבר בן 57, הערכה גסה)
TARGET_CALORIES = st.sidebar.number_input("יעד קלורי יומי", value=2000)

delta_cal = TARGET_CALORIES - total_cals

col1.metric("קלוריות", f"{total_cals:,.0f}", f"{delta_cal:,.0f} נותר", delta_color="normal")
col2.metric("חלבון ($g$)", f"{total_prot:,.1f}")
col3.metric("סוכר ($g$)", f"{total_sugar:,.1f}")

st.progress(min(total_cals / TARGET_CALORIES, 1.0))

st.markdown("---")

# --- טופס הזנה ---
st.subheader("מה אכלת?")

with st.form("eat_form"):
    col_input, col_amount, col_unit = st.columns([2, 1, 1])
    
    # השלמה אוטומטית מתוך הדאטא בייס הקיים
    food_input = col_input.text_input("שם המאכל/משקה") 
    amount_input = col_amount.number_input("כמות", min_value=1.0, value=100.0)
    unit_input = col_unit.selectbox("יחידה", ["גרם", "יחידות (כ-100 גרם)"])
    
    submitted = st.form_submit_button("הוסף ליומן")

    if submitted and food_input:
        # 1. בדיקה אם קיים בבסיס הנתונים המקומי
        existing_food = db_df[db_df['name'] == food_input]
        
        nutrients = None
        source = ""
        
        if not existing_food.empty:
            source = "database"
            row = existing_food.iloc[0]
            nutrients = {'calories': row['calories'], 'protein': row['protein'], 'sugar': row['sugar']}
            st.success(f"נמצא בזיכרון: {food_input}")
        else:
            # 2. אם לא, חיפוש באינטרנט
            with st.spinner('מחפש נתונים באינטרנט...'):
                nutrients = fetch_nutrients(food_input)
                if nutrients:
                    source = "internet"
                    save_new_food(food_input, nutrients)
                    st.info(f"נמצא באינטרנט ונוסף למאגר: {food_input}")
                else:
                    st.error("לא נמצא מוצר כזה. נסה שם באנגלית או שם כללי יותר.")

        if nutrients:
            log_meal(food_input, amount_input, unit_input, nutrients)
            st.rerun() # רענון המסך לעדכון המונים

# --- היסטוריה יומית ---
if not today_log.empty:
    st.subheader("היסטוריה להיום")
    st.dataframe(today_log[['time', 'food', 'amount', 'calories', 'protein', 'sugar']], use_container_width=True)

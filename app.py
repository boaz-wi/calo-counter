import streamlit as st
import pandas as pd
import requests
from datetime import datetime
import os

# --- הגדרות קבצים ---
DB_FILE = 'food_db_v3.csv'      # גרסה 3 - בסיס נתונים מעודכן
LOG_FILE = 'daily_log_v3.csv'   # יומן גרסה 3

# --- ה"מוח" של המשקלים (מילון משקלים ממוצעים בגרמים ליחידה) ---
# זה פותר את בעיית השקד מול המנגו
AVERAGE_WEIGHTS = {
    # פירות
    'תפוח': 160, 'בננה': 120, 'תפוז': 150, 'אגס': 160, 'מנגו': 300,
    'אפרסק': 150, 'שזיף': 60, 'משמש': 40, 'תמר': 10, 'ענבים': 5,
    'אבטיח': 200, 'מלון': 200, 'תות': 15, 'קלמנטינה': 80,
    
    # ירקות
    'מלפפון': 100, 'עגבניה': 120, 'גמבה': 150, 'פלפל': 150, 
    'גזר': 100, 'בצל': 100, 'תפוח אדמה': 200, 'בטטה': 200,
    
    # אגוזים ושומנים (חשוב מאוד - משקלים קטנים)
    'שקד': 1.2, 'אגוז מלך': 5, 'קשיו': 1.5, 'אגוז ברזיל': 4,
    'זית': 3, 'בוטנים': 1, 'פיסטוק': 1,
    
    # פחמימות ומאפים
    'לחם': 30, 'פרוסת לחם': 30, 'לחמניה': 80, 'פיתה': 100, 
    'בייגלה': 80, 'קרקר': 10, 'פריכית': 8,
    
    # חלבונים
    'ביצה': 60, 'יוגורט': 150, 'מעדן': 150,
    
    # אחר
    'כפית סוכר': 5, 'כף שמן': 15, 'כפית דבש': 8
}

def get_estimated_weight(food_name):
    """
    פונקציה שמנסה לנחש משקל יחידה לפי השם.
    אם מוצאת - מחזירה את המשקל בגרמים.
    אם לא מוצאת - מחזירה 100 גרם כברירת מחדל.
    """
    food_name = food_name.lower() # ניקוי טקסט
    
    # חיפוש חכם: בודק אם מילת המפתח מופיעה בשם שכתבת
    # לדוגמא: אם כתבת "לחם מלא", הוא ימצא את "לחם" ויחזיר 30
    for key, weight in AVERAGE_WEIGHTS.items():
        if key in food_name:
            return weight, True # True מסמן שמצאנו התאמה
            
    return 100, False # לא מצאנו, ברירת מחדל 100

# --- פונקציות ליבה (לוגיקה) ---

def load_data():
    if not os.path.exists(DB_FILE):
        pd.DataFrame(columns=['name', 'calories', 'protein', 'sugar']).to_csv(DB_FILE, index=False)
    if not os.path.exists(LOG_FILE):
        pd.DataFrame(columns=['date', 'time', 'food', 'amount', 'unit', 'calories', 'protein', 'sugar']).to_csv(LOG_FILE, index=False)
    return pd.read_csv(DB_FILE), pd.read_csv(LOG_FILE)

def fetch_nutrients_reliable(query):
    """חיפוש נתונים ל-100 גרם ב-OpenFoodFacts"""
    url = f"https://world.openfoodfacts.org/cgi/search.pl?search_terms={query}&search_simple=1&action=process&json=1&page_size=3"
    try:
        response = requests.get(url, timeout=5)
        data = response.json()
        if data['count'] > 0:
            for product in data['products']:
                nutriments = product.get('nutriments', {})
                if 'energy-kcal_100g' in nutriments:
                    return {
                        'calories': float(nutriments.get('energy-kcal_100g', 0)),
                        'protein': float(nutriments.get('proteins_100g', 0)),
                        'sugar': float(nutriments.get('sugars_100g', 0))
                    }
    except:
        return None
    return None

def save_new_food(name, nutrients):
    df = pd.read_csv(DB_FILE)
    new_row = {'name': name, 'calories': nutrients['calories'], 'protein': nutrients['protein'], 'sugar': nutrients['sugar']}
    df = pd.concat([df, pd.DataFrame([new_row])], ignore_index=True)
    df.to_csv(DB_FILE, index=False)

def log_meal(food_name, amount, unit, nutrients, unit_weight_grams):
    """
    חישוב סופי
    amount = כמה יחידות אכלתי (למשל 5)
    unit_weight_grams = כמה שוקלת יחידה אחת (למשל שקד = 1.2 גרם)
    """
    
    # חישוב המשקל הכולל בגרמים שאכלתי
    if unit == 'גרם':
        total_grams_eaten = amount
    else: # יחידות
        total_grams_eaten = amount * unit_weight_grams
    
    # הפקטור לחישוב (הנתונים מגיעים ל-100 גרם)
    factor = total_grams_eaten / 100.0
    
    new_entry = {
        'date': datetime.now().strftime("%Y-%m-%d"),
        'time': datetime.now().strftime("%H:%M"),
        'food': food_name,
        'amount': amount,
        'unit': unit, # נשמור את מה שהמשתמש בחר
        'calories': round(nutrients['calories'] * factor, 0),
        'protein': round(nutrients['protein'] * factor, 1),
        'sugar': round(nutrients['sugar'] * factor, 1)
    }
    
    log_df = pd.read_csv(LOG_FILE)
    log_df = pd.concat([log_df, pd.DataFrame([new_entry])], ignore_index=True)
    log_df.to_csv(LOG_FILE, index=False)

# --- ממשק משתמש (UI) ---

st.set_page_config(page_title="ניהול קלוריות", page_icon="🥑", layout="centered")
st.markdown("<h1 style='text-align: center;'>יומן תזונה חכם</h1>", unsafe_allow_html=True)

db_df, log_df = load_data()

# --- חישובים יומיים ---
today = datetime.now().strftime("%Y-%m-%d")
today_log = log_df[log_df['date'] == today]

# מדדים
c1, c2, c3 = st.columns(3)
c1.metric("קלוריות היום", f"{today_log['calories'].sum():,.0f}")
c2.metric("חלבון (גרם)", f"{today_log['protein'].sum():,.1f}")
c3.metric("סוכר (גרם)", f"{today_log['sugar'].sum():,.1f}")

st.divider()

# --- טופס הזנה ---
st.subheader("הוספת אכילה")

with st.form("main_form"):
    col_food, col_amount, col_unit = st.columns([2, 1, 1])
    
    food_input = col_food.text_input("מה אכלת? (לדוגמה: 5 שקדים)")
    amount_input = col_amount.number_input("כמות", min_value=0.1, value=1.0)
    unit_input = col_unit.selectbox("לפי", ["יחידות", "גרם"])
    
    submitted = st.form_submit_button("חשב והוסף")

    if submitted and food_input:
        # 1. איתור נתונים תזונתיים (קלוריות ל-100 גרם)
        nutrients = None
        existing = db_df[db_df['name'] == food_input]
        
        if not existing.empty:
            row = existing.iloc[0]
            nutrients = {'calories': row['calories'], 'protein': row['protein'], 'sugar': row['sugar']}
            st.success(f"נמצא במאגר: {food_input}")
        else:
            with st.spinner('מחפש נתונים ברשת...'):
                nutrients = fetch_nutrients_reliable(food_input)
                if nutrients:
                    save_new_food(food_input, nutrients)
                else:
                    st.error("לא מצאתי את המוצר. נסה שם אחר.")

        # 2. אם יש נתונים, בצע את חישוב המשקלים החכם
        if nutrients:
            detected_weight, is_known = get_estimated_weight(food_input)
            
            # הצגת מידע למשתמש על החישוב
            if unit_input == 'יחידות':
                if is_known:
                    st.info(f"💡 זוהה: יחידה אחת של '{food_input}' = {detected_weight} גרם בממוצע.")
                else:
                    st.warning(f"⚠️ לא יודע כמה שוקלת יחידה של '{food_input}'. מניח 100 גרם. לפעמים הבאות כדאי לכתוב בגרמים.")
            
            log_meal(food_input, amount_input, unit_input, nutrients, detected_weight)
            st.rerun()

# --- היסטוריה ---
if not today_log.empty:
    st.markdown("### מה אכלת היום")
    st.dataframe(today_log[['time', 'food', 'amount', 'unit', 'calories', 'protein', 'sugar']], use_container_width=True)

import streamlit as st
import pandas as pd
import requests
from datetime import datetime
from deep_translator import GoogleTranslator
import os

# --- הגדרות ---
DB_FILE = 'food_db_usda.csv'
LOG_FILE = 'daily_log_usda.csv'
USDA_API_KEY = "DEMO_KEY"  # מפתח ציבורי לשימוש סביר

# --- משקלים ממוצעים (נשאר כדי להמיר 'יחידה' לגרמים) ---
# הנתונים מארה"ב מגיעים ל-100 גרם, אנחנו צריכים לדעת כמה שוקלת יחידה
AVERAGE_WEIGHTS = {
    'apple': 180, 'banana': 120, 'orange': 150, 'egg': 60, 
    'bread': 30, 'pita': 100, 'date': 10, 'almond': 1.2,
    'walnut': 5, 'cucumber': 100, 'tomato': 120, 'pepper': 150,
    'chicken breast': 150, 'rice': 150, 'yogurt': 150
}

def load_data():
    if not os.path.exists(DB_FILE):
        pd.DataFrame(columns=['name_he', 'name_en', 'calories', 'protein', 'sugar']).to_csv(DB_FILE, index=False)
    if not os.path.exists(LOG_FILE):
        pd.DataFrame(columns=['date', 'time', 'food', 'amount', 'unit', 'calories', 'protein', 'sugar']).to_csv(LOG_FILE, index=False)
    return pd.read_csv(DB_FILE), pd.read_csv(LOG_FILE)

def translate_to_english(text):
    """תרגום עברית לאנגלית עבור ה-API האמריקאי"""
    try:
        translated = GoogleTranslator(source='auto', target='en').translate(text)
        return translated
    except:
        return text # במקרה חירום מחזיר את המקור

def fetch_from_usda(query_en):
    """
    שאיבת נתונים ממשרד החקלאות האמריקאי (USDA)
    מחפש בסיס נתונים 'SR Legacy' או 'Foundation' שהם המדויקים ביותר לחומרי גלם
    """
    # 1. חיפוש המוצר וקבלת ID
    search_url = f"https://api.nal.usda.gov/fdc/v1/foods/search?api_key={USDA_API_KEY}&query={query_en}&dataType=SR%20Legacy,Foundation&pageSize=3"
    
    try:
        response = requests.get(search_url, timeout=10)
        data = response.json()
        
        if not data.get('foods'):
            return None
            
        # לוקח את התוצאה הראשונה
        food_item = data['foods'][0]
        description = food_item['description']
        
        # שליפת הערכים התזונתיים מתוך רשימת הרכיבים
        # USDA משתמשים בקודים: 208=קלוריות, 203=חלבון, 269=סוכר
        nutrients = food_item['foodNutrients']
        
        cal = 0
        prot = 0
        sugar = 0
        
        for n in nutrients:
            nutrient_id = n.get('nutrientId') # בגרסאות חדשות זה נקרא nutrientId
            value = n.get('value', 0)
            
            # לפעמים ה-ID מגיע בשם אחר, נבדוק גם לפי שמות
            name = n.get('nutrientName', '').lower()
            
            if nutrient_id == 208 or 'energy' in name:
                cal = value
            elif nutrient_id == 203 or 'protein' in name:
                prot = value
            elif nutrient_id == 269 or 'sugar' in name:
                sugar = value
                
        return {
            'name_en': description,
            'calories': float(cal),
            'protein': float(prot),
            'sugar': float(sugar)
        }
        
    except Exception as e:
        print(f"Error: {e}")
        return None

def save_new_food(name_he, name_en, nutrients):
    df = pd.read_csv(DB_FILE)
    new_row = {
        'name_he': name_he, 
        'name_en': name_en,
        'calories': nutrients['calories'], 
        'protein': nutrients['protein'], 
        'sugar': nutrients['sugar']
    }
    df = pd.concat([df, pd.DataFrame([new_row])], ignore_index=True)
    df.to_csv(DB_FILE, index=False)

def get_weight_estimate(name_en):
    """מנסה לנחש משקל לפי השם באנגלית"""
    name_lower = name_en.lower()
    for key, weight in AVERAGE_WEIGHTS.items():
        if key in name_lower:
            return weight
    return 100 # ברירת מחדל

# --- ממשק משתמש ---
st.set_page_config(page_title="ניהול תזונה USDA", page_icon="🇺🇸", layout="centered")
st.markdown("<h1 style='text-align: center;'>מעקב תזונה - מבוסס USDA</h1>", unsafe_allow_html=True)
st.markdown("<p style='text-align: center; color: gray;'>מחובר למאגר משרד החקלאות האמריקאי</p>", unsafe_allow_html=True)

db_df, log_df = load_data()

# --- חישוב יומי ---
today = datetime.now().strftime("%Y-%m-%d")
today_log = log_df[log_df['date'] == today]

c1, c2, c3 = st.columns(3)
c1.metric("קלוריות", f"{today_log['calories'].sum():,.0f}")
c2.metric("חלבון", f"{today_log['protein'].sum():,.1f} גרם")
c3.metric("סוכר", f"{today_log['sugar'].sum():,.1f} גרם")

st.divider()

# --- טופס ---
with st.form("usda_form"):
    col_input, col_amount, col_unit = st.columns([2,1,1])
    
    food_input = col_input.text_input("מה אכלת? (בעברית)")
    amount_input = col_amount.number_input("כמות", 1.0, step=0.5)
    unit_input = col_unit.selectbox("יחידה", ["יחידות", "גרם"])
    
    submit = st.form_submit_button("חפש בארה\"ב והוסף")
    
    if submit and food_input:
        # 1. בדיקה אם קיים כבר בהיסטוריה (כדי לחסוך פניה לאמריקה)
        existing = db_df[db_df['name_he'] == food_input]
        
        nutrients = None
        final_english_name = ""
        
        if not existing.empty:
            row = existing.iloc[0]
            nutrients = {'calories': row['calories'], 'protein': row['protein'], 'sugar': row['sugar']}
            final_english_name = row['name_en']
            st.success(f"נמצא בזיכרון מקומי: {food_input}")
            
        else:
            # 2. תהליך מלא: תרגום -> USDA
            with st.spinner(f"מתרגם '{food_input}' ופונה למשרד החקלאות האמריקאי..."):
                # א. תרגום
                english_term = translate_to_english(food_input)
                # ב. שליפה
                usda_data = fetch_from_usda(english_term)
                
                if usda_data:
                    nutrients = usda_data
                    final_english_name = usda_data['name_en']
                    save_new_food(food_input, final_english_name, nutrients)
                    st.info(f"מקור USDA: {final_english_name}")
                    st.caption(f"קלוריות ל-100 גרם: {nutrients['calories']}")
                else:
                    st.error("לא נמצא במאגר האמריקאי. נסה שם מדויק יותר.")

        # 3. חישוב והוספה
        if nutrients:
            # חישוב משקל
            item_weight = 100
            if unit_input == 'יחידות':
                item_weight = get_weight_estimate(final_english_name)
                # אם זה מוצר שהמערכת לא מכירה את משקלו
                if item_weight == 100 and unit_input == 'יחידות':
                    st.warning(f"שים לב: לא ידוע משקל יחידה של '{final_english_name}', החישוב בוצע לפי 100 גרם.")
            
            # חישוב סופי
            grams = amount_input if unit_input == 'גרם' else amount_input * item_weight
            factor = grams / 100.0
            
            new_entry = {
                'date': datetime.now().strftime("%Y-%m-%d"),
                'time': datetime.now().strftime("%H:%M"),
                'food': food_input,
                'amount': amount_input,
                'unit': unit_input,
                'calories': round(nutrients['calories'] * factor),
                'protein': round(nutrients['protein'] * factor, 1),
                'sugar': round(nutrients['sugar'] * factor, 1)
            }
            
            log_df = pd.read_csv(LOG_FILE)
            log_df = pd.concat([log_df, pd.DataFrame([new_entry])], ignore_index=True)
            log_df.to_csv(LOG_FILE, index=False)
            st.rerun()

if not today_log.empty:
    st.markdown("### יומן אכילה")
    view = today_log[['time', 'food', 'amount', 'unit', 'calories', 'protein', 'sugar']].copy()
    view.columns = ['שעה', 'מוצר', 'כמות', 'יחידה', 'קלוריות', 'חלבון', 'סוכר']
    st.table(view)

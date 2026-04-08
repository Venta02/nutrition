import os
from dotenv import load_dotenv

load_dotenv()

class Config:
    SECRET_KEY = os.environ.get('SECRET_KEY') or 'enhanced-meal-analyzer-secret-2025-auth'
    
    GEMINI_API_KEY = os.environ.get('GEMINI_API_KEY') or 'your-gemini-api-key-here'
    GEMINI_MODEL = 'gemini-2.5-flash'
    
    UPLOAD_FOLDER = 'uploads'
    MAX_CONTENT_LENGTH = 16 * 1024 * 1024 
    
    DATABASE_PATH = os.environ.get('DATABASE_PATH') or 'nutrition_analyzer.db'
    
    RATE_LIMIT_DELAY = 1
    MAX_RETRIES = 3
    
    SESSION_PERMANENT = True
    PERMANENT_SESSION_LIFETIME = 7 * 24 * 60 * 60
    
    SESSION_COOKIE_SECURE = os.environ.get('SESSION_COOKIE_SECURE', 'False').lower() == 'true'
    SESSION_COOKIE_HTTPONLY = True
    SESSION_COOKIE_SAMESITE = 'Lax'
    
    GUEST_ANALYSIS_LIMIT = int(os.environ.get('GUEST_ANALYSIS_LIMIT', '1'))
    GUEST_SESSION_DURATION = 24 * 60 * 60
    
    MAIL_SERVER = os.environ.get('MAIL_SERVER')
    MAIL_PORT = int(os.environ.get('MAIL_PORT', '587'))
    MAIL_USE_TLS = os.environ.get('MAIL_USE_TLS', 'true').lower() in ['true', 'on', '1']
    MAIL_USERNAME = os.environ.get('MAIL_USERNAME')
    MAIL_PASSWORD = os.environ.get('MAIL_PASSWORD')
    MAIL_DEFAULT_SENDER = os.environ.get('MAIL_DEFAULT_SENDER')
    
    DEBUG = os.environ.get('FLASK_DEBUG', 'True').lower() == 'true'
    TESTING = os.environ.get('FLASK_TESTING', 'False').lower() == 'true'

NUTRITION_DB = {
    "white rice": {
        "calories": 130, "protein": 2.7, "carbs": 28.0, "fat": 0.3, "fiber": 0.4,
        "vitamin_a": 0, "vitamin_c": 0, "calcium": 10, "iron": 0.8, "water": 68.4
    },
    "brown rice": {
        "calories": 112, "protein": 2.3, "carbs": 22.0, "fat": 0.9, "fiber": 1.8,
        "vitamin_a": 0, "vitamin_c": 0, "calcium": 10, "iron": 0.5, "water": 72.6
    },
    "chicken": {
        "calories": 165, "protein": 31.0, "carbs": 0.0, "fat": 3.6, "fiber": 0.0,
        "vitamin_a": 11, "vitamin_c": 1.6, "calcium": 11, "iron": 0.7, "water": 65.3
    },
    "pork": {
        "calories": 242, "protein": 26.0, "carbs": 0.0, "fat": 14.0, "fiber": 0.0,
        "vitamin_a": 2, "vitamin_c": 0.7, "calcium": 19, "iron": 0.9, "water": 58.0
    },
    "beef": {
        "calories": 250, "protein": 26.0, "carbs": 0.0, "fat": 15.0, "fiber": 0.0,
        "vitamin_a": 7, "vitamin_c": 0, "calcium": 18, "iron": 2.6, "water": 56.0
    },
    "fish": {
        "calories": 208, "protein": 20.0, "carbs": 0.0, "fat": 12.0, "fiber": 0.0,
        "vitamin_a": 54, "vitamin_c": 0, "calcium": 16, "iron": 0.2, "water": 67.0
    },
    "salmon": {
        "calories": 208, "protein": 20.0, "carbs": 0.0, "fat": 12.0, "fiber": 0.0,
        "vitamin_a": 58, "vitamin_c": 0, "calcium": 12, "iron": 0.8, "water": 67.0
    },
    "eggs": {
        "calories": 155, "protein": 13.0, "carbs": 1.1, "fat": 11.0, "fiber": 0.0,
        "vitamin_a": 140, "vitamin_c": 0, "calcium": 56, "iron": 1.7, "water": 76.0
    },
    "tofu": {
        "calories": 76, "protein": 8.0, "carbs": 1.9, "fat": 4.8, "fiber": 0.3,
        "vitamin_a": 5, "vitamin_c": 0.1, "calcium": 350, "iron": 5.4, "water": 84.0
    },

    "bubble tea": {
        "calories": 278, "protein": 0.9, "carbs": 68.0, "fat": 1.0, "fiber": 0.5,
        "vitamin_a": 0, "vitamin_c": 0, "calcium": 8, "iron": 0.7, "water": 85.0
    },
    "taiwanese beef noodle soup": {
        "calories": 450, "protein": 25.0, "carbs": 55.0, "fat": 15.0, "fiber": 3.0,
        "vitamin_a": 15, "vitamin_c": 5, "calcium": 40, "iron": 3.5, "water": 70.0
    },
    "xiaolongbao": {
        "calories": 42, "protein": 2.8, "carbs": 4.2, "fat": 1.8, "fiber": 0.2,
        "vitamin_a": 5, "vitamin_c": 0, "calcium": 8, "iron": 0.4, "water": 60.0
    },
    "gua bao": {
        "calories": 280, "protein": 12.0, "carbs": 35.0, "fat": 10.0, "fiber": 2.0,
        "vitamin_a": 8, "vitamin_c": 2, "calcium": 45, "iron": 1.8, "water": 55.0
    },
    "taiwanese fried chicken": {
        "calories": 320, "protein": 18.0, "carbs": 15.0, "fat": 22.0, "fiber": 1.0,
        "vitamin_a": 12, "vitamin_c": 1, "calcium": 15, "iron": 1.2, "water": 45.0
    },
    "taiwanese sausage": {
        "calories": 312, "protein": 13.0, "carbs": 3.0, "fat": 27.0, "fiber": 0.0,
        "vitamin_a": 0, "vitamin_c": 0, "calcium": 11, "iron": 1.1, "water": 55.0
    },
    "stinky tofu": {
        "calories": 190, "protein": 12.0, "carbs": 10.0, "fat": 11.0, "fiber": 1.5,
        "vitamin_a": 8, "vitamin_c": 2, "calcium": 280, "iron": 2.8, "water": 65.0
    },
    "taiwanese meatball": {
        "calories": 165, "protein": 8.0, "carbs": 22.0, "fat": 5.0, "fiber": 1.0,
        "vitamin_a": 3, "vitamin_c": 1, "calcium": 20, "iron": 1.0, "water": 62.0
    },
    "oyster omelette": {
        "calories": 240, "protein": 14.0, "carbs": 18.0, "fat": 13.0, "fiber": 1.0,
        "vitamin_a": 85, "vitamin_c": 5, "calcium": 80, "iron": 7.2, "water": 68.0
    },
    "taiwanese popcorn chicken": {
        "calories": 290, "protein": 16.0, "carbs": 12.0, "fat": 20.0, "fiber": 0.5,
        "vitamin_a": 10, "vitamin_c": 1, "calcium": 12, "iron": 1.0, "water": 48.0
    },

    "dan zai noodles": {
        "calories": 380, "protein": 15.0, "carbs": 60.0, "fat": 8.0, "fiber": 2.5,
        "vitamin_a": 12, "vitamin_c": 3, "calcium": 35, "iron": 2.2, "water": 72.0
    },
    "taiwanese minced pork rice": {
        "calories": 420, "protein": 18.0, "carbs": 58.0, "fat": 12.0, "fiber": 1.5,
        "vitamin_a": 8, "vitamin_c": 2, "calcium": 25, "iron": 2.5, "water": 65.0
    },
    "taiwanese rice cake": {
        "calories": 98, "protein": 1.2, "carbs": 22.0, "fat": 0.2, "fiber": 0.8,
        "vitamin_a": 0, "vitamin_c": 0, "calcium": 3, "iron": 0.2, "water": 76.0
    },
    "taiwanese sticky rice": {
        "calories": 116, "protein": 2.4, "carbs": 23.0, "fat": 0.3, "fiber": 1.4,
        "vitamin_a": 0, "vitamin_c": 0, "calcium": 4, "iron": 0.4, "water": 73.0
    },

    "bok choy": {
        "calories": 13, "protein": 1.5, "carbs": 2.2, "fat": 0.2, "fiber": 1.0,
        "vitamin_a": 156, "vitamin_c": 45.0, "calcium": 105, "iron": 0.8, "water": 95.3
    },
    "chinese cabbage": {
        "calories": 16, "protein": 1.2, "carbs": 3.2, "fat": 0.2, "fiber": 1.2,
        "vitamin_a": 16, "vitamin_c": 27.0, "calcium": 77, "iron": 0.3, "water": 94.4
    },
    "chinese broccoli": {
        "calories": 19, "protein": 1.1, "carbs": 4.6, "fat": 0.6, "fiber": 1.2,
        "vitamin_a": 121, "vitamin_c": 93.7, "calcium": 87, "iron": 1.0, "water": 92.3
    },
    "watercress": {
        "calories": 11, "protein": 2.3, "carbs": 1.3, "fat": 0.1, "fiber": 0.5,
        "vitamin_a": 160, "vitamin_c": 43.0, "calcium": 120, "iron": 0.2, "water": 95.1
    },
    "taiwanese lettuce": {
        "calories": 15, "protein": 1.4, "carbs": 2.9, "fat": 0.2, "fiber": 1.3,
        "vitamin_a": 148, "vitamin_c": 9.2, "calcium": 36, "iron": 0.9, "water": 94.6
    },
    "bamboo shoots": {
        "calories": 27, "protein": 2.6, "carbs": 5.2, "fat": 0.3, "fiber": 2.2,
        "vitamin_a": 0, "vitamin_c": 4.0, "calcium": 13, "iron": 0.5, "water": 91.0
    },
    "chinese spinach": {
        "calories": 23, "protein": 2.9, "carbs": 3.6, "fat": 0.4, "fiber": 2.2,
        "vitamin_a": 469, "vitamin_c": 28.1, "calcium": 99, "iron": 2.7, "water": 91.4
    },

    "taiwanese mango": {
        "calories": 60, "protein": 0.8, "carbs": 15.0, "fat": 0.4, "fiber": 1.6,
        "vitamin_a": 54, "vitamin_c": 36.4, "calcium": 11, "iron": 0.2, "water": 83.5
    },
    "dragon fruit": {
        "calories": 60, "protein": 1.2, "carbs": 13.0, "fat": 0.4, "fiber": 3.0,
        "vitamin_a": 0, "vitamin_c": 20.5, "calcium": 8, "iron": 1.9, "water": 87.0
    },
    "taiwanese guava": {
        "calories": 68, "protein": 2.6, "carbs": 14.3, "fat": 1.0, "fiber": 5.4,
        "vitamin_a": 31, "vitamin_c": 228.3, "calcium": 18, "iron": 0.3, "water": 80.8
    },
    "taiwanese papaya": {
        "calories": 43, "protein": 0.5, "carbs": 11.0, "fat": 0.3, "fiber": 1.7,
        "vitamin_a": 47, "vitamin_c": 60.9, "calcium": 20, "iron": 0.3, "water": 88.1
    },
    "lychee": {
        "calories": 66, "protein": 0.8, "carbs": 16.5, "fat": 0.4, "fiber": 1.3,
        "vitamin_a": 0, "vitamin_c": 71.5, "calcium": 5, "iron": 0.3, "water": 82.0
    },
    "longan": {
        "calories": 60, "protein": 1.3, "carbs": 15.1, "fat": 0.1, "fiber": 1.1,
        "vitamin_a": 0, "vitamin_c": 84.0, "calcium": 1, "iron": 0.1, "water": 83.0
    },

    "taiwanese milkfish": {
        "calories": 140, "protein": 20.0, "carbs": 0.0, "fat": 6.2, "fiber": 0.0,
        "vitamin_a": 25, "vitamin_c": 0, "calcium": 50, "iron": 2.0, "water": 72.0
    },
    "taiwanese mackerel": {
        "calories": 205, "protein": 19.0, "carbs": 0.0, "fat": 14.0, "fiber": 0.0,
        "vitamin_a": 40, "vitamin_c": 0, "calcium": 12, "iron": 1.6, "water": 64.0
    },
    "taiwanese shrimp": {
        "calories": 99, "protein": 18.0, "carbs": 0.2, "fat": 1.4, "fiber": 0.0,
        "vitamin_a": 54, "vitamin_c": 2.1, "calcium": 70, "iron": 2.4, "water": 78.0
    },
    "taiwanese squid": {
        "calories": 92, "protein": 15.6, "carbs": 3.1, "fat": 1.4, "fiber": 0.0,
        "vitamin_a": 11, "vitamin_c": 4.7, "calcium": 32, "iron": 0.7, "water": 78.5
    },

    "soy sauce": {
        "calories": 8, "protein": 1.3, "carbs": 0.8, "fat": 0.0, "fiber": 0.1,
        "vitamin_a": 0, "vitamin_c": 0, "calcium": 3, "iron": 0.4, "water": 68.0
    },
    "taiwanese black vinegar": {
        "calories": 18, "protein": 0.0, "carbs": 0.9, "fat": 0.0, "fiber": 0.0,
        "vitamin_a": 0, "vitamin_c": 0, "calcium": 6, "iron": 0.2, "water": 94.0
    },
    "sesame oil": {
        "calories": 884, "protein": 0.0, "carbs": 0.0, "fat": 100.0, "fiber": 0.0,
        "vitamin_a": 0, "vitamin_c": 0, "calcium": 0, "iron": 0.0, "water": 0.0
    },

    "taiwanese pineapple cake": {
        "calories": 85, "protein": 1.0, "carbs": 15.0, "fat": 2.5, "fiber": 0.5,
        "vitamin_a": 5, "vitamin_c": 3, "calcium": 8, "iron": 0.3, "water": 25.0
    },
    "taiwanese mochi": {
        "calories": 96, "protein": 1.0, "carbs": 22.0, "fat": 0.2, "fiber": 0.4,
        "vitamin_a": 0, "vitamin_c": 0, "calcium": 2, "iron": 0.4, "water": 44.0
    },
    "shaved ice": {
        "calories": 38, "protein": 0.0, "carbs": 10.0, "fat": 0.0, "fiber": 0.0,
        "vitamin_a": 0, "vitamin_c": 0, "calcium": 0, "iron": 0.0, "water": 90.0
    },
    "taiwanese douhua": {
        "calories": 57, "protein": 4.8, "carbs": 4.6, "fat": 2.7, "fiber": 0.1,
        "vitamin_a": 3, "vitamin_c": 0, "calcium": 111, "iron": 1.7, "water": 86.0
    },

    "ginger": {
        "calories": 80, "protein": 1.8, "carbs": 18.0, "fat": 0.8, "fiber": 2.0,
        "vitamin_a": 0, "vitamin_c": 5.0, "calcium": 16, "iron": 0.6, "water": 79.0
    },
    "garlic": {
        "calories": 149, "protein": 6.4, "carbs": 33.1, "fat": 0.5, "fiber": 2.1,
        "vitamin_a": 0, "vitamin_c": 31.2, "calcium": 181, "iron": 1.7, "water": 59.0
    },
    "green onion": {
        "calories": 32, "protein": 1.8, "carbs": 7.3, "fat": 0.2, "fiber": 2.6,
        "vitamin_a": 50, "vitamin_c": 18.8, "calcium": 72, "iron": 1.5, "water": 89.8
    },
    "cilantro": {
        "calories": 23, "protein": 2.1, "carbs": 3.7, "fat": 0.5, "fiber": 2.8,
        "vitamin_a": 337, "vitamin_c": 27.0, "calcium": 67, "iron": 1.8, "water": 92.2
    },

    "bread": {
        "calories": 247, "protein": 13.0, "carbs": 41.0, "fat": 4.2, "fiber": 6.0,
        "vitamin_a": 0, "vitamin_c": 0, "calcium": 95, "iron": 3.7, "water": 36.0
    },
    "pasta": {
        "calories": 131, "protein": 5.0, "carbs": 25.0, "fat": 1.1, "fiber": 1.8,
        "vitamin_a": 0, "vitamin_c": 0, "calcium": 7, "iron": 1.3, "water": 66.0
    },
    "noodles": {
        "calories": 138, "protein": 4.5, "carbs": 25.0, "fat": 2.1, "fiber": 1.2,
        "vitamin_a": 0, "vitamin_c": 0, "calcium": 8, "iron": 1.7, "water": 68.0
    },
    "spinach": {
        "calories": 23, "protein": 2.9, "carbs": 3.6, "fat": 0.4, "fiber": 2.2,
        "vitamin_a": 469, "vitamin_c": 28.1, "calcium": 99, "iron": 2.7, "water": 91.4
    },
    "carrots": {
        "calories": 41, "protein": 0.9, "carbs": 10.0, "fat": 0.2, "fiber": 2.8,
        "vitamin_a": 835, "vitamin_c": 5.9, "calcium": 33, "iron": 0.3, "water": 88.3
    },
    "tomatoes": {
        "calories": 18, "protein": 0.9, "carbs": 3.9, "fat": 0.2, "fiber": 1.2,
        "vitamin_a": 42, "vitamin_c": 13.7, "calcium": 10, "iron": 0.3, "water": 94.5
    },
    "broccoli": {
        "calories": 34, "protein": 2.8, "carbs": 7.0, "fat": 0.4, "fiber": 2.6,
        "vitamin_a": 31, "vitamin_c": 89.2, "calcium": 47, "iron": 0.7, "water": 89.3
    },
    "banana": {
        "calories": 89, "protein": 1.1, "carbs": 23.0, "fat": 0.3, "fiber": 2.6,
        "vitamin_a": 3, "vitamin_c": 8.7, "calcium": 5, "iron": 0.3, "water": 74.9
    },
    "apple": {
        "calories": 52, "protein": 0.3, "carbs": 14.0, "fat": 0.2, "fiber": 2.4,
        "vitamin_a": 3, "vitamin_c": 4.6, "calcium": 6, "iron": 0.1, "water": 85.6
    },
    "orange": {
        "calories": 47, "protein": 0.9, "carbs": 12.0, "fat": 0.1, "fiber": 2.4,
        "vitamin_a": 11, "vitamin_c": 53.2, "calcium": 40, "iron": 0.1, "water": 86.8
    },
    "milk": {
        "calories": 42, "protein": 3.4, "carbs": 5.0, "fat": 1.0, "fiber": 0.0,
        "vitamin_a": 46, "vitamin_c": 0, "calcium": 113, "iron": 0.0, "water": 87.0
    },
    "cheese": {
        "calories": 113, "protein": 7.0, "carbs": 1.0, "fat": 9.0, "fiber": 0.0,
        "vitamin_a": 84, "vitamin_c": 0, "calcium": 200, "iron": 0.1, "water": 37.0
    },
    "yogurt": {
        "calories": 59, "protein": 10.0, "carbs": 3.6, "fat": 0.4, "fiber": 0.0,
        "vitamin_a": 1, "vitamin_c": 0.5, "calcium": 110, "iron": 0.1, "water": 85.0
    },
    "almonds": {
        "calories": 579, "protein": 21.0, "carbs": 22.0, "fat": 50.0, "fiber": 12.0,
        "vitamin_a": 0, "vitamin_c": 0, "calcium": 269, "iron": 3.9, "water": 4.4
    },
    "peanuts": {
        "calories": 567, "protein": 26.0, "carbs": 16.0, "fat": 49.0, "fiber": 8.5,
        "vitamin_a": 0, "vitamin_c": 0, "calcium": 92, "iron": 4.6, "water": 6.5
    },
}

DAILY_TARGETS = {
    "calories": 2000,
    "protein": 50,
    "carbs": 250,
    "fat": 65,
    "fiber": 25,
    "vitamin_a": 900,      # mcg
    "vitamin_c": 90,       # mg
    "calcium": 1000,       # mg
    "iron": 18,           # mg
    "water": 2000         # ml
}

ACTIVITY_MULTIPLIERS = {
    'sedentary': 1.2,
    'lightly_active': 1.375,
    'moderately_active': 1.55,
    'very_active': 1.725,
    'extra_active': 1.9
}

FITNESS_GOAL_ADJUSTMENTS = {
    'lose_weight': -500,    
    'maintain_weight': 0,   
    'gain_weight': 500,     
    'build_muscle': 300     
}
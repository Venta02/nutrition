import re
import json
import random
import sqlite3
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple
from config import NUTRITION_DB, DAILY_TARGETS
from database import get_db_connection

class NutriBot:
    def __init__(self, db_path, gemini_model=None):
        self.db_path = db_path
        self.gemini_model = gemini_model
        
        self.nutrition_knowledge = {
            "high_protein_foods": [
                "chicken breast", "fish", "eggs", "tofu", "greek yogurt", 
                "lentils", "quinoa", "almonds", "cottage cheese", "beans"
            ],
            "low_calorie_foods": [
                "spinach", "broccoli", "cucumber", "tomatoes", "berries",
                "zucchini", "cauliflower", "lettuce", "mushrooms", "peppers"
            ],
            "high_fiber_foods": [
                "oats", "chia seeds", "beans", "apples", "broccoli",
                "quinoa", "sweet potato", "avocado", "pears", "artichokes"
            ],
            "healthy_fats": [
                "avocado", "olive oil", "nuts", "seeds", "fatty fish",
                "coconut oil", "olives", "nut butters", "dark chocolate"
            ]
        }
        
        self.diet_plans = {
            "weight_loss": {
                "breakfast": ["oatmeal with berries", "greek yogurt with nuts", "veggie omelet"],
                "lunch": ["grilled chicken salad", "quinoa bowl", "vegetable soup"],
                "dinner": ["baked fish with vegetables", "stir-fry with tofu", "lean meat with sweet potato"],
                "snacks": ["apple with almond butter", "carrot sticks", "handful of nuts"]
            },
            "muscle_gain": {
                "breakfast": ["protein smoothie", "eggs with whole grain toast", "greek yogurt parfait"],
                "lunch": ["chicken breast with rice", "protein-rich quinoa bowl", "tuna sandwich"],
                "dinner": ["salmon with sweet potato", "beef with vegetables", "tofu stir-fry"],
                "snacks": ["protein shake", "nuts and seeds", "cheese with crackers"]
            },
            "balanced": {
                "breakfast": ["whole grain cereal", "fruit and yogurt", "avocado toast"],
                "lunch": ["balanced salad", "soup and sandwich", "rice bowl"],
                "dinner": ["grilled protein with vegetables", "pasta with lean meat", "fish with quinoa"],
                "snacks": ["fresh fruit", "vegetable sticks", "small portion nuts"]
            }
        }
        
        self.quick_responses = {
            "greeting": [
                "Hi! I'm NutriBot your personal nutrition assistant! How can I help you today?",
                "Hello! Ready to boost your nutrition game? What would you like to know?",
                "Hey there! I'm here to help with all your nutrition questions!"
            ],
            "thanks": [
                "You're welcome! Keep up the great nutrition tracking!",
                "Happy to help! Remember, consistency is key to reaching your goals!",
                "Glad I could assist! Feel free to ask more nutrition questions anytime!"
            ],
            "motivation": [
                "You're doing great! Every healthy choice counts towards your goals!",
                "Keep it up! Small steps lead to big changes in nutrition!",
                "Awesome progress! Your body will thank you for these healthy choices!"
            ]
        }

    def get_user_context(self, user_id):
        try:
            conn = get_db_connection(self.db_path)
            cursor = conn.cursor()
            
            today = datetime.now().date()
            cursor.execute('''
                SELECT total_calories, total_protein, total_carbs, total_fat, total_fiber, meal_count
                FROM daily_nutrition 
                WHERE user_id = ? AND date = ?
            ''', (user_id, today))
            
            today_data = cursor.fetchone()
            
            cursor.execute('''
                SELECT analysis_result, created_at 
                FROM meal_analyses 
                WHERE user_id = ? 
                ORDER BY created_at DESC 
                LIMIT 5
            ''', (user_id,))
            
            recent_meals = cursor.fetchall()
            
            week_ago = datetime.now().date() - timedelta(days=7)
            cursor.execute('''
                SELECT AVG(total_calories), AVG(total_protein), COUNT(*) as days
                FROM daily_nutrition 
                WHERE user_id = ? AND date >= ?
            ''', (user_id, week_ago))
            
            weekly_data = cursor.fetchone()
            
            conn.close()
            
            context = {
                "today": {
                    "calories": today_data[0] if today_data else 0,
                    "protein": today_data[1] if today_data else 0,
                    "carbs": today_data[2] if today_data else 0,
                    "fat": today_data[3] if today_data else 0,
                    "fiber": today_data[4] if today_data else 0,
                    "meals": today_data[5] if today_data else 0
                },
                "weekly": {
                    "avg_calories": weekly_data[0] if weekly_data[0] else 0,
                    "avg_protein": weekly_data[1] if weekly_data[1] else 0,
                    "days_tracked": weekly_data[2] if weekly_data else 0
                },
                "recent_meals": []
            }
            
            for meal_data in recent_meals:
                try:
                    analysis = json.loads(meal_data[0])
                    context["recent_meals"].append({
                        "description": analysis.get("meal_description", ""),
                        "calories": analysis.get("total_nutrition", {}).get("calories", 0),
                        "timestamp": meal_data[1]
                    })
                except:
                    continue
            
            return context
            
        except Exception as e:
            print(f"Error getting user context: {e}")
            return {"today": {}, "weekly": {}, "recent_meals": []}

    def analyze_intent(self, message):
        message_lower = message.lower()
        
        intents = {
            "greeting": r"(hi|hello|hey|good morning|good afternoon)",
            "thanks": r"(thank|thanks|thx|appreciate)",
            "calorie_question": r"(calorie|kcal|energy)",
            "protein_question": r"(protein|muscle|building|gym)",
            "weight_loss": r"(lose weight|weight loss|diet|slim|fat loss)",
            "weight_gain": r"(gain weight|bulk|mass|muscle gain)",
            "meal_suggestion": r"(suggest|recommend|what to eat|meal|food)",
            "progress_check": r"(progress|how am i|doing|track)",
            "food_info": r"(is.*healthy|good for|bad for|nutrition)",
            "recipe": r"(recipe|how to cook|prepare)",
            "health_goal": r"(goal|target|achieve|want to)",
            "motivation": r"(motivate|encourage|support|hard)"
        }
        
        entities = {
            "food_items": [],
            "numbers": [],
            "time_references": []
        }
        
        food_keywords = ["chicken", "fish", "rice", "bread", "egg", "fruit", "vegetable", 
                        "protein", "carb", "fat", "salad", "soup", "smoothie"]
        entities["food_items"] = [food for food in food_keywords if food in message_lower]
        
        numbers = re.findall(r'\d+', message)
        entities["numbers"] = [int(n) for n in numbers]
        
        time_words = ["today", "yesterday", "week", "month", "breakfast", "lunch", "dinner"]
        entities["time_references"] = [time for time in time_words if time in message_lower]
        
        detected_intent = "general"
        for intent, pattern in intents.items():
            if re.search(pattern, message_lower):
                detected_intent = intent
                break
        
        return detected_intent, entities

    def generate_response(self, message, user_id, user_context):
        intent, entities = self.analyze_intent(message)
        
        response = {
            "text": "",
            "suggestions": [],
            "actions": [],
            "data": None
        }
        
        if intent == "greeting":
            response["text"] = random.choice(self.quick_responses["greeting"])
            response["suggestions"] = [
                "Check my progress today",
                "Suggest healthy meals",
                "What should I eat to reach my protein goal?",
                "Help me lose weight"
            ]
            
        elif intent == "thanks":
            response["text"] = random.choice(self.quick_responses["thanks"])
            
        elif intent == "progress_check":
            response = self.generate_progress_response(user_context)
            
        elif intent == "calorie_question":
            response = self.generate_calorie_response(user_context, entities)
            
        elif intent == "protein_question":
            response = self.generate_protein_response(user_context, entities)
            
        elif intent == "weight_loss":
            response = self.generate_weight_loss_response(user_context)
            
        elif intent == "meal_suggestion":
            response = self.generate_meal_suggestion(user_context, entities)
            
        elif intent == "motivation":
            response["text"] = random.choice(self.quick_responses["motivation"])
            
        else:
            if self.gemini_model:
                response = self.generate_ai_response(message, user_context)
            else:
                response["text"] = "I can help you with nutrition questions! Try asking about your progress, meal suggestions, or health goals."
                response["suggestions"] = [
                    "How's my nutrition today?",
                    "Suggest high protein foods",
                    "Help me plan meals"
                ]
        
        return response

    def generate_progress_response(self, context):
        today = context.get("today", {})
        calories = today.get("calories", 0)
        protein = today.get("protein", 0)
        meals = today.get("meals", 0)
        
        response = {
            "text": "**Today's Progress:**\n\n",
            "suggestions": [],
            "actions": ["view_dashboard"],
            "data": today
        }
        
        calorie_target = 2000
        calorie_percent = (calories / calorie_target) * 100
        
        if calorie_percent < 50:
            response["text"] += f"Calories: {int(calories)}/{calorie_target} ({calorie_percent:.0f}%)\n"
            response["text"] += "You're quite low on calories today. Let's add some nutritious meals!\n\n"
            response["suggestions"] = ["Suggest calorie-rich meals", "What's for lunch?"]
        elif calorie_percent > 100:
            response["text"] += f"Calories: {int(calories)}/{calorie_target} ({calorie_percent:.0f}%)\n"
            response["text"] += "You've reached your calorie goal! Consider lighter options for remaining meals.\n\n"
        else:
            response["text"] += f"Calories: {int(calories)}/{calorie_target} ({calorie_percent:.0f}%)\n"
            response["text"] += "Great progress on calories!\n\n"
        
        protein_target = 50
        protein_percent = (protein / protein_target) * 100
        
        response["text"] += f"Protein: {protein:.1f}g/{protein_target}g ({protein_percent:.0f}%)\n"
        
        if protein_percent < 60:
            response["text"] += "Consider adding more protein to your meals!\n\n"
            response["suggestions"].append("High protein food ideas")
        
        response["text"] += f"Meals logged: {meals}\n\n"
        
        if meals < 3:
            response["text"] += "**Tip:** Try to log at least 3 meals daily for better tracking!"
            response["actions"].append("take_photo")
        
        return response

    def generate_calorie_response(self, context, entities):
        today = context.get("today", {})
        current_calories = today.get("calories", 0)
        target_calories = 2000
        
        remaining = target_calories - current_calories
        
        response = {
            "text": "**Calorie Status:**\n\n",
            "suggestions": [],
            "actions": [],
            "data": {"current": current_calories, "target": target_calories, "remaining": remaining}
        }
        
        if remaining > 500:
            response["text"] += f"You have {int(remaining)} calories remaining today.\n\n"
            response["text"] += "**Meal suggestions to reach your goal:**\n"
            response["text"] += "• Balanced lunch: Rice + protein + vegetables (600 kcal)\n"
            response["text"] += "• Healthy snack: Nuts + fruit (200 kcal)\n"
            response["text"] += "• Light dinner: Fish + salad (400 kcal)"
            
            response["suggestions"] = ["Meal ideas for lunch", "Healthy snack options"]
            
        elif remaining > 0:
            response["text"] += f"You have {int(remaining)} calories left for today.\n\n"
            response["text"] += "**Light meal suggestions:**\n"
            response["text"] += f"• Greek yogurt with berries ({remaining//2} kcal)\n"
            response["text"] += f"• Small salad with protein ({remaining//2} kcal)"
            
        else:
            response["text"] += "You've reached your calorie goal for today!\n\n"
            response["text"] += "**Tips for the rest of the day:**\n"
            response["text"] += "• Stay hydrated\n"
            response["text"] += "• Choose lighter options if still hungry\n"
            response["text"] += "• Focus on vegetables and lean proteins"
        
        return response

    def generate_protein_response(self, context, entities):
        today = context.get("today", {})
        current_protein = today.get("protein", 0)
        target_protein = 50
        
        response = {
            "text": "**Protein Status:**\n\n",
            "suggestions": [],
            "actions": [],
            "data": {"current": current_protein, "target": target_protein}
        }
        
        remaining = target_protein - current_protein
        
        if remaining > 20:
            response["text"] += f"You need {remaining:.1f}g more protein today.\n\n"
            response["text"] += "**High-protein food suggestions:**\n"
            response["text"] += "• Chicken breast (100g = 31g protein)\n"
            response["text"] += "• Greek yogurt (200g = 20g protein)\n"
            response["text"] += "• Eggs (2 large = 12g protein)\n"
            response["text"] += "• Tofu (100g = 8g protein)"
            
            response["suggestions"] = ["Protein-rich recipes", "Vegetarian protein sources"]
            
        elif remaining > 0:
            response["text"] += f"Almost there! You need {remaining:.1f}g more protein.\n\n"
            response["text"] += "**Quick protein boosts:**\n"
            response["text"] += f"• Handful of almonds ({remaining//2:.0f}g protein)\n"
            response["text"] += f"• Protein smoothie ({remaining:.0f}g protein)"
            
        else:
            response["text"] += "Excellent! You've met your protein goal!\n\n"
            response["text"] += "**Benefits you're getting:**\n"
            response["text"] += "• Muscle maintenance and growth\n"
            response["text"] += "• Better satiety and appetite control\n"
            response["text"] += "• Improved metabolism"
        
        return response

    def generate_meal_suggestion(self, context, entities):
        today = context.get("today", {})
        current_calories = today.get("calories", 0)
        remaining_calories = 2000 - current_calories
        
        current_hour = datetime.now().hour
        if current_hour < 10:
            meal_type = "breakfast"
        elif current_hour < 15:
            meal_type = "lunch"
        elif current_hour < 18:
            meal_type = "snacks"
        else:
            meal_type = "dinner"
        
        if "breakfast" in entities.get("time_references", []):
            meal_type = "breakfast"
        elif "lunch" in entities.get("time_references", []):
            meal_type = "lunch"
        elif "dinner" in entities.get("time_references", []):
            meal_type = "dinner"
        
        response = {
            "text": f"**{meal_type.title()} Suggestions:**\n\n",
            "suggestions": [],
            "actions": ["take_photo"],
            "data": {"meal_type": meal_type, "calories_remaining": remaining_calories}
        }
        
        diet_type = "balanced"
        if remaining_calories > 800:
            diet_type = "muscle_gain"
        elif remaining_calories < 400:
            diet_type = "weight_loss"
        
        meals = self.diet_plans.get(diet_type, {}).get(meal_type, [])
        
        for i, meal in enumerate(meals[:3], 1):
            calorie_estimate = self.estimate_meal_calories(meal, meal_type)
            response["text"] += f"{i}. **{meal.title()}** (~{calorie_estimate} kcal)\n"
        
        response["text"] += f"\nYou have ~{int(remaining_calories)} calories remaining today."
        
        response["suggestions"] = [
            f"Recipe for {meals[0] if meals else 'healthy meal'}",
            "Nutrition tips",
            "Take photo when ready"
        ]
        
        return response

    def estimate_meal_calories(self, meal, meal_type):
        base_calories = {
            "breakfast": 350,
            "lunch": 500,
            "dinner": 450,
            "snacks": 150
        }
        
        meal_lower = meal.lower()
        multiplier = 1.0
        
        if any(word in meal_lower for word in ["protein", "chicken", "fish", "meat"]):
            multiplier += 0.3
        if any(word in meal_lower for word in ["nuts", "oil", "avocado", "cheese"]):
            multiplier += 0.2
        if any(word in meal_lower for word in ["salad", "vegetables", "soup"]):
            multiplier -= 0.2
        
        return int(base_calories.get(meal_type, 400) * multiplier)

    def generate_weight_loss_response(self, context):
        today = context.get("today", {})
        weekly = context.get("weekly", {})
        
        response = {
            "text": "**Weight Loss Guidance:**\n\n",
            "suggestions": [],
            "actions": [],
            "data": {}
        }
        
        avg_calories = weekly.get("avg_calories", 0)
        
        if avg_calories > 2200:
            response["text"] += "**Current Analysis:** Your average intake is quite high.\n\n"
            response["text"] += "**Recommendations:**\n"
            response["text"] += "• Target 1800-2000 calories daily\n"
            response["text"] += "• Increase vegetable portions\n"
            response["text"] += "• Choose lean proteins\n"
            response["text"] += "• Reduce portion sizes gradually"
            
        elif avg_calories < 1400:
            response["text"] += "**Current Analysis:** Your intake might be too low.\n\n"
            response["text"] += "**Recommendations:**\n"
            response["text"] += "• Aim for 1500-1800 calories for sustainable loss\n"
            response["text"] += "• Don't skip meals\n"
            response["text"] += "• Include healthy fats\n"
            response["text"] += "• Focus on nutrient-dense foods"
            
        else:
            response["text"] += "**Current Analysis:** Your calorie range looks good!\n\n"
            response["text"] += "**Optimization tips:**\n"
            response["text"] += "• Increase protein to 30% of calories\n"
            response["text"] += "• Add more fiber-rich foods\n"
            response["text"] += "• Stay consistent with tracking\n"
            response["text"] += "• Consider meal timing"
        
        response["text"] += "\n**Remember:** Slow and steady wins the race!"
        
        response["suggestions"] = [
            "Low-calorie meal ideas",
            "High-fiber foods",
            "Healthy snack options",
            "Track my progress"
        ]
        
        return response

    def generate_ai_response(self, message, context):
        try:
            prompt = f"""
            You are NutriBot, a friendly nutrition assistant. Answer this nutrition question briefly and helpfully.
            
            User's current context:
            - Today's calories: {context.get('today', {}).get('calories', 0)}
            - Today's protein: {context.get('today', {}).get('protein', 0)}g
            - Meals logged today: {context.get('today', {}).get('meals', 0)}
            
            User question: {message}
            
            Provide a helpful, encouraging response in 2-3 sentences. Be specific to their situation.
            """
            
            response_obj = self.gemini_model.generate_content(prompt)
            
            if response_obj and response_obj.text:
                return {
                    "text": response_obj.text.strip(),
                    "suggestions": ["Tell me more", "Check my progress", "Meal suggestions"],
                    "actions": [],
                    "data": None
                }
        except Exception as e:
            print(f"AI response error: {e}")
        
        return {
            "text": "I'd love to help with that! Could you ask about specific nutrition topics like calories, protein, meal suggestions, or your progress?",
            "suggestions": ["Check my progress", "Meal ideas", "Nutrition tips"],
            "actions": [],
            "data": None
        }
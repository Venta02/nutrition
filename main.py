from flask import Flask, request, jsonify, render_template, session, g, redirect
from flask_cors import CORS
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address
import google.generativeai as genai
from PIL import Image
import io
import base64
import json
import os
import time
import hashlib
from datetime import datetime, timedelta
from typing import Dict, List, Optional
import logging
from werkzeug.utils import secure_filename
import uuid
import statistics
import bcrypt

from config import Config, NUTRITION_DB, DAILY_TARGETS
from database import init_database, get_db_connection, get_user_profile
from nutribot import NutriBot
from auth import AuthManager, GuestManager, login_required, auth_or_guest_allowed, get_current_user

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = Flask(__name__)
CORS(app)

app.config.update(
    SECRET_KEY=Config.SECRET_KEY,
    SESSION_PERMANENT=True,
    PERMANENT_SESSION_LIFETIME=timedelta(days=7),
    SESSION_COOKIE_SECURE=Config.SESSION_COOKIE_SECURE,
    SESSION_COOKIE_HTTPONLY=Config.SESSION_COOKIE_HTTPONLY,
    SESSION_COOKIE_SAMESITE=Config.SESSION_COOKIE_SAMESITE,
    SESSION_REFRESH_EACH_REQUEST=True
)

app.permanent_session_lifetime = timedelta(days=7) 

limiter = Limiter(
    key_func=get_remote_address,
    app=app,
    default_limits=["500 per day", "100 per hour", "20 per minute"]
)

app.config.from_object(Config)

auth_manager = AuthManager(app.config['DATABASE_PATH'])
guest_manager = GuestManager(app.config['DATABASE_PATH'])


@app.route('/api/update-daily-nutrition', methods=['POST'])
@login_required
def api_update_daily_nutrition():
    try:
        data = request.get_json()
        if not data:
            return jsonify({'error': 'No data provided'}), 400
        
        current_user = get_current_user()
        user_id = current_user['user_id']
        
        nutrition_data = data.get('nutrition', {})
        update_daily_nutrition(user_id, nutrition_data)
        
        return jsonify({
            'success': True,
            'message': 'Daily nutrition updated successfully'
        })
        
    except Exception as e:
        logger.error(f"API update daily nutrition error: {str(e)}")
        return jsonify({'error': 'Failed to update daily nutrition'}), 500

@app.route('/api/debug/analyze-test', methods=['POST'])
def debug_analyze_test():
    """Debug endpoint untuk test nutrition calculation"""
    try:
        test_foods = [
            {'name': 'chicken', 'estimated_portion': '1 serving'},
            {'name': 'rice', 'estimated_portion': '1 bowl'},
            {'name': 'spinach', 'estimated_portion': '1 cup'}
        ]
        
        enhanced_foods = []
        for food in test_foods:
            nutrition = get_nutrition_info(food['name'])
            portion_multiplier = estimate_portion_multiplier(food.get('estimated_portion', ''))
            
            enhanced_nutrition = {}
            for key, value in nutrition.items():
                enhanced_nutrition[key] = round(value * portion_multiplier, 1)
            
            enhanced_foods.append({
                'name': food['name'],
                'nutrition': enhanced_nutrition,
                'portion_multiplier': portion_multiplier
            })
        
        total_nutrition = {
            'calories': round(sum(food['nutrition']['calories'] for food in enhanced_foods), 1),
            'protein': round(sum(food['nutrition']['protein'] for food in enhanced_foods), 1),
            'carbs': round(sum(food['nutrition']['carbs'] for food in enhanced_foods), 1),
            'fat': round(sum(food['nutrition']['fat'] for food in enhanced_foods), 1),
            'fiber': round(sum(food['nutrition']['fiber'] for food in enhanced_foods), 1),
            'vitamin_a': round(sum(food['nutrition'].get('vitamin_a', 0) for food in enhanced_foods), 1),
            'vitamin_c': round(sum(food['nutrition'].get('vitamin_c', 0) for food in enhanced_foods), 1),
            'calcium': round(sum(food['nutrition'].get('calcium', 0) for food in enhanced_foods), 1),
            'iron': round(sum(food['nutrition'].get('iron', 0) for food in enhanced_foods), 1),
            'water': round(sum(food['nutrition'].get('water', 0) for food in enhanced_foods), 1)
        }
        
        current_user = get_current_user()
        if current_user and not current_user['is_guest']:
            user_id = current_user['user_id']
            
            try:
                update_daily_nutrition(user_id, total_nutrition)
                save_status = "SUCCESS"
                save_error = None
            except Exception as e:
                save_status = "FAILED"
                save_error = str(e)
        else:
            save_status = "SKIPPED - Guest user"
            save_error = None
            user_id = None
        
        return jsonify({
            'test_foods': test_foods,
            'enhanced_foods': enhanced_foods,
            'total_nutrition': total_nutrition,
            'save_status': save_status,
            'save_error': save_error,
            'user_id': user_id
        })
        
    except Exception as e:
        logger.error(f"Debug analyze test error: {e}")
        return jsonify({'error': str(e)}), 500

@app.before_request
def before_request():
    if app.debug:
        logger.info(f"Request to {request.endpoint} - Session: {dict(session)}")
        logger.info(f"Is authenticated: {session.get('is_authenticated', False)}")

if app.config['GEMINI_API_KEY'] == 'your-gemini-api-key-here':
    logger.warning("GEMINI_API_KEY not set! Please set in .env file")
    print("WARNING: GEMINI_API_KEY not found in .env file!")
    print("Please add your API key to .env file")
else:
    genai.configure(api_key=app.config['GEMINI_API_KEY'])
    model = genai.GenerativeModel(app.config['GEMINI_MODEL'])
    logger.info("Gemini AI configured successfully")

os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)
os.makedirs('logs', exist_ok=True)

def log_api_usage(endpoint, success=True, response_time=0):
    try:
        conn = get_db_connection(app.config['DATABASE_PATH'])
        cursor = conn.cursor()
        
        current_user = get_current_user()
        user_id = current_user['user_id'] if current_user and not current_user['is_guest'] else None
        
        cursor.execute('''
            INSERT INTO api_usage (ip_address, endpoint, success, response_time, user_id)
            VALUES (?, ?, ?, ?, ?)
        ''', (request.remote_addr, endpoint, success, response_time, user_id))
        
        conn.commit()
        conn.close()
    except Exception as e:
        logger.error(f"Failed to log API usage: {e}")

def get_user_daily_targets(user_id):
    """Get user's personalized daily targets"""
    if user_id.startswith('guest_') or user_id.startswith('landing_guest_'):
        return DAILY_TARGETS
    
    user_profile = get_user_profile(app.config['DATABASE_PATH'], user_id)
    if user_profile:
        return {
            'calories': user_profile.get('daily_calorie_goal', DAILY_TARGETS['calories']),
            'protein': user_profile.get('daily_protein_goal', DAILY_TARGETS['protein']),
            'carbs': user_profile.get('daily_carbs_goal', DAILY_TARGETS['carbs']),
            'fat': user_profile.get('daily_fat_goal', DAILY_TARGETS['fat']),
            'fiber': user_profile.get('daily_fiber_goal', DAILY_TARGETS['fiber']),
            'vitamin_a': user_profile.get('daily_vitamin_a_goal', DAILY_TARGETS.get('vitamin_a', 900)),
            'vitamin_c': user_profile.get('daily_vitamin_c_goal', DAILY_TARGETS.get('vitamin_c', 90)),
            'calcium': user_profile.get('daily_calcium_goal', DAILY_TARGETS.get('calcium', 1000)),
            'iron': user_profile.get('daily_iron_goal', DAILY_TARGETS.get('iron', 18)),
            'water': user_profile.get('daily_water_goal', DAILY_TARGETS.get('water', 2000))
        }
    return DAILY_TARGETS

def ensure_clean_daily_start(user_id):
    try:
        today = datetime.now().date()
        conn = get_db_connection(app.config['DATABASE_PATH'])
        cursor = conn.cursor()
        
        cursor.execute('''
            SELECT COUNT(*) as count FROM daily_nutrition 
            WHERE user_id = ? AND date = ?
        ''', (user_id, today))
        
        today_count = cursor.fetchone()['count']
        cursor.execute('''
            SELECT COUNT(*) as count FROM meal_analyses 
            WHERE user_id = ? AND DATE(created_at) = ?
        ''', (user_id, today))
        
        analyses_today = cursor.fetchone()['count']
        
        logger.info(f"Daily check - User {user_id}: {today_count} daily records, {analyses_today} analyses today")
        
        if today_count > 0 and analyses_today == 0:
            logger.warning(f"Cleaning stale daily data for user {user_id} on {today}")
            cursor.execute('''
                DELETE FROM daily_nutrition 
                WHERE user_id = ? AND date = ?
            ''', (user_id, today))
            conn.commit()
            logger.info("âœ… Stale daily data cleaned")
        
        conn.close()
        return analyses_today == 0 
        
    except Exception as e:
        logger.error(f"Error ensuring clean daily start: {e}")
        return False

def update_daily_nutrition(user_id, nutrition_data):
    if user_id.startswith('guest_') or user_id.startswith('landing_guest_'):
        logger.info(f"Skipping nutrition tracking for guest user: {user_id}")
        return
    
    logger.info(f"Attempting to update daily nutrition for user: {user_id}")
    logger.info(f"Nutrition data received: {nutrition_data}")
    
    conn = None
    try:
        today = datetime.now().date()
        conn = get_db_connection(app.config['DATABASE_PATH'])
        cursor = conn.cursor()
        
        cursor.execute('''
            SELECT * FROM daily_nutrition WHERE user_id = ? AND date = ?
        ''', (user_id, today))
        
        existing = cursor.fetchone()
        logger.info(f"Existing data for today: {dict(existing) if existing else 'None'}")
        
        if existing:
            logger.info("Updating existing daily nutrition record")
            cursor.execute('''
                UPDATE daily_nutrition SET
                    total_calories = total_calories + ?,
                    total_protein = total_protein + ?,
                    total_carbs = total_carbs + ?,
                    total_fat = total_fat + ?,
                    total_fiber = total_fiber + ?,
                    total_vitamin_a = total_vitamin_a + ?,
                    total_vitamin_c = total_vitamin_c + ?,
                    total_calcium = total_calcium + ?,
                    total_iron = total_iron + ?,
                    total_water = total_water + ?,
                    meal_count = meal_count + 1,
                    updated_at = CURRENT_TIMESTAMP
                WHERE user_id = ? AND date = ?
            ''', (
                nutrition_data.get('calories', 0),
                nutrition_data.get('protein', 0),
                nutrition_data.get('carbs', 0),
                nutrition_data.get('fat', 0),
                nutrition_data.get('fiber', 0),
                nutrition_data.get('vitamin_a', 0),
                nutrition_data.get('vitamin_c', 0),
                nutrition_data.get('calcium', 0),
                nutrition_data.get('iron', 0),
                nutrition_data.get('water', 0),
                user_id,
                today
            ))
            logger.info(f"UPDATE executed, rows affected: {cursor.rowcount}")
        else:
            logger.info("Creating new daily nutrition record")
            cursor.execute('''
                INSERT INTO daily_nutrition 
                (user_id, date, total_calories, total_protein, total_carbs, total_fat, total_fiber,
                 total_vitamin_a, total_vitamin_c, total_calcium, total_iron, total_water, meal_count)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 1)
            ''', (
                user_id,
                today,
                nutrition_data.get('calories', 0),
                nutrition_data.get('protein', 0),
                nutrition_data.get('carbs', 0),
                nutrition_data.get('fat', 0),
                nutrition_data.get('fiber', 0),
                nutrition_data.get('vitamin_a', 0),
                nutrition_data.get('vitamin_c', 0),
                nutrition_data.get('calcium', 0),
                nutrition_data.get('iron', 0),
                nutrition_data.get('water', 0)
            ))
            logger.info(f"INSERT executed, last row ID: {cursor.lastrowid}")
        
        conn.commit()
        logger.info("Daily nutrition update committed successfully")
        
        cursor.execute('SELECT * FROM daily_nutrition WHERE user_id = ? AND date = ?', (user_id, today))
        updated_data = cursor.fetchone()
        logger.info(f"Verification - Updated data: {dict(updated_data) if updated_data else 'None'}")
        
    except Exception as e:
        logger.error(f"Failed to update daily nutrition: {e}")
        logger.exception("Full traceback:")
        if conn:
            conn.rollback()
            logger.info("Database transaction rolled back")
        raise e 
    finally:
        if conn:
            conn.close()

@app.route('/api/debug/gemini', methods=['GET'])
def debug_gemini():
    """Debug endpoint untuk cek konfigurasi Gemini"""
    return jsonify({
        'gemini_configured': app.config['GEMINI_API_KEY'] != 'your-gemini-api-key-here',
        'api_key_length': len(app.config['GEMINI_API_KEY']) if app.config['GEMINI_API_KEY'] != 'your-gemini-api-key-here' else 0,
        'api_key_prefix': app.config['GEMINI_API_KEY'][:10] + '...' if app.config['GEMINI_API_KEY'] != 'your-gemini-api-key-here' else 'not configured',
        'model': app.config['GEMINI_MODEL'],
        'env_file_exists': os.path.exists('.env'),
        'env_vars': {
            'GEMINI_API_KEY_exists': 'GEMINI_API_KEY' in os.environ,
            'GEMINI_API_KEY_length': len(os.environ.get('GEMINI_API_KEY', ''))
        }
    })

@app.route('/api/debug/nutrition-today', methods=['GET'])
def debug_nutrition_today():

    try:
        current_user = get_current_user()
        if not current_user:
            return jsonify({'error': 'Not authenticated'}), 401
        
        user_id = current_user['user_id']
        today = datetime.now().date()
        
        conn = get_db_connection(app.config['DATABASE_PATH'])
        cursor = conn.cursor()
        
        cursor.execute('SELECT * FROM daily_nutrition WHERE user_id = ? AND date = ?', (user_id, today))
        today_data = cursor.fetchone()
        
        cursor.execute('SELECT * FROM daily_nutrition WHERE user_id = ? ORDER BY date DESC LIMIT 5', (user_id,))
        all_data = cursor.fetchall()
        
        cursor.execute('PRAGMA table_info(daily_nutrition)')
        table_structure = cursor.fetchall()
        
        conn.close()
        
        return jsonify({
            'user_id': user_id,
            'today': str(today),
            'today_data': dict(today_data) if today_data else None,
            'recent_data': [dict(row) for row in all_data],
            'table_structure': [dict(row) for row in table_structure]
        })
        
    except Exception as e:
        logger.error(f"Debug nutrition error: {e}")
        return jsonify({'error': str(e)}), 500
@app.route('/api/dashboard-simple', methods=['GET'])
@login_required
def get_dashboard_simple():
    try:
        current_user = get_current_user()
        user_id = current_user['user_id']
        today = datetime.now().date()
        
        conn = get_db_connection(app.config['DATABASE_PATH'])
        cursor = conn.cursor()
        
        cursor.execute('''
            SELECT * FROM daily_nutrition 
            WHERE user_id = ? AND date = ?
        ''', (user_id, today))
        
        today_data = cursor.fetchone()
        conn.close()
        
        if today_data:
            return jsonify({
                'success': True,
                'today_progress': {
                    'calories': {
                        'current': today_data.get('total_calories', 0),
                        'target': 2000,
                        'percentage': round((today_data.get('total_calories', 0) / 2000) * 100, 1)
                    },
                    'protein': {
                        'current': today_data.get('total_protein', 0),
                        'target': 50,
                        'percentage': round((today_data.get('total_protein', 0) / 50) * 100, 1)
                    },
                    'carbs': {
                        'current': today_data.get('total_carbs', 0),
                        'target': 250,
                        'percentage': round((today_data.get('total_carbs', 0) / 250) * 100, 1)
                    },
                    'fat': {
                        'current': today_data.get('total_fat', 0),
                        'target': 65,
                        'percentage': round((today_data.get('total_fat', 0) / 65) * 100, 1)
                    }
                },
                'raw_data': dict(today_data)
            })
        else:
            return jsonify({
                'success': True,
                'today_progress': {
                    'calories': {'current': 0, 'target': 2000, 'percentage': 0},
                    'protein': {'current': 0, 'target': 50, 'percentage': 0},
                    'carbs': {'current': 0, 'target': 250, 'percentage': 0},
                    'fat': {'current': 0, 'target': 65, 'percentage': 0}
                },
                'message': 'No data for today'
            })
            
    except Exception as e:
        logger.error(f"Simple dashboard error: {e}")
        return jsonify({'error': str(e)}), 500
    
@app.route('/api/test-dashboard', methods=['GET'])
def test_dashboard():
    return jsonify({
        'status': 'Dashboard API working',
        'test_data': {
            'calories': {'current': 1073.9, 'target': 2000, 'percentage': 53.7},
            'protein': {'current': 113.8, 'target': 50, 'percentage': 227.6}
        },
        'timestamp': datetime.now().isoformat()
    })

@app.route('/api/debug/last-analysis', methods=['GET'])  
def debug_last_analysis():
    try:
        current_user = get_current_user()
        if not current_user:
            return jsonify({'error': 'Not authenticated'}), 401
        
        user_id = current_user['user_id']
        
        conn = get_db_connection(app.config['DATABASE_PATH'])
        cursor = conn.cursor()
        
        cursor.execute('''
            SELECT analysis_result, created_at, confidence_score 
            FROM meal_analyses 
            WHERE user_id = ? 
            ORDER BY created_at DESC 
            LIMIT 3
        ''', (user_id,))
        analyses = cursor.fetchall()
        
        conn.close()
        
        result = []
        for analysis in analyses:
            try:
                data = json.loads(analysis['analysis_result'])
                result.append({
                    'timestamp': analysis['created_at'],
                    'confidence': analysis['confidence_score'],
                    'total_nutrition': data.get('total_nutrition', {}),
                    'food_count': len(data.get('identified_foods', []))
                })
            except:
                result.append({
                    'timestamp': analysis['created_at'],
                    'error': 'Failed to parse analysis'
                })
        
        return jsonify({
            'user_id': user_id,
            'recent_analyses': result
        })
        
    except Exception as e:
        logger.error(f"Debug analysis error: {e}")
        return jsonify({'error': str(e)}), 500
    
@app.route('/')
def serve_landing_page():
    """Serve landing page"""
    return render_template('landing.html')

@app.route('/app')
def serve_app_page():
    """Serve app page - cek authentication di client side"""
    try:
        is_authenticated = session.get('is_authenticated', False)
        user_id = session.get('user_id')
        
        logger.info(f"App page access - Auth: {is_authenticated}, User: {user_id}")
        logger.info(f"Session data: {dict(session)}")
        
        return render_template('app.html')
        
    except Exception as e:
        logger.error(f"Error in serve_app_page: {e}")
        return render_template('app.html')

@app.route('/index') 
def serve_old_index():
    """Redirect old index to new landing page"""
    return redirect('/')

@app.route('/api/auth/register', methods=['POST'])
@limiter.limit("5 per minute")
def register():

    try:
        data = request.get_json()
        if not data:
            return jsonify({'success': False, 'message': 'No data provided'}), 400
        
        email = data.get('email', '').strip().lower()
        password = data.get('password', '')
        name = data.get('name', '').strip()
        profile_data = data.get('profile', {})
        
        if not all([email, password, name]):
            return jsonify({'success': False, 'message': 'Email, password, and name are required'}), 400
        
        result = auth_manager.register_user(email, password, name, profile_data)
        
        if result['success']:
            result['redirect_url'] = '/app'
                
        return jsonify(result), 201 if result['success'] else 400
        
    except Exception as e:
        logger.error(f"Registration error: {e}")
        return jsonify({'success': False, 'message': 'Registration failed'}), 500

@app.route('/api/auth/login', methods=['POST'])
@limiter.limit("10 per minute")
def login():
    try:
        data = request.get_json()
        if not data:
            return jsonify({'success': False, 'message': 'No data provided'}), 400
        
        email = data.get('email', '').strip().lower()
        password = data.get('password', '')
        
        if not all([email, password]):
            return jsonify({'success': False, 'message': 'Email and password are required'}), 400
        
        result = auth_manager.login_user(email, password)
        
        if result['success']:
            result['redirect_url'] = '/app'
        
        return jsonify(result), 200 if result['success'] else 401
        
    except Exception as e:
        logger.error(f"Login error: {e}")
        return jsonify({'success': False, 'message': 'Login failed'}), 500

@app.route('/api/auth/logout', methods=['POST'])
def logout():
    try:
        logger.info(f"Logout request from IP: {request.remote_addr}")
        
        if not session.get('is_authenticated') and not session.get('user_id'):
            logger.info("Logout attempt but no active session found")
            return jsonify({
                'success': True, 
                'message': 'No active session to logout',
                'was_authenticated': False
            }), 200
        
        user_id = session.get('user_id')
        session_token = session.get('session_token')
        
        try:
            session.clear()
            session.modified = True
            logger.info(f"Session cleared for user {user_id}")
        except Exception as session_error:
            logger.error(f"Error clearing session: {session_error}")
        if session_token:
            try:
                conn = get_db_connection(app.config['DATABASE_PATH'])
                cursor = conn.cursor()
                cursor.execute('UPDATE user_sessions SET is_active = 0 WHERE session_token = ?', (session_token,))
                conn.commit()
                conn.close()
                logger.debug(f"Session token deactivated: {session_token}")
            except Exception as db_error:
                logger.warning(f"Could not deactivate session token: {db_error}")
        response_data = {
            'success': True,
            'message': 'Logged out successfully',
            'user_id': user_id,
            'timestamp': datetime.now().isoformat()
        }
        
        logger.info(f"Logout completed successfully for user {user_id}")
        return jsonify(response_data), 200
            
    except Exception as e:
        logger.error(f"Logout endpoint error: {e}")

        try:
            session.clear()
            session.modified = True
            logger.info("Session cleared after error")

            return jsonify({
                'success': True,
                'message': 'Logged out (session cleared after error)',
                'had_errors': True
            }), 200
            
        except Exception as session_error:
            logger.error(f"Critical error - could not clear session: {session_error}")
            
            return jsonify({
                'success': False,
                'message': 'Please refresh your browser to complete logout',
                'error': 'session_clear_failed'
            }), 500

@app.route('/api/auth/profile', methods=['GET'])
@login_required
def get_profile():
    """Get user profile dengan error handling yang lebih baik"""
    try:
        current_user = get_current_user()
        logger.info(f"Profile request from user {current_user['user_id']}")
        
        user_profile = get_user_profile(app.config['DATABASE_PATH'], current_user['user_id'])
        
        if user_profile:
            user_profile.pop('password_hash', None)
            
            logger.info(f"Profile retrieved successfully for user {current_user['user_id']}")
            return jsonify({
                'success': True, 
                'profile': user_profile
            })
        else:
            logger.error(f"Profile not found for user {current_user['user_id']}")
            return jsonify({
                'success': False, 
                'message': 'Profile not found'
            }), 404
            
    except Exception as e:
        logger.error(f"Profile retrieval error: {e}")
        return jsonify({
            'success': False, 
            'message': 'Failed to retrieve profile',
            'error': str(e) if app.debug else 'Internal server error'
        }), 500
@app.route('/api/auth/profile', methods=['PUT'])
@login_required
def update_profile():
    try:
        logger.info(f"Profile update request from user {g.current_user_id}")
        
        data = request.get_json()
        if not data:
            logger.warning("No data provided in profile update request")
            return jsonify({'success': False, 'message': 'No data provided'}), 400
        
        logger.info(f"Profile update data received: {data}")
        
        if not data.get('name') or not data['name'].strip():
            return jsonify({'success': False, 'message': 'Name is required'}), 400
        
        profile_data = {}
        
        profile_data['name'] = data['name'].strip()
        
        if data.get('age'):
            try:
                age = int(data['age'])
                if 13 <= age <= 120:
                    profile_data['age'] = age
                else:
                    return jsonify({'success': False, 'message': 'Age must be between 13 and 120'}), 400
            except (ValueError, TypeError):
                return jsonify({'success': False, 'message': 'Invalid age format'}), 400
        
        if data.get('height'):
            try:
                height = int(data['height'])
                if 100 <= height <= 250:
                    profile_data['height'] = height
                else:
                    return jsonify({'success': False, 'message': 'Height must be between 100-250 cm'}), 400
            except (ValueError, TypeError):
                return jsonify({'success': False, 'message': 'Invalid height format'}), 400
        
        if data.get('weight'):
            try:
                weight = int(data['weight'])
                if 30 <= weight <= 300:
                    profile_data['weight'] = weight
                else:
                    return jsonify({'success': False, 'message': 'Weight must be between 30-300 kg'}), 400
            except (ValueError, TypeError):
                return jsonify({'success': False, 'message': 'Invalid weight format'}), 400
        
        if data.get('gender') and data['gender'] in ['male', 'female', 'other']:
            profile_data['gender'] = data['gender']
        
        if data.get('activity_level') and data['activity_level'] in [
            'sedentary', 'lightly_active', 'moderately_active', 'very_active', 'extra_active'
        ]:
            profile_data['activity_level'] = data['activity_level']
        
        if data.get('fitness_goal') and data['fitness_goal'] in [
            'lose_weight', 'maintain_weight', 'gain_weight', 'build_muscle'
        ]:
            profile_data['fitness_goal'] = data['fitness_goal']
        
        logger.info(f"Cleaned profile data: {profile_data}")
        
        current_user = get_current_user()
        result = auth_manager.update_user_profile(current_user['user_id'], profile_data)
        
        logger.info(f"Profile update result: {result}")
        
        if result['success']:
            updated_profile = get_user_profile(app.config['DATABASE_PATH'], current_user['user_id'])
            if updated_profile:
                updated_profile.pop('password_hash', None)
                
                if 'name' in profile_data:
                    session['user_name'] = profile_data['name']
                    session.modified = True
                    logger.info(f"Session updated with new name: {profile_data['name']}")
                
                return jsonify({
                    'success': True,
                    'message': 'Profile updated successfully',
                    'profile': updated_profile
                }), 200
            else:
                logger.error("Could not retrieve updated profile")
                return jsonify({
                    'success': True,
                    'message': 'Profile updated but could not retrieve updated data'
                }), 200
        else:
            logger.error(f"Profile update failed: {result['message']}")
            return jsonify(result), 400
        
    except Exception as e:
        logger.error(f"Profile update error: {e}")
        logger.exception("Full profile update error traceback:")
        return jsonify({
            'success': False, 
            'message': 'Profile update failed due to server error',
            'error': str(e) if app.debug else 'Internal server error'
        }), 500
    
@app.route('/api/auth/status', methods=['GET'])
def auth_status():
    """Check authentication status dengan error handling"""
    try:
        if app.debug:
            logger.info(f"Auth status check - Session: {dict(session)}")
        
        is_authenticated = session.get('is_authenticated', False)
        user_id = session.get('user_id')
        user_name = session.get('user_name')
        
        if is_authenticated and user_id:
            user_data = {
                'user_id': user_id,
                'name': user_name,
                'is_guest': False
            }
            
            return jsonify({
                'authenticated': True,
                'user': user_data
            })
        else:
            return jsonify({
                'authenticated': False,
                'user': None,
                'debug_info': {
                    'session_exists': bool(session),
                    'has_user_id': bool(session.get('user_id')),
                    'is_authenticated_flag': session.get('is_authenticated', False)
                } if app.debug else None
            })
            
    except Exception as e:
        logger.error(f"Error in auth_status: {e}")
        return jsonify({
            'authenticated': False,
            'user': None,
            'error': str(e) if app.debug else 'Internal error'
        }), 500

@app.route('/api/debug/session', methods=['GET'])
def debug_session():
    if not app.debug:
        return jsonify({'error': 'Not available in production'}), 403
    
    return jsonify({
        'session_data': dict(session),
        'session_permanent': session.permanent,
        'session_new': session.new,
        'session_modified': session.modified,
        'user_id': session.get('user_id'),
        'user_name': session.get('user_name'),
        'is_authenticated': session.get('is_authenticated', False),
        'session_token': session.get('session_token')
    })

@app.route('/api/guest/check-limit', methods=['GET'])
def check_guest_limit():
    try:
        ip_address = request.remote_addr
        can_use_trial = guest_manager.check_landing_guest_limit(ip_address)
        
        return jsonify({
            'can_use_trial': can_use_trial,
            'message': 'Guest trial available' if can_use_trial else 'Guest trial already used'
        })
        
    except Exception as e:
        logger.error(f"Guest limit check error: {e}")
        return jsonify({'can_use_trial': False, 'message': 'Error checking limit'}), 500

def get_image_hash(image_data):
    return hashlib.md5(image_data).hexdigest()

def allowed_file(filename):
    ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif', 'bmp', 'webp'}
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

def estimate_portion_multiplier(portion_description):
    portion_lower = portion_description.lower()
    
    if any(word in portion_lower for word in ['small', 'little', 'tiny', 'mini']):
        return 0.5
    elif any(word in portion_lower for word in ['large', 'big', 'huge', 'jumbo']):
        return 1.5
    elif any(word in portion_lower for word in ['medium', 'regular', 'normal']):
        return 1.0
    elif 'plate' in portion_lower:
        return 1.2
    elif 'bowl' in portion_lower:
        return 0.8
    elif any(word in portion_lower for word in ['slice', 'piece', 'serving']):
        return 0.7
    elif 'cup' in portion_lower:
        return 0.6
    elif 'tablespoon' in portion_lower:
        return 0.2
    
    return 1.0

def get_nutrition_info(food_name):
    food_lower = food_name.lower()
    
    if food_lower in NUTRITION_DB:
        nutrition = NUTRITION_DB[food_lower].copy()
    else:
        nutrition = None
        for db_food, nutrition_data in NUTRITION_DB.items():
            if food_lower in db_food or db_food in food_lower:
                nutrition = nutrition_data.copy()
                break
        
        if not nutrition:
            if any(word in food_lower for word in ['vegetable', 'greens', 'salad']):
                nutrition = {
                    "calories": 25, "protein": 2.0, "carbs": 5.0, "fat": 0.3, "fiber": 2.0,
                    "vitamin_a": 100, "vitamin_c": 15, "calcium": 30, "iron": 1.0, "water": 85.0
                }
            elif any(word in food_lower for word in ['fruit', 'berry']):
                nutrition = {
                    "calories": 50, "protein": 0.8, "carbs": 13.0, "fat": 0.2, "fiber": 2.0,
                    "vitamin_a": 10, "vitamin_c": 20, "calcium": 10, "iron": 0.3, "water": 80.0
                }
            elif any(word in food_lower for word in ['meat', 'protein']):
                nutrition = {
                    "calories": 200, "protein": 25.0, "carbs": 0.0, "fat": 10.0, "fiber": 0.0,
                    "vitamin_a": 5, "vitamin_c": 1, "calcium": 15, "iron": 2.0, "water": 65.0
                }
            elif any(word in food_lower for word in ['rice', 'grain', 'bread']):
                nutrition = {
                    "calories": 130, "protein": 3.0, "carbs": 28.0, "fat": 0.5, "fiber": 1.0,
                    "vitamin_a": 0, "vitamin_c": 0, "calcium": 10, "iron": 0.8, "water": 70.0
                }
            else:
                nutrition = {
                    "calories": 100, "protein": 5.0, "carbs": 15.0, "fat": 3.0, "fiber": 2.0,
                    "vitamin_a": 10, "vitamin_c": 5, "calcium": 20, "iron": 1.0, "water": 75.0
                }
    
    required_keys = ['calories', 'protein', 'carbs', 'fat', 'fiber', 'vitamin_a', 'vitamin_c', 'calcium', 'iron', 'water']
    for key in required_keys:
        if key not in nutrition:
            nutrition[key] = 0
            logger.warning(f"Missing nutrition key '{key}' for food '{food_name}', using default value 0")
    
    logger.debug(f"Nutrition for '{food_name}': {nutrition}")
    return nutrition

def create_food_analysis_prompt():
    return """Analyze this food image and provide results in exact JSON format.

Identify all visible foods and classify them into these 6 groups:
1. Whole Grains: rice, bread, pasta, noodles, oats, quinoa, cereals
2. Protein-Rich Foods: chicken, fish, eggs, meat, tofu, tempeh, beans as protein
3. Vegetables: leafy greens, carrots, tomatoes, broccoli, spinach, etc.
4. Fruits: fresh fruits, dried fruits, fruit juices
5. Dairy: milk, cheese, yogurt, butter
6. Nuts/Seeds: almonds, peanuts, seeds (as snacks/toppings)

Expected JSON format:
{
    "identified_foods": [
        {
            "name": "food_name_in_english",
            "food_group": "one_of_the_6_groups_above",
            "estimated_portion": "portion_description_in_english",
            "confidence": confidence_value_0_to_100,
            "estimated_calories": estimated_calories_integer,
            "estimated_protein": estimated_protein_grams
        }
    ],
    "meal_description": "meal_description_in_english",
    "cooking_methods": ["cooking_methods"],
    "overall_confidence": overall_confidence_0_to_100
}

Ensure:
- Use common English food names
- Food group classification must be accurate according to the 6 groups
- Realistic calorie and protein estimates based on visual assessment
- Accurate confidence scores
- Clear portion descriptions (examples: "1 plate", "2 slices", "1 bowl")

Provide only JSON, no other text."""


@app.route('/api/health', methods=['GET'])
def health_check():
    api_status = "configured" if app.config['GEMINI_API_KEY'] != 'your-gemini-api-key-here' else "not_configured"
    
    try:
        conn = get_db_connection(app.config['DATABASE_PATH'])
        cursor = conn.cursor()
        cursor.execute('SELECT COUNT(*) as count FROM meal_analyses')
        total_analyses = cursor.fetchone()['count']
        cursor.execute('SELECT COUNT(*) as count FROM users WHERE is_active = TRUE')
        total_users = cursor.fetchone()['count']
        conn.close()
    except:
        total_analyses = 0
        total_users = 0
    
    return jsonify({
        'status': 'healthy',
        'timestamp': datetime.now().isoformat(),
        'version': '3.0.0',
        'api_status': api_status,
        'database': 'connected' if os.path.exists(app.config['DATABASE_PATH']) else 'not_found',
        'total_analyses': total_analyses,
        'total_users': total_users,
        'features': ['nutrition_tracking', 'user_authentication', 'guest_mode', 'daily_goals', 'meal_history', 'progress_analytics', 'chatbot', 'landing_page']
    })

@app.route('/api/analyze', methods=['POST'])
@limiter.limit("10 per minute")
def analyze_meal():
    start_time = time.time()
    
    try:
        if app.config['GEMINI_API_KEY'] == 'your-gemini-api-key-here':
            return jsonify({'error': 'Gemini API key not configured. Please set GEMINI_API_KEY in .env file'}), 500
        
        if 'image' not in request.files:
            return jsonify({'error': 'No image provided'}), 400
        
        file = request.files['image']
        if file.filename == '':
            return jsonify({'error': 'No image selected'}), 400
        
        if not allowed_file(file.filename):
            return jsonify({'error': 'Invalid file type. Please use JPG, PNG, or other image formats'}), 400
        
        is_landing_guest = request.headers.get('X-Landing-Guest', 'false').lower() == 'true'
        
        if is_landing_guest:
            ip_address = request.remote_addr
            
            if not guest_manager.check_landing_guest_limit(ip_address):
                return jsonify({
                    'error': 'Guest trial limit reached. Please register for unlimited access.',
                    'guest_limit_reached': True,
                    'register_required': True
                }), 403
            
            guest_manager.record_landing_guest_usage(ip_address)
            
            user_id = f"landing_guest_{ip_address}_{int(time.time())}"
            is_guest = True
        else:
            current_user = get_current_user()
            if not current_user:
                return jsonify({'error': 'Authentication required', 'login_required': True}), 401
            
            user_id = current_user['user_id']
            is_guest = current_user['is_guest']
            
            if is_guest:
                session_id = user_id.replace('guest_', '')
                if not guest_manager.check_guest_limit(session_id):
                    return jsonify({
                        'error': 'Guest analysis limit reached. Please register to continue.',
                        'guest_limit_reached': True,
                        'register_required': True
                    }), 403
                guest_manager.increment_guest_usage(session_id)
        
        meal_type = request.form.get('meal_type', 'general')
        
        image_data = file.read()
        image_hash = get_image_hash(image_data)
        
        if not is_guest and not is_landing_guest:
            conn = None
            try:
                conn = get_db_connection(app.config['DATABASE_PATH'])
                cursor = conn.cursor()
                cursor.execute('''
                    SELECT analysis_result, id FROM meal_analyses 
                    WHERE image_hash = ? AND user_id = ?
                ''', (image_hash, user_id))
                cached_result = cursor.fetchone()
                
                if cached_result:
                    logger.info(f"Returning cached result for user {user_id}")
                    result = json.loads(cached_result['analysis_result'])
                    result['from_cache'] = True
                    result['analysis_id'] = cached_result['id']
                    
                    conn.close()
                    return jsonify(result)
                    
            except Exception as e:
                logger.error(f"Database error during cache check: {e}")
                if conn:
                    conn.close()
            finally:
                if conn:
                    conn.close()
        
        image = Image.open(io.BytesIO(image_data))
        
        if image.mode in ('RGBA', 'LA', 'P'):
            image = image.convert('RGB')
        
        if image.width > 1024 or image.height > 1024:
            image.thumbnail((1024, 1024), Image.Resampling.LANCZOS)
        
        prompt = create_food_analysis_prompt()
        
        analysis_data = None
        for attempt in range(app.config['MAX_RETRIES']):
            try:
                response = model.generate_content([prompt, image])
                
                if response and response.text:
                    response_text = response.text.strip()
                    
                    if response_text.startswith("```json"):
                        response_text = response_text[7:]
                    if response_text.endswith("```"):
                        response_text = response_text[:-3]
                    
                    response_text = response_text.strip()
                    analysis_data = json.loads(response_text)
                    break
                    
            except Exception as e:
                logger.error(f"Gemini API error (attempt {attempt + 1}): {str(e)}")
                if attempt == app.config['MAX_RETRIES'] - 1:
                    raise e
                time.sleep(2 ** attempt)
        
        if not analysis_data:
            raise Exception("Failed to get valid response from AI")
        
        enhanced_foods = []
        seen_foods = set()

        for food in analysis_data.get('identified_foods', []):
            food_key = f"{food['name'].lower().strip()}_{food.get('food_group', '').lower().strip()}"
            
            if food_key in seen_foods:
                continue
            
            seen_foods.add(food_key)
            
            nutrition = get_nutrition_info(food['name'])
            portion_multiplier = estimate_portion_multiplier(food.get('estimated_portion', ''))
            
            enhanced_food = {
                **food,
                'nutrition': {
                    'calories': round(nutrition['calories'] * portion_multiplier, 1),
                    'protein': round(nutrition['protein'] * portion_multiplier, 1),
                    'carbs': round(nutrition['carbs'] * portion_multiplier, 1),
                    'fat': round(nutrition['fat'] * portion_multiplier, 1),
                    'fiber': round(nutrition['fiber'] * portion_multiplier, 1),
                    'vitamin_a': round(nutrition['vitamin_a'] * portion_multiplier, 1),
                    'vitamin_c': round(nutrition['vitamin_c'] * portion_multiplier, 1),
                    'calcium': round(nutrition['calcium'] * portion_multiplier, 1),
                    'iron': round(nutrition['iron'] * portion_multiplier, 1),
                    'water': round(nutrition['water'] * portion_multiplier, 1)
                },
                'portion_multiplier': portion_multiplier
            }
            enhanced_foods.append(enhanced_food)

        logger.info(f"Processed {len(enhanced_foods)} unique foods from {len(analysis_data.get('identified_foods', []))} total foods")
                
        all_food_groups = ['Whole Grains', 'Protein-Rich Foods', 'Vegetables', 'Fruits', 'Dairy', 'Nuts/Seeds']
        present_groups = list(set(food['food_group'] for food in enhanced_foods))
        missing_groups = [group for group in all_food_groups if group not in present_groups]
        
        total_nutrition = {
            'calories': round(sum(food['nutrition']['calories'] for food in enhanced_foods), 1),
            'protein': round(sum(food['nutrition']['protein'] for food in enhanced_foods), 1),
            'carbs': round(sum(food['nutrition']['carbs'] for food in enhanced_foods), 1),
            'fat': round(sum(food['nutrition']['fat'] for food in enhanced_foods), 1),
            'fiber': round(sum(food['nutrition']['fiber'] for food in enhanced_foods), 1),
            'vitamin_a': round(sum(food['nutrition'].get('vitamin_a', 0) for food in enhanced_foods), 1),
            'vitamin_c': round(sum(food['nutrition'].get('vitamin_c', 0) for food in enhanced_foods), 1),
            'calcium': round(sum(food['nutrition'].get('calcium', 0) for food in enhanced_foods), 1),
            'iron': round(sum(food['nutrition'].get('iron', 0) for food in enhanced_foods), 1),
            'water': round(sum(food['nutrition'].get('water', 0) for food in enhanced_foods), 1)
        }
        
        logger.info(f"Calculated total nutrition: {total_nutrition}")
        
        daily_targets = get_user_daily_targets(user_id)
        
        recommendations = []
        health_insights = []
        
        if missing_groups:
            group_suggestions = {
                'Whole Grains': 'Add carbohydrates: brown rice, whole wheat bread, oats',
                'Protein-Rich Foods': 'Add protein: chicken, fish, eggs, tofu, beans',
                'Vegetables': 'Add vegetables: spinach, carrots, broccoli',
                'Fruits': 'Add fruits: banana, apple, orange',
                'Dairy': 'Add dairy: milk, cheese, yogurt',
                'Nuts/Seeds': 'Add nuts/seeds: almonds, chia seeds'
            }
            
            for group in missing_groups:
                if group in group_suggestions:
                    recommendations.append(group_suggestions[group])
        else:
            recommendations.append("Complete meal! All food groups represented")
        
        protein_target = daily_targets['protein']
        if total_nutrition['protein'] < protein_target * 0.3:
            health_insights.append("Consider adding more protein for muscle health")
        elif total_nutrition['protein'] > protein_target * 0.8:
            health_insights.append("High protein content - great for muscle building")
        
        if total_nutrition['fiber'] < 8:
            health_insights.append("Add high-fiber foods for digestive health")
        elif total_nutrition['fiber'] > 15:
            health_insights.append("Excellent fiber content for digestion")
        
        calorie_target = daily_targets['calories']
        if total_nutrition['calories'] > calorie_target * 0.4:
            health_insights.append("High calorie meal - consider portion control")
        elif total_nutrition['calories'] < calorie_target * 0.125:
            health_insights.append("Low calorie meal - might need more food")
        else:
            health_insights.append("Well-balanced calorie content")
        
        if total_nutrition['vitamin_a'] < daily_targets['vitamin_a'] * 0.3:
            health_insights.append("ðŸ¥• Low Vitamin A - add carrots, spinach, or sweet potatoes")
        else:
            health_insights.append("âœ… Good Vitamin A for eye health")

        if total_nutrition['vitamin_c'] < daily_targets['vitamin_c'] * 0.3:
            health_insights.append("ðŸŠ Low Vitamin C - add citrus fruits or vegetables")
        else:
            health_insights.append("âœ… Good Vitamin C for immune system")

        if total_nutrition['calcium'] < daily_targets['calcium'] * 0.3:
            health_insights.append("ðŸ¥› Low calcium - consider dairy products or leafy greens")
        else:
            health_insights.append("âœ… Good calcium content for bone health")

        if total_nutrition['iron'] < daily_targets['iron'] * 0.25:
            health_insights.append("ðŸ¥© Low iron - add red meat, spinach, or lentils")
        else:
            health_insights.append("âœ… Adequate iron for oxygen transport")

        water_percentage = (total_nutrition['water'] / daily_targets['water']) * 100
        if water_percentage < 15:
            health_insights.append("ðŸ’§ Low water content - drink more fluids and eat water-rich foods")
        else:
            health_insights.append("âœ… Good hydration from food sources")
        daily_progress = {}
        if not is_guest and not is_landing_guest:
            conn = None
            try:
                today = datetime.now().date()
                conn = get_db_connection(app.config['DATABASE_PATH'])
                cursor = conn.cursor()
                cursor.execute('''
                    SELECT * FROM daily_nutrition WHERE user_id = ? AND date = ?
                ''', (user_id, today))
                daily_data = cursor.fetchone()
                
                if daily_data:
                    current_calories = daily_data['total_calories'] + total_nutrition['calories']
                    current_protein = daily_data['total_protein'] + total_nutrition['protein']
                    
                    daily_progress = {
                        'current_calories': round(current_calories, 1),
                        'current_protein': round(current_protein, 1),
                        'calories_percentage': round((current_calories / daily_targets['calories']) * 100, 1),
                        'protein_percentage': round((current_protein / daily_targets['protein']) * 100, 1),
                        'meal_count': daily_data['meal_count'] + 1
                    }
                else:
                    daily_progress = {
                        'current_calories': total_nutrition['calories'],
                        'current_protein': total_nutrition['protein'],
                        'calories_percentage': round((total_nutrition['calories'] / daily_targets['calories']) * 100, 1),
                        'protein_percentage': round((total_nutrition['protein'] / daily_targets['protein']) * 100, 1),
                        'meal_count': 1
                    }
                    
                conn.close()
            except Exception as e:
                logger.error(f"Failed to calculate daily progress: {e}")
                daily_progress = {}
            finally:
                if conn:
                    conn.close()
        
        result = {
            'success': True,
            'identified_foods': enhanced_foods,
            'meal_description': analysis_data.get('meal_description', ''),
            'cooking_methods': analysis_data.get('cooking_methods', []),
            'meal_type': meal_type,
            'present_food_groups': present_groups,
            'missing_food_groups': missing_groups,
            'total_nutrition': total_nutrition,
            'daily_progress': daily_progress,
            'daily_targets': daily_targets,
            'completeness_score': round(len(present_groups) / len(all_food_groups) * 100),
            'health_score': min(100, round(
                (total_nutrition['protein'] / protein_target * 25) +
                (total_nutrition['fiber'] / 15 * 25) +
                (len(present_groups) / 6 * 25) +
                (min(total_nutrition['calories'] / (calorie_target * 0.25), 1) * 25)
            )),
            'recommendations': recommendations,
            'health_insights': health_insights,
            'overall_confidence': analysis_data.get('overall_confidence', 0),
            'analysis_timestamp': datetime.now().isoformat(),
            'from_cache': False,
            'is_guest': is_guest,
            'is_landing_guest': is_landing_guest
        }
        
        if is_landing_guest:
            result['guest_info'] = {
                'message': 'Great! You\'ve tried our AI analysis. Register for unlimited access and progress tracking!',
                'register_to_continue': True
            }
        elif is_guest:
            result['guest_info'] = {
                'message': 'This is your free trial analysis! Register for unlimited access and progress tracking.',
                'analyses_remaining': 0,
                'register_to_continue': True
            }
        
        analysis_id = None
        analysis_id = None
        if not is_guest and not is_landing_guest:
            logger.info(f"Saving analysis for registered user: {user_id}")
            conn = None
            try:
                conn = get_db_connection(app.config['DATABASE_PATH'])
                cursor = conn.cursor()
                
                cursor.execute('''
                    INSERT INTO meal_analyses (user_id, session_id, image_hash, meal_type, analysis_result, confidence_score, ip_address, user_agent)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                ''', (
                    user_id,
                    session.get('session_token', str(uuid.uuid4())),
                    image_hash,
                    meal_type,
                    json.dumps(result),
                    analysis_data.get('overall_confidence', 0),
                    request.remote_addr,
                    request.headers.get('User-Agent', '')
                ))
                
                analysis_id = cursor.lastrowid
                logger.info(f"Analysis saved with ID: {analysis_id}")
                
                conn.commit()
                logger.info("About to update daily nutrition...")
                update_daily_nutrition(user_id, total_nutrition)
                logger.info("Daily nutrition update completed")
                
                conn.close()
                
            except Exception as e:
                logger.error(f"Failed to save to database: {e}")
                logger.exception("Database save error traceback:")
                if conn:
                    conn.rollback()
                    conn.close()
            finally:
                if conn:
                    conn.close()
        else:
            logger.info(f"Skipping database save for guest user: {user_id}")
        
        result['analysis_id'] = analysis_id
        
        response_time = time.time() - start_time
        log_api_usage('/api/analyze', True, response_time)
        time.sleep(app.config['RATE_LIMIT_DELAY'])
        
        return jsonify(result)
        
    except json.JSONDecodeError as e:
        response_time = time.time() - start_time
        log_api_usage('/api/analyze', False, response_time)
        logger.error(f"JSON decode error: {e}")
        return jsonify({'error': 'Invalid response format from AI'}), 500
    except Exception as e:
        response_time = time.time() - start_time
        logger.error(f"Analysis error: {str(e)}")
        log_api_usage('/api/analyze', False, response_time)
        return jsonify({'error': 'Analysis failed', 'details': str(e)}), 500


@app.route('/api/dashboard', methods=['GET'])
@login_required
@limiter.limit("20 per minute")
def get_dashboard():
    try:
        logger.info("ðŸŽ¯ Dashboard request started")
        current_user = get_current_user()
        user_id = current_user['user_id']
        days = request.args.get('days', 7, type=int)
        
        logger.info(f"ðŸ“Š Getting dashboard for user: {user_id}")
        
        conn = get_db_connection(app.config['DATABASE_PATH'])
        cursor = conn.cursor()
        
        logger.info(f"Executing query for user_id: {user_id}")
        
        cursor.execute('SELECT * FROM daily_nutrition WHERE user_id = ? ORDER BY date DESC', (user_id,))
        all_user_data = cursor.fetchall()
        logger.info(f"ðŸ“Š Found {len(all_user_data)} total records for user")
        
        cursor.execute('''
            SELECT * FROM daily_nutrition 
            WHERE user_id = ? AND date >= date('now', '-{} days')
            ORDER BY date DESC
        '''.format(days), (user_id,))
        daily_data = cursor.fetchall()
        logger.info(f"ðŸ“ˆ Found {len(daily_data)} records within {days} days")
        
        today = datetime.now().date()
        today_str = str(today)
        cursor.execute('SELECT * FROM daily_nutrition WHERE user_id = ? AND date = ?', (user_id, today_str))
        today_specific = cursor.fetchone()
        logger.info(f"ðŸ“… Today specific data: {today_specific is not None}")
        
        cursor.execute('''
            SELECT analysis_result, created_at FROM meal_analyses 
            WHERE user_id = ? 
            ORDER BY created_at DESC 
            LIMIT 10
        ''', (user_id,))
        recent_meals = cursor.fetchall()
        logger.info(f"ðŸ½ï¸ Found {len(recent_meals)} recent meals")
        
        conn.close()
        
        is_clean_start = ensure_clean_daily_start(user_id)
        
        if is_clean_start:
            logger.info(f"Clean start for user {user_id} - returning empty progress")
            return jsonify({
                'success': True,
                'today_progress': {
                    'calories': {'current': 0, 'target': 2000, 'percentage': 0},
                    'protein': {'current': 0, 'target': 50, 'percentage': 0},
                    'carbs': {'current': 0, 'target': 250, 'percentage': 0},
                    'fat': {'current': 0, 'target': 65, 'percentage': 0},
                    'vitamin_a': {'current': 0, 'target': 900, 'percentage': 0},
                    'vitamin_c': {'current': 0, 'target': 90, 'percentage': 0},
                    'calcium': {'current': 0, 'target': 1000, 'percentage': 0},
                    'iron': {'current': 0, 'target': 18, 'percentage': 0},
                    'water': {'current': 0, 'target': 2000, 'percentage': 0}
                },
                'nutrition_history': [],
                'meal_history': [],
                'statistics': {
                    'total_analyses': 0,
                    'avg_daily_calories': 0,
                    'avg_daily_protein': 0,
                    'total_meals': 0,
                    'days_tracked': 0
                },
                'daily_targets': {
                    'calories': 2000,
                    'protein': 50,
                    'carbs': 250,
                    'fat': 65
                },
                'message': 'New day started - no data yet',
                'timestamp': datetime.now().isoformat()
            })

        logger.info("ðŸ”„ Processing nutrition data...")
        
        data_to_process = daily_data if daily_data else all_user_data
        logger.info(f"ðŸ“Š Processing {len(data_to_process)} records")
        
        nutrition_history = []
        for i, row in enumerate(data_to_process):
            try:
                row_dict = dict(row)
                logger.info(f"  Row {i}: date={row_dict.get('date')}, calories={row_dict.get('total_calories')}")
                
                processed_row = {
                    'date': row_dict['date'],
                    'calories': float(row_dict.get('total_calories', 0) or 0),
                    'protein': float(row_dict.get('total_protein', 0) or 0),
                    'carbs': float(row_dict.get('total_carbs', 0) or 0),
                    'fat': float(row_dict.get('total_fat', 0) or 0),
                    'fiber': float(row_dict.get('total_fiber', 0) or 0),
                    'vitamin_a': float(row_dict.get('total_vitamin_a', 0) or 0),
                    'vitamin_c': float(row_dict.get('total_vitamin_c', 0) or 0),
                    'calcium': float(row_dict.get('total_calcium', 0) or 0),
                    'iron': float(row_dict.get('total_iron', 0) or 0),
                    'water': float(row_dict.get('total_water', 0) or 0),
                    'meals': int(row_dict.get('meal_count', 0) or 0)
                }
                
                nutrition_history.append(processed_row)
                logger.info(f"  âœ… Processed row {i}: {processed_row['calories']} calories")
                
            except Exception as e:
                logger.error(f"âŒ Error processing row {i}: {e}")
                logger.error(f"Raw row data: {dict(row)}")
                continue
        
        logger.info(f"ðŸ“Š Processed {len(nutrition_history)} nutrition records successfully")
        
        try:
            daily_targets = get_user_daily_targets(user_id)
        except Exception as e:
            logger.error(f"âŒ Error getting targets: {e}")
            daily_targets = {
                'calories': 2000, 'protein': 50, 'carbs': 250, 'fat': 65,
                'fiber': 25, 'vitamin_a': 900, 'vitamin_c': 90,
                'calcium': 1000, 'iron': 18, 'water': 2000
            }
        
        enhanced_targets = {
            'calories': daily_targets.get('calories', 2000),
            'protein': daily_targets.get('protein', 50),
            'carbs': daily_targets.get('carbs', 250),
            'fat': daily_targets.get('fat', 65),
            'fiber': daily_targets.get('fiber', 25),
            'vitamin_a': daily_targets.get('vitamin_a', 900),
            'vitamin_c': daily_targets.get('vitamin_c', 90),
            'calcium': daily_targets.get('calcium', 1000),
            'iron': daily_targets.get('iron', 18),
            'water': daily_targets.get('water', 2000)
        }
        
        logger.info(f"ðŸ” Looking for today's data: {today_str}")
        
        today_data = None
        
        if today_specific:
            row_dict = dict(today_specific)
            today_data = {
                'date': row_dict['date'],
                'calories': float(row_dict.get('total_calories', 0) or 0),
                'protein': float(row_dict.get('total_protein', 0) or 0),
                'carbs': float(row_dict.get('total_carbs', 0) or 0),
                'fat': float(row_dict.get('total_fat', 0) or 0),
                'fiber': float(row_dict.get('total_fiber', 0) or 0),
                'vitamin_a': float(row_dict.get('total_vitamin_a', 0) or 0),
                'vitamin_c': float(row_dict.get('total_vitamin_c', 0) or 0),
                'calcium': float(row_dict.get('total_calcium', 0) or 0),
                'iron': float(row_dict.get('total_iron', 0) or 0),
                'water': float(row_dict.get('total_water', 0) or 0),
                'meals': int(row_dict.get('meal_count', 0) or 0)
            }
            logger.info(f"âœ… Found today data via today_specific query")
        
        if not today_data:
            for item in nutrition_history:
                if item['date'] == today_str:
                    today_data = item
                    logger.info(f"âœ… Found today data in nutrition_history")
                    break
        
        if not today_data and nutrition_history:
            today_data = nutrition_history[0]
            logger.info(f"âœ… Using most recent data as today's data")
        
        logger.info(f"ðŸ“Š Today data final: {today_data is not None}")
        if today_data:
            logger.info(f"ðŸ“ˆ Today values: calories={today_data['calories']}, protein={today_data['protein']}")

        def safe_percentage(current, target):
            try:
                if target and target > 0:
                    result = round((current / target) * 100, 1)
                    return result
                return 0
            except Exception as e:
                logger.error(f"Error calculating percentage: current={current}, target={target}, error={e}")
                return 0
        
        if today_data:
            logger.info("ðŸ”„ Calculating today's progress...")
            
            today_progress = {}
            nutrients = ['calories', 'protein', 'carbs', 'fat', 'vitamin_a', 'vitamin_c', 'calcium', 'iron', 'water']
            
            for nutrient in nutrients:
                current = today_data.get(nutrient, 0)
                target = enhanced_targets.get(nutrient, 1)
                percentage = safe_percentage(current, target)
                
                today_progress[nutrient] = {
                    'current': current,
                    'target': target,
                    'percentage': percentage
                }
                
                logger.info(f"  {nutrient}: {current}/{target} = {percentage}%")
            
            today_progress['meals'] = today_data.get('meals', 0)
            logger.info(f"  meals: {today_progress['meals']}")
            
        else:
            logger.warning("âš ï¸ No today data found, using zero progress")
            today_progress = {}
            nutrients = ['calories', 'protein', 'carbs', 'fat', 'vitamin_a', 'vitamin_c', 'calcium', 'iron', 'water']
            
            for nutrient in nutrients:
                today_progress[nutrient] = {
                    'current': 0,
                    'target': enhanced_targets.get(nutrient, 1),
                    'percentage': 0
                }
            today_progress['meals'] = 0
        meal_history = []
        for meal in recent_meals:
            try:
                analysis = json.loads(meal['analysis_result'])
                meal_history.append({
                    'timestamp': meal['created_at'],
                    'description': analysis.get('meal_description', ''),
                    'health_score': analysis.get('health_score', 0),
                    'overall_confidence': analysis.get('overall_confidence', 0),
                    'calories': analysis.get('total_nutrition', {}).get('calories', 0),
                    'protein': analysis.get('total_nutrition', {}).get('protein', 0)
                })
            except Exception as e:
                logger.error(f"Error processing meal: {e}")
                continue
        
        total_calories = sum(item['calories'] for item in nutrition_history)
        total_protein = sum(item['protein'] for item in nutrition_history)
        total_meals = sum(item['meals'] for item in nutrition_history)
        
        avg_calories = round(total_calories / max(len(nutrition_history), 1), 1)
        avg_protein = round(total_protein / max(len(nutrition_history), 1), 1)
        
        response_data = {
            'success': True,
            'user_id': user_id,
            'today_progress': today_progress,
            'nutrition_history': nutrition_history,
            'meal_history': meal_history,
            'statistics': {
                'total_analyses': len(recent_meals),
                'avg_daily_calories': avg_calories,
                'avg_daily_protein': avg_protein,
                'total_meals': total_meals,
                'days_tracked': len(nutrition_history)
            },
            'daily_targets': enhanced_targets,
            'timestamp': datetime.now().isoformat(),
            'debug_info': {
                'found_data': len(nutrition_history) > 0,
                'today_data_exists': today_data is not None,
                'total_records_found': len(all_user_data),
                'processed_records': len(nutrition_history)
            }
        }
        
        logger.info("âœ… Dashboard response built successfully")
        logger.info(f"ðŸ“Š Final response summary:")
        logger.info(f"  - today_progress keys: {list(today_progress.keys())}")
        logger.info(f"  - nutrition_history length: {len(nutrition_history)}")
        logger.info(f"  - today calories: {today_progress.get('calories', {}).get('current', 'N/A')}")
        
        return jsonify(response_data)
        
    except Exception as e:
        logger.error(f"ðŸ’¥ Dashboard error: {str(e)}")
        logger.exception("Full dashboard error traceback:")
        return jsonify({
            'error': 'Failed to load dashboard',
            'details': str(e) if app.debug else 'Internal server error',
            'user_id': user_id if 'user_id' in locals() else 'unknown'
        }), 500

@app.route('/api/debug/daily-reset', methods=['POST'])
@login_required
def debug_daily_reset():
    try:
        current_user = get_current_user()
        user_id = current_user['user_id']
        today = datetime.now().date()
        
        conn = get_db_connection(app.config['DATABASE_PATH'])
        cursor = conn.cursor()
        
        cursor.execute('DELETE FROM daily_nutrition WHERE user_id = ? AND date = ?', 
                      (user_id, today))
        
        deleted_count = cursor.rowcount
        conn.commit()
        conn.close()
        
        return jsonify({
            'success': True,
            'message': f'Deleted {deleted_count} daily nutrition records for today',
            'user_id': user_id,
            'date': str(today)
        })
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/history', methods=['GET'])
@login_required
@limiter.limit("15 per minute")
def get_analysis_history():
    try:
        current_user = get_current_user()
        user_id = current_user['user_id']
        limit = request.args.get('limit', 20, type=int)
        meal_type = request.args.get('meal_type', '')
        date_from = request.args.get('date_from', '')
        
        conn = get_db_connection(app.config['DATABASE_PATH'])
        cursor = conn.cursor()
        
        query = '''
            SELECT analysis_result, created_at, meal_type, confidence_score 
            FROM meal_analyses 
            WHERE user_id = ?
        '''
        params = [user_id]
        
        if meal_type:
            query += ' AND meal_type = ?'
            params.append(meal_type)
        
        if date_from:
            query += ' AND DATE(created_at) >= ?'
            params.append(date_from)
        
        query += ' ORDER BY created_at DESC LIMIT ?'
        params.append(limit)
        
        cursor.execute(query, params)
        results = cursor.fetchall()
        conn.close()
        
        history = []
        for row in results:
            try:
                analysis = json.loads(row['analysis_result'])
                history.append({
                    'analysis': analysis,
                    'timestamp': row['created_at'],
                    'meal_type': row['meal_type'],
                    'confidence_score': row['confidence_score']
                })
            except:
                continue
        
        return jsonify({
            'success': True,
            'history': history,
            'count': len(history),
            'filters': {
                'meal_type': meal_type,
                'date_from': date_from,
                'limit': limit
            }
        })
        
    except Exception as e:
        logger.error(f"History error: {str(e)}")
        return jsonify({'error': 'Failed to retrieve history'}), 500
@app.route('/api/debug/nutrition-data', methods=['GET'])
def debug_nutrition_data():
    try:
        current_user = get_current_user()
        if not current_user:
            return jsonify({'error': 'Not authenticated'}), 401
        
        user_id = current_user['user_id']
        today = datetime.now().date()
        
        conn = get_db_connection(app.config['DATABASE_PATH'])
        cursor = conn.cursor()
        
        cursor.execute('SELECT * FROM daily_nutrition WHERE user_id = ? ORDER BY date DESC', (user_id,))
        all_user_data = cursor.fetchall()
        
        cursor.execute('SELECT * FROM daily_nutrition WHERE user_id = ? AND date = ?', (user_id, today))
        today_specific = cursor.fetchone()
        
        cursor.execute('''
            SELECT * FROM daily_nutrition 
            WHERE user_id = ? AND date >= date('now', '-7 days')
            ORDER BY date DESC
        ''', (user_id,))
        last_7_days = cursor.fetchall()
        
        cursor.execute('SELECT user_id, date, total_calories FROM daily_nutrition ORDER BY date DESC LIMIT 10')
        all_recent_data = cursor.fetchall()
        
        cursor.execute('SELECT date("now")')
        sqlite_now = cursor.fetchone()[0]
        
        cursor.execute('SELECT datetime("now")')
        sqlite_datetime = cursor.fetchone()[0]
        
        conn.close()
        
        return jsonify({
            'user_id': user_id,
            'today_python': str(today),
            'sqlite_now': sqlite_now,
            'sqlite_datetime': sqlite_datetime,
            'all_user_data_count': len(all_user_data),
            'all_user_data': [dict(row) for row in all_user_data],
            'today_specific_data': dict(today_specific) if today_specific else None,
            'last_7_days_count': len(last_7_days),
            'last_7_days_data': [dict(row) for row in last_7_days],
            'all_recent_data': [dict(row) for row in all_recent_data],
            'debug_info': {
                'user_id_type': type(user_id).__name__,
                'today_type': type(today).__name__,
                'user_id_value': user_id
            }
        })
        
    except Exception as e:
        logger.error(f"Debug nutrition data error: {e}")
        return jsonify({'error': str(e)}), 500

@app.route('/api/stats', methods=['GET'])
@limiter.limit("10 per minute")
def get_enhanced_stats():
    try:
        conn = get_db_connection(app.config['DATABASE_PATH'])
        cursor = conn.cursor()
        
        cursor.execute('SELECT COUNT(*) as total FROM meal_analyses')
        total_analyses = cursor.fetchone()['total']
        
        cursor.execute('''
            SELECT COUNT(*) as today FROM meal_analyses 
            WHERE DATE(created_at) = DATE('now')
        ''')
        today_analyses = cursor.fetchone()['today']
        
        cursor.execute('''
            SELECT COUNT(DISTINCT user_id) as active FROM meal_analyses 
            WHERE created_at > datetime('now', '-7 days')
        ''')
        active_users = cursor.fetchone()['active']
        
        cursor.execute('''
            SELECT AVG(confidence_score) as avg_confidence FROM meal_analyses 
            WHERE confidence_score > 0
        ''')
        avg_confidence = cursor.fetchone()['avg_confidence'] or 0
        
        cursor.execute('''
            SELECT COUNT(*) as requests, 
                   AVG(response_time) as avg_response_time,
                   SUM(CASE WHEN success = 1 THEN 1 ELSE 0 END) as successful
            FROM api_usage 
            WHERE timestamp > datetime('now', '-24 hours')
        ''')
        api_stats = cursor.fetchone()
        
        conn.close()
        
        return jsonify({
            'total_analyses': total_analyses,
            'today_analyses': today_analyses,
            'active_users_7d': active_users,
            'avg_confidence_score': round(avg_confidence, 1),
            'api_performance': {
                'requests_24h': api_stats['requests'],
                'avg_response_time': round(api_stats['avg_response_time'] or 0, 3),
                'success_rate': round((api_stats['successful'] / max(api_stats['requests'], 1)) * 100, 1)
            },
            'timestamp': datetime.now().isoformat()
        })
        
    except Exception as e:
        logger.error(f"Stats error: {str(e)}")
        return jsonify({'error': 'Failed to retrieve stats'}), 500

@app.route('/api/nutrition-db', methods=['GET'])
def get_nutrition_database():
    return jsonify({
        'nutrition_database': NUTRITION_DB,
        'food_groups': {
            'Whole Grains': 'Complex carbohydrates and energy',
            'Protein-Rich Foods': 'Muscle building and repair',
            'Vegetables': 'Vitamins, minerals, and fiber',
            'Fruits': 'Natural sugars and vitamins',
            'Dairy': 'Calcium and protein',
            'Nuts/Seeds': 'Healthy fats and protein'
        },
        'daily_targets': DAILY_TARGETS,
        'total_foods': len(NUTRITION_DB)
    })

@app.route('/api/chatbot', methods=['POST'])
@limiter.limit("30 per minute")
def chatbot_endpoint():
    start_time = time.time()
    
    try:
        data = request.get_json()
        if not data or 'message' not in data:
            return jsonify({'error': 'Message is required'}), 400
        
        message = data['message'].strip()
        if not message:
            return jsonify({'error': 'Message cannot be empty'}), 400
        
        current_user = get_current_user()
        if not current_user:
            return jsonify({'error': 'User session not found'}), 401
        
        user_id = current_user['user_id']
        
        bot = NutriBot(app.config['DATABASE_PATH'], model if 'model' in globals() else None)
        
        user_context = bot.get_user_context(user_id)
        
        bot_response = bot.generate_response(message, user_id, user_context)
        
        if not current_user['is_guest']:
            try:
                conn = get_db_connection(app.config['DATABASE_PATH'])
                cursor = conn.cursor()
                
                cursor.execute('''
                    INSERT INTO chatbot_conversations (user_id, message, response, intent)
                    VALUES (?, ?, ?, ?)
                ''', (user_id, message, json.dumps(bot_response), "unknown"))
                
                conn.commit()
                conn.close()
            except Exception as e:
                logger.error(f"Failed to log conversation: {e}")
        
        response_time = time.time() - start_time
        log_api_usage('/api/chatbot', True, response_time)
        
        return jsonify({
            'success': True,
            'response': bot_response,
            'user_context': user_context,
            'timestamp': datetime.now().isoformat()
        })
        
    except Exception as e:
        response_time = time.time() - start_time
        logger.error(f"Chatbot error: {str(e)}")
        log_api_usage('/api/chatbot', False, response_time)
        
        return jsonify({
            'error': 'Chatbot service temporarily unavailable',
            'details': str(e) if app.debug else None
        }), 500

@app.route('/api/chatbot/history', methods=['GET'])
@login_required
@limiter.limit("10 per minute")
def chatbot_history():
    try:
        current_user = get_current_user()
        user_id = current_user['user_id']
        limit = min(request.args.get('limit', 20, type=int), 50)
        
        conn = get_db_connection(app.config['DATABASE_PATH'])
        cursor = conn.cursor()
        
        cursor.execute('''
            SELECT message, response, created_at 
            FROM chatbot_conversations 
            WHERE user_id = ? 
            ORDER BY created_at DESC 
            LIMIT ?
        ''', (user_id, limit))
        
        conversations = []
        for row in cursor.fetchall():
            try:
                response_data = json.loads(row[1])
                conversations.append({
                    'message': row[0],
                    'response': response_data,
                    'timestamp': row[2]
                })
            except:
                conversations.append({
                    'message': row[0],
                    'response': {'text': row[1]},
                    'timestamp': row[2]
                })
        
        conn.close()
        
        return jsonify({
            'success': True,
            'conversations': list(reversed(conversations)),
            'count': len(conversations)
        })
        
    except Exception as e:
        logger.error(f"Chatbot history error: {str(e)}")
        return jsonify({'error': 'Failed to retrieve conversation history'}), 500

@app.route('/api/chatbot/suggestions', methods=['GET'])
def chatbot_suggestions():
    try:
        current_user = get_current_user()
        if not current_user:
            return jsonify({
                'suggestions': [
                    "How's my nutrition today?",
                    "Suggest healthy meals",
                    "Help me reach my goals",
                    "Nutrition tips"
                ]
            })
        
        user_id = current_user['user_id']
        
        bot = NutriBot(app.config['DATABASE_PATH'])
        user_context = bot.get_user_context(user_id)
        
        today = user_context.get("today", {})
        calories = today.get("calories", 0)
        protein = today.get("protein", 0)
        meals = today.get("meals", 0)
        
        suggestions = []
        
        if not current_user['is_guest']:
            if calories < 800:
                suggestions.extend([
                    "What should I eat to reach my calorie goal?",
                    "Suggest high-calorie healthy meals",
                    "Am I eating enough today?"
                ])
            
            if protein < 25:
                suggestions.extend([
                    "How can I get more protein?",
                    "High protein food suggestions",
                    "Protein-rich snack ideas"
                ])
            
            if meals < 2:
                suggestions.extend([
                    "Plan my meals for today",
                    "Healthy meal prep ideas",
                    "What's good for lunch?"
                ])
            
            suggestions.extend([
                "Check my nutrition progress",
                "How am I doing this week?",
                "Tips for healthy eating"
            ])
        else:
            suggestions.extend([
                "What are healthy foods?",
                "Tips for balanced nutrition",
                "How to start eating healthy",
                "Benefits of good nutrition"
            ])
        
        suggestions.extend([
            "Help me lose weight",
            "Motivate me to stay on track"
        ])
        
        suggestions = list(dict.fromkeys(suggestions))[:8]
        
        return jsonify({
            'success': True,
            'suggestions': suggestions,
            'user_context': user_context
        })
        
    except Exception as e:
        logger.error(f"Suggestions error: {str(e)}")
        return jsonify({
            'suggestions': [
                "How's my nutrition today?",
                "Suggest healthy meals",
                "Help me reach my goals",
                "Nutrition tips"
            ]
        })

@app.route('/api/feedback', methods=['POST'])
@login_required
@limiter.limit("20 per minute")
def submit_feedback():
    """Submit user feedback for meal analysis"""
    try:
        data = request.get_json()
        if not data:
            return jsonify({'error': 'No data provided'}), 400
        
        current_user = get_current_user()
        user_id = current_user['user_id']
        analysis_id = data.get('analysis_id')
        feedback_type = data.get('feedback_type', 'general')
        rating = data.get('rating')
        comment = data.get('comment', '')
        is_helpful = data.get('is_helpful')
        
        if not analysis_id:
            return jsonify({'error': 'Analysis ID is required'}), 400
        
        conn = get_db_connection(app.config['DATABASE_PATH'])
        cursor = conn.cursor()
        
        cursor.execute('''
            INSERT INTO user_feedback (user_id, analysis_id, feedback_type, rating, comment, is_helpful)
            VALUES (?, ?, ?, ?, ?, ?)
        ''', (user_id, analysis_id, feedback_type, rating, comment, is_helpful))
        
        conn.commit()
        conn.close()
        
        return jsonify({
            'success': True,
            'message': 'Feedback submitted successfully',
            'feedback_id': cursor.lastrowid
        })
        
    except Exception as e:
        logger.error(f"Feedback submission error: {str(e)}")
        return jsonify({'error': 'Failed to submit feedback'}), 500

@app.route('/api/feedback/correction', methods=['POST'])
@login_required
@limiter.limit("10 per minute")
def submit_correction():
    """Submit food correction/improvement"""
    try:
        data = request.get_json()
        if not data:
            return jsonify({'error': 'No data provided'}), 400
        
        current_user = get_current_user()
        user_id = current_user['user_id']
        analysis_id = data.get('analysis_id')
        original_food_name = data.get('original_food_name')
        corrected_food_name = data.get('corrected_food_name')
        original_portion = data.get('original_portion', '')
        corrected_portion = data.get('corrected_portion', '')
        correction_type = data.get('correction_type', 'food_name')
        
        if not all([analysis_id, original_food_name, corrected_food_name]):
            return jsonify({'error': 'Required fields missing'}), 400
        
        conn = get_db_connection(app.config['DATABASE_PATH'])
        cursor = conn.cursor()
        
        cursor.execute('''
            INSERT INTO food_corrections 
            (user_id, analysis_id, original_food_name, corrected_food_name, 
             original_portion, corrected_portion, correction_type)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        ''', (user_id, analysis_id, original_food_name, corrected_food_name, 
              original_portion, corrected_portion, correction_type))
        
        conn.commit()
        conn.close()
        
        return jsonify({
            'success': True,
            'message': 'Correction submitted successfully',
            'correction_id': cursor.lastrowid
        })
        
    except Exception as e:
        logger.error(f"Correction submission error: {str(e)}")
        return jsonify({'error': 'Failed to submit correction'}), 500

@app.route('/api/feedback/rating', methods=['POST'])
@login_required
@limiter.limit("15 per minute")
def submit_rating():
    """Submit detailed rating for analysis"""
    try:
        data = request.get_json()
        if not data:
            return jsonify({'error': 'No data provided'}), 400
        
        current_user = get_current_user()
        user_id = current_user['user_id']
        analysis_id = data.get('analysis_id')
        accuracy_rating = data.get('accuracy_rating')
        portion_rating = data.get('portion_rating')
        overall_rating = data.get('overall_rating')
        would_recommend = data.get('would_recommend')
        improvement_suggestions = data.get('improvement_suggestions', '')
        
        if not analysis_id:
            return jsonify({'error': 'Analysis ID is required'}), 400
        
        conn = get_db_connection(app.config['DATABASE_PATH'])
        cursor = conn.cursor()
        
        cursor.execute('''
            INSERT OR REPLACE INTO analysis_ratings 
            (user_id, analysis_id, accuracy_rating, portion_rating, overall_rating, 
             would_recommend, improvement_suggestions)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        ''', (user_id, analysis_id, accuracy_rating, portion_rating, overall_rating,
              would_recommend, improvement_suggestions))
        
        conn.commit()
        conn.close()
        
        return jsonify({
            'success': True,
            'message': 'Rating submitted successfully'
        })
        
    except Exception as e:
        logger.error(f"Rating submission error: {str(e)}")
        return jsonify({'error': 'Failed to submit rating'}), 500

@app.route('/api/feedback/stats', methods=['GET'])
@limiter.limit("30 per minute")
def get_feedback_stats():
    """Get feedback statistics"""
    try:
        conn = get_db_connection(app.config['DATABASE_PATH'])
        cursor = conn.cursor()
        
        cursor.execute('''
            SELECT 
                COUNT(*) as total_ratings,
                AVG(accuracy_rating) as avg_accuracy,
                AVG(portion_rating) as avg_portion,
                AVG(overall_rating) as avg_overall,
                SUM(CASE WHEN would_recommend = 1 THEN 1 ELSE 0 END) as recommend_count
            FROM analysis_ratings
        ''')
        overall_stats = cursor.fetchone()
        
        cursor.execute('''
            SELECT feedback_type, rating, comment, created_at
            FROM user_feedback 
            WHERE comment IS NOT NULL AND comment != ''
            ORDER BY created_at DESC 
            LIMIT 10
        ''')
        recent_feedback = cursor.fetchall()
        
        cursor.execute('''
            SELECT 
                COUNT(*) as total_corrections,
                correction_type,
                COUNT(*) as count
            FROM food_corrections 
            GROUP BY correction_type
        ''')
        correction_stats = cursor.fetchall()
        
        conn.close()
        
        return jsonify({
            'success': True,
            'stats': {
                'total_ratings': overall_stats['total_ratings'] if overall_stats else 0,
                'avg_accuracy': round(overall_stats['avg_accuracy'] or 0, 2),
                'avg_portion': round(overall_stats['avg_portion'] or 0, 2),
                'avg_overall': round(overall_stats['avg_overall'] or 0, 2),
                'recommend_percentage': round((overall_stats['recommend_count'] / max(overall_stats['total_ratings'], 1)) * 100, 1) if overall_stats else 0,
                'recent_feedback': [dict(row) for row in recent_feedback],
                'correction_stats': [dict(row) for row in correction_stats]
            }
        })
        
    except Exception as e:
        logger.error(f"Stats retrieval error: {str(e)}")
        return jsonify({'error': 'Failed to retrieve stats'}), 500


@app.errorhandler(429)
def ratelimit_handler(e):
    return jsonify({'error': 'Rate limit exceeded', 'retry_after': str(e.retry_after)}), 429

@app.errorhandler(413)
def too_large(e):
    return jsonify({'error': 'File too large (max 16MB)'}), 413

@app.errorhandler(500)
def internal_error(e):
    return jsonify({'error': 'Internal server error'}), 500

@app.errorhandler(404)
def not_found(e):
    return jsonify({'error': 'Endpoint not found'}), 404

if __name__ == '__main__':
    init_database(app.config['DATABASE_PATH'])
    
    print("Starting Enhanced NutriVision AI with Authentication Fix...")
    print("=" * 70)
    print(f"Landing Page: http://localhost:{os.environ.get('PORT', 5000)}/")
    print(f"App Dashboard: http://localhost:{os.environ.get('PORT', 5000)}/app")
    print(f"Health Check: http://localhost:{os.environ.get('PORT', 5000)}/api/health")
    print(f"Authentication API: http://localhost:{os.environ.get('PORT', 5000)}/api/auth/")
    print(f"Debug Session: http://localhost:{os.environ.get('PORT', 5000)}/api/debug/session")
    
    
    if app.config['GEMINI_API_KEY'] == 'your-gemini-api-key-here':
        print("\nWARNING: GEMINI_API_KEY not configured!")
        print("Please set your API key in .env file")
    else:
        print("\nGemini AI API key configured âœ“")
    
    print("=" * 70)
    
    app.run(
        debug=os.environ.get('FLASK_DEBUG', 'True').lower() == 'true',
        host='0.0.0.0',
        port=int(os.environ.get('PORT', 5000))
    )
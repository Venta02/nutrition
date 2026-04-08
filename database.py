import sqlite3
import os
import logging
from datetime import datetime
import hashlib
import bcrypt

logger = logging.getLogger(__name__)

def get_db_connection(db_path):
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    return conn

def column_exists(db_path, table_name, column_name):
    try:
        conn = get_db_connection(db_path)
        cursor = conn.cursor()
        cursor.execute(f"PRAGMA table_info({table_name})")
        columns = [row[1] for row in cursor.fetchall()]
        conn.close()
        return column_name in columns
    except:
        return False

def table_exists(db_path, table_name):
    try:
        conn = get_db_connection(db_path)
        cursor = conn.cursor()
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name=?", (table_name,))
        result = cursor.fetchone()
        conn.close()
        return result is not None
    except:
        return False

def cleanup_anonymous_data(db_path):
    try:
        conn = get_db_connection(db_path)
        cursor = conn.cursor()
        
        cursor.execute("SELECT user_id FROM users WHERE email IS NULL OR email = ''")
        anonymous_users = [row[0] for row in cursor.fetchall()]
        
        if anonymous_users:
            user_ids_placeholder = ','.join(['?' for _ in anonymous_users])
            
            tables_to_clean = [
                'meal_analyses',
                'daily_nutrition', 
                'nutrition_goals',
                'chatbot_conversations',
                'user_feedback',
                'food_corrections',
                'analysis_ratings'
            ]
            
            for table in tables_to_clean:
                if table_exists(db_path, table):
                    cursor.execute(f"DELETE FROM {table} WHERE user_id IN ({user_ids_placeholder})", anonymous_users)
            
            cursor.execute(f"DELETE FROM users WHERE user_id IN ({user_ids_placeholder})", anonymous_users)
            
            conn.commit()
            logger.info(f"Cleaned up {len(anonymous_users)} anonymous users and their data")
        
        conn.close()
    except Exception as e:
        logger.error(f"Error cleaning anonymous data: {e}")
def check_and_update_daily_nutrition_table(db_path):
    """Check dan update struktur table daily_nutrition"""
    try:
        conn = get_db_connection(db_path)
        cursor = conn.cursor()
        
        cursor.execute('PRAGMA table_info(daily_nutrition)')
        existing_columns = [row[1] for row in cursor.fetchall()]
        print(f"Existing columns in daily_nutrition: {existing_columns}")
        
        required_columns = [
            ('total_vitamin_a', 'REAL DEFAULT 0'),
            ('total_vitamin_c', 'REAL DEFAULT 0'),
            ('total_calcium', 'REAL DEFAULT 0'),
            ('total_iron', 'REAL DEFAULT 0'),
            ('total_water', 'REAL DEFAULT 0')
        ]
        
        for column_name, column_def in required_columns:
            if column_name not in existing_columns:
                try:
                    cursor.execute(f'ALTER TABLE daily_nutrition ADD COLUMN {column_name} {column_def}')
                    print(f"✓ Added column: {column_name}")
                except Exception as e:
                    print(f"✗ Failed to add column {column_name}: {e}")
        
        conn.commit()
        
        cursor.execute('PRAGMA table_info(daily_nutrition)')
        final_columns = [row[1] for row in cursor.fetchall()]
        print(f"Final columns in daily_nutrition: {final_columns}")
        
        conn.close()
        return True
        
    except Exception as e:
        print(f"Error updating daily_nutrition table: {e}")
        return False
    
def init_database(db_path):
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    cleanup_anonymous_data(db_path)
    
    if not table_exists(db_path, 'users'):
        cursor.execute('''
            CREATE TABLE users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id TEXT UNIQUE NOT NULL,
                email TEXT UNIQUE NOT NULL,
                password_hash TEXT NOT NULL,
                name TEXT NOT NULL,
                age INTEGER,
                gender TEXT CHECK(gender IN ('male', 'female', 'other')),
                height REAL,
                weight REAL,
                activity_level TEXT CHECK(activity_level IN ('sedentary', 'lightly_active', 'moderately_active', 'very_active', 'extra_active')) DEFAULT 'moderately_active',
                fitness_goal TEXT CHECK(fitness_goal IN ('lose_weight', 'maintain_weight', 'gain_weight', 'build_muscle')) DEFAULT 'maintain_weight',
                daily_calorie_goal INTEGER,
                daily_protein_goal INTEGER DEFAULT 50,
                daily_carbs_goal INTEGER DEFAULT 250,
                daily_fat_goal INTEGER DEFAULT 65,
                daily_fiber_goal INTEGER DEFAULT 25,
                is_active BOOLEAN DEFAULT TRUE,
                email_verified BOOLEAN DEFAULT FALSE,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                last_login TIMESTAMP
            )
        ''')
    else:
        new_columns = [
            ('email', 'TEXT'),
            ('password_hash', 'TEXT'),
            ('name', 'TEXT'),
            ('fitness_goal', 'TEXT DEFAULT "maintain_weight"'),
            ('daily_protein_goal', 'INTEGER DEFAULT 50'),
            ('daily_carbs_goal', 'INTEGER DEFAULT 250'),
            ('daily_fat_goal', 'INTEGER DEFAULT 65'),
            ('daily_fiber_goal', 'INTEGER DEFAULT 25'),
            ('is_active', 'BOOLEAN DEFAULT TRUE'),
            ('email_verified', 'BOOLEAN DEFAULT FALSE'),
            ('last_login', 'TIMESTAMP')
        ]
        
        for column_name, column_type in new_columns:
            if not column_exists(db_path, 'users', column_name):
                cursor.execute(f'ALTER TABLE users ADD COLUMN {column_name} {column_type}')
    
    if not table_exists(db_path, 'guest_sessions'):
        cursor.execute('''
            CREATE TABLE guest_sessions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                session_id TEXT UNIQUE NOT NULL,
                ip_address TEXT NOT NULL,
                user_agent TEXT,
                analyses_count INTEGER DEFAULT 0,
                max_analyses INTEGER DEFAULT 1,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                expires_at TIMESTAMP DEFAULT (datetime('now', '+24 hours'))
            )
        ''')
    
    if not table_exists(db_path, 'user_sessions'):
        cursor.execute('''
            CREATE TABLE user_sessions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id TEXT NOT NULL,
                session_token TEXT UNIQUE NOT NULL,
                ip_address TEXT,
                user_agent TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                expires_at TIMESTAMP DEFAULT (datetime('now', '+7 days')),
                is_active BOOLEAN DEFAULT TRUE,
                FOREIGN KEY (user_id) REFERENCES users (user_id)
            )
        ''')
    
    if not table_exists(db_path, 'password_reset_tokens'):
        cursor.execute('''
            CREATE TABLE password_reset_tokens (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id TEXT NOT NULL,
                token TEXT UNIQUE NOT NULL,
                expires_at TIMESTAMP DEFAULT (datetime('now', '+1 hour')),
                used BOOLEAN DEFAULT FALSE,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (user_id) REFERENCES users (user_id)
            )
        ''')
    
    if not table_exists(db_path, 'meal_analyses'):
        cursor.execute('''
            CREATE TABLE meal_analyses (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id TEXT NOT NULL,
                session_id TEXT NOT NULL,
                image_hash TEXT NOT NULL,
                meal_type TEXT DEFAULT 'general',
                analysis_result TEXT NOT NULL,
                confidence_score INTEGER DEFAULT 0,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                ip_address TEXT,
                user_agent TEXT,
                FOREIGN KEY (user_id) REFERENCES users (user_id)
            )
        ''')
    else:
        
        pass
    if not table_exists(db_path, 'api_usage'):
        cursor.execute('''
            CREATE TABLE api_usage (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                ip_address TEXT NOT NULL,
                endpoint TEXT NOT NULL,
                timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                success BOOLEAN DEFAULT TRUE,
                response_time REAL DEFAULT 0.0,
                user_id TEXT,
                FOREIGN KEY (user_id) REFERENCES users (user_id)
            )
        ''')
    else:
        if not column_exists(db_path, 'api_usage', 'user_id'):
            cursor.execute('ALTER TABLE api_usage ADD COLUMN user_id TEXT')
    
    if not table_exists(db_path, 'daily_nutrition'):
        cursor.execute('''
            CREATE TABLE daily_nutrition (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id TEXT NOT NULL,
                date DATE NOT NULL,
                total_calories REAL DEFAULT 0,
                total_protein REAL DEFAULT 0,
                total_carbs REAL DEFAULT 0,
                total_fat REAL DEFAULT 0,
                total_fiber REAL DEFAULT 0,
                total_vitamin_a REAL DEFAULT 0,
                total_vitamin_c REAL DEFAULT 0,
                total_calcium REAL DEFAULT 0,
                total_iron REAL DEFAULT 0,
                total_water REAL DEFAULT 0,
                meal_count INTEGER DEFAULT 0,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(user_id, date),
                FOREIGN KEY (user_id) REFERENCES users (user_id)
            )
        ''')
    else:
        new_columns = [
            'total_vitamin_a REAL DEFAULT 0',
            'total_vitamin_c REAL DEFAULT 0', 
            'total_calcium REAL DEFAULT 0',
            'total_iron REAL DEFAULT 0',
            'total_water REAL DEFAULT 0'
        ]
        
        for column in new_columns:
            column_name = column.split(' ')[0] 
            if not column_exists(db_path, 'daily_nutrition', column_name):
                try:
                    cursor.execute(f'ALTER TABLE daily_nutrition ADD COLUMN {column}')
                except Exception as e:
                    logger.warning(f"Failed to add column {column_name}: {e}")
    if not table_exists(db_path, 'nutrition_goals'):
        cursor.execute('''
            CREATE TABLE nutrition_goals (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id TEXT NOT NULL,
                goal_type TEXT NOT NULL,
                target_value REAL NOT NULL,
                current_value REAL DEFAULT 0,
                target_date DATE,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (user_id) REFERENCES users (user_id)
            )
        ''')
    
    if not table_exists(db_path, 'chatbot_conversations'):
        cursor.execute('''
            CREATE TABLE chatbot_conversations (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id TEXT NOT NULL,
                message TEXT NOT NULL,
                response TEXT NOT NULL,
                intent TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (user_id) REFERENCES users (user_id)
            )
        ''')
    
    if not table_exists(db_path, 'user_feedback'):
        cursor.execute('''
            CREATE TABLE user_feedback (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id TEXT NOT NULL,
                analysis_id INTEGER,
                feedback_type TEXT NOT NULL,
                rating INTEGER,
                comment TEXT,
                is_helpful BOOLEAN,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (analysis_id) REFERENCES meal_analyses (id),
                FOREIGN KEY (user_id) REFERENCES users (user_id)
            )
        ''')
    
    if not table_exists(db_path, 'food_corrections'):
        cursor.execute('''
            CREATE TABLE food_corrections (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id TEXT NOT NULL,
                analysis_id INTEGER,
                original_food_name TEXT NOT NULL,
                corrected_food_name TEXT NOT NULL,
                original_portion TEXT,
                corrected_portion TEXT,
                correction_type TEXT DEFAULT 'food_name',
                status TEXT DEFAULT 'pending',
                admin_notes TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                reviewed_at TIMESTAMP,
                FOREIGN KEY (analysis_id) REFERENCES meal_analyses (id),
                FOREIGN KEY (user_id) REFERENCES users (user_id)
            )
        ''')
    
    if not table_exists(db_path, 'analysis_ratings'):
        cursor.execute('''
            CREATE TABLE analysis_ratings (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id TEXT NOT NULL,
                analysis_id INTEGER NOT NULL,
                accuracy_rating INTEGER,
                portion_rating INTEGER,
                overall_rating INTEGER,
                would_recommend BOOLEAN,
                improvement_suggestions TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (analysis_id) REFERENCES meal_analyses (id),
                FOREIGN KEY (user_id) REFERENCES users (user_id),
                UNIQUE(user_id, analysis_id)
            )
        ''')
    
    if not table_exists(db_path, 'feedback_stats'):
        cursor.execute('''
            CREATE TABLE feedback_stats (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                date DATE NOT NULL,
                total_feedbacks INTEGER DEFAULT 0,
                avg_accuracy_rating REAL DEFAULT 0,
                avg_portion_rating REAL DEFAULT 0,
                avg_overall_rating REAL DEFAULT 0,
                total_corrections INTEGER DEFAULT 0,
                helpful_feedback_count INTEGER DEFAULT 0,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(date)
            )
        ''')
    print("Checking and updating daily_nutrition table structure...")
    check_and_update_daily_nutrition_table(db_path)
    print("Database initialization completed")
    conn.commit()
    conn.close()
    logger.info("Database initialized with authentication system")

def hash_password(password):
    return bcrypt.hashpw(password.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')

def verify_password(password, hashed):
    return bcrypt.checkpw(password.encode('utf-8'), hashed.encode('utf-8'))

def calculate_daily_calorie_goal(age, gender, height, weight, activity_level, fitness_goal):
    if gender.lower() == 'male':
        bmr = 88.362 + (13.397 * weight) + (4.799 * height) - (5.677 * age)
    else:
        bmr = 447.593 + (9.247 * weight) + (3.098 * height) - (4.330 * age)

    activity_multipliers = {
        'sedentary': 1.2,
        'lightly_active': 1.375,
        'moderately_active': 1.55,
        'very_active': 1.725,
        'extra_active': 1.9
    }
    
    tdee = bmr * activity_multipliers.get(activity_level, 1.55)
    
    if fitness_goal == 'lose_weight':
        return int(tdee - 500) 
    elif fitness_goal == 'gain_weight':
        return int(tdee + 500)  
    elif fitness_goal == 'build_muscle':
        return int(tdee + 300)  
    else:  
        return int(tdee)

def create_user(db_path, email, password, name, age=None, gender=None, height=None, weight=None, activity_level='moderately_active', fitness_goal='maintain_weight'):
    import uuid
    
    conn = get_db_connection(db_path)
    cursor = conn.cursor()
    
    try:
        cursor.execute("SELECT id FROM users WHERE email = ?", (email,))
        if cursor.fetchone():
            return None, "Email already exists"
        
        user_id = str(uuid.uuid4())
        password_hash = hash_password(password)
        
        daily_calorie_goal = None
        if all([age, gender, height, weight]):
            daily_calorie_goal = calculate_daily_calorie_goal(age, gender, height, weight, activity_level, fitness_goal)
        else:
            daily_calorie_goal = 2000  
        
        cursor.execute('''
            INSERT INTO users (
                user_id, email, password_hash, name, age, gender, height, weight,
                activity_level, fitness_goal, daily_calorie_goal, created_at, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
        ''', (user_id, email, password_hash, name, age, gender, height, weight, activity_level, fitness_goal, daily_calorie_goal))
        
        conn.commit()
        conn.close()
        return user_id, "User created successfully"
    
    except Exception as e:
        conn.rollback()
        conn.close()
        return None, str(e)

def authenticate_user(db_path, email, password):
    conn = get_db_connection(db_path)
    cursor = conn.cursor()
    
    try:
        cursor.execute("SELECT user_id, password_hash, name, is_active FROM users WHERE email = ?", (email,))
        user = cursor.fetchone()
        
        if user and user['is_active'] and verify_password(password, user['password_hash']):
            # Update last login
            cursor.execute("UPDATE users SET last_login = CURRENT_TIMESTAMP WHERE user_id = ?", (user['user_id'],))
            conn.commit()
            conn.close()
            return user['user_id'], user['name']
        
        conn.close()
        return None, "Invalid email or password"
    
    except Exception as e:
        conn.close()
        return None, str(e)

def get_user_profile(db_path, user_id):
    conn = get_db_connection(db_path)
    cursor = conn.cursor()
    
    try:
        cursor.execute('''
            SELECT user_id, email, name, age, gender, height, weight, activity_level,
                   fitness_goal, daily_calorie_goal, daily_protein_goal, daily_carbs_goal,
                   daily_fat_goal, daily_fiber_goal, created_at, last_login
            FROM users WHERE user_id = ? AND is_active = TRUE
        ''', (user_id,))
        
        user = cursor.fetchone()
        conn.close()
        
        if user:
            return dict(user)
        return None
    
    except Exception as e:
        conn.close()
        return None
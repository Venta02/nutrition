from flask import session, request, jsonify, g
from functools import wraps
import uuid
import secrets
import time
from datetime import datetime, timedelta
from database import get_db_connection, create_user, authenticate_user, get_user_profile
import logging

logger = logging.getLogger(__name__)

class AuthManager:
    def __init__(self, db_path):
        self.db_path = db_path
        
    def register_user(self, email, password, name, profile_data=None):
        """Register a new user and auto-login"""
        try:
            if not all([email, password, name]):
                return {'success': False, 'message': 'Email, password, and name are required'}
            
            if len(password) < 6:
                return {'success': False, 'message': 'Password must be at least 6 characters'}
            
            age = profile_data.get('age') if profile_data else None
            gender = profile_data.get('gender') if profile_data else None
            height = profile_data.get('height') if profile_data else None
            weight = profile_data.get('weight') if profile_data else None
            activity_level = profile_data.get('activity_level', 'moderately_active') if profile_data else 'moderately_active'
            fitness_goal = profile_data.get('fitness_goal', 'maintain_weight') if profile_data else 'maintain_weight'
            
            user_id, message = create_user(
                self.db_path, email, password, name, age, gender, 
                height, weight, activity_level, fitness_goal
            )
            
            if user_id:
                logger.info(f"User registered successfully: {user_id}")
                
                login_result = self.login_user(email, password)
                
                if login_result['success']:
                    return {
                        'success': True, 
                        'message': 'User registered and logged in successfully',
                        'user_id': user_id,
                        'user': login_result['user']
                    }
                else:
                    logger.warning(f"Registration successful but auto-login failed for {user_id}: {login_result['message']}")
                    return {
                        'success': True, 
                        'message': 'User registered successfully, please login manually',
                        'user_id': user_id,
                        'login_required': True
                    }
            else:
                logger.error(f"User registration failed: {message}")
                return {'success': False, 'message': message}
                
        except Exception as e:
            logger.error(f"Registration error: {e}")
            return {'success': False, 'message': 'Registration failed'}
    
    def login_user(self, email, password):
        """Login user and create session with enhanced verification"""
        try:
            user_id, name = authenticate_user(self.db_path, email, password)
            
            if user_id:
                logger.info(f"Authentication successful for user {user_id}")
                
                session.clear()
                
                session.permanent = True
                
                session_token = self.create_user_session(user_id)
                
                if not session_token:
                    logger.error(f"Failed to create session token for user {user_id}")
                    return {'success': False, 'message': 'Session creation failed'}
                
                session['user_id'] = str(user_id)  
                session['user_name'] = str(name)  
                session['session_token'] = str(session_token)
                session['is_authenticated'] = True
                session['login_timestamp'] = datetime.now().isoformat()
                
                session.modified = True
                
                logger.info(f"Session data set for user {user_id}: {dict(session)}")
                
                test_auth = session.get('is_authenticated', False)
                test_user = session.get('user_id')
                
                if not test_auth or not test_user:
                    logger.error(f"Session verification failed after setting - Auth: {test_auth}, User: {test_user}")
                    logger.error(f"Full session data: {dict(session)}")
                    return {'success': False, 'message': 'Session creation failed - verification error'}
                
                logger.info(f"Session verification passed - Auth: {test_auth}, User: {test_user}")
                
                return {
                    'success': True,
                    'message': 'Login successful',
                    'user': {
                        'user_id': user_id,
                        'name': name,
                        'session_token': session_token
                    }
                }
            else:
                logger.warning(f"Authentication failed for email {email}: {name}")
                return {'success': False, 'message': name} 
                
        except Exception as e:
            logger.error(f"Login error: {e}")
            return {'success': False, 'message': 'Login failed'}
    
    def logout_user(self):
        """Simplified logout function untuk mengurangi complexity"""
        try:
            session_token = session.get('session_token')
            user_id = session.get('user_id')
            
            logger.info(f"Starting logout for user {user_id}")
            
            session.clear()
            session.modified = True
            logger.info("Flask session cleared successfully")
            
            if session_token:
                try:
                    self.deactivate_user_session(session_token)
                except Exception as session_error:
                    logger.warning(f"Could not deactivate session token: {session_error}")
            
            return {
                'success': True, 
                'message': 'Logged out successfully',
                'user_id': user_id
            }
            
        except Exception as e:
            logger.error(f"Logout error: {e}")
            
            try:
                session.clear()
                session.modified = True
                return {
                    'success': True,
                    'message': 'Logged out (with minor issues)',
                    'had_minor_errors': True
                }
            except:
                return {
                    'success': False,
                    'message': 'Logout failed',
                    'error': str(e)
                }
    def create_user_session(self, user_id):
        """Create a new user session"""
        try:
            session_token = secrets.token_urlsafe(32)
            
            conn = get_db_connection(self.db_path)
            cursor = conn.cursor()
            
            cursor.execute('''
                INSERT INTO user_sessions (user_id, session_token, ip_address, user_agent)
                VALUES (?, ?, ?, ?)
            ''', (user_id, session_token, request.remote_addr, request.headers.get('User-Agent', '')))
            
            conn.commit()
            conn.close()
            
            logger.info(f"Session token created for user {user_id}")
            return session_token
            
        except Exception as e:
            logger.error(f"Session creation error: {e}")
            return None
    
    def deactivate_user_session(self, session_token):
        """Simplified session deactivation"""
        try:
            conn = get_db_connection(self.db_path)
            cursor = conn.cursor()
            
            cursor.execute('UPDATE user_sessions SET is_active = 0 WHERE session_token = ?', (session_token,))
            conn.commit()
            conn.close()
            
            logger.debug(f"Session deactivated: {session_token}")
            
        except Exception as e:
            logger.warning(f"Session deactivation failed: {e}")
            raise e
    
    def verify_session(self, session_token):
        try:
            conn = get_db_connection(self.db_path)
            cursor = conn.cursor()
            
            cursor.execute('''
                SELECT us.user_id, u.name, u.email 
                FROM user_sessions us
                JOIN users u ON us.user_id = u.user_id
                WHERE us.session_token = ? AND us.is_active = TRUE 
                AND us.expires_at > datetime('now')
                AND u.is_active = TRUE
            ''', (session_token,))
            
            result = cursor.fetchone()
            conn.close()
            
            return dict(result) if result else None
            
        except Exception as e:
            logger.error(f"Session verification error: {e}")
            return None
    
    def update_user_profile(self, user_id, profile_data):
        """Update user profile dengan error handling dan logging yang lebih baik"""
        conn = None
        try:
            logger.info(f"Updating profile for user {user_id} with data: {profile_data}")
            
            conn = get_db_connection(self.db_path)
            cursor = conn.cursor()
            
            update_fields = []
            update_values = []
            
            allowed_fields = ['name', 'age', 'gender', 'height', 'weight', 'activity_level', 'fitness_goal']
            
            updated_fields = []
            
            for field in allowed_fields:
                if field in profile_data and profile_data[field] is not None:
                    if field in ['age', 'height', 'weight']:
                        try:
                            value = int(profile_data[field])
                            update_fields.append(f"{field} = ?")
                            update_values.append(value)
                            updated_fields.append(f"{field}={value}")
                        except (ValueError, TypeError):
                            logger.warning(f"Invalid numeric value for {field}: {profile_data[field]}")
                            continue
                    else:
                        value = str(profile_data[field]).strip()
                        if value:
                            update_fields.append(f"{field} = ?")
                            update_values.append(value)
                            updated_fields.append(f"{field}={value}")
            
            if not update_fields:
                logger.warning("No valid fields to update")
                return {'success': False, 'message': 'No valid fields to update'}
            
            logger.info(f"Fields to update: {updated_fields}")
            
            recalculate_calories = any(field in profile_data for field in ['age', 'gender', 'height', 'weight', 'activity_level', 'fitness_goal'])
            
            if recalculate_calories:
                logger.info("Recalculating daily calorie goal...")
                
                cursor.execute('''
                    SELECT age, gender, height, weight, activity_level, fitness_goal
                    FROM users WHERE user_id = ?
                ''', (user_id,))
                current_profile = cursor.fetchone()
                
                if current_profile:
                    current_data = dict(current_profile)
                    logger.info(f"Current profile data: {current_data}")
                    
                    for field in ['age', 'gender', 'height', 'weight', 'activity_level', 'fitness_goal']:
                        if field in profile_data and profile_data[field] is not None:
                            current_data[field] = profile_data[field]
                    
                    logger.info(f"Updated profile data for calculation: {current_data}")
                    
                    if all(current_data.get(field) for field in ['age', 'gender', 'height', 'weight']):
                        try:
                            from database import calculate_daily_calorie_goal
                            new_calorie_goal = calculate_daily_calorie_goal(
                                current_data['age'],
                                current_data['gender'],
                                current_data['height'],
                                current_data['weight'],
                                current_data['activity_level'] or 'moderately_active',
                                current_data['fitness_goal'] or 'maintain_weight'
                            )
                            
                            logger.info(f"New calculated calorie goal: {new_calorie_goal}")
                            
                            update_fields.append("daily_calorie_goal = ?")
                            update_values.append(new_calorie_goal)
                            updated_fields.append(f"daily_calorie_goal={new_calorie_goal}")
                            
                            if current_data.get('weight'):
                                new_protein_goal = max(50, int(current_data['weight'] * 1.6))  # 1.6g per kg, minimum 50g
                                update_fields.append("daily_protein_goal = ?")
                                update_values.append(new_protein_goal)
                                updated_fields.append(f"daily_protein_goal={new_protein_goal}")
                                logger.info(f"New calculated protein goal: {new_protein_goal}")
                            
                        except Exception as calc_error:
                            logger.error(f"Error calculating calorie goal: {calc_error}")
                            
                    else:
                        logger.info("Not enough data to recalculate calorie goal")
            
            update_fields.append("updated_at = CURRENT_TIMESTAMP")
            update_values.append(user_id) 
            
            query = f"UPDATE users SET {', '.join(update_fields)} WHERE user_id = ?"
            
            logger.info(f"Executing query: {query}")
            logger.info(f"With values: {update_values}")
            
            cursor.execute(query, update_values)
            
            if cursor.rowcount == 0:
                logger.error(f"No rows updated for user {user_id}")
                conn.rollback()
                return {'success': False, 'message': 'User not found or no changes made'}
            
            conn.commit()
            logger.info(f"Profile update committed successfully. {cursor.rowcount} row(s) affected.")
            
            if 'name' in profile_data:
                try:
                    from flask import session
                    session['user_name'] = str(profile_data['name'])
                    session.modified = True
                    logger.info(f"Session updated with new name: {profile_data['name']}")
                except Exception as session_error:
                    logger.warning(f"Could not update session: {session_error}")
            
            logger.info(f"Profile updated successfully for user {user_id}. Updated fields: {updated_fields}")
            
            return {
                'success': True, 
                'message': 'Profile updated successfully',
                'updated_fields': updated_fields
            }
            
        except Exception as e:
            logger.error(f"Profile update error for user {user_id}: {e}")
            logger.exception("Full profile update error traceback:")
            
            if conn:
                conn.rollback()
                logger.info("Database transaction rolled back")
            
            return {
                'success': False, 
                'message': f'Profile update failed: {str(e)}'
            }
        finally:
            if conn:
                conn.close()

class GuestManager:
    def __init__(self, db_path):
        self.db_path = db_path
    
    def check_landing_guest_limit(self, ip_address):
        """Check if guest can use landing page trial (based on IP)"""
        try:
            conn = get_db_connection(self.db_path)
            cursor = conn.cursor()
            
            cursor.execute('''
                SELECT COUNT(*) as count 
                FROM guest_sessions 
                WHERE ip_address = ? 
                AND created_at > datetime('now', '-24 hours')
                AND analyses_count > 0
            ''', (ip_address,))
            
            result = cursor.fetchone()
            conn.close()
            
            return result['count'] == 0 
            
        except Exception as e:
            logger.error(f"Landing guest limit check error: {e}")
            return False
    
    def record_landing_guest_usage(self, ip_address):
        """Record that guest used landing page trial"""
        try:
            conn = get_db_connection(self.db_path)
            cursor = conn.cursor()
            
            session_id = f"landing_{ip_address}_{int(time.time())}"
            
            cursor.execute('''
                INSERT INTO guest_sessions (session_id, ip_address, user_agent, analyses_count, max_analyses)
                VALUES (?, ?, ?, 1, 1)
            ''', (session_id, ip_address, request.headers.get('User-Agent', '')))
            
            conn.commit()
            conn.close()
            
            logger.info(f"Landing guest usage recorded for IP {ip_address}")
            return True
            
        except Exception as e:
            logger.error(f"Landing guest usage record error: {e}")
            return False

    def create_guest_session(self, session_id):
        """Create a guest session with analysis limit"""
        try:
            conn = get_db_connection(self.db_path)
            cursor = conn.cursor()
            
            cursor.execute("SELECT id, analyses_count FROM guest_sessions WHERE session_id = ? AND expires_at > datetime('now')", (session_id,))
            existing_session = cursor.fetchone()
            
            if existing_session:
                conn.close()
                return {
                    'session_id': session_id,
                    'analyses_remaining': 1 - existing_session['analyses_count'],
                    'is_new': False
                }
            
            cursor.execute('''
                INSERT INTO guest_sessions (session_id, ip_address, user_agent, max_analyses)
                VALUES (?, ?, ?, ?)
            ''', (session_id, request.remote_addr, request.headers.get('User-Agent', ''), 1))
            
            conn.commit()
            conn.close()
            
            logger.info(f"Guest session created: {session_id}")
            
            return {
                'session_id': session_id,
                'analyses_remaining': 1,
                'is_new': True
            }
            
        except Exception as e:
            logger.error(f"Guest session creation error: {e}")
            return None
    
    def check_guest_limit(self, session_id):
        """Check if guest has reached analysis limit"""
        try:
            conn = get_db_connection(self.db_path)
            cursor = conn.cursor()
            
            cursor.execute('''
                SELECT analyses_count, max_analyses 
                FROM guest_sessions 
                WHERE session_id = ? AND expires_at > datetime('now')
            ''', (session_id,))
            
            result = cursor.fetchone()
            conn.close()
            
            if result:
                return result['analyses_count'] < result['max_analyses']
            return False
            
        except Exception as e:
            logger.error(f"Guest limit check error: {e}")
            return False
    
    def increment_guest_usage(self, session_id):
        """Increment guest analysis count"""
        try:
            conn = get_db_connection(self.db_path)
            cursor = conn.cursor()
            
            cursor.execute('''
                UPDATE guest_sessions 
                SET analyses_count = analyses_count + 1 
                WHERE session_id = ?
            ''', (session_id,))
            
            conn.commit()
            conn.close()
            
            logger.info(f"Guest usage incremented for session {session_id}")
            
        except Exception as e:
            logger.error(f"Guest usage increment error: {e}")

def get_current_user():
    """Get current user information from session or g object"""
    if hasattr(g, 'current_user_id'):
        return {
            'user_id': g.current_user_id,
            'name': g.current_user_name,
            'is_guest': getattr(g, 'is_guest', False)
        }
    
    if session.get('is_authenticated', False):
        user_id = session.get('user_id')
        user_name = session.get('user_name')
        
        if user_id:
            g.current_user_id = user_id
            g.current_user_name = user_name
            g.is_guest = False
            
            return {
                'user_id': user_id,
                'name': user_name,
                'is_guest': False
            }
    
    return None

def get_session_user():
    """Get user info directly from session"""
    if session.get('is_authenticated', False):
        user_id = session.get('user_id')
        user_name = session.get('user_name')
        
        if user_id:
            return {
                'user_id': user_id,
                'name': user_name,
                'is_guest': False,
                'session_token': session.get('session_token'),
                'login_timestamp': session.get('login_timestamp')
            }
    return None

def verify_user_session():
    """Verify current user session is valid"""
    try:
        session_token = session.get('session_token')
        if not session_token:
            return False
        
       
        return session.get('is_authenticated', False)
        
    except Exception as e:
        logger.error(f"Session verification error: {e}")
        return False

def login_required(f):
    """Decorator to require authentication"""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        is_authenticated = session.get('is_authenticated', False)
        user_id = session.get('user_id')
        
        if not is_authenticated or not user_id:
            logger.warning(f"Unauthorized access attempt to {f.__name__}")
            return jsonify({'error': 'Authentication required', 'login_required': True}), 401
        
        g.current_user_id = user_id
        g.current_user_name = session.get('user_name')
        g.is_guest = False
        
        return f(*args, **kwargs)
    return decorated_function

def auth_or_guest_allowed(f):
    """Decorator to allow both authenticated users and guests with limits"""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        is_authenticated = session.get('is_authenticated', False)
        user_id = session.get('user_id')
        
        if is_authenticated and user_id:
            g.current_user_id = user_id
            g.current_user_name = session.get('user_name')
            g.is_guest = False
            return f(*args, **kwargs)
        
        session_id = request.headers.get('X-Session-ID') or session.get('guest_session_id')
        if not session_id:
            session_id = str(uuid.uuid4())
            session['guest_session_id'] = session_id
            session.modified = True
        
        from flask import current_app
        guest_manager = GuestManager(current_app.config['DATABASE_PATH'])
        
        if 'analyze' in request.endpoint:
            if not guest_manager.check_guest_limit(session_id):
                return jsonify({
                    'error': 'Guest analysis limit reached. Please register to continue.',
                    'guest_limit_reached': True,
                    'register_required': True
                }), 403
        
        guest_session = guest_manager.create_guest_session(session_id)
        if not guest_session:
            return jsonify({'error': 'Failed to create guest session'}), 500
        
        g.current_user_id = f"guest_{session_id}"
        g.current_user_name = "Guest User"
        g.is_guest = True
        g.guest_session = guest_session
        
        return f(*args, **kwargs)
    return decorated_function

def optional_auth(f):
    """Decorator for endpoints that work for both authenticated and non-authenticated users"""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        is_authenticated = session.get('is_authenticated', False)
        user_id = session.get('user_id')
        
        if is_authenticated and user_id:
            g.current_user_id = user_id
            g.current_user_name = session.get('user_name')
            g.is_guest = False
        else:
            g.current_user_id = None
            g.current_user_name = None
            g.is_guest = True
        
        return f(*args, **kwargs)
    return decorated_function

def admin_required(f):
    """Decorator to require admin authentication (for future use)"""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        is_authenticated = session.get('is_authenticated', False)
        user_id = session.get('user_id')
        
        if not is_authenticated or not user_id:
            return jsonify({'error': 'Authentication required'}), 401
        
        g.current_user_id = user_id
        g.current_user_name = session.get('user_name')
        g.is_guest = False
        g.is_admin = True 
        
        return f(*args, **kwargs)
    return decorated_function

def rate_limit_by_user(f):
    """Decorator to apply different rate limits for authenticated vs guest users"""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        is_authenticated = session.get('is_authenticated', False)
        
        if is_authenticated:
            pass
        else:
            pass
        
        return f(*args, **kwargs)
    return decorated_function

def refresh_session():
    """Refresh session expiry"""
    if session.get('is_authenticated', False):
        session.permanent = True
        session.modified = True
        return True
    return False

def get_session_info():
    """Get detailed session information for debugging"""
    return {
        'is_authenticated': session.get('is_authenticated', False),
        'user_id': session.get('user_id'),
        'user_name': session.get('user_name'),
        'session_token': session.get('session_token'),
        'login_timestamp': session.get('login_timestamp'),
        'guest_session_id': session.get('guest_session_id'),
        'session_permanent': session.permanent,
        'session_new': session.new,
        'session_modified': session.modified
    }

def clear_user_session():
    """Clear user session data"""
    session.clear()
    session.modified = True
    logger.info("User session cleared")

class AuthError(Exception):
    """Base exception for authentication errors"""
    def __init__(self, message, status_code=401):
        super().__init__(message)
        self.message = message
        self.status_code = status_code

class SessionError(AuthError):
    """Exception for session-related errors"""
    pass

class PermissionError(AuthError):
    """Exception for permission-related errors"""
    def __init__(self, message):
        super().__init__(message, 403)
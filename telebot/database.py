import sqlite3
import json
import time
from typing import Dict, Any, Optional

DB_FILE = "data/bot_database.db"

def init_database():
    """Initialize SQLite database with all required tables"""
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    
    # Users table
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS users (
        user_id INTEGER PRIMARY KEY,
        first_name TEXT,
        username TEXT,
        balance REAL DEFAULT 0,
        total_earnings REAL DEFAULT 0,
        completed_tasks TEXT DEFAULT '[]',
        referrals INTEGER DEFAULT 0,
        referred_by INTEGER,
        joined_at REAL,
        current_task TEXT,
        language TEXT DEFAULT 'hindi',
        custom_settings TEXT DEFAULT '{}'
    )
    ''')
    
    # Tasks table
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS tasks (
        task_id TEXT PRIMARY KEY,
        title TEXT,
        description TEXT,
        link TEXT,
        reward REAL,
        quantity INTEGER,
        completed_count INTEGER DEFAULT 0,
        active INTEGER DEFAULT 1,
        created_at REAL
    )
    ''')
    
    # Withdrawal requests table
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS withdrawal_requests (
        request_id TEXT PRIMARY KEY,
        user_id INTEGER,
        amount REAL,
        upi_id TEXT,
        timestamp REAL,
        status TEXT DEFAULT 'pending',
        processed_at REAL
    )
    ''')
    
    # Blocked users table
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS blocked_users (
        user_id INTEGER PRIMARY KEY
    )
    ''')
    
    # Activity log table
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS activity_log (
        log_id INTEGER PRIMARY KEY AUTOINCREMENT,
        timestamp REAL,
        user_id INTEGER,
        action TEXT,
        data TEXT,
        datetime TEXT
    )
    ''')
    
    # Bot settings table
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS bot_settings (
        setting_key TEXT PRIMARY KEY,
        setting_value TEXT
    )
    ''')
    
    conn.commit()
    conn.close()
    print("✅ SQLite database initialized")

# User functions
def get_user(user_id: int) -> Optional[Dict]:
    conn = sqlite3.connect(DB_FILE)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM users WHERE user_id = ?", (user_id,))
    row = cursor.fetchone()
    conn.close()
    
    if row:
        user = dict(row)
        user['completed_tasks'] = json.loads(user['completed_tasks'])
        user['custom_settings'] = json.loads(user['custom_settings'])
        return user
    return None

def user_exists(user_id: int) -> bool:
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    cursor.execute("SELECT 1 FROM users WHERE user_id = ?", (user_id,))
    exists = cursor.fetchone() is not None
    conn.close()
    return exists

def create_user(user_id: int, first_name: str, username: str, referrer_id: Optional[int] = None, welcome_bonus: float = 5):
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    cursor.execute('''
    INSERT INTO users (user_id, first_name, username, balance, total_earnings, 
                      completed_tasks, referrals, referred_by, joined_at, 
                      current_task, language, custom_settings)
    VALUES (?, ?, ?, 0, 0, '[]', 0, ?, ?, NULL, 'hindi', ?)
    ''', (user_id, first_name, username, referrer_id, time.time(), 
          json.dumps({"welcome_bonus": welcome_bonus, "referral_reward": None, 
                     "milestone_count": None, "milestone_reward": None})))
    conn.commit()
    conn.close()

def get_all_users() -> Dict:
    conn = sqlite3.connect(DB_FILE)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM users")
    rows = cursor.fetchall()
    conn.close()
    
    users = {}
    for row in rows:
        user = dict(row)
        user['completed_tasks'] = json.loads(user['completed_tasks'])
        user['custom_settings'] = json.loads(user['custom_settings'])
        users[str(user['user_id'])] = user
    return users

def update_user_balance(user_id: int, amount: float):
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    cursor.execute('''
    UPDATE users 
    SET balance = balance + ?, total_earnings = total_earnings + ?
    WHERE user_id = ?
    ''', (amount, amount, user_id))
    conn.commit()
    conn.close()

def deduct_user_balance(user_id: int, amount: float):
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    cursor.execute('''
    UPDATE users 
    SET balance = MAX(0, balance - ?)
    WHERE user_id = ?
    ''', (amount, user_id))
    conn.commit()
    conn.close()

# Migration function from JSON to SQLite
def migrate_from_json():
    """Migrate existing JSON data to SQLite"""
    import os
    
    if not os.path.exists("data/users_data.json"):
        print("⚠️ No JSON file to migrate")
        return
    
    try:
        with open("data/users_data.json", 'r', encoding='utf-8') as f:
            users_data = json.load(f)
        
        conn = sqlite3.connect(DB_FILE)
        cursor = conn.cursor()
        
        migrated_count = 0
        for user_id, user in users_data.items():
            try:
                cursor.execute('''
                INSERT OR REPLACE INTO users 
                (user_id, first_name, username, balance, total_earnings, 
                 completed_tasks, referrals, referred_by, joined_at, 
                 current_task, language, custom_settings)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ''', (
                    user['id'], user.get('first_name', ''), user.get('username', ''),
                    user.get('balance', 0), user.get('total_earnings', 0),
                    json.dumps(user.get('completed_tasks', [])),
                    user.get('referrals', 0), user.get('referred_by'),
                    user.get('joined_at', time.time()), user.get('current_task'),
                    user.get('language', 'hindi'), 
                    json.dumps(user.get('custom_settings', {}))
                ))
                migrated_count += 1
            except Exception as e:
                print(f"❌ Failed to migrate user {user_id}: {e}")
        
        conn.commit()
        conn.close()
        
        # Backup the JSON file
        import shutil
        shutil.copy("data/users_data.json", "data/users_data.json.backup")
        
        print(f"✅ Migrated {migrated_count} users from JSON to SQLite")
        print(f"✅ Backup created at data/users_data.json.backup")
        
    except Exception as e:
        print(f"❌ Migration failed: {e}")

#!/usr/bin/env python3
import json
import os
import shutil
import threading
import time
import uuid
from datetime import datetime, timedelta
from typing import Any, Dict, List

import requests
import telebot
from flask import Flask
from telebot import types
from dotenv import load_dotenv
from urllib.parse import quote_plus, unquote_plus

load_dotenv()

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(BASE_DIR, "data")
BOT_TOKEN = os.environ.get("BOT_TOKEN")
ADMIN_ID = int(os.environ.get("ADMIN_ID", "5367009004"))
ADMIN_IDS = [int(x.strip()) for x in os.environ.get("ADMIN_IDS", "5367009004,6580698563").split(",") if x.strip()]

BOT_USERNAME = os.getenv("BOT_USERNAME", "Tasktoearnmoneybot")
MINIMUM_WITHDRAWAL = 10
REFERRAL_REWARD = 2
REFERRAL_MILESTONE_COUNT = 5
REFERRAL_MILESTONE_REWARD = 10
DEFAULT_WELCOME_BONUS = 5
USERS_DATA_FILE = os.path.join(DATA_DIR, "users_data.json")
BOT_DATA_FILE = os.path.join(DATA_DIR, "bot_data.json")
BLOCKED_USERS_FILE = os.path.join(DATA_DIR, "blocked_users.json")
ACTIVITY_LOG_FILE = os.path.join(DATA_DIR, "activity_log.json")
TASK_SUBMISSIONS_FILE = os.path.join(DATA_DIR, "task_submissions.json")
BACKUP_DIR = os.path.join(DATA_DIR, "backups")
MAX_BACKUPS = 50

admin_state = {}
pending_referrals = {}  # Store referrer_id for users who need to join channels first

MESSAGES = {
    "hindi": {
        "welcome": """🎉 स्वागत है! Task Reward Bot में आपका स्वागत है!

💰 कार्य पूरे करें और पैसे कमाएं
📸 स्क्रीनशॉट भेजकर कार्य सत्यापित करें
💵 न्यूनतम निकासी: ₹{min_withdrawal}
🔗 रेफर करें और ₹{referral_reward} प्रति रेफरल पाएं
🎁 वेलकम बोनस: ₹{welcome_bonus}

नीचे दिए गए बटन का उपयोग करें:""",
        "help": """📚 सहायता

🎯 सभी कार्य: सभी कार्य देखें
💰 बैलेंस: अपना बैलेंस चेक करें
💸 निकासी: पैसे निकालें (न्यूनतम ₹{min_withdrawal})
🔗 रेफर: दोस्तों को रेफर करें
❓ सहायता: यह मेसेज

⚠️ महत्वपूर्ण नियम:
• वास्तविक स्क्रीनशॉट भेजें
• नकली स्क्रीनशॉट से बैन हो सकते हैं
• एक कार्य केवल एक बार कर सकते हैं

📞 सहायता के लिए एडमिन से संपर्क करें""",
        "btn_new_task": "🎯 सभी कार्य",
        "btn_balance": "💰 बैलेंस",
        "btn_withdrawal": "💸 निकासी",
        "btn_refer": "🔗 रेफर",
        "btn_help": "❓ सहायता",
        "btn_language": "🌐 भाषा",
        "no_tasks": "❌ कोई कार्य उपलब्ध नहीं\n⏳ नए कार्य के लिए बाद में आएं",
        "task_already_active": "⚠️ आपका कार्य पहले से चालू है\n📸 स्क्रीनशॉट भेजें या /newtask दबाएं",
        "task_assigned": "✅ कार्य सौंपा गया!\n\n📋 कार्य: {title}\n📝 विवरण: {description}\n🌐 लिंक: {link}\n💰 रिवार्ड: ₹{reward}\n\n📸 कार्य पूरा करने के बाद स्क्रीनशॉट भेजें",
        "balance_info": "💰 आपका बैलेंस\n\n💵 उपलब्ध बैलेंस: ₹{balance}\n📊 कुल कमाई: ₹{total_earnings}\n🎯 पूर्ण कार्य: {completed_tasks}\n🔗 रेफरल्स: {referrals}",
        "insufficient_balance": "❌ अपर्याप्त बैलेंस\n💰 आपका बैलेंस: ₹{balance}\n💸 न्यूनतम निकासी: ₹{min_withdrawal}",
        "enter_upi": "💳 कृपया अपना UPI ID भेजें\nउदाहरण: 9876543210@paytm",
        "withdrawal_submitted": "✅ निकासी अनुरोध भेजा गया\n⏳ एडमिन द्वारा सत्यापन की प्रतीक्षा करें\n💰 राशि: ₹{amount}\n🏦 UPI: {upi_id}",
        "referral_info": """🔗 आपका रेफरल लिंक

{referral_link}

📊 आंकड़े:
🔗 कुल रेफरल्स: {referrals_count}
💰 रेफरल कमाई: ₹{referral_earnings}

🎁 रेफरल रिवार्ड:
• प्रत्येक रेफरल: ₹{referral_reward}
• {milestone_count} रेफरल पर बोनस: ₹{milestone_reward}

💡 अपने दोस्तों के साथ लिंक शेयर करें!""",
        "no_active_task": "❌ कोई सक्रिय कार्य नहीं\n🎯 पहले /newtask दबाएं",
        "screenshot_submitted": "✅ स्क्रीनशॉट भेजा गया\n⏳ सत्यापन के लिए प्रतीक्षा करें\n📝 एडमिन जल्द ही आपके कार्य की जांच करेंगे",
        "user_blocked": "🚫 आप इस बॉट का उपयोग नहीं कर सकते",
        "start_first": "❌ कृपया पहले /start दबाएं",
        "invalid_format": "❌ गलत फॉर्मेट। सही फॉर्मेट का उपयोग करें।",
        "select_language": "🌐 भाषा चुनें\nSelect Language:",
        "language_changed": "✅ भाषा बदली गई!",
        "menu_text": "📋 मेनू के लिए /start दबाएं या नीचे दिए गए बटन का उपयोग करें",
        "welcome_bonus_received": "🎁 वेलकम बोनस!\n\n💰 आपको ₹{amount} का वेलकम बोनस मिला है!",
        "task_approved": "✅ कार्य स्वीकृत!\n\n📋 कार्य: {title}\n💰 रिवार्ड: ₹{reward}\n💵 नया बैलेंस: ₹{balance}",
        "task_rejected": "❌ कार्य अस्वीकृत\n\n📋 कार्य: {title}\n📝 कारण: {reason}\n\n🔄 कृपया पुनः प्रयास करें",
        "task_limit_reached": "⚠️ यह कार्य पूरा हो गया है\n📊 कार्य पूर्ण: {assigned}/{quantity}\n\n🎯 अन्य कार्य देखें: /newtask",
        "select_category": "🎯 **कार्य श्रेणी चुनें**\n\nकृपया एक श्रेणी चुनें:",
        "task_list_header": "📋 **उपलब्ध कार्य**\n\nकार्य चुनें:",
    },
    "english": {
        "welcome": """🎉 Welcome to Task Reward Bot!

💰 Complete tasks and earn money
📸 Submit screenshots to verify tasks
💵 Minimum withdrawal: ₹{min_withdrawal}
🔗 Refer friends and earn ₹{referral_reward} per referral
🎁 Welcome Bonus: ₹{welcome_bonus}

Use the buttons below:""",
        "help": """📚 Help

🎯 All Tasks: View available tasks
💰 Balance: Check your balance
💸 Withdrawal: Withdraw money (minimum ₹{min_withdrawal})
🔗 Refer: Refer friends
❓ Help: This message

⚠️ Important Rules:
• Submit real screenshots
• Fake screenshots will result in ban
• Each task can only be completed once

📞 Contact admin for support""",
        "btn_new_task": "🎯 All Tasks",
        "btn_balance": "💰 Balance",
        "btn_withdrawal": "💸 Withdrawal",
        "btn_refer": "🔗 Refer",
        "btn_help": "❓ Help",
        "btn_language": "🌐 Language",
        "no_tasks": "❌ No tasks available\n⏳ Check back later for new tasks",
        "task_already_active": "⚠️ You already have an active task\n📸 Submit screenshot or press /newtask",
        "task_assigned": "✅ Task assigned!\n\n📋 Task: {title}\n📝 Description: {description}\n🌐 Link: {link}\n💰 Reward: ₹{reward}\n\n📸 Submit screenshot after completing the task",
        "balance_info": "💰 Your Balance\n\n💵 Available Balance: ₹{balance}\n📊 Total Earnings: ₹{total_earnings}\n🎯 Completed Tasks: {completed_tasks}\n🔗 Referrals: {referrals}",
        "insufficient_balance": "❌ Insufficient balance\n💰 Your balance: ₹{balance}\n💸 Minimum withdrawal: ₹{min_withdrawal}",
        "enter_upi": "💳 Please send your UPI ID\nExample: 9876543210@paytm",
        "withdrawal_submitted": "✅ Withdrawal request submitted\n⏳ Wait for admin verification\n💰 Amount: ₹{amount}\n🏦 UPI: {upi_id}",
        "referral_info": """🔗 Your Referral Link

{referral_link}

📊 Statistics:
🔗 Total Referrals: {referrals_count}
💰 Referral Earnings: ₹{referral_earnings}

🎁 Referral Rewards:
• Each referral: ₹{referral_reward}
• Bonus at {milestone_count} referrals: ₹{milestone_reward}

💡 Share the link with your friends!""",
        "no_active_task": "❌ No active task\n🎯 Press /newtask first",
        "screenshot_submitted": "✅ Screenshot submitted\n⏳ Waiting for verification\n📝 Admin will verify your task soon",
        "user_blocked": "🚫 You are blocked from using this bot",
        "start_first": "❌ Please press /start first",
        "invalid_format": "❌ Invalid format. Please use correct format.",
        "select_language": "🌐 Select Language\nभाषा चुनें:",
        "language_changed": "✅ Language changed!",
        "menu_text": "📋 Press /start for menu or use the buttons below",
        "welcome_bonus_received": "🎁 Welcome Bonus!\n\n💰 You received ₹{amount} as welcome bonus!",
        "task_approved": "✅ Task Approved!\n\n📋 Task: {title}\n💰 Reward: ₹{reward}\n💵 New Balance: ₹{balance}",
        "task_rejected": "❌ Task Rejected\n\n📋 Task: {title}\n📝 Reason: {reason}\n\n🔄 Please try again",
        "task_limit_reached": "⚠️ This task is full\n📊 Task Completed: {assigned}/{quantity}\n\n🎯 Try other tasks: /newtask",
        "select_category": "🎯 **Select Task Category**\n\nPlease choose a category:",
        "task_list_header": "📋 **Available Tasks**\n\nSelect a task:",
    },
}


def get_message(user_language, key, **kwargs):
    if user_language not in MESSAGES:
        user_language = "hindi"
    message = MESSAGES[user_language].get(
        key, MESSAGES["hindi"].get(key, "Message not found")
    )
    if kwargs:
        try:
            return message.format(**kwargs)
        except:
            return message
    return message


def get_language_keyboard():
    keyboard = types.InlineKeyboardMarkup(row_width=2)
    hindi_btn = types.InlineKeyboardButton("🇮🇳 हिंदी", callback_data="lang_hindi")
    english_btn = types.InlineKeyboardButton("🇬🇧 English", callback_data="lang_english")
    keyboard.add(hindi_btn, english_btn)
    return keyboard


def is_admin(user_id):
    """Check if user is an admin"""
    return user_id in ADMIN_IDS


def ensure_data_directory():
    if not os.path.exists(DATA_DIR):
        os.makedirs(DATA_DIR)
    if not os.path.exists(BACKUP_DIR):
        os.makedirs(BACKUP_DIR)


def create_backup(filepath):
    """Create a timestamped backup of a JSON file"""
    if not os.path.exists(filepath):
        return False
    try:
        filename = os.path.basename(filepath)
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        backup_filename = f"{filename}.{timestamp}.backup"
        backup_path = os.path.join(BACKUP_DIR, backup_filename)
        shutil.copy2(filepath, backup_path)

        # Cleanup old backups
        backups = [f for f in os.listdir(BACKUP_DIR) if f.startswith(filename)]
        backups.sort(reverse=True)
        for old_backup in backups[MAX_BACKUPS:]:
            os.remove(os.path.join(BACKUP_DIR, old_backup))

        return True
    except Exception as e:
        print(f"❌ Backup failed for {filepath}: {e}")
        return False


def restore_latest_backup(filepath):
    """Restore the latest backup of a file"""
    try:
        filename = os.path.basename(filepath)
        backups = [f for f in os.listdir(BACKUP_DIR) if f.startswith(filename)]

        if not backups:
            print(f"⚠️ No backups found for {filename}")
            return False

        backups.sort(reverse=True)
        latest_backup = backups[0]
        backup_path = os.path.join(BACKUP_DIR, latest_backup)
        shutil.copy2(backup_path, filepath)
        print(f"✅ Restored {filename} from backup: {latest_backup}")
        return True
    except Exception as e:
        print(f"❌ Restore failed for {filepath}: {e}")
        return False


def initialize_data_files():
    ensure_data_directory()
    if not os.path.exists(USERS_DATA_FILE):
        print(f"⚠️ WARNING: {USERS_DATA_FILE} NOT FOUND!")
        print(f"🔄 Attempting to restore from backup...")
        if restore_latest_backup(USERS_DATA_FILE):
            print(f"✅ USER DATA RESTORED from backup!")
            try:
                with open(USERS_DATA_FILE, "r") as f:
                    data = json.load(f)
                    print(f"✅ Recovered {len(data)} users from backup")
            except:
                pass
        else:
            print(f"⚠️ No backup found - Creating new empty file (first run)")
            with open(USERS_DATA_FILE, "w") as f:
                json.dump({}, f)
    else:
        print(f"✅ {USERS_DATA_FILE} found - Loading existing user data")
        try:
            with open(USERS_DATA_FILE, "r") as f:
                data = json.load(f)
                print(f"✅ Loaded {len(data)} users from file")
        except Exception as e:
            print(f"❌ Error reading {USERS_DATA_FILE}: {e}")
    if not os.path.exists(BOT_DATA_FILE):
        initial_data = {
            "tasks": [],
            "withdrawal_requests": [],
            "required_channels": [],
            "settings": {
                "min_withdrawal": MINIMUM_WITHDRAWAL,
                "referral_reward": REFERRAL_REWARD,
                "default_welcome_bonus": DEFAULT_WELCOME_BONUS,
                "referral_milestone_count": REFERRAL_MILESTONE_COUNT,
                "referral_milestone_reward": REFERRAL_MILESTONE_REWARD,
            },
        }
        with open(BOT_DATA_FILE, "w") as f:
            json.dump(initial_data, f, indent=2)
    else:
        # Ensure required_channels exists in existing bot_data
        bot_data = get_bot_data()
        if "required_channels" not in bot_data:
            bot_data["required_channels"] = []
            save_bot_data(bot_data)
    if not os.path.exists(BLOCKED_USERS_FILE):
        with open(BLOCKED_USERS_FILE, "w") as f:
            json.dump([], f)
    if not os.path.exists(ACTIVITY_LOG_FILE):
        with open(ACTIVITY_LOG_FILE, "w") as f:
            json.dump([], f)
    if not os.path.exists(TASK_SUBMISSIONS_FILE):
        with open(TASK_SUBMISSIONS_FILE, "w") as f:
            json.dump([], f)


def load_json_file(filepath):
    try:
        with open(filepath, "r", encoding="utf-8") as f:
            return json.load(f)
    except:
        return {} if filepath in [USERS_DATA_FILE] else []


def save_json_file(filepath, data):
    try:
        # Create backup before saving (if file exists)
        if os.path.exists(filepath) and filepath == USERS_DATA_FILE:
            create_backup(filepath)

        with open(filepath, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
        return True
    except Exception as e:
        print(f"❌ Save failed for {filepath}: {e}")
        return False


def make_callback_data(prefix, value):
    return f"{prefix}:{quote_plus(str(value))}"


def parse_callback_data(data, prefix):
    if data.startswith(prefix + ":"):
        return unquote_plus(data.split(":", 1)[1])
    return None


def get_all_users_data():
    return load_json_file(USERS_DATA_FILE)


def get_user_data(user_id):
    users_data = get_all_users_data()
    return users_data.get(str(user_id), {})


def user_exists(user_id):
    users_data = get_all_users_data()
    return str(user_id) in users_data


def create_user(user_id, first_name, username, referrer_id=None):
    # Do not create user accounts for admins
    if is_admin(user_id):
        return
    users_data = get_all_users_data()
    bot_data = get_bot_data()
    settings = bot_data.get("settings", {})
    default_welcome_bonus = settings.get("default_welcome_bonus", DEFAULT_WELCOME_BONUS)

    user_data = {
        "id": user_id,
        "first_name": first_name,
        "username": username,
        "balance": 0,
        "total_earnings": 0,
        "completed_tasks": [],
        "referrals": 0,
        "referred_by": referrer_id,
        "joined_at": time.time(),
        "current_task": None,
        "language": "hindi",
        "custom_settings": {
            "referral_reward": None,
            "milestone_count": None,
            "milestone_reward": None,
            "welcome_bonus": default_welcome_bonus,
        },
    }
    users_data[str(user_id)] = user_data
    save_json_file(USERS_DATA_FILE, users_data)


def get_user_custom_setting(user_id, setting_key, default_value):
    user_data = get_user_data(user_id)
    if user_data and "custom_settings" in user_data:
        custom_value = user_data["custom_settings"].get(setting_key)
        if custom_value is not None:
            return custom_value
    return default_value


def set_user_custom_setting(user_id, setting_key, value):
    users_data = get_all_users_data()
    if str(user_id) in users_data:
        if "custom_settings" not in users_data[str(user_id)]:
            users_data[str(user_id)]["custom_settings"] = {}
        users_data[str(user_id)]["custom_settings"][setting_key] = value
        save_json_file(USERS_DATA_FILE, users_data)
        return True
    return False


def add_user_balance(user_id, amount):
    users_data = get_all_users_data()
    if str(user_id) in users_data:
        users_data[str(user_id)]["balance"] = (
            users_data[str(user_id)].get("balance", 0) + amount
        )
        users_data[str(user_id)]["total_earnings"] = (
            users_data[str(user_id)].get("total_earnings", 0) + amount
        )
        save_json_file(USERS_DATA_FILE, users_data)


def deduct_user_balance(user_id, amount):
    users_data = get_all_users_data()
    if str(user_id) in users_data:
        current_balance = users_data[str(user_id)].get("balance", 0)
        new_balance = max(0, current_balance - amount)
        users_data[str(user_id)]["balance"] = new_balance
        save_json_file(USERS_DATA_FILE, users_data)


def add_completed_task(user_id, task_id):
    users_data = get_all_users_data()
    if str(user_id) in users_data:
        completed_tasks = users_data[str(user_id)].get("completed_tasks", [])
        if task_id not in completed_tasks:
            completed_tasks.append(task_id)
            users_data[str(user_id)]["completed_tasks"] = completed_tasks
            save_json_file(USERS_DATA_FILE, users_data)


def increment_user_referrals(user_id):
    users_data = get_all_users_data()
    if str(user_id) in users_data:
        users_data[str(user_id)]["referrals"] = (
            users_data[str(user_id)].get("referrals", 0) + 1
        )
        save_json_file(USERS_DATA_FILE, users_data)


def set_user_current_task(user_id, task_id):
    users_data = get_all_users_data()
    if str(user_id) in users_data:
        users_data[str(user_id)]["current_task"] = task_id
        save_json_file(USERS_DATA_FILE, users_data)


def clear_user_current_task(user_id):
    users_data = get_all_users_data()
    if str(user_id) in users_data:
        users_data[str(user_id)]["current_task"] = None
        save_json_file(USERS_DATA_FILE, users_data)


def get_bot_data():
    return load_json_file(BOT_DATA_FILE)


def save_bot_data(data):
    save_json_file(BOT_DATA_FILE, data)


def add_withdrawal_request(request):
    bot_data = get_bot_data()
    if "withdrawal_requests" not in bot_data:
        bot_data["withdrawal_requests"] = []
    bot_data["withdrawal_requests"].append(request)
    save_bot_data(bot_data)


def add_task(task):
    bot_data = get_bot_data()
    if "tasks" not in bot_data:
        bot_data["tasks"] = []
    bot_data["tasks"].append(task)
    save_bot_data(bot_data)


def get_blocked_users():
    return load_json_file(BLOCKED_USERS_FILE)


def is_user_blocked(user_id):
    blocked_users = get_blocked_users()
    return user_id in blocked_users


def block_user(user_id):
    blocked_users = get_blocked_users()
    if user_id not in blocked_users:
        blocked_users.append(user_id)
        save_json_file(BLOCKED_USERS_FILE, blocked_users)


def unblock_user(user_id):
    blocked_users = get_blocked_users()
    if user_id in blocked_users:
        blocked_users.remove(user_id)
        save_json_file(BLOCKED_USERS_FILE, blocked_users)


def update_withdrawal_request_status(request_id, status):
    bot_data = get_bot_data()
    withdrawal_requests = bot_data.get("withdrawal_requests", [])
    for request in withdrawal_requests:
        if request["id"] == request_id:
            request["status"] = status
            request["processed_at"] = time.time()
            break
    save_bot_data(bot_data)


def get_user_language(user_id):
    user_data = get_user_data(user_id)
    if user_data:
        return user_data.get("language", "hindi")
    return "hindi"


def set_user_language(user_id, language):
    users_data = get_all_users_data()
    if str(user_id) in users_data:
        users_data[str(user_id)]["language"] = language
        save_json_file(USERS_DATA_FILE, users_data)


def log_activity(user_id, action, data=None):
    try:
        try:
            with open(ACTIVITY_LOG_FILE, "r", encoding="utf-8") as f:
                logs = json.load(f)
        except:
            logs = []
        log_entry = {
            "timestamp": time.time(),
            "user_id": user_id,
            "action": action,
            "data": data or {},
            "datetime": time.strftime("%Y-%m-%d %H:%M:%S"),
        }
        logs.append(log_entry)
        if len(logs) > 10000:
            logs = logs[-10000:]
        with open(ACTIVITY_LOG_FILE, "w", encoding="utf-8") as f:
            json.dump(logs, f, indent=2, ensure_ascii=False)
        return True
    except Exception as e:
        print(f"Logging error: {e}")
        return False


def broadcast_notification(message_text, exclude_user_id=None):
    """Send notification to all active users"""
    users_data = get_all_users_data()
    success_count = 0
    failed_count = 0

    for user_id_str, user_data in users_data.items():
        user_id = int(user_id_str)
        if exclude_user_id and user_id == exclude_user_id:
            continue
        if is_user_blocked(user_id):
            continue

        try:
            bot.send_message(user_id, message_text, parse_mode="Markdown")
            success_count += 1
            time.sleep(0.05)
        except Exception as e:
            failed_count += 1
            print(f"Broadcast failed for {user_id}: {e}")

    return success_count, failed_count


def get_required_channels():
    """Get list of required channels"""
    bot_data = get_bot_data()
    return bot_data.get("required_channels", [])


def add_required_channel(channel_username, channel_name):
    """Add a channel to the required channels list"""
    bot_data = get_bot_data()
    if "required_channels" not in bot_data:
        bot_data["required_channels"] = []

    # Remove @ if present
    channel_username = channel_username.strip().replace("@", "")

    # Check if channel already exists
    for channel in bot_data["required_channels"]:
        if channel["username"].lower() == channel_username.lower():
            return False, "Channel already exists"

    channel_data = {
        "username": channel_username,
        "name": channel_name,
        "added_at": time.time(),
    }
    bot_data["required_channels"].append(channel_data)
    save_bot_data(bot_data)
    return True, "Channel added successfully"


def remove_required_channel(channel_username):
    """Remove a channel from the required channels list"""
    bot_data = get_bot_data()
    if "required_channels" not in bot_data:
        bot_data["required_channels"] = []
        return False, "No channels found"

    initial_count = len(bot_data["required_channels"])
    bot_data["required_channels"] = [
        ch for ch in bot_data["required_channels"] if ch["username"] != channel_username
    ]

    if len(bot_data["required_channels"]) < initial_count:
        save_bot_data(bot_data)
        return True, "Channel removed successfully"
    return False, "Channel not found"


def check_user_joined_channels(user_id):
    """Check if user has joined all required channels"""
    required_channels = get_required_channels()

    if not required_channels:
        return True, [], []  # No channels required

    not_joined = []

    for channel in required_channels:
        try:
            # Use @username format to check membership
            chat_username = "@" + channel["username"]
            member = bot.get_chat_member(chat_username, user_id)
            if member.status in ["left", "kicked"]:
                not_joined.append(channel)
        except Exception as e:
            print(f"Error checking membership for channel @{channel['username']}: {e}")
            # If error, assume user hasn't joined
            not_joined.append(channel)

    if not_joined:
        return False, not_joined, required_channels
    return True, [], required_channels


def create_join_channels_keyboard(channels):
    """Create inline keyboard with channel join buttons"""
    keyboard = types.InlineKeyboardMarkup(row_width=1)

    for channel in channels:
        channel_url = f"https://t.me/{channel['username']}"
        btn = types.InlineKeyboardButton(f"📢 Join {channel['name']}", url=channel_url)
        keyboard.add(btn)

    check_btn = types.InlineKeyboardButton(
        "✅ Check Membership", callback_data="check_membership"
    )
    keyboard.add(check_btn)

    return keyboard


def get_task_categories():
    """Get all unique task categories from tasks"""
    bot_data = get_bot_data()
    tasks = bot_data.get("tasks", [])
    categories = set()
    for task in tasks:
        if task.get("active", True):
            category = task.get("category", "General")
            categories.add(category)
    return sorted(list(categories))


def get_tasks_by_category(category, user_id=None):
    """Get all active tasks in a specific category"""
    bot_data = get_bot_data()
    tasks = bot_data.get("tasks", [])
    user_data = get_user_data(user_id) if user_id else {}
    completed_tasks = user_data.get("completed_tasks", [])
    
    category_tasks = []
    for task in tasks:
        if task.get("active", True) and task.get("category", "General") == category:
            completed_count = task.get("completed_count", 0)
            quantity = task.get("quantity", 999999)
            if completed_count < quantity and task["id"] not in completed_tasks:
                category_tasks.append(task)
    return category_tasks


def create_category_keyboard(categories):
    """Create inline keyboard with category buttons"""
    keyboard = types.InlineKeyboardMarkup(row_width=1)
    
    category_icons = {
        "Download & Register": "📥",
        "Join Telegram Channel": "📢",
        "Follow Social Media": "👥",
        "Referral Tasks": "🔗",
        "General": "🎯",
    }
    
    for category in categories:
        icon = category_icons.get(category, "📋")
        btn = types.InlineKeyboardButton(
            f"{icon} {category}", 
            callback_data=make_callback_data("category", category)
        )
        keyboard.add(btn)
    
    return keyboard


def refresh_admin_panel(admin_chat_id, message_id):
    keyboard = types.InlineKeyboardMarkup(row_width=2)
    btn1 = types.InlineKeyboardButton(
        "💸 Withdrawal Requests", callback_data="admin_withdrawals"
    )
    btn2 = types.InlineKeyboardButton("🎯 Manage Tasks", callback_data="admin_tasks")
    btn3 = types.InlineKeyboardButton("📊 User Statistics", callback_data="admin_stats")
    btn4 = types.InlineKeyboardButton(
        "💰 Adjust Balance", callback_data="admin_adjust_balance"
    )
    btn5 = types.InlineKeyboardButton(
        "🚫 Block/Unblock User", callback_data="admin_block_user"
    )
    btn6 = types.InlineKeyboardButton(
        "📨 Message Center", callback_data="admin_message_center"
    )
    btn7 = types.InlineKeyboardButton(
        "🔗 Referral Settings", callback_data="admin_referral_settings"
    )
    btn8 = types.InlineKeyboardButton(
        "⚙️ Bot Settings", callback_data="admin_global_settings"
    )
    btn9 = types.InlineKeyboardButton(
        "📢 Manage Channels", callback_data="admin_channels"
    )
    refresh_btn = types.InlineKeyboardButton(
        "🔄 Refresh Panel", callback_data="admin_refresh"
    )

    keyboard.add(btn1, btn2)
    keyboard.add(btn3, btn4)
    keyboard.add(btn5, btn6)
    keyboard.add(btn7, btn8)
    keyboard.add(btn9)
    keyboard.add(refresh_btn)

    admin_msg = """🔧 **Admin Panel**

Select an option:

💸 Withdrawal Requests - Manage user withdrawals
🎯 Manage Tasks - Add/Edit tasks
📊 User Statistics - View all user stats
💰 Adjust Balance - Add/deduct user balance
🚫 Block/Unblock - Block or unblock users
📨 Message Center - Broadcast messages
🔗 Referral Settings - Per-user referral settings
⚙️ Bot Settings - Global bot settings
📢 Manage Channels - Add/Remove required channels
🔄 Refresh Panel - Refresh this panel"""

    try:
        bot.edit_message_text(
            admin_msg,
            admin_chat_id,
            message_id,
            reply_markup=keyboard,
            parse_mode="Markdown",
        )
    except Exception:
        # Fallback: send a new admin panel message
        try:
            bot.send_message(admin_chat_id, admin_msg, reply_markup=keyboard, parse_mode="Markdown")
        except Exception:
            pass


def complete_admin_action(admin_id, state):
    try:
        refresh_admin_panel(admin_id, state.get("message_id"))
    except Exception:
        pass
    admin_state.pop(admin_id, None)


app = Flask(__name__)


@app.route("/")
def home():
    return (
        """<!DOCTYPE html>
<html>
<head><title>Telegram Task Bot</title><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<style>body{font-family:Arial,sans-serif;margin:0;padding:20px;background:linear-gradient(135deg,#667eea 0%,#764ba2 100%);color:white;text-align:center;min-height:100vh;display:flex;flex-direction:column;justify-content:center;align-items:center}.container{background:rgba(255,255,255,0.1);padding:40px;border-radius:20px;backdrop-filter:blur(10px);box-shadow:0 8px 32px rgba(0,0,0,0.1);max-width:500px}.status{font-size:24px;margin-bottom:20px}.emoji{font-size:64px;margin-bottom:20px}.info{font-size:16px;opacity:0.8;line-height:1.6}.pulse{animation:pulse 2s infinite}@keyframes pulse{0%{transform:scale(1)}50%{transform:scale(1.05)}100%{transform:scale(1)}}</style>
</head>
<body><div class="container"><div class="emoji pulse">🤖</div><div class="status">Telegram Task Bot is Running!</div>
<div class="info"><p>✅ Bot Status: Online 24/7</p><p>🕐 Server Time: """
        + time.strftime("%Y-%m-%d %H:%M:%S UTC")
        + """</p><p>🚀 Ready to serve users</p><p>🔄 Auto-restart enabled</p></div></div></body></html>"""
    )


@app.route("/ping")
def ping():
    return "Bot is alive!"


@app.route("/health")
def health():
    return {"status": "UP", "service": "telegram-bot"}


@app.route("/alive")
def alive():
    return "UP"


@app.route("/status")
def status():
    return {
        "status": "online",
        "message": "🤖 Bot is alive!",
        "timestamp": time.strftime("%Y-%m-%d %H:%M:%S UTC"),
        "uptime": "24/7",
        "deployment": "stable",
    }


def run_server():
    try:
        port = int(os.environ.get("PORT", 5000))
        app.run(host="0.0.0.0", port=port, debug=False, use_reloader=False)
    except Exception as e:
        print(f"❌ Keep-alive server error: {e}")


def keep_alive():
    server_thread = threading.Thread(target=run_server)
    server_thread.daemon = True
    server_thread.start()
    print(
        f"🌐 Keep-alive server started on 0.0.0.0:{os.environ.get('PORT', '5000')}"
    )


if not BOT_TOKEN:
    raise RuntimeError(
        "BOT_TOKEN is not set. Please add BOT_TOKEN to your environment variables or .env file."
    )

bot = telebot.TeleBot(BOT_TOKEN)
print(f"Loaded bot with ADMIN_ID={ADMIN_ID}, ADMIN_IDS={ADMIN_IDS}")

initialize_data_files()


@bot.message_handler(commands=["start"])
def start_command(message):
    user_id = message.from_user.id
    if is_user_blocked(user_id):
        bot.reply_to(
            message,
            "🚫 आप इस बॉट का उपयोग नहीं कर सकते / You are blocked from using this bot",
        )
        return

    # If admin uses /start, open admin panel instead of user menu
    if is_admin(user_id):
        admin_panel(message)
        return

    # Extract referrer_id from command if present (for new users)
    referrer_id = None
    if len(message.text.split()) > 1 and not user_exists(user_id):
        try:
            referrer_id = int(message.text.split()[1])
            if user_exists(referrer_id) and referrer_id != user_id:
                # Store referrer_id for later processing after channel join
                pending_referrals[user_id] = referrer_id
        except:
            pass

    # Check if user needs to join channels
    has_joined, not_joined_channels, all_channels = check_user_joined_channels(user_id)
    if not has_joined:
        user_language = get_user_language(user_id) if user_exists(user_id) else "hindi"

        if user_language == "hindi":
            msg = f"""📢 **चैनल Join करें**

बॉट का उपयोग करने के लिए पहले नीचे दिए गए चैनल्स को join करें:

"""
        else:
            msg = f"""📢 **Join Channels Required**

To use this bot, please join the following channels:

"""

        for i, channel in enumerate(not_joined_channels, 1):
            msg += f"{i}. {channel['name']} (@{channel['username']})\n"

        if user_language == "hindi":
            msg += "\n✅ सभी चैनल्स join करने के बाद 'Check Membership' बटन दबाएं"
        else:
            msg += "\n✅ After joining all channels, click 'Check Membership'"

        keyboard = create_join_channels_keyboard(not_joined_channels)
        bot.reply_to(message, msg, reply_markup=keyboard, parse_mode="Markdown")
        return

    # User should already exist at this point (created after channel join verification)
    # If not, create them without referral (referral would have been stored in pending_referrals)
    if not user_exists(user_id):
        bot_data = get_bot_data()
        settings = bot_data.get("settings", {})
        welcome_bonus = settings.get("default_welcome_bonus", DEFAULT_WELCOME_BONUS)

        create_user(
            user_id, message.from_user.first_name, message.from_user.username, None
        )
        add_user_balance(user_id, welcome_bonus)
        log_activity(user_id, "user_registered", {"referrer": None})

    user_language = get_user_language(user_id)
    keyboard = types.ReplyKeyboardMarkup(
        row_width=2, resize_keyboard=True, one_time_keyboard=False
    )
    btn1 = types.KeyboardButton(get_message(user_language, "btn_new_task"))
    btn2 = types.KeyboardButton(get_message(user_language, "btn_balance"))
    btn3 = types.KeyboardButton(get_message(user_language, "btn_withdrawal"))
    btn4 = types.KeyboardButton(get_message(user_language, "btn_refer"))
    btn5 = types.KeyboardButton(get_message(user_language, "btn_help"))
    btn6 = types.KeyboardButton(get_message(user_language, "btn_language"))
    keyboard.add(btn1, btn2)
    keyboard.add(btn3, btn4)
    keyboard.add(btn5, btn6)

    bot_data = get_bot_data()
    settings = bot_data.get("settings", {})
    min_withdrawal = settings.get("min_withdrawal", MINIMUM_WITHDRAWAL)
    referral_reward = settings.get("referral_reward", REFERRAL_REWARD)
    welcome_bonus = settings.get("default_welcome_bonus", DEFAULT_WELCOME_BONUS)

    welcome_msg = get_message(
        user_language,
        "welcome",
        min_withdrawal=min_withdrawal,
        referral_reward=referral_reward,
        welcome_bonus=welcome_bonus,
    )
    bot.reply_to(message, welcome_msg, reply_markup=keyboard)
    log_activity(user_id, "start_command", {})


@bot.message_handler(commands=["admin"])
def admin_panel(message):
    if not is_admin(message.from_user.id):
        return

    keyboard = types.InlineKeyboardMarkup(row_width=2)
    btn1 = types.InlineKeyboardButton(
        "💸 Withdrawal Requests", callback_data="admin_withdrawals"
    )
    btn2 = types.InlineKeyboardButton("🎯 Manage Tasks", callback_data="admin_tasks")
    btn3 = types.InlineKeyboardButton("📊 User Statistics", callback_data="admin_stats")
    btn4 = types.InlineKeyboardButton(
        "💰 Adjust Balance", callback_data="admin_adjust_balance"
    )
    btn5 = types.InlineKeyboardButton(
        "🚫 Block/Unblock User", callback_data="admin_block_user"
    )
    btn6 = types.InlineKeyboardButton(
        "📨 Message Center", callback_data="admin_message_center"
    )
    btn7 = types.InlineKeyboardButton(
        "🔗 Referral Settings", callback_data="admin_referral_settings"
    )
    btn8 = types.InlineKeyboardButton(
        "⚙️ Bot Settings", callback_data="admin_global_settings"
    )
    btn9 = types.InlineKeyboardButton(
        "📢 Manage Channels", callback_data="admin_channels"
    )
    refresh_btn = types.InlineKeyboardButton(
        "🔄 Refresh Panel", callback_data="admin_refresh"
    )

    keyboard.add(btn1, btn2)
    keyboard.add(btn3, btn4)
    keyboard.add(btn5, btn6)
    keyboard.add(btn7, btn8)
    keyboard.add(btn9)
    keyboard.add(refresh_btn)

    admin_msg = """🔧 **Admin Panel**

Select an option:

💸 Withdrawal Requests - Manage user withdrawals
🎯 Manage Tasks - Add/Edit tasks
📊 User Statistics - View all user stats
💰 Adjust Balance - Add/deduct user balance
🚫 Block/Unblock - Block or unblock users
📨 Message Center - Broadcast messages
🔗 Referral Settings - Per-user referral settings
⚙️ Bot Settings - Global bot settings
📢 Manage Channels - Add/Remove required channels
🔄 Refresh Panel - Refresh this panel"""

    bot.send_message(
        message.from_user.id, admin_msg, reply_markup=keyboard, parse_mode="Markdown"
    )


@bot.callback_query_handler(func=lambda call: call.data.startswith("admin_"))
def handle_admin_callbacks(call):
    if not is_admin(call.from_user.id):
        return

    admin_id = call.from_user.id
    ADMIN_ID = admin_id

    if call.data == "admin_users_list":
        users_data = get_all_users_data()
        total_users = len(users_data)

        if total_users == 0:
            bot.edit_message_text(
                "❌ कोई user नहीं है", call.message.chat.id, call.message.message_id
            )
            return

        page = 0
        users_per_page = 10
        show_users_page(
            call.message.chat.id, call.message.message_id, page, users_per_page
        )

    elif call.data == "admin_stats":
        show_users_page(call.message.chat.id, call.message.message_id, 0, 10)

    elif call.data == "admin_referral_settings":
        msg = bot.edit_message_text(
            "🔍 User ID enter करें जिसके referral settings change करने हैं:",
            call.message.chat.id,
            call.message.message_id,
        )
        admin_state[call.from_user.id] = {
            "action": "search_user_for_referral",
            "message_id": msg.message_id,
        }

    elif call.data == "admin_adjust_balance":
        msg = bot.edit_message_text(
            "🔍 User ID enter करें जिसका balance adjust करना है:",
            call.message.chat.id,
            call.message.message_id,
        )
        admin_state[call.from_user.id] = {
            "action": "search_user_for_balance",
            "message_id": msg.message_id,
        }

    elif call.data == "admin_block_user":
        msg = bot.edit_message_text(
            "🔍 User ID enter करें जिसे block/unblock करना है:",
            call.message.chat.id,
            call.message.message_id,
        )
        admin_state[call.from_user.id] = {
            "action": "search_user_for_block",
            "message_id": msg.message_id,
        }

    elif call.data == "admin_withdrawals":
        bot_data = get_bot_data()
        withdrawal_requests = bot_data.get("withdrawal_requests", [])
        pending = [w for w in withdrawal_requests if w.get("status") == "pending"]

        if not pending:
            keyboard = types.InlineKeyboardMarkup()
            back_btn = types.InlineKeyboardButton(
                "🔙 Back", callback_data="admin_refresh"
            )
            keyboard.add(back_btn)
            bot.edit_message_text(
                "✅ कोई pending withdrawal नहीं है",
                call.message.chat.id,
                call.message.message_id,
                reply_markup=keyboard,
            )
            return

        msg = f"💸 **Pending Withdrawals** ({len(pending)})\n\n"
        for w in pending[:5]:
            msg += (
                f"User: {w['user_id']}\nAmount: ₹{w['amount']}\nUPI: {w['upi_id']}\n\n"
            )

        keyboard = types.InlineKeyboardMarkup()
        back_btn = types.InlineKeyboardButton("🔙 Back", callback_data="admin_refresh")
        keyboard.add(back_btn)
        bot.edit_message_text(
            msg,
            call.message.chat.id,
            call.message.message_id,
            reply_markup=keyboard,
            parse_mode="Markdown",
        )

    elif call.data == "admin_tasks":
        bot_data = get_bot_data()
        tasks = bot_data.get("tasks", [])

        msg = f"🎯 **Task Management**\n\n📋 Total Tasks: {len(tasks)}\n\n"

        if tasks:
            active_tasks = [t for t in tasks if t.get("active", True)]
            inactive_tasks = [t for t in tasks if not t.get("active", True)]
            msg += f"✅ Active: {len(active_tasks)}\n❌ Inactive: {len(inactive_tasks)}\n\n"

            for i, task in enumerate(tasks[:5], 1):
                status = "✅" if task.get("active", True) else "❌"
                completed = task.get("completed_count", 0)
                quantity = task.get("quantity", 999999)
                category = task.get("category", "General")
                msg += f"{i}. {status} {task['title']}\n   Category: {category} | Reward: ₹{task['reward']} | Done: {completed}/{quantity}\n\n"
        else:
            msg += "⚠️ No tasks available\n\n"

        keyboard = types.InlineKeyboardMarkup(row_width=2)
        add_btn = types.InlineKeyboardButton(
            "➕ Add New Task", callback_data="admin_task_add"
        )
        category_btn = types.InlineKeyboardButton(
            "📂 Manage Categories", callback_data="admin_manage_categories"
        )
        if tasks:
            view_btn = types.InlineKeyboardButton(
                "📋 View All Tasks", callback_data="admin_task_view_0"
            )
            keyboard.add(add_btn, view_btn)
            keyboard.add(category_btn)
        else:
            keyboard.add(add_btn, category_btn)
        back_btn = types.InlineKeyboardButton("🔙 Back", callback_data="admin_refresh")
        keyboard.add(back_btn)

        bot.edit_message_text(
            msg,
            call.message.chat.id,
            call.message.message_id,
            reply_markup=keyboard,
            parse_mode="Markdown",
        )

    elif call.data == "admin_message_center":
        msg = """📨 **Message Center**

Choose message type:

👤 **Single User** - Send message to specific user
📢 **Broadcast** - Send message to all users"""

        keyboard = types.InlineKeyboardMarkup(row_width=1)
        btn1 = types.InlineKeyboardButton(
            "👤 Send to Single User", callback_data="admin_msg_single"
        )
        btn2 = types.InlineKeyboardButton(
            "📢 Broadcast to All Users", callback_data="admin_msg_broadcast"
        )
        back_btn = types.InlineKeyboardButton("🔙 Back", callback_data="admin_refresh")
        keyboard.add(btn1, btn2, back_btn)
        bot.edit_message_text(
            msg,
            call.message.chat.id,
            call.message.message_id,
            reply_markup=keyboard,
            parse_mode="Markdown",
        )

    elif call.data == "admin_manage_categories":
        categories = get_task_categories()
        
        msg = "📂 **Task Categories Management**\n\n"
        msg += "Available Categories:\n\n"
        
        for i, cat in enumerate(categories, 1):
            tasks_in_cat = get_tasks_by_category(cat)
            msg += f"{i}. {cat} ({len(tasks_in_cat)} tasks)\n"
        
        if not categories:
            msg += "No categories found yet.\n"
        
        keyboard = types.InlineKeyboardMarkup(row_width=1)
        
        for cat in categories:
            btn = types.InlineKeyboardButton(
                f"📝 Edit: {cat}", callback_data=make_callback_data("admin_edit_category", cat)
            )
            keyboard.add(btn)
        
        back_btn = types.InlineKeyboardButton("🔙 Back to Tasks", callback_data="admin_tasks")
        keyboard.add(back_btn)
        
        bot.edit_message_text(
            msg,
            call.message.chat.id,
            call.message.message_id,
            reply_markup=keyboard,
            parse_mode="Markdown",
        )

    elif parse_callback_data(call.data, "admin_edit_category") is not None:
        category = parse_callback_data(call.data, "admin_edit_category")
        tasks_in_cat = get_tasks_by_category(category)
        
        msg = f"📝 **Edit Category: {category}**\n\n"
        msg += f"📊 Tasks in this category: {len(tasks_in_cat)}\n\n"
        msg += "**Tasks:**\n"
        
        for i, task in enumerate(tasks_in_cat, 1):
            msg += f"{i}. {task['title']}\n   Reward: ₹{task['reward']}\n"
        
        keyboard = types.InlineKeyboardMarkup(row_width=1)
        
        rename_btn = types.InlineKeyboardButton(
            "✏️ Rename Category", callback_data=make_callback_data("admin_rename_category", category)
        )
        delete_btn = types.InlineKeyboardButton(
            "🗑 Delete Category", callback_data=make_callback_data("admin_delete_category", category)
        )
        back_btn = types.InlineKeyboardButton(
            "🔙 Back to Categories", callback_data="admin_manage_categories"
        )
        
        keyboard.add(rename_btn)
        keyboard.add(delete_btn)
        keyboard.add(back_btn)
        
        bot.edit_message_text(
            msg,
            call.message.chat.id,
            call.message.message_id,
            reply_markup=keyboard,
            parse_mode="Markdown",
        )

    elif parse_callback_data(call.data, "admin_rename_category") is not None:
        category = parse_callback_data(call.data, "admin_rename_category")
        msg = bot.edit_message_text(
            f"📝 **Rename Category**\n\nCurrent name: {category}\n\nEnter new category name:",
            call.message.chat.id,
            call.message.message_id,
            parse_mode="Markdown",
        )
        admin_state[ADMIN_ID] = {
            "action": "rename_category",
            "old_category": category,
            "message_id": msg.message_id,
        }

    elif parse_callback_data(call.data, "admin_delete_category") is not None:
        category = parse_callback_data(call.data, "admin_delete_category")
        tasks_in_cat = get_tasks_by_category(category)
        
        msg = f"🗑 **Delete Category: {category}**\n\n"
        msg += f"⚠️ This will affect {len(tasks_in_cat)} tasks!\n\n"
        msg += "Choose action:\n"
        msg += "• **Move to General** - Move all tasks to General category\n"
        msg += "• **Delete All** - Delete all tasks in this category\n"
        msg += "• **Cancel** - Don't delete\n"
        
        keyboard = types.InlineKeyboardMarkup(row_width=1)
        move_btn = types.InlineKeyboardButton(
            "📂 Move to General", callback_data=make_callback_data("admin_move_category", category)
        )
        delete_all_btn = types.InlineKeyboardButton(
            "🗑 Delete All Tasks", callback_data=make_callback_data("admin_delete_all_category", category)
        )
        cancel_btn = types.InlineKeyboardButton(
            "❌ Cancel", callback_data=make_callback_data("admin_edit_category", category)
        )
        
        keyboard.add(move_btn)
        keyboard.add(delete_all_btn)
        keyboard.add(cancel_btn)
        
        bot.edit_message_text(
            msg,
            call.message.chat.id,
            call.message.message_id,
            reply_markup=keyboard,
            parse_mode="Markdown",
        )

    elif parse_callback_data(call.data, "admin_move_category") is not None:
        category = parse_callback_data(call.data, "admin_move_category")
        bot_data = get_bot_data()
        tasks = bot_data.get("tasks", [])
        moved_count = sum(1 for task in tasks if task.get("category") == category)
        
        # Move all tasks from this category to General
        for task in tasks:
            if task.get("category") == category:
                task["category"] = "General"
        
        save_bot_data(bot_data)
        
        bot.answer_callback_query(call.id, f"✅ Moved {moved_count} tasks to General")
        
        # Go back to categories
        categories = get_task_categories()
        msg = "📂 **Task Categories Management**\n\n"
        msg += "Available Categories:\n\n"
        
        for i, cat in enumerate(categories, 1):
            tasks_in_cat = get_tasks_by_category(cat)
            msg += f"{i}. {cat} ({len(tasks_in_cat)} tasks)\n"
        
        keyboard = types.InlineKeyboardMarkup(row_width=1)
        
        for cat in categories:
            btn = types.InlineKeyboardButton(
                f"📝 Edit: {cat}", callback_data=make_callback_data("admin_edit_category", cat)
            )
            keyboard.add(btn)
        
        back_btn = types.InlineKeyboardButton("🔙 Back to Tasks", callback_data="admin_tasks")
        keyboard.add(back_btn)
        
        bot.edit_message_text(
            msg,
            call.message.chat.id,
            call.message.message_id,
            reply_markup=keyboard,
            parse_mode="Markdown",
        )

    elif parse_callback_data(call.data, "admin_delete_all_category") is not None:
        category = parse_callback_data(call.data, "admin_delete_all_category")
        bot_data = get_bot_data()
        tasks = bot_data.get("tasks", [])
        
        # Delete all tasks in this category
        initial_count = len(tasks)
        bot_data["tasks"] = [t for t in tasks if t.get("category") != category]
        deleted_count = initial_count - len(bot_data["tasks"])
        
        save_bot_data(bot_data)
        
        bot.answer_callback_query(call.id, f"✅ Deleted {deleted_count} tasks")
        
        # Go back to categories
        categories = get_task_categories()
        msg = "📂 **Task Categories Management**\n\n"
        msg += "Available Categories:\n\n"
        
        for i, cat in enumerate(categories, 1):
            tasks_in_cat = get_tasks_by_category(cat)
            msg += f"{i}. {cat} ({len(tasks_in_cat)} tasks)\n"
        
        keyboard = types.InlineKeyboardMarkup(row_width=1)
        
        for cat in categories:
            btn = types.InlineKeyboardButton(
                f"📝 Edit: {cat}", callback_data=make_callback_data("admin_edit_category", cat)
            )
            keyboard.add(btn)
        
        back_btn = types.InlineKeyboardButton("🔙 Back to Tasks", callback_data="admin_tasks")
        keyboard.add(back_btn)
        
        bot.edit_message_text(
            msg,
            call.message.chat.id,
            call.message.message_id,
            reply_markup=keyboard,
            parse_mode="Markdown",
        )

    elif call.data == "admin_refresh":
        keyboard = types.InlineKeyboardMarkup(row_width=2)
        btn1 = types.InlineKeyboardButton(
            "💸 Withdrawal Requests", callback_data="admin_withdrawals"
        )
        btn2 = types.InlineKeyboardButton(
            "🎯 Manage Tasks", callback_data="admin_tasks"
        )
        btn3 = types.InlineKeyboardButton(
            "📊 User Statistics", callback_data="admin_stats"
        )
        btn4 = types.InlineKeyboardButton(
            "💰 Adjust Balance", callback_data="admin_adjust_balance"
        )
        btn5 = types.InlineKeyboardButton(
            "🚫 Block/Unblock User", callback_data="admin_block_user"
        )
        btn6 = types.InlineKeyboardButton(
            "📨 Message Center", callback_data="admin_message_center"
        )
        btn7 = types.InlineKeyboardButton(
            "🔗 Referral Settings", callback_data="admin_referral_settings"
        )
        btn8 = types.InlineKeyboardButton(
            "⚙️ Bot Settings", callback_data="admin_global_settings"
        )
        btn9 = types.InlineKeyboardButton(
            "📢 Manage Channels", callback_data="admin_channels"
        )
        refresh_btn = types.InlineKeyboardButton(
            "🔄 Refresh Panel", callback_data="admin_refresh"
        )

        keyboard.add(btn1, btn2)
        keyboard.add(btn3, btn4)
        keyboard.add(btn5, btn6)
        keyboard.add(btn7, btn8)
        keyboard.add(btn9)
        keyboard.add(refresh_btn)

        admin_msg = """🔧 **Admin Panel**

Select an option:

💸 Withdrawal Requests - Manage user withdrawals
🎯 Manage Tasks - Add/Edit tasks
📊 User Statistics - View all user stats
💰 Adjust Balance - Add/deduct user balance
🚫 Block/Unblock - Block or unblock users
📨 Message Center - Broadcast messages
🔗 Referral Settings - Per-user referral settings
⚙️ Bot Settings - Global bot settings
📢 Manage Channels - Add/Remove required channels
🔄 Refresh Panel - Refresh this panel"""

        bot.edit_message_text(
            admin_msg,
            call.message.chat.id,
            call.message.message_id,
            reply_markup=keyboard,
            parse_mode="Markdown",
        )

    elif call.data == "admin_channels":
        required_channels = get_required_channels()
        msg = f"""📢 **Manage Required Channels**

📋 Total Channels: {len(required_channels)}

"""

        if required_channels:
            for i, channel in enumerate(required_channels, 1):
                msg += f"{i}. **{channel['name']}**\n   @{channel['username']}\n\n"
        else:
            msg += "⚠️ No required channels set\n\n"

        keyboard = types.InlineKeyboardMarkup(row_width=1)
        add_btn = types.InlineKeyboardButton(
            "➕ Add Channel", callback_data="admin_channel_add"
        )
        keyboard.add(add_btn)

        if required_channels:
            for channel in required_channels:
                remove_btn = types.InlineKeyboardButton(
                    f"🗑 Remove {channel['name']}",
                    callback_data=f"admin_channel_remove_{channel['username']}",
                )
                keyboard.add(remove_btn)

        back_btn = types.InlineKeyboardButton("🔙 Back", callback_data="admin_refresh")
        keyboard.add(back_btn)

        bot.edit_message_text(
            msg,
            call.message.chat.id,
            call.message.message_id,
            reply_markup=keyboard,
            parse_mode="Markdown",
        )

    elif call.data == "admin_channel_add":
        msg = bot.edit_message_text(
            """➕ **Add Required Channel**

📝 Send channel details in this format:

`channel_username|channel_name`

**Example:**
`myawesomechannel|My Awesome Channel`

or

`@myawesomechannel|My Awesome Channel`

⚠️ **Important:**
1. Channel must be PUBLIC (have a username)
2. Bot must be admin in the channel
3. Don't include @ in username (it will be added automatically)""",
            call.message.chat.id,
            call.message.message_id,
            parse_mode="Markdown",
        )
        admin_state[call.from_user.id] = {
            "action": "channel_add_details",
            "message_id": msg.message_id,
        }

    elif call.data.startswith("admin_channel_remove_"):
        channel_username = call.data.replace("admin_channel_remove_", "")
        success, message = remove_required_channel(channel_username)

        if success:
            bot.answer_callback_query(call.id, "✅ Channel removed successfully!")
            log_activity(
                call.from_user.id,
                "channel_removed",
                {"channel_username": channel_username},
            )
        else:
            bot.answer_callback_query(call.id, f"❌ {message}")

        # Refresh the channels view
        required_channels = get_required_channels()
        msg = f"""📢 **Manage Required Channels**

📋 Total Channels: {len(required_channels)}

"""

        if required_channels:
            for i, channel in enumerate(required_channels, 1):
                msg += f"{i}. **{channel['name']}**\n   @{channel['username']}\n\n"
        else:
            msg += "⚠️ No required channels set\n\n"

        keyboard = types.InlineKeyboardMarkup(row_width=1)
        add_btn = types.InlineKeyboardButton(
            "➕ Add Channel", callback_data="admin_channel_add"
        )
        keyboard.add(add_btn)

        if required_channels:
            for channel in required_channels:
                remove_btn = types.InlineKeyboardButton(
                    f"🗑 Remove {channel['name']}",
                    callback_data=f"admin_channel_remove_{channel['username']}",
                )
                keyboard.add(remove_btn)

        back_btn = types.InlineKeyboardButton("🔙 Back", callback_data="admin_refresh")
        keyboard.add(back_btn)

        bot.edit_message_text(
            msg,
            call.message.chat.id,
            call.message.message_id,
            reply_markup=keyboard,
            parse_mode="Markdown",
        )

    elif call.data == "admin_search_user":
        msg = bot.edit_message_text(
            "🔍 User ID भेजें (number):", call.message.chat.id, call.message.message_id
        )
        admin_state[ADMIN_ID] = {"action": "search_user", "message_id": msg.message_id}

    elif call.data == "admin_global_settings":
        bot_data = get_bot_data()
        settings = bot_data.get("settings", {})

        msg = f"""⚙️ **Global Default Settings**

💸 Min Withdrawal: ₹{settings.get("min_withdrawal", MINIMUM_WITHDRAWAL)}
🔗 Referral Reward: ₹{settings.get("referral_reward", REFERRAL_REWARD)}
🎯 Milestone Count: {settings.get("referral_milestone_count", REFERRAL_MILESTONE_COUNT)}
🎁 Milestone Reward: ₹{settings.get("referral_milestone_reward", REFERRAL_MILESTONE_REWARD)}
🎉 Welcome Bonus: ₹{settings.get("default_welcome_bonus", DEFAULT_WELCOME_BONUS)}

ℹ️ These are default values for ALL users."""

        keyboard = types.InlineKeyboardMarkup(row_width=1)
        btn1 = types.InlineKeyboardButton(
            "💸 Edit Min Withdrawal", callback_data="admin_edit_global_min_withdrawal"
        )
        btn2 = types.InlineKeyboardButton(
            "🔗 Edit Referral Reward", callback_data="admin_edit_global_ref_reward"
        )
        btn3 = types.InlineKeyboardButton(
            "🎯 Edit Milestone Count", callback_data="admin_edit_global_milestone_count"
        )
        btn4 = types.InlineKeyboardButton(
            "🎁 Edit Milestone Reward",
            callback_data="admin_edit_global_milestone_reward",
        )
        btn5 = types.InlineKeyboardButton(
            "🎉 Edit Welcome Bonus", callback_data="admin_edit_global_welcome_bonus"
        )
        back_btn = types.InlineKeyboardButton("🔙 Back", callback_data="admin_back")
        keyboard.add(btn1, btn2, btn3, btn4, btn5, back_btn)

        bot.edit_message_text(
            msg,
            call.message.chat.id,
            call.message.message_id,
            reply_markup=keyboard,
            parse_mode="Markdown",
        )

    elif call.data == "admin_back":
        keyboard = types.InlineKeyboardMarkup(row_width=2)
        btn1 = types.InlineKeyboardButton(
            "💸 Withdrawal Requests", callback_data="admin_withdrawals"
        )
        btn2 = types.InlineKeyboardButton(
            "🎯 Manage Tasks", callback_data="admin_tasks"
        )
        btn3 = types.InlineKeyboardButton(
            "📊 User Statistics", callback_data="admin_stats"
        )
        btn4 = types.InlineKeyboardButton(
            "💰 Adjust Balance", callback_data="admin_adjust_balance"
        )
        btn5 = types.InlineKeyboardButton(
            "🚫 Block/Unblock User", callback_data="admin_block_user"
        )
        btn6 = types.InlineKeyboardButton(
            "📨 Message Center", callback_data="admin_message_center"
        )
        btn7 = types.InlineKeyboardButton(
            "🔗 Referral Settings", callback_data="admin_referral_settings"
        )
        btn8 = types.InlineKeyboardButton(
            "⚙️ Bot Settings", callback_data="admin_global_settings"
        )
        refresh_btn = types.InlineKeyboardButton(
            "🔄 Refresh Panel", callback_data="admin_refresh"
        )

        keyboard.add(btn1, btn2)
        keyboard.add(btn3, btn4)
        keyboard.add(btn5, btn6)
        keyboard.add(btn7, btn8)
        keyboard.add(refresh_btn)

        admin_msg = """🔧 **Admin Panel**

Select an option:

💸 Withdrawal Requests - Manage user withdrawals
🎯 Manage Tasks - Add/Edit tasks
📊 User Statistics - View all user stats
💰 Adjust Balance - Add/deduct user balance
🚫 Block/Unblock - Block or unblock users
📨 Message Center - Broadcast messages
🔗 Referral Settings - Per-user referral settings
⚙️ Bot Settings - Global bot settings
🔄 Refresh Panel - Refresh this panel"""

        bot.edit_message_text(
            admin_msg,
            call.message.chat.id,
            call.message.message_id,
            reply_markup=keyboard,
            parse_mode="Markdown",
        )

    elif call.data.startswith("admin_page_"):
        page = int(call.data.split("_")[-1])
        show_users_page(call.message.chat.id, call.message.message_id, page, 10)

    elif call.data.startswith("admin_view_user_"):
        user_id = int(call.data.replace("admin_view_user_", ""))
        show_user_details(call.message.chat.id, call.message.message_id, user_id)

    elif call.data.startswith("admin_edit_user_"):
        user_id = int(call.data.replace("admin_edit_user_", ""))
        show_user_edit_options(call.message.chat.id, call.message.message_id, user_id)

    elif call.data.startswith("admin_set_ref_reward_"):
        user_id = int(call.data.replace("admin_set_ref_reward_", ""))
        msg = bot.edit_message_text(
            f"💰 User {user_id} के लिए Referral Reward enter करें:\n\n(रुपये में, या 'default' type करें)",
            call.message.chat.id,
            call.message.message_id,
        )
        admin_state[ADMIN_ID] = {
            "action": "set_ref_reward",
            "user_id": user_id,
            "message_id": msg.message_id,
        }

    elif call.data.startswith("admin_set_milestone_count_"):
        user_id = int(call.data.replace("admin_set_milestone_count_", ""))
        msg = bot.edit_message_text(
            f"🎯 User {user_id} के लिए Milestone Count enter करें:\n\n(number, या 'default' type करें)",
            call.message.chat.id,
            call.message.message_id,
        )
        admin_state[ADMIN_ID] = {
            "action": "set_milestone_count",
            "user_id": user_id,
            "message_id": msg.message_id,
        }

    elif call.data.startswith("admin_set_milestone_reward_"):
        user_id = int(call.data.replace("admin_set_milestone_reward_", ""))
        msg = bot.edit_message_text(
            f"🎁 User {user_id} के लिए Milestone Reward enter करें:\n\n(रुपये में, या 'default' type करें)",
            call.message.chat.id,
            call.message.message_id,
        )
        admin_state[ADMIN_ID] = {
            "action": "set_milestone_reward",
            "user_id": user_id,
            "message_id": msg.message_id,
        }

    elif call.data.startswith("admin_set_welcome_bonus_"):
        user_id = int(call.data.replace("admin_set_welcome_bonus_", ""))
        msg = bot.edit_message_text(
            f"🎉 User {user_id} के लिए Welcome Bonus enter करें:\n\n(रुपये में, या 'default' type करें)",
            call.message.chat.id,
            call.message.message_id,
        )
        admin_state[ADMIN_ID] = {
            "action": "set_welcome_bonus",
            "user_id": user_id,
            "message_id": msg.message_id,
        }

    elif call.data.startswith("admin_add_balance_"):
        user_id = int(call.data.replace("admin_add_balance_", ""))
        msg = bot.edit_message_text(
            f"💰 User {user_id} के balance में add करने के लिए amount enter करें:",
            call.message.chat.id,
            call.message.message_id,
        )
        admin_state[ADMIN_ID] = {
            "action": "add_balance",
            "user_id": user_id,
            "message_id": msg.message_id,
        }

    elif call.data.startswith("admin_deduct_balance_"):
        user_id = int(call.data.replace("admin_deduct_balance_", ""))
        msg = bot.edit_message_text(
            f"💸 User {user_id} के balance से deduct करने के लिए amount enter करें:",
            call.message.chat.id,
            call.message.message_id,
        )
        admin_state[ADMIN_ID] = {
            "action": "deduct_balance",
            "user_id": user_id,
            "message_id": msg.message_id,
        }

    elif call.data.startswith("admin_block_"):
        user_id = int(call.data.replace("admin_block_", ""))
        block_user(user_id)
        bot.answer_callback_query(call.id, f"✅ User {user_id} blocked successfully!")
        bot.edit_message_text(
            f"🚫 User {user_id} has been blocked",
            call.message.chat.id,
            call.message.message_id,
        )
        log_activity(ADMIN_ID, "user_blocked_by_admin", {"user_id": user_id})
        try:
            bot.send_message(
                user_id, "🚫 आपका account admin द्वारा block कर दिया गया है।"
            )
        except:
            pass

    elif call.data.startswith("admin_unblock_"):
        user_id = int(call.data.replace("admin_unblock_", ""))
        unblock_user(user_id)
        bot.answer_callback_query(call.id, f"✅ User {user_id} unblocked successfully!")
        bot.edit_message_text(
            f"✅ User {user_id} has been unblocked",
            call.message.chat.id,
            call.message.message_id,
        )
        log_activity(ADMIN_ID, "user_unblocked_by_admin", {"user_id": user_id})
        try:
            bot.send_message(
                user_id,
                "✅ आपका account unblock कर दिया गया है। अब आप bot use कर सकते हैं।",
            )
        except:
            pass

    elif call.data == "admin_edit_global_min_withdrawal":
        msg = bot.edit_message_text(
            "💸 सभी users के लिए Minimum Withdrawal amount enter करें (रुपये में):",
            call.message.chat.id,
            call.message.message_id,
        )
        admin_state[ADMIN_ID] = {
            "action": "edit_global_min_withdrawal",
            "message_id": msg.message_id,
        }

    elif call.data == "admin_edit_global_ref_reward":
        msg = bot.edit_message_text(
            "🔗 सभी users के लिए Referral Reward enter करें (रुपये में):",
            call.message.chat.id,
            call.message.message_id,
        )
        admin_state[ADMIN_ID] = {
            "action": "edit_global_ref_reward",
            "message_id": msg.message_id,
        }

    elif call.data == "admin_edit_global_milestone_count":
        msg = bot.edit_message_text(
            "🎯 सभी users के लिए Milestone Count enter करें (संख्या में):",
            call.message.chat.id,
            call.message.message_id,
        )
        admin_state[ADMIN_ID] = {
            "action": "edit_global_milestone_count",
            "message_id": msg.message_id,
        }

    elif call.data == "admin_edit_global_milestone_reward":
        msg = bot.edit_message_text(
            "🎁 सभी users के लिए Milestone Reward enter करें (रुपये में):",
            call.message.chat.id,
            call.message.message_id,
        )
        admin_state[ADMIN_ID] = {
            "action": "edit_global_milestone_reward",
            "message_id": msg.message_id,
        }

    elif call.data == "admin_edit_global_welcome_bonus":
        msg = bot.edit_message_text(
            "🎉 सभी users के लिए Welcome Bonus enter करें (रुपये में):",
            call.message.chat.id,
            call.message.message_id,
        )
        admin_state[ADMIN_ID] = {
            "action": "edit_global_welcome_bonus",
            "message_id": msg.message_id,
        }

    elif call.data == "admin_msg_single":
        msg = bot.edit_message_text(
            "👤 **Send Message to Single User**\n\nUser ID enter करें जिसे message भेजना है:",
            call.message.chat.id,
            call.message.message_id,
            parse_mode="Markdown",
        )
        admin_state[ADMIN_ID] = {
            "action": "msg_single_get_user",
            "message_id": msg.message_id,
        }

    elif call.data == "admin_msg_broadcast":
        msg = bot.edit_message_text(
            "📢 **Broadcast Message to All Users**\n\nवह message type करें जो सभी users को भेजना है:",
            call.message.chat.id,
            call.message.message_id,
            parse_mode="Markdown",
        )
        admin_state[ADMIN_ID] = {
            "action": "msg_broadcast_get_message",
            "message_id": msg.message_id,
        }

    elif call.data == "admin_task_add":
        msg = bot.edit_message_text(
            "➕ **Add New Task**\n\n📝 Task का Title enter करें:",
            call.message.chat.id,
            call.message.message_id,
            parse_mode="Markdown",
        )
        admin_state[ADMIN_ID] = {
            "action": "task_add_title",
            "message_id": msg.message_id,
            "task_data": {},
        }

    elif call.data.startswith("admin_task_view_"):
        page = int(call.data.split("_")[-1])
        bot_data = get_bot_data()
        tasks = bot_data.get("tasks", [])

        per_page = 5
        total_pages = (len(tasks) - 1) // per_page + 1 if tasks else 0
        start = page * per_page
        end = start + per_page

        msg = f"📋 **All Tasks** (Page {page + 1}/{total_pages})\n\n"

        for i, task in enumerate(tasks[start:end], start + 1):
            status = "✅ Active" if task.get("active", True) else "❌ Inactive"
            completed = task.get("completed_count", 0)
            quantity = task.get("quantity", 999999)
            msg += f"**{i}. {task['title']}**\n"
            msg += f"   Status: {status}\n"
            msg += f"   Reward: ₹{task['reward']}\n"
            msg += f"   Completed: {completed}/{quantity}\n"
            msg += f"   Link: {task['link'][:30]}...\n\n"

        keyboard = types.InlineKeyboardMarkup(row_width=3)

        for task in tasks[start:end]:
            edit_btn = types.InlineKeyboardButton(
                f"✏️ Edit", callback_data=f"admin_task_edit_{task['id']}"
            )
            toggle_btn = types.InlineKeyboardButton(
                "🔄 Toggle" if task.get("active", True) else "🔄 Toggle",
                callback_data=f"admin_task_toggle_{task['id']}",
            )
            delete_btn = types.InlineKeyboardButton(
                f"🗑 Delete", callback_data=f"admin_task_delete_{task['id']}"
            )
            keyboard.row(edit_btn, toggle_btn, delete_btn)

        nav_buttons = []
        if page > 0:
            nav_buttons.append(
                types.InlineKeyboardButton(
                    "⬅️ Previous", callback_data=f"admin_task_view_{page - 1}"
                )
            )
        if page < total_pages - 1:
            nav_buttons.append(
                types.InlineKeyboardButton(
                    "➡️ Next", callback_data=f"admin_task_view_{page + 1}"
                )
            )

        if nav_buttons:
            keyboard.row(*nav_buttons)

        back_btn = types.InlineKeyboardButton(
            "🔙 Back to Tasks", callback_data="admin_tasks"
        )
        keyboard.add(back_btn)

        bot.edit_message_text(
            msg,
            call.message.chat.id,
            call.message.message_id,
            reply_markup=keyboard,
            parse_mode="Markdown",
        )

    elif call.data.startswith("admin_task_toggle_"):
        task_id = call.data.split("_")[-1]
        bot_data = get_bot_data()
        tasks = bot_data.get("tasks", [])

        for task in tasks:
            if task["id"] == task_id:
                task["active"] = not task.get("active", True)
                save_bot_data(bot_data)
                status = "Active" if task["active"] else "Inactive"
                bot.answer_callback_query(call.id, f"✅ Task is now {status}!")

                if task["active"]:
                    msg_text = f"🔔 **New Task Available!**\n\n📋 {task['title']}\n💰 Reward: ₹{task['reward']}\n\nGet task now: /newtask"
                    success, failed = broadcast_notification(msg_text)
                    bot.send_message(
                        ADMIN_ID,
                        f"📢 Task activated! Notification sent to {success} users",
                    )

                log_activity(
                    ADMIN_ID,
                    "admin_task_toggled",
                    {"task_id": task_id, "active": task["active"]},
                )

                # Refresh the view
                bot_data = get_bot_data()
                tasks = bot_data.get("tasks", [])
                msg = f"🎯 **Task Management**\n\n📋 Total Tasks: {len(tasks)}\n\n"

                if tasks:
                    active_tasks = [t for t in tasks if t.get("active", True)]
                    inactive_tasks = [t for t in tasks if not t.get("active", True)]
                    msg += f"✅ Active: {len(active_tasks)}\n❌ Inactive: {len(inactive_tasks)}\n\n"

                    for i, t in enumerate(tasks[:5], 1):
                        st = "✅" if t.get("active", True) else "❌"
                        completed = t.get("completed_count", 0)
                        quantity = t.get("quantity", 999999)
                        msg += f"{i}. {st} {t['title']}\n   Reward: ₹{t['reward']} | Done: {completed}/{quantity}\n\n"

                keyboard = types.InlineKeyboardMarkup(row_width=2)
                add_btn = types.InlineKeyboardButton(
                    "➕ Add New Task", callback_data="admin_task_add"
                )
                view_btn = types.InlineKeyboardButton(
                    "📋 View All Tasks", callback_data="admin_task_view_0"
                )
                keyboard.add(add_btn, view_btn)
                back_btn = types.InlineKeyboardButton(
                    "🔙 Back", callback_data="admin_refresh"
                )
                keyboard.add(back_btn)

                bot.edit_message_text(
                    msg,
                    call.message.chat.id,
                    call.message.message_id,
                    reply_markup=keyboard,
                    parse_mode="Markdown",
                )
                break

    elif call.data.startswith("admin_task_delete_"):
        task_id = call.data.split("_")[-1]
        bot_data = get_bot_data()
        tasks = bot_data.get("tasks", [])

        for i, task in enumerate(tasks):
            if task["id"] == task_id:
                task_title = task["title"]
                del tasks[i]
                save_bot_data(bot_data)
                bot.answer_callback_query(call.id, f"✅ Task '{task_title}' deleted!")
                log_activity(
                    ADMIN_ID,
                    "admin_task_deleted",
                    {"task_id": task_id, "title": task_title},
                )

                # Refresh the view
                bot_data = get_bot_data()
                tasks = bot_data.get("tasks", [])
                msg = f"🎯 **Task Management**\n\n📋 Total Tasks: {len(tasks)}\n\n"

                if tasks:
                    active_tasks = [t for t in tasks if t.get("active", True)]
                    inactive_tasks = [t for t in tasks if not t.get("active", True)]
                    msg += f"✅ Active: {len(active_tasks)}\n❌ Inactive: {len(inactive_tasks)}\n\n"

                    for i, t in enumerate(tasks[:5], 1):
                        st = "✅" if t.get("active", True) else "❌"
                        completed = t.get("completed_count", 0)
                        quantity = t.get("quantity", 999999)
                        msg += f"{i}. {st} {t['title']}\n   Reward: ₹{t['reward']} | Done: {completed}/{quantity}\n\n"
                else:
                    msg += "⚠️ No tasks available\n\n"

                keyboard = types.InlineKeyboardMarkup(row_width=2)
                add_btn = types.InlineKeyboardButton(
                    "➕ Add New Task", callback_data="admin_task_add"
                )
                if tasks:
                    view_btn = types.InlineKeyboardButton(
                        "📋 View All Tasks", callback_data="admin_task_view_0"
                    )
                    keyboard.add(add_btn, view_btn)
                else:
                    keyboard.add(add_btn)
                back_btn = types.InlineKeyboardButton(
                    "🔙 Back", callback_data="admin_refresh"
                )
                keyboard.add(back_btn)

                bot.edit_message_text(
                    msg,
                    call.message.chat.id,
                    call.message.message_id,
                    reply_markup=keyboard,
                    parse_mode="Markdown",
                )
                break

    elif call.data.startswith("admin_task_edit_title_"):
        task_id = call.data.split("_")[-1]
        msg = bot.edit_message_text(
            "📝 नया Task Title enter करें:", call.message.chat.id, call.message.message_id
        )
        admin_state[ADMIN_ID] = {
            "action": "task_edit_title",
            "task_id": task_id,
            "message_id": msg.message_id,
        }

    elif call.data.startswith("admin_task_edit_desc_"):
        task_id = call.data.split("_")[-1]
        msg = bot.edit_message_text(
            "📄 नया Task Description enter करें:",
            call.message.chat.id,
            call.message.message_id,
        )
        admin_state[ADMIN_ID] = {
            "action": "task_edit_desc",
            "task_id": task_id,
            "message_id": msg.message_id,
        }

    elif call.data.startswith("admin_task_edit_link_"):
        task_id = call.data.split("_")[-1]
        msg = bot.edit_message_text(
            "🔗 नया Task Link enter करें:", call.message.chat.id, call.message.message_id
        )
        admin_state[ADMIN_ID] = {
            "action": "task_edit_link",
            "task_id": task_id,
            "message_id": msg.message_id,
        }

    elif call.data.startswith("admin_task_edit_reward_"):
        task_id = call.data.split("_")[-1]
        msg = bot.edit_message_text(
            "💰 नया Task Reward enter करें (रुपये में):",
            call.message.chat.id,
            call.message.message_id,
        )
        admin_state[ADMIN_ID] = {
            "action": "task_edit_reward",
            "task_id": task_id,
            "message_id": msg.message_id,
        }

    elif call.data.startswith("admin_task_edit_qty_"):
        task_id = call.data.split("_")[-1]
        msg = bot.edit_message_text(
            "📊 नया Task Quantity enter करें (कितने users कर सकते हैं):",
            call.message.chat.id,
            call.message.message_id,
        )
        admin_state[ADMIN_ID] = {
            "action": "task_edit_qty",
            "task_id": task_id,
            "message_id": msg.message_id,
        }

    elif call.data.startswith("admin_task_edit_category_"):
        task_id = call.data.split("_")[-1]
        msg = bot.edit_message_text(
            "📂 **Edit Task Category**\n\nAvailable categories:\n1️⃣ Download & Register\n2️⃣ Join Telegram Channel\n3️⃣ Follow Social Media\n4️⃣ Referral Tasks\n5️⃣ General\n\nया कोई अन्य category का नाम type करें:",
            call.message.chat.id,
            call.message.message_id,
            parse_mode="Markdown",
        )
        admin_state[ADMIN_ID] = {
            "action": "task_edit_category",
            "task_id": task_id,
            "message_id": msg.message_id,
        }

    elif call.data.startswith("admin_task_edit_"):
        task_id = call.data.split("_")[-1]
        bot_data = get_bot_data()
        tasks = bot_data.get("tasks", [])

        for task in tasks:
            if task["id"] == task_id:
                msg = f"""✏️ **Edit Task**

📝 Title: {task["title"]}
📄 Description: {task["description"]}
🔗 Link: {task["link"]}
💰 Reward: ₹{task["reward"]}
📊 Quantity: {task.get("quantity", 999999)}
📂 Category: {task.get("category", "General")}
✅ Status: {"Active" if task.get("active", True) else "Inactive"}

Select what to edit:"""

                keyboard = types.InlineKeyboardMarkup(row_width=2)
                title_btn = types.InlineKeyboardButton(
                    "📝 Title", callback_data=f"admin_task_edit_title_{task_id}"
                )
                desc_btn = types.InlineKeyboardButton(
                    "📄 Description", callback_data=f"admin_task_edit_desc_{task_id}"
                )
                link_btn = types.InlineKeyboardButton(
                    "🔗 Link", callback_data=f"admin_task_edit_link_{task_id}"
                )
                reward_btn = types.InlineKeyboardButton(
                    "💰 Reward", callback_data=f"admin_task_edit_reward_{task_id}"
                )
                qty_btn = types.InlineKeyboardButton(
                    "📊 Quantity", callback_data=f"admin_task_edit_qty_{task_id}"
                )
                category_btn = types.InlineKeyboardButton(
                    "📂 Category", callback_data=f"admin_task_edit_category_{task_id}"
                )

                keyboard.add(title_btn, desc_btn)
                keyboard.add(link_btn, reward_btn)
                keyboard.add(qty_btn, category_btn)

                back_btn = types.InlineKeyboardButton(
                    "🔙 Back", callback_data="admin_task_view_0"
                )
                keyboard.add(back_btn)

                bot.edit_message_text(
                    msg,
                    call.message.chat.id,
                    call.message.message_id,
                    reply_markup=keyboard,
                    parse_mode="Markdown",
                )
                break

def show_users_page(chat_id, message_id, page, per_page):
    users_data = get_all_users_data()
    users_list = list(users_data.items())
    total_users = len(users_list)
    total_pages = (total_users + per_page - 1) // per_page

    start_idx = page * per_page
    end_idx = min(start_idx + per_page, total_users)

    msg = f"👥 **All Users** (Page {page + 1}/{total_pages})\n\n"

    keyboard = types.InlineKeyboardMarkup(row_width=1)

    for user_id, user_data in users_list[start_idx:end_idx]:
        user_name = user_data.get("first_name", "Unknown")
        balance = user_data.get("balance", 0)
        tasks = len(user_data.get("completed_tasks", []))

        btn_text = f"{user_name} (ID: {user_id}) - ₹{balance} | {tasks} tasks"
        btn = types.InlineKeyboardButton(
            btn_text, callback_data=f"admin_view_user_{user_id}"
        )
        keyboard.add(btn)

    nav_buttons = []
    if page > 0:
        nav_buttons.append(
            types.InlineKeyboardButton(
                "◀️ Previous", callback_data=f"admin_page_{page - 1}"
            )
        )
    if page < total_pages - 1:
        nav_buttons.append(
            types.InlineKeyboardButton("Next ▶️", callback_data=f"admin_page_{page + 1}")
        )

    if nav_buttons:
        keyboard.row(*nav_buttons)

    back_btn = types.InlineKeyboardButton("🔙 Back to Menu", callback_data="admin_back")
    keyboard.add(back_btn)

    bot.edit_message_text(
        msg, chat_id, message_id, reply_markup=keyboard, parse_mode="Markdown"
    )


def show_user_details(chat_id, message_id, user_id):
    user_data = get_user_data(user_id)

    if not user_data:
        bot.edit_message_text("❌ User not found", chat_id, message_id)
        return

    bot_data = get_bot_data()
    settings = bot_data.get("settings", {})

    custom_ref_reward = get_user_custom_setting(user_id, "referral_reward", None)
    ref_reward_display = (
        f"₹{custom_ref_reward} (Custom)"
        if custom_ref_reward is not None
        else f"₹{settings.get('referral_reward', REFERRAL_REWARD)} (Default)"
    )

    custom_milestone_count = get_user_custom_setting(user_id, "milestone_count", None)
    milestone_count_display = (
        f"{custom_milestone_count} (Custom)"
        if custom_milestone_count is not None
        else f"{settings.get('referral_milestone_count', REFERRAL_MILESTONE_COUNT)} (Default)"
    )

    custom_milestone_reward = get_user_custom_setting(user_id, "milestone_reward", None)
    milestone_reward_display = (
        f"₹{custom_milestone_reward} (Custom)"
        if custom_milestone_reward is not None
        else f"₹{settings.get('referral_milestone_reward', REFERRAL_MILESTONE_REWARD)} (Default)"
    )

    custom_welcome_bonus = get_user_custom_setting(user_id, "welcome_bonus", None)
    welcome_bonus_display = (
        f"₹{custom_welcome_bonus} (Custom)"
        if custom_welcome_bonus is not None
        else f"₹{settings.get('default_welcome_bonus', DEFAULT_WELCOME_BONUS)} (Default)"
    )

    join_date = datetime.fromtimestamp(user_data.get("joined_at", 0)).strftime(
        "%Y-%m-%d %H:%M"
    )

    msg = f"""👤 **User Details**

**Basic Info:**
• ID: `{user_id}`
• Name: {user_data.get("first_name", "N/A")}
• Username: @{user_data.get("username", "N/A")}
• Language: {user_data.get("language", "hindi")}
• Joined: {join_date}

**Balance & Earnings:**
• Current Balance: ₹{user_data.get("balance", 0)}
• Total Earnings: ₹{user_data.get("total_earnings", 0)}

**Activity:**
• Completed Tasks: {len(user_data.get("completed_tasks", []))}
• Referrals: {user_data.get("referrals", 0)}
• Referred By: {user_data.get("referred_by", "None")}

**Custom Settings:**
• Referral Reward: {ref_reward_display}
• Milestone Count: {milestone_count_display}
• Milestone Reward: {milestone_reward_display}
• Welcome Bonus: {welcome_bonus_display}"""

    keyboard = types.InlineKeyboardMarkup(row_width=2)
    edit_btn = types.InlineKeyboardButton(
        "✏️ Edit Settings", callback_data=f"admin_edit_user_{user_id}"
    )
    back_btn = types.InlineKeyboardButton("🔙 Back", callback_data="admin_users_list")
    keyboard.add(edit_btn)
    keyboard.add(back_btn)

    bot.edit_message_text(
        msg, chat_id, message_id, reply_markup=keyboard, parse_mode="Markdown"
    )


def show_user_edit_options(chat_id, message_id, user_id):
    msg = f"✏️ **Edit User Settings**\n\nUser ID: `{user_id}`\n\nक्या edit करना चाहते हैं?"

    keyboard = types.InlineKeyboardMarkup(row_width=1)
    btn1 = types.InlineKeyboardButton(
        "💰 Set Referral Reward", callback_data=f"admin_set_ref_reward_{user_id}"
    )
    btn2 = types.InlineKeyboardButton(
        "🎯 Set Milestone Count", callback_data=f"admin_set_milestone_count_{user_id}"
    )
    btn3 = types.InlineKeyboardButton(
        "🎁 Set Milestone Reward", callback_data=f"admin_set_milestone_reward_{user_id}"
    )
    btn4 = types.InlineKeyboardButton(
        "🎉 Set Welcome Bonus", callback_data=f"admin_set_welcome_bonus_{user_id}"
    )
    btn5 = types.InlineKeyboardButton(
        "➕ Add Balance", callback_data=f"admin_add_balance_{user_id}"
    )
    btn6 = types.InlineKeyboardButton(
        "➖ Deduct Balance", callback_data=f"admin_deduct_balance_{user_id}"
    )
    back_btn = types.InlineKeyboardButton(
        "🔙 Back", callback_data=f"admin_view_user_{user_id}"
    )

    keyboard.add(btn1, btn2, btn3, btn4, btn5, btn6, back_btn)

    bot.edit_message_text(
        msg, chat_id, message_id, reply_markup=keyboard, parse_mode="Markdown"
    )


@bot.message_handler(
    func=lambda message: is_admin(message.from_user.id)
    and message.from_user.id in admin_state
)
def handle_admin_input(message):
    admin_id = message.from_user.id
    # allow existing code below that references ADMIN_ID to use the current admin's id
    ADMIN_ID = admin_id
    state = admin_state.get(admin_id)
    if not state:
        return

    action = state.get("action")

    if action == "search_user":
        try:
            user_id = int(message.text.strip())
            if user_exists(user_id):
                bot.delete_message(message.chat.id, message.message_id)
                show_user_details(message.chat.id, state["message_id"], user_id)
            else:
                bot.send_message(ADMIN_ID, f"❌ User ID {user_id} not found")
        except:
            bot.send_message(ADMIN_ID, "❌ Invalid User ID")
        complete_admin_action(admin_id, state)

    elif action == "set_ref_reward":
        user_id = state["user_id"]
        try:
            if message.text.strip().lower() == "default":
                set_user_custom_setting(user_id, "referral_reward", None)
                bot.send_message(
                    ADMIN_ID,
                    f"✅ User {user_id} का Referral Reward default पर set हो गया",
                )
            else:
                amount = float(message.text.strip())
                set_user_custom_setting(user_id, "referral_reward", amount)
                bot.send_message(
                    ADMIN_ID,
                    f"✅ User {user_id} का Referral Reward ₹{amount} set हो गया",
                )
            log_activity(
                ADMIN_ID,
                "admin_set_referral_reward",
                {
                    "user_id": user_id,
                    "amount": amount
                    if message.text.strip().lower() != "default"
                    else "default",
                },
            )
        except:
            bot.send_message(ADMIN_ID, "❌ Invalid amount")
        complete_admin_action(admin_id, state)

    elif action == "set_milestone_count":
        user_id = state["user_id"]
        try:
            if message.text.strip().lower() == "default":
                set_user_custom_setting(user_id, "milestone_count", None)
                bot.send_message(
                    ADMIN_ID,
                    f"✅ User {user_id} का Milestone Count default पर set हो गया",
                )
            else:
                count = int(message.text.strip())
                set_user_custom_setting(user_id, "milestone_count", count)
                bot.send_message(
                    ADMIN_ID, f"✅ User {user_id} का Milestone Count {count} set हो गया"
                )
            log_activity(
                ADMIN_ID,
                "admin_set_milestone_count",
                {
                    "user_id": user_id,
                    "count": count
                    if message.text.strip().lower() != "default"
                    else "default",
                },
            )
        except:
            bot.send_message(ADMIN_ID, "❌ Invalid number")
        complete_admin_action(admin_id, state)

    elif action == "set_milestone_reward":
        user_id = state["user_id"]
        try:
            if message.text.strip().lower() == "default":
                set_user_custom_setting(user_id, "milestone_reward", None)
                bot.send_message(
                    ADMIN_ID,
                    f"✅ User {user_id} का Milestone Reward default पर set हो गया",
                )
            else:
                amount = float(message.text.strip())
                set_user_custom_setting(user_id, "milestone_reward", amount)
                bot.send_message(
                    ADMIN_ID,
                    f"✅ User {user_id} का Milestone Reward ₹{amount} set हो गया",
                )
            log_activity(
                ADMIN_ID,
                "admin_set_milestone_reward",
                {
                    "user_id": user_id,
                    "amount": amount
                    if message.text.strip().lower() != "default"
                    else "default",
                },
            )
        except:
            bot.send_message(ADMIN_ID, "❌ Invalid amount")
        complete_admin_action(admin_id, state)

    elif action == "set_welcome_bonus":
        user_id = state["user_id"]
        try:
            if message.text.strip().lower() == "default":
                set_user_custom_setting(user_id, "welcome_bonus", None)
                bot.send_message(
                    ADMIN_ID,
                    f"✅ User {user_id} का Welcome Bonus default पर set हो गया",
                )
            else:
                amount = float(message.text.strip())
                set_user_custom_setting(user_id, "welcome_bonus", amount)
                bot.send_message(
                    ADMIN_ID, f"✅ User {user_id} का Welcome Bonus ₹{amount} set हो गया"
                )
            log_activity(
                ADMIN_ID,
                "admin_set_welcome_bonus",
                {
                    "user_id": user_id,
                    "amount": amount
                    if message.text.strip().lower() != "default"
                    else "default",
                },
            )
        except:
            bot.send_message(ADMIN_ID, "❌ Invalid amount")
        complete_admin_action(admin_id, state)

    elif action == "add_balance":
        user_id = state["user_id"]
        try:
            amount = float(message.text.strip())
            add_user_balance(user_id, amount)
            bot.send_message(
                ADMIN_ID, f"✅ User {user_id} के balance में ₹{amount} add हो गया"
            )
            log_activity(
                ADMIN_ID, "admin_add_balance", {"user_id": user_id, "amount": amount}
            )
        except:
            bot.send_message(ADMIN_ID, "❌ Invalid amount")
        complete_admin_action(admin_id, state)

    elif action == "deduct_balance":
        user_id = state["user_id"]
        try:
            amount = float(message.text.strip())
            deduct_user_balance(user_id, amount)
            bot.send_message(
                ADMIN_ID, f"✅ User {user_id} के balance से ₹{amount} deduct हो गया"
            )
            log_activity(
                ADMIN_ID, "admin_deduct_balance", {"user_id": user_id, "amount": amount}
            )
        except:
            bot.send_message(ADMIN_ID, "❌ Invalid amount")
        complete_admin_action(admin_id, state)

    elif action == "search_user_for_referral":
        try:
            user_id = int(message.text.strip())
            if user_exists(user_id):
                bot.delete_message(message.chat.id, message.message_id)
                show_user_edit_options(message.chat.id, state["message_id"], user_id)
            else:
                bot.send_message(ADMIN_ID, f"❌ User ID {user_id} not found")
        except:
            bot.send_message(ADMIN_ID, "❌ Invalid User ID")
        complete_admin_action(admin_id, state)

    elif action == "search_user_for_balance":
        try:
            user_id = int(message.text.strip())
            if user_exists(user_id):
                bot.delete_message(message.chat.id, message.message_id)
                user_data = get_user_data(user_id)

                keyboard = types.InlineKeyboardMarkup(row_width=2)
                add_btn = types.InlineKeyboardButton(
                    "➕ Add Balance", callback_data=f"admin_add_balance_{user_id}"
                )
                deduct_btn = types.InlineKeyboardButton(
                    "➖ Deduct Balance", callback_data=f"admin_deduct_balance_{user_id}"
                )
                back_btn = types.InlineKeyboardButton(
                    "🔙 Back", callback_data="admin_refresh"
                )
                keyboard.add(add_btn, deduct_btn)
                keyboard.add(back_btn)

                msg = f"""💰 **Adjust Balance**

User ID: `{user_id}`
Name: {user_data.get("first_name", "N/A")}
Current Balance: ₹{user_data.get("balance", 0)}

Choose action:"""

                bot.edit_message_text(
                    msg,
                    message.chat.id,
                    state["message_id"],
                    reply_markup=keyboard,
                    parse_mode="Markdown",
                )
            else:
                bot.send_message(ADMIN_ID, f"❌ User ID {user_id} not found")
        except:
            bot.send_message(ADMIN_ID, "❌ Invalid User ID")
        complete_admin_action(admin_id, state)

    elif action == "search_user_for_block":
        try:
            user_id = int(message.text.strip())
            if user_exists(user_id):
                bot.delete_message(message.chat.id, message.message_id)
                user_data = get_user_data(user_id)
                is_blocked = is_user_blocked(user_id)

                keyboard = types.InlineKeyboardMarkup()
                if is_blocked:
                    action_btn = types.InlineKeyboardButton(
                        "✅ Unblock User", callback_data=f"admin_unblock_{user_id}"
                    )
                else:
                    action_btn = types.InlineKeyboardButton(
                        "🚫 Block User", callback_data=f"admin_block_{user_id}"
                    )
                back_btn = types.InlineKeyboardButton(
                    "🔙 Back", callback_data="admin_refresh"
                )
                keyboard.add(action_btn)
                keyboard.add(back_btn)

                status = "🚫 Blocked" if is_blocked else "✅ Active"
                msg = f"""🚫 **Block/Unblock User**

User ID: `{user_id}`
Name: {user_data.get("first_name", "N/A")}
Status: {status}

Choose action:"""

                bot.edit_message_text(
                    msg,
                    message.chat.id,
                    state["message_id"],
                    reply_markup=keyboard,
                    parse_mode="Markdown",
                )
            else:
                bot.send_message(ADMIN_ID, f"❌ User ID {user_id} not found")
        except:
            bot.send_message(ADMIN_ID, "❌ Invalid User ID")
        complete_admin_action(admin_id, state)

    elif action == "edit_global_min_withdrawal":
        try:
            amount = float(message.text.strip())
            bot_data = get_bot_data()
            if "settings" not in bot_data:
                bot_data["settings"] = {}
            bot_data["settings"]["min_withdrawal"] = amount
            save_bot_data(bot_data)
            bot.send_message(
                ADMIN_ID,
                f"✅ सभी users के लिए Minimum Withdrawal ₹{amount} set हो गया!\n\nअब सभी नए withdrawals के लिए यह limit apply होगी।",
            )
            log_activity(
                ADMIN_ID, "admin_edit_global_min_withdrawal", {"amount": amount}
            )
            # refresh admin panel in-place
            try:
                refresh_admin_panel(admin_id, state.get("message_id"))
            except Exception:
                pass
        except:
            bot.send_message(ADMIN_ID, "❌ Invalid amount. कृपया सही राशि enter करें।")
        del admin_state[admin_id]

    elif action == "edit_global_ref_reward":
        try:
            amount = float(message.text.strip())
            bot_data = get_bot_data()
            if "settings" not in bot_data:
                bot_data["settings"] = {}
            bot_data["settings"]["referral_reward"] = amount
            save_bot_data(bot_data)
            bot.send_message(
                ADMIN_ID,
                f"✅ सभी users के लिए Referral Reward ₹{amount} set हो गया!\n\nअब हर नए referral पर यह amount मिलेगा (जिन users के custom settings नहीं हैं)।",
            )

            msg_text = f"🔔 **Referral Reward Updated!**\n\n💰 New reward: ₹{amount} per referral\n\n🔗 Share your link: /refer"
            success, failed = broadcast_notification(msg_text)
            bot.send_message(
                ADMIN_ID,
                f"📢 Notification sent to users!\n✅ Success: {success}\n❌ Failed: {failed}",
            )

            log_activity(
                ADMIN_ID,
                "admin_edit_global_ref_reward",
                {"amount": amount, "notified": success},
            )
            try:
                refresh_admin_panel(admin_id, state.get("message_id"))
            except Exception:
                pass
        except:
            bot.send_message(ADMIN_ID, "❌ Invalid amount. कृपया सही राशि enter करें।")
        del admin_state[admin_id]

    elif action == "edit_global_milestone_count":
        try:
            count = int(message.text.strip())
            bot_data = get_bot_data()
            if "settings" not in bot_data:
                bot_data["settings"] = {}
            bot_data["settings"]["referral_milestone_count"] = count
            save_bot_data(bot_data)
            bot.send_message(
                ADMIN_ID,
                f"✅ सभी users के लिए Milestone Count {count} set हो गया!\n\nअब हर {count} referrals पर milestone bonus मिलेगा।",
            )

            msg_text = f"🔔 **Milestone Updated!**\n\n🎯 New milestone: Every {count} referrals\n\n🔗 Check progress: /refer"
            success, failed = broadcast_notification(msg_text)
            bot.send_message(
                ADMIN_ID,
                f"📢 Notification sent!\n✅ Success: {success}\n❌ Failed: {failed}",
            )

            log_activity(
                ADMIN_ID,
                "admin_edit_global_milestone_count",
                {"count": count, "notified": success},
            )
            try:
                refresh_admin_panel(admin_id, state.get("message_id"))
            except Exception:
                pass
        except:
            bot.send_message(ADMIN_ID, "❌ Invalid number. कृपया सही संख्या enter करें।")
        del admin_state[admin_id]

    elif action == "edit_global_milestone_reward":
        try:
            amount = float(message.text.strip())
            bot_data = get_bot_data()
            if "settings" not in bot_data:
                bot_data["settings"] = {}
            bot_data["settings"]["referral_milestone_reward"] = amount
            save_bot_data(bot_data)
            bot.send_message(
                ADMIN_ID,
                f"✅ सभी users के लिए Milestone Reward ₹{amount} set हो गया!\n\nअब milestone complete होने पर यह bonus मिलेगा।",
            )

            msg_text = f"🔔 **Milestone Reward Updated!**\n\n🏆 New bonus: ₹{amount}\n\n🔗 Start referring: /refer"
            success, failed = broadcast_notification(msg_text)
            bot.send_message(
                ADMIN_ID,
                f"📢 Notification sent!\n✅ Success: {success}\n❌ Failed: {failed}",
            )

            log_activity(
                ADMIN_ID,
                "admin_edit_global_milestone_reward",
                {"amount": amount, "notified": success},
            )
            try:
                refresh_admin_panel(admin_id, state.get("message_id"))
            except Exception:
                pass
        except:
            bot.send_message(ADMIN_ID, "❌ Invalid amount. कृपया सही राशि enter करें।")
        del admin_state[admin_id]

    elif action == "edit_global_welcome_bonus":
        try:
            amount = float(message.text.strip())
            bot_data = get_bot_data()
            if "settings" not in bot_data:
                bot_data["settings"] = {}
            bot_data["settings"]["default_welcome_bonus"] = amount
            save_bot_data(bot_data)
            bot.send_message(
                ADMIN_ID,
                f"✅ सभी users के लिए Welcome Bonus ₹{amount} set हो गया!\n\nअब हर नए user को यह welcome bonus मिलेगा।",
            )

            msg_text = f"🔔 **Welcome Bonus Updated!**\n\n🎁 New users get ₹{amount} bonus!\n\n🔗 Share your link: /refer"
            success, failed = broadcast_notification(msg_text)
            bot.send_message(
                ADMIN_ID,
                f"📢 Notification sent!\n✅ Success: {success}\n❌ Failed: {failed}",
            )

            log_activity(
                ADMIN_ID,
                "admin_edit_global_welcome_bonus",
                {"amount": amount, "notified": success},
            )
            try:
                refresh_admin_panel(admin_id, state.get("message_id"))
            except Exception:
                pass
        except:
            bot.send_message(ADMIN_ID, "❌ Invalid amount. कृपया सही राशि enter करें।")
        del admin_state[admin_id]

    elif action == "msg_single_get_user":
        try:
            user_id = int(message.text.strip())
            if user_exists(user_id):
                bot.delete_message(message.chat.id, message.message_id)
                user_data = get_user_data(user_id)
                bot.send_message(
                    ADMIN_ID,
                    f"✅ User मिल गया!\n\n👤 ID: {user_id}\n📝 Name: {user_data.get('first_name', 'N/A')}\n\nअब वह message type करें जो इस user को भेजना है:",
                )
                admin_state[ADMIN_ID] = {
                    "action": "msg_single_send",
                    "user_id": user_id,
                }
            else:
                bot.send_message(
                    ADMIN_ID,
                    f"❌ User ID {user_id} not found. कृपया सही User ID enter करें।",
                )
                complete_admin_action(admin_id, state)
        except:
            bot.send_message(ADMIN_ID, "❌ Invalid User ID. कृपया सही number enter करें।")
            complete_admin_action(admin_id, state)

    elif action == "msg_single_send":
        user_id = state["user_id"]
        message_text = message.text.strip()

        try:
            bot.send_message(
                user_id,
                f"📩 **Message from Admin**\n\n{message_text}",
                parse_mode="Markdown",
            )
            bot.send_message(
                ADMIN_ID,
                f"✅ Message successfully sent!\n\n👤 User ID: {user_id}\n📝 Message: {message_text}",
            )
            log_activity(
                ADMIN_ID,
                "admin_message_single",
                {"user_id": user_id, "message": message_text[:100]},
            )
        except Exception as e:
            bot.send_message(ADMIN_ID, f"❌ Message send करने में error आई:\n{str(e)}")
        complete_admin_action(admin_id, state)

    elif action == "msg_broadcast_get_message":
        message_text = message.text.strip()
        bot.delete_message(message.chat.id, message.message_id)

        users_data = get_all_users_data()
        total_users = len(users_data)

        bot.send_message(
            ADMIN_ID,
            f"📢 Broadcast शुरू हो रहा है...\n\n👥 Total Users: {total_users}\n📝 Message: {message_text}\n\n⏳ कृपया थोड़ा wait करें...",
        )

        success_count = 0
        failed_count = 0
        blocked_count = 0

        for user_id_str in users_data.keys():
            try:
                user_id = int(user_id_str)
                if is_user_blocked(user_id):
                    blocked_count += 1
                    continue

                bot.send_message(
                    user_id,
                    f"📢 **Broadcast Message**\n\n{message_text}",
                    parse_mode="Markdown",
                )
                success_count += 1
                time.sleep(0.05)
            except Exception as e:
                failed_count += 1

        summary = f"""✅ **Broadcast Complete!**

📊 Statistics:
• Total Users: {total_users}
• ✅ Sent Successfully: {success_count}
• ❌ Failed: {failed_count}
• 🚫 Blocked Users: {blocked_count}

📝 Message: {message_text[:100]}"""

        bot.send_message(ADMIN_ID, summary)
        log_activity(
            ADMIN_ID,
            "admin_broadcast",
            {
                "total_users": total_users,
                "success": success_count,
                "failed": failed_count,
                "blocked": blocked_count,
                "message": message_text[:100],
            },
        )
        complete_admin_action(admin_id, state)

    elif action == "task_add_title":
        state["task_data"]["title"] = message.text.strip()
        bot.delete_message(message.chat.id, message.message_id)
        bot.send_message(ADMIN_ID, "📄 अब Task का Description enter करें:")
        admin_state[ADMIN_ID]["action"] = "task_add_desc"

    elif action == "task_add_desc":
        state["task_data"]["description"] = message.text.strip()
        bot.delete_message(message.chat.id, message.message_id)
        bot.send_message(ADMIN_ID, "🔗 अब Task का Link enter करें:")
        admin_state[ADMIN_ID]["action"] = "task_add_link"

    elif action == "task_add_link":
        state["task_data"]["link"] = message.text.strip()
        bot.delete_message(message.chat.id, message.message_id)
        bot.send_message(ADMIN_ID, "💰 अब Task का Reward enter करें (रुपये में):")
        admin_state[ADMIN_ID]["action"] = "task_add_reward"

    elif action == "task_add_reward":
        try:
            reward = float(message.text.strip())
            state["task_data"]["reward"] = reward
            bot.delete_message(message.chat.id, message.message_id)
            bot.send_message(
                ADMIN_ID, "📊 अब Task की Quantity enter करें (कितने users कर सकते हैं):"
            )
            admin_state[ADMIN_ID]["action"] = "task_add_qty"
        except:
            bot.send_message(
                ADMIN_ID, "❌ Invalid reward amount. कृपया सही राशि enter करें।"
            )

    elif action == "task_add_category":
        state["task_data"]["category"] = message.text.strip()
        bot.delete_message(message.chat.id, message.message_id)
        bot.send_message(
            ADMIN_ID,
            "✅ Task Category set!\n\n📝 Title: " + state["task_data"]["title"] +
            "\n📄 Description: " + state["task_data"]["description"] +
            "\n🔗 Link: " + state["task_data"]["link"] +
            "\n💰 Reward: ₹" + str(state["task_data"]["reward"]) +
            "\n📊 Quantity: " + str(state["task_data"]["quantity"]) +
            "\n📂 Category: " + state["task_data"]["category"] +
            "\n\n✅ Task successfully created!"
        )
        
        # Save the task
        task_data = state["task_data"]
        task_data["id"] = str(uuid.uuid4())
        task_data["active"] = True
        task_data["completed_count"] = 0
        task_data["created_at"] = time.time()
        
        bot_data = get_bot_data()
        if "tasks" not in bot_data:
            bot_data["tasks"] = []
        bot_data["tasks"].append(task_data)
        save_bot_data(bot_data)
        
        msg_text = f"🔔 **New Task Available!**\n\n📋 {task_data['title']}\n📂 Category: {task_data['category']}\n💰 Reward: ₹{task_data['reward']}\n\nGet task now: /newtask"
        success, failed = broadcast_notification(msg_text)
        bot.send_message(
            ADMIN_ID,
            f"📢 Notification sent to users!\n✅ Success: {success}\n❌ Failed: {failed}",
        )
        
        log_activity(
            ADMIN_ID,
            "admin_task_added",
            {
                "task_id": task_data["id"],
                "title": task_data["title"],
                "category": task_data["category"],
                "reward": task_data["reward"],
                "notified": success,
            },
        )
        complete_admin_action(admin_id, state)

    elif action == "rename_category":
        old_category = state["old_category"]
        new_category = message.text.strip()
        bot.delete_message(message.chat.id, message.message_id)
        
        if not new_category:
            bot.send_message(ADMIN_ID, "❌ Category name cannot be empty!")
            complete_admin_action(admin_id, state)
            return
        
        if old_category == new_category:
            bot.send_message(ADMIN_ID, "❌ New name is same as old name!")
            complete_admin_action(admin_id, state)
            return
        
        bot_data = get_bot_data()
        tasks = bot_data.get("tasks", [])
        
        # Rename category for all tasks
        renamed_count = 0
        for task in tasks:
            if task.get("category") == old_category:
                task["category"] = new_category
                renamed_count += 1
        
        save_bot_data(bot_data)
        
        bot.send_message(
            ADMIN_ID,
            f"✅ Category Renamed!\n\n📝 Old name: {old_category}\n📝 New name: {new_category}\n📊 Tasks updated: {renamed_count}"
        )
        
        log_activity(
            ADMIN_ID,
            "admin_category_renamed",
            {
                "old_category": old_category,
                "new_category": new_category,
                "tasks_updated": renamed_count,
            },
        )
        complete_admin_action(admin_id, state)

    elif action == "channel_add_details":
        try:
            parts = message.text.strip().split("|")
            if len(parts) != 2:
                bot.send_message(
                    admin_id,
                    "❌ Invalid format!\n\nकृपया सही format में भेजें:\n`channel_username|channel_name`\n\nExample: myawesomechannel|My Awesome Channel",
                )
                return

            channel_username = parts[0].strip().replace("@", "")
            channel_name = parts[1].strip()

            if not channel_username or not channel_name:
                bot.send_message(
                    admin_id, "❌ Channel username and name cannot be empty!"
                )
                return

            success, msg = add_required_channel(channel_username, channel_name)

            if success:
                bot.send_message(
                    admin_id,
                    f"✅ Channel Added!\n\n📢 {channel_name}\n@{channel_username}\n\n⚠️ Bot must be admin in channel!\n✅ Users need to join to use bot.",
                )
                log_activity(
                    admin_id,
                    "channel_added",
                    {
                        "channel_username": channel_username,
                        "channel_name": channel_name,
                    },
                )
            else:
                bot.send_message(admin_id, f"❌ {msg}")

            del admin_state[admin_id]
        except Exception as e:
            bot.send_message(
                admin_id, f"❌ Error: {str(e)}\n\nFormat: channel_username|channel_name"
            )

    elif action == "task_add_qty":
        try:
            quantity = int(message.text.strip())
            state["task_data"]["quantity"] = quantity
            bot.delete_message(message.chat.id, message.message_id)
            
            # Show category options
            msg = """📂 **Select Task Category**

Available categories:
1️⃣ Download & Register
2️⃣ Join Telegram Channel
3️⃣ Follow Social Media
4️⃣ Referral Tasks
5️⃣ General

या कोई अन्य category का नाम type करें:"""
            
            bot.send_message(ADMIN_ID, msg)
            admin_state[ADMIN_ID]["action"] = "task_add_category"
        except:
            bot.send_message(ADMIN_ID, "❌ Invalid quantity. कृपया सही संख्या enter करें।")

    elif action == "task_edit_title":
        task_id = state["task_id"]
        new_title = message.text.strip()
        bot_data = get_bot_data()
        tasks = bot_data.get("tasks", [])

        for task in tasks:
            if task["id"] == task_id:
                old_title = task["title"]
                task["title"] = new_title
                save_bot_data(bot_data)
                bot.send_message(
                    ADMIN_ID,
                    f"✅ Task title updated!\n\nOld: {old_title}\nNew: {new_title}",
                )
                log_activity(
                    ADMIN_ID,
                    "admin_task_edited",
                    {"task_id": task_id, "field": "title", "new_value": new_title},
                )
                break
        complete_admin_action(admin_id, state)

    elif action == "task_edit_desc":
        task_id = state["task_id"]
        new_desc = message.text.strip()
        bot_data = get_bot_data()
        tasks = bot_data.get("tasks", [])

        for task in tasks:
            if task["id"] == task_id:
                task["description"] = new_desc
                save_bot_data(bot_data)
                bot.send_message(
                    ADMIN_ID, f"✅ Task description updated!\n\n{new_desc}"
                )
                log_activity(
                    ADMIN_ID,
                    "admin_task_edited",
                    {"task_id": task_id, "field": "description"},
                )
                break
        complete_admin_action(admin_id, state)

    elif action == "task_edit_link":
        task_id = state["task_id"]
        new_link = message.text.strip()
        bot_data = get_bot_data()
        tasks = bot_data.get("tasks", [])

        for task in tasks:
            if task["id"] == task_id:
                task["link"] = new_link
                save_bot_data(bot_data)
                bot.send_message(ADMIN_ID, f"✅ Task link updated!\n\n{new_link}")
                log_activity(
                    ADMIN_ID, "admin_task_edited", {"task_id": task_id, "field": "link"}
                )
                break
        complete_admin_action(admin_id, state)

    elif action == "task_edit_reward":
        try:
            task_id = state["task_id"]
            new_reward = float(message.text.strip())
            bot_data = get_bot_data()
            tasks = bot_data.get("tasks", [])

            for task in tasks:
                if task["id"] == task_id:
                    old_reward = task["reward"]
                    task["reward"] = new_reward
                    save_bot_data(bot_data)
                    bot.send_message(
                        ADMIN_ID,
                        f"✅ Task reward updated!\n\nOld: ₹{old_reward}\nNew: ₹{new_reward}",
                    )
                    log_activity(
                        ADMIN_ID,
                        "admin_task_edited",
                        {
                            "task_id": task_id,
                            "field": "reward",
                            "new_value": new_reward,
                        },
                    )
                    break
            complete_admin_action(admin_id, state)
        except:
            bot.send_message(
                ADMIN_ID, "❌ Invalid reward amount. कृपया सही राशि enter करें।"
            )
            complete_admin_action(admin_id, state)

    elif action == "task_edit_qty":
        try:
            task_id = state["task_id"]
            new_qty = int(message.text.strip())
            bot_data = get_bot_data()
            tasks = bot_data.get("tasks", [])

            for task in tasks:
                if task["id"] == task_id:
                    old_qty = task.get("quantity", 999999)
                    task["quantity"] = new_qty
                    save_bot_data(bot_data)
                    bot.send_message(
                        ADMIN_ID,
                        f"✅ Task quantity updated!\n\nOld: {old_qty}\nNew: {new_qty}",
                    )
                    log_activity(
                        ADMIN_ID,
                        "admin_task_edited",
                        {"task_id": task_id, "field": "quantity", "new_value": new_qty},
                    )
                    break
            complete_admin_action(admin_id, state)
        except:
            bot.send_message(ADMIN_ID, "❌ Invalid quantity. कृपया सही संख्या enter करें।")
            complete_admin_action(admin_id, state)

    elif action == "task_edit_category":
        task_id = state["task_id"]
        new_category = message.text.strip()
        bot.delete_message(message.chat.id, message.message_id)
        
        if not new_category:
            bot.send_message(ADMIN_ID, "❌ Category name cannot be empty!")
            complete_admin_action(admin_id, state)
            return
        
        bot_data = get_bot_data()
        tasks = bot_data.get("tasks", [])
        
        for task in tasks:
            if task["id"] == task_id:
                old_category = task.get("category", "General")
                task["category"] = new_category
                save_bot_data(bot_data)
                bot.send_message(
                    ADMIN_ID,
                    f"✅ Task category updated!\n\n📂 Old: {old_category}\n📂 New: {new_category}",
                )
                log_activity(
                    ADMIN_ID,
                    "admin_task_edited",
                    {"task_id": task_id, "field": "category", "new_value": new_category},
                )
                break
        complete_admin_action(admin_id, state)


@bot.message_handler(
    func=lambda message: message.text and message.text.startswith("🌐")
)
def language_command(message):
    user_id = message.from_user.id
    if is_user_blocked(user_id):
        return
    if not user_exists(user_id):
        bot.reply_to(message, get_message("hindi", "start_first"))
        return
    user_language = get_user_language(user_id)
    keyboard = get_language_keyboard()
    bot.send_message(
        user_id, get_message(user_language, "select_language"), reply_markup=keyboard
    )


@bot.callback_query_handler(func=lambda call: call.data == "check_membership")
def handle_check_membership(call):
    user_id = call.from_user.id

    # Check if user has joined all required channels
    has_joined, not_joined_channels, all_channels = check_user_joined_channels(user_id)

    if has_joined:
        user_language = get_user_language(user_id) if user_exists(user_id) else "hindi"

        # Process pending referral if user is new
        if not user_exists(user_id) and user_id in pending_referrals:
            referrer_id = pending_referrals[user_id]

            # Create the new user first
            bot_data = get_bot_data()
            settings = bot_data.get("settings", {})

            referrer_custom_reward = get_user_custom_setting(
                referrer_id, "referral_reward", None
            )
            if referrer_custom_reward is not None:
                referral_reward = referrer_custom_reward
            else:
                referral_reward = settings.get("referral_reward", REFERRAL_REWARD)

            referrer_custom_milestone_count = get_user_custom_setting(
                referrer_id, "milestone_count", None
            )
            if referrer_custom_milestone_count is not None:
                milestone_count = referrer_custom_milestone_count
            else:
                milestone_count = settings.get(
                    "referral_milestone_count", REFERRAL_MILESTONE_COUNT
                )

            referrer_custom_milestone_reward = get_user_custom_setting(
                referrer_id, "milestone_reward", None
            )
            if referrer_custom_milestone_reward is not None:
                milestone_reward = referrer_custom_milestone_reward
            else:
                milestone_reward = settings.get(
                    "referral_milestone_reward", REFERRAL_MILESTONE_REWARD
                )

            # Create new user with referral
            if not is_admin(user_id):
                create_user(
                    user_id, call.from_user.first_name, call.from_user.username, referrer_id
                )
            else:
                # Don't create admin as a regular user
                bot.send_message(user_id, "You're using an admin account.")

            # Reward referrer
            add_user_balance(referrer_id, referral_reward)
            increment_user_referrals(referrer_id)
            updated_referrer_data = get_user_data(referrer_id)
            new_referral_count = updated_referrer_data["referrals"]

            # Check milestone
            if new_referral_count % milestone_count == 0:
                add_user_balance(referrer_id, milestone_reward)
                bot.send_message(
                    referrer_id,
                    f"🎉 Milestone Bonus!\n\nआपने {milestone_count} referrals complete किए हैं!\nबोनस: ₹{milestone_reward}",
                )

            bot.send_message(
                referrer_id,
                f"🎉 New Referral!\n\nआपका एक friend बॉट में join कर गया!\nरिवॉर्ड: ₹{referral_reward}\nTotal Referrals: {new_referral_count}",
            )

            # Give welcome bonus to new user
            new_user_welcome_bonus = get_user_custom_setting(
                user_id, "welcome_bonus", None
            )
            if new_user_welcome_bonus is None:
                new_user_welcome_bonus = settings.get(
                    "default_welcome_bonus", DEFAULT_WELCOME_BONUS
                )
            add_user_balance(user_id, new_user_welcome_bonus)

            # Remove from pending
            del pending_referrals[user_id]

            log_activity(
                user_id,
                "new_user_registered",
                {"referred_by": referrer_id, "welcome_bonus": new_user_welcome_bonus},
            )
        elif not user_exists(user_id):
            # New user without referral
            bot_data = get_bot_data()
            settings = bot_data.get("settings", {})
            new_user_welcome_bonus = settings.get(
                "default_welcome_bonus", DEFAULT_WELCOME_BONUS
            )

            create_user(
                user_id, call.from_user.first_name, call.from_user.username, None
            )
            add_user_balance(user_id, new_user_welcome_bonus)

            log_activity(
                user_id,
                "new_user_registered",
                {"referred_by": None, "welcome_bonus": new_user_welcome_bonus},
            )

        if user_language == "hindi":
            success_msg = "✅ बधाई हो! आपने सभी चैनल्स join कर लिए हैं।\n\nअब आप बॉट का उपयोग कर सकते हैं। /start दबाएं"
        else:
            success_msg = "✅ Congratulations! You have joined all required channels.\n\nYou can now use the bot. Press /start"

        bot.answer_callback_query(call.id, "✅ Verification successful!")
        bot.edit_message_text(
            success_msg, call.message.chat.id, call.message.message_id
        )
        log_activity(
            user_id, "channel_membership_verified", {"channels": len(all_channels)}
        )
    else:
        user_language = get_user_language(user_id) if user_exists(user_id) else "hindi"

        if user_language == "hindi":
            fail_msg = f"❌ आपने अभी तक सभी चैनल्स join नहीं किए हैं।\n\nकृपया नीचे दिए गए चैनल्स को join करें:\n\n"
        else:
            fail_msg = f"❌ You haven't joined all channels yet.\n\nPlease join the following channels:\n\n"

        for i, channel in enumerate(not_joined_channels, 1):
            fail_msg += f"{i}. {channel['name']} (@{channel['username']})\n"

        if user_language == "hindi":
            fail_msg += "\nजoin करने के बाद फिर से 'Check Membership' दबाएं"
        else:
            fail_msg += "\nAfter joining, click 'Check Membership' again"

        keyboard = create_join_channels_keyboard(not_joined_channels)
        bot.answer_callback_query(call.id, "❌ Please join all channels first")
        bot.edit_message_text(
            fail_msg,
            call.message.chat.id,
            call.message.message_id,
            reply_markup=keyboard,
        )


@bot.callback_query_handler(func=lambda call: call.data.startswith("lang_"))
def handle_language_selection(call):
    user_id = call.from_user.id
    language = call.data.split("_")[1]
    set_user_language(user_id, language)
    bot.edit_message_text(
        get_message(language, "language_changed"),
        chat_id=call.message.chat.id,
        message_id=call.message.message_id,
    )
    bot.send_message(user_id, get_message(language, "menu_text"))
    log_activity(user_id, "language_changed", {"language": language})


@bot.message_handler(
    func=lambda message: message.text
    and (message.text.startswith("🎯") or message.text == "🎯 All Tasks")
)
@bot.message_handler(
    func=lambda message: message.text and message.text.startswith("📝")
)
@bot.message_handler(commands=["tasks"])
def tasks_command(message):
    user_id = message.from_user.id
    user_language = get_user_language(user_id)
    if is_user_blocked(user_id):
        bot.reply_to(message, get_message(user_language, "user_blocked"))
        return
    if not user_exists(user_id):
        bot.reply_to(message, get_message(user_language, "start_first"))
        return

    has_joined, not_joined_channels, all_channels = check_user_joined_channels(user_id)
    if not has_joined:
        if user_language == "hindi":
            msg = "📢 बॉट का उपयोग करने के लिए पहले सभी चैनल्स join करें:\\n\\n"
        else:
            msg = "📢 Please join all required channels first:\\n\\n"
        for i, ch in enumerate(not_joined_channels, 1):
            msg += f"{i}. {ch['name']} (@{ch['username']})\\n"
        keyboard = create_join_channels_keyboard(not_joined_channels)
        bot.reply_to(message, msg, reply_markup=keyboard)
        return

    # Get all categories
    categories = get_task_categories()
    
    if not categories:
        bot.reply_to(message, get_message(user_language, "no_tasks"))
        return

    msg = get_message(user_language, "select_category")
    keyboard = create_category_keyboard(categories)
    bot.reply_to(message, msg, reply_markup=keyboard, parse_mode="Markdown")
    log_activity(user_id, "tasks_categories_viewed", {"categories": len(categories)})


@bot.callback_query_handler(func=lambda call: call.data.startswith("category:"))
def handle_category_selection(call):
    user_id = call.from_user.id
    user_language = get_user_language(user_id)
    category = parse_callback_data(call.data, "category")
    
    if is_user_blocked(user_id):
        bot.answer_callback_query(call.id, get_message(user_language, "user_blocked"))
        return
    
    # Get tasks in this category
    category_tasks = get_tasks_by_category(category, user_id)
    
    if not category_tasks:
        bot.answer_callback_query(call.id, "❌ No tasks available in this category")
        return
    
    msg = get_message(user_language, "task_list_header")
    keyboard = types.InlineKeyboardMarkup(row_width=1)
    
    for task in category_tasks:
        button_text = f"📝 {task['title']} | 💰 ₹{task['reward']}"
        keyboard.add(
            types.InlineKeyboardButton(
                button_text, callback_data=f"view_task_{task['id']}"
            )
        )
    
    # Add back button
    back_btn = types.InlineKeyboardButton("🔙 Back to Categories", callback_data="back_to_categories")
    keyboard.add(back_btn)
    
    bot.edit_message_text(
        msg,
        chat_id=call.message.chat.id,
        message_id=call.message.message_id,
        reply_markup=keyboard,
        parse_mode="Markdown"
    )
    log_activity(user_id, "category_selected", {"category": category, "tasks_count": len(category_tasks)})


@bot.callback_query_handler(func=lambda call: call.data == "back_to_categories")
def handle_back_to_categories(call):
    user_id = call.from_user.id
    user_language = get_user_language(user_id)
    
    categories = get_task_categories()
    msg = get_message(user_language, "select_category")
    keyboard = create_category_keyboard(categories)
    
    bot.edit_message_text(
        msg,
        chat_id=call.message.chat.id,
        message_id=call.message.message_id,
        reply_markup=keyboard,
        parse_mode="Markdown"
    )


@bot.callback_query_handler(func=lambda call: call.data.startswith("view_task_"))
def handle_view_task_callback(call):
    user_id = call.from_user.id
    task_id = call.data.split("_")[-1]
    user_language = get_user_language(user_id)

    if is_user_blocked(user_id):
        bot.answer_callback_query(call.id, get_message(user_language, "user_blocked"))
        return

    tasks = get_bot_data().get("tasks", [])
    task = next((t for t in tasks if t["id"] == task_id), None)

    if not task:
        bot.answer_callback_query(call.id, "❌ Task not found.")
        return

    user_data = get_user_data(user_id)
    if task_id in user_data.get("completed_tasks", []):
        bot.answer_callback_query(call.id, "✅ You have already completed this task.")
        return

    set_user_current_task(user_id, task_id)
    task_message = get_message(
        user_language,
        "task_assigned",
        title=task["title"],
        description=task["description"],
        link=task["link"],
        reward=task["reward"],
    )
    bot.edit_message_text(
        task_message, chat_id=call.message.chat.id, message_id=call.message.message_id
    )
    log_activity(user_id, "task_selected", {"task_id": task_id})


@bot.message_handler(
    func=lambda message: message.text and message.text.startswith("💰")
)
@bot.message_handler(commands=["balance"])
def balance_command(message):
    user_id = message.from_user.id
    user_language = get_user_language(user_id)
    if is_user_blocked(user_id):
        bot.reply_to(message, get_message(user_language, "user_blocked"))
        return
    if not user_exists(user_id):
        bot.reply_to(message, get_message(user_language, "start_first"))
        return

    # Check channel membership
    has_joined, not_joined_channels, all_channels = check_user_joined_channels(user_id)
    if not has_joined:
        if user_language == "hindi":
            msg = "📢 बॉट का उपयोग करने के लिए पहले सभी चैनल्स join करें:\n\n"
        else:
            msg = "📢 Please join all required channels first:\n\n"
        for i, ch in enumerate(not_joined_channels, 1):
            msg += f"{i}. {ch['name']} (@{ch['username']})\n"
        keyboard = create_join_channels_keyboard(not_joined_channels)
        bot.reply_to(message, msg, reply_markup=keyboard)
        return
    user_data = get_user_data(user_id)
    if not user_data:
        bot.reply_to(message, get_message(user_language, "start_first"))
        return
    total_earnings = user_data.get("total_earnings", 0)
    current_balance = user_data.get("balance", 0)
    completed_tasks = len(user_data.get("completed_tasks", []))
    referrals = user_data.get("referrals", 0)
    balance_message = get_message(
        user_language,
        "balance_info",
        balance=current_balance,
        total_earnings=total_earnings,
        completed_tasks=completed_tasks,
        referrals=referrals,
    )
    bot.reply_to(message, balance_message)
    log_activity(user_id, "balance_checked", {"balance": current_balance})


@bot.message_handler(
    func=lambda message: message.text and message.text.startswith("💸")
)
@bot.message_handler(commands=["withdrawal"])
def withdrawal_command(message):
    user_id = message.from_user.id
    user_language = get_user_language(user_id)
    if is_user_blocked(user_id):
        bot.reply_to(message, get_message(user_language, "user_blocked"))
        return
    if not user_exists(user_id):
        bot.reply_to(message, get_message(user_language, "start_first"))
        return

    # Check channel membership
    has_joined, not_joined_channels, all_channels = check_user_joined_channels(user_id)
    if not has_joined:
        if user_language == "hindi":
            msg = "📢 बॉट का उपयोग करने के लिए पहले सभी चैनल्स join करें:\n\n"
        else:
            msg = "📢 Please join all required channels first:\n\n"
        for i, ch in enumerate(not_joined_channels, 1):
            msg += f"{i}. {ch['name']} (@{ch['username']})\n"
        keyboard = create_join_channels_keyboard(not_joined_channels)
        bot.reply_to(message, msg, reply_markup=keyboard)
        return
    user_data = get_user_data(user_id)
    if not user_data:
        bot.reply_to(message, get_message(user_language, "start_first"))
        return
    bot_data = get_bot_data()
    settings = bot_data.get("settings", {})
    min_withdrawal = settings.get("min_withdrawal", MINIMUM_WITHDRAWAL)
    balance = user_data.get("balance", 0)
    if balance < min_withdrawal:
        bot.reply_to(
            message,
            get_message(
                user_language,
                "insufficient_balance",
                balance=balance,
                min_withdrawal=min_withdrawal,
            ),
        )
        return
    msg = bot.reply_to(message, get_message(user_language, "enter_upi"))
    bot.register_next_step_handler(msg, process_upi_id, balance)
    log_activity(user_id, "withdrawal_initiated", {"balance": balance})


def process_upi_id(message, balance):
    user_id = message.from_user.id
    upi_id = message.text.strip()
    user_language = get_user_language(user_id)
    if "@" not in upi_id or len(upi_id) < 10:
        bot.reply_to(message, get_message(user_language, "invalid_format"))
        return
    withdrawal_request = {
        "id": str(uuid.uuid4()),
        "user_id": user_id,
        "amount": balance,
        "upi_id": upi_id,
        "timestamp": time.time(),
        "status": "pending",
    }
    add_withdrawal_request(withdrawal_request)
    deduct_user_balance(user_id, balance)
    bot.reply_to(
        message,
        get_message(
            user_language, "withdrawal_submitted", amount=balance, upi_id=upi_id
        ),
    )
    admin_message = f"""💸 नया निकासी अनुरोध

👤 User ID: {user_id}
💰 Amount: ₹{balance}
💳 UPI ID: {upi_id}
🕐 Time: {time.strftime("%Y-%m-%d %H:%M:%S")}

Request ID: {withdrawal_request["id"]}"""
    keyboard = types.InlineKeyboardMarkup()
    approve_btn = types.InlineKeyboardButton(
        "✅ Approve Payment",
        callback_data=f"approve_withdrawal_{withdrawal_request['id']}",
    )
    reject_btn = types.InlineKeyboardButton(
        "❌ Reject & Refund",
        callback_data=f"reject_withdrawal_{withdrawal_request['id']}",
    )
    keyboard.add(approve_btn, reject_btn)
    try:
        bot.send_message(ADMIN_ID, admin_message, reply_markup=keyboard)
    except:
        pass
    log_activity(
        user_id,
        "withdrawal_requested",
        {"amount": balance, "upi_id": upi_id, "request_id": withdrawal_request["id"]},
    )


@bot.message_handler(
    func=lambda message: message.text and message.text.startswith("🔗")
)
@bot.message_handler(commands=["refer"])
def refer_command(message):
    user_id = message.from_user.id
    user_language = get_user_language(user_id)
    if is_user_blocked(user_id):
        bot.reply_to(message, get_message(user_language, "user_blocked"))
        return
    if not user_exists(user_id):
        bot.reply_to(message, get_message(user_language, "start_first"))
        return

    # Check channel membership
    has_joined, not_joined_channels, all_channels = check_user_joined_channels(user_id)
    if not has_joined:
        if user_language == "hindi":
            msg = "📢 बॉट का उपयोग करने के लिए पहले सभी चैनल्स join करें:\n\n"
        else:
            msg = "📢 Please join all required channels first:\n\n"
        for i, ch in enumerate(not_joined_channels, 1):
            msg += f"{i}. {ch['name']} (@{ch['username']})\n"
        keyboard = create_join_channels_keyboard(not_joined_channels)
        bot.reply_to(message, msg, reply_markup=keyboard)
        return
    bot_data = get_bot_data()
    settings = bot_data.get("settings", {})
    bot_username = settings.get("bot_username", BOT_USERNAME)

    user_ref_reward = get_user_custom_setting(user_id, "referral_reward", None)
    if user_ref_reward is not None:
        referral_reward = user_ref_reward
    else:
        referral_reward = settings.get("referral_reward", REFERRAL_REWARD)

    user_milestone_count = get_user_custom_setting(user_id, "milestone_count", None)
    if user_milestone_count is not None:
        referral_milestone_count = user_milestone_count
    else:
        referral_milestone_count = settings.get(
            "referral_milestone_count", REFERRAL_MILESTONE_COUNT
        )

    user_milestone_reward = get_user_custom_setting(user_id, "milestone_reward", None)
    if user_milestone_reward is not None:
        referral_milestone_reward = user_milestone_reward
    else:
        referral_milestone_reward = settings.get(
            "referral_milestone_reward", REFERRAL_MILESTONE_REWARD
        )

    referral_link = f"https://t.me/{bot_username}?start={user_id}"
    user_data = get_user_data(user_id)
    referrals_count = user_data.get("referrals", 0)
    referral_earnings = referrals_count * referral_reward
    refer_message = get_message(
        user_language,
        "referral_info",
        referral_link=referral_link,
        referrals_count=referrals_count,
        referral_earnings=referral_earnings,
        referral_reward=referral_reward,
        milestone_count=referral_milestone_count,
        milestone_reward=referral_milestone_reward,
    )
    bot.reply_to(message, refer_message)
    log_activity(
        user_id, "referral_link_accessed", {"referrals_count": referrals_count}
    )


@bot.message_handler(
    func=lambda message: message.text and message.text.startswith("❓")
)
@bot.message_handler(commands=["help"])
def help_command(message):
    user_id = message.from_user.id
    user_language = get_user_language(user_id)
    bot_data = get_bot_data()
    settings = bot_data.get("settings", {})
    min_withdrawal = settings.get("min_withdrawal", MINIMUM_WITHDRAWAL)
    help_msg = get_message(user_language, "help", min_withdrawal=min_withdrawal)
    bot.reply_to(message, help_msg)
    log_activity(user_id, "help_accessed", {})


@bot.message_handler(content_types=["photo"])
def handle_screenshot(message):
    user_id = message.from_user.id
    user_language = get_user_language(user_id)
    if is_user_blocked(user_id):
        bot.reply_to(message, get_message(user_language, "user_blocked"))
        return
    user_data = get_user_data(user_id)
    if not user_data:
        bot.reply_to(message, get_message(user_language, "start_first"))
        return
    current_task_id = user_data.get("current_task")
    if not current_task_id:
        bot.reply_to(message, get_message(user_language, "no_active_task"))
        return
    tasks = get_bot_data().get("tasks", [])
    current_task = None
    for task in tasks:
        if task["id"] == current_task_id:
            current_task = task
            break
    if not current_task:
        bot.reply_to(message, "❌ कार्य नहीं मिला / Task not found")
        return
    if current_task_id in user_data.get("completed_tasks", []):
        bot.reply_to(
            message, "✅ यह कार्य पहले से पूरा है\n❌ एक कार्य केवल एक बार ही किया जा सकता है"
        )
        clear_user_current_task(user_id)
        return
    admin_message = f"""📸 **स्क्रीनशॉट सत्यापन / Screenshot Verification**

👤 **User Details:**
• ID: {user_id}
• Name: {message.from_user.first_name}
• Username: @{message.from_user.username or "N/A"}

🎯 **Task Details:**
• Title: {current_task["title"]}
• Reward: ₹{current_task["reward"]}
• Task ID: {current_task_id}

🕐 Submitted: {time.strftime("%Y-%m-%d %H:%M:%S")}"""
    keyboard = types.InlineKeyboardMarkup()
    approve_btn = types.InlineKeyboardButton(
        "✅ Approve", callback_data=f"approve_{user_id}_{current_task_id}"
    )
    reject_btn = types.InlineKeyboardButton(
        "❌ Reject", callback_data=f"reject_{user_id}_{current_task_id}"
    )
    block_btn = types.InlineKeyboardButton(
        "🚫 Block User", callback_data=f"block_{user_id}"
    )
    keyboard.add(approve_btn, reject_btn)
    keyboard.add(block_btn)
    try:
        bot.send_photo(
            ADMIN_ID,
            message.photo[-1].file_id,
            caption=admin_message,
            parse_mode="Markdown",
            reply_markup=keyboard,
        )
    except:
        pass
    bot.reply_to(message, get_message(user_language, "screenshot_submitted"))
    log_activity(user_id, "screenshot_submitted", {"task_id": current_task_id})


@bot.callback_query_handler(
    func=lambda call: call.data.startswith(
        ("approve_", "reject_", "block_", "approve_withdrawal_", "reject_withdrawal_")
    )
)
def handle_verification_callbacks(call):
    if not is_admin(call.from_user.id):
        return
    if call.data.startswith("approve_withdrawal_"):
        request_id = call.data.replace("approve_withdrawal_", "")
        bot_data = get_bot_data()
        withdrawal_requests = bot_data.get("withdrawal_requests", [])
        request = None
        for req in withdrawal_requests:
            if req["id"] == request_id:
                request = req
                break
        if not request:
            bot.edit_message_text(
                "❌ Withdrawal request not found",
                call.message.chat.id,
                call.message.message_id,
            )
            return
        update_withdrawal_request_status(request_id, "approved")
        bot.edit_message_text(
            f"✅ **Withdrawal Approved**\n\n👤 User: {request['user_id']}\n💰 Amount: ₹{request['amount']}\n💳 UPI ID: {request['upi_id']}\n📅 Date: {request['timestamp']}\n✨ Payment approved",
            call.message.chat.id,
            call.message.message_id,
        )
        try:
            bot.send_message(
                request["user_id"],
                f"✅ **निकासी स्वीकृत**\n\n💰 राशि: ₹{request['amount']}\n💳 UPI ID: {request['upi_id']}\n✨ पेमेंट 24-48 घंटे में आपके खाते में आ जाएगी!",
            )
        except:
            pass
        log_activity(
            ADMIN_ID,
            "withdrawal_approved",
            {
                "request_id": request_id,
                "user_id": request["user_id"],
                "amount": request["amount"],
            },
        )
    elif call.data.startswith("reject_withdrawal_"):
        request_id = call.data.replace("reject_withdrawal_", "")
        bot_data = get_bot_data()
        withdrawal_requests = bot_data.get("withdrawal_requests", [])
        request = None
        for req in withdrawal_requests:
            if req["id"] == request_id:
                request = req
                break
        if not request:
            bot.edit_message_text(
                "❌ Withdrawal request not found",
                call.message.chat.id,
                call.message.message_id,
            )
            return
        add_user_balance(request["user_id"], request["amount"])
        update_withdrawal_request_status(request_id, "rejected")
        bot.edit_message_text(
            f"❌ **Withdrawal Rejected**\n\nUser: {request['user_id']}\nAmount: ₹{request['amount']}\nStatus: Rejected and refunded",
            call.message.chat.id,
            call.message.message_id,
        )
        try:
            bot.send_message(
                request["user_id"],
                f"❌ **निकासी अस्वीकृत**\n\n💰 राशि: ₹{request['amount']}\n💸 राशि वापस आपके बैलेंस में जोड़ दी गई है",
            )
        except:
            pass
        log_activity(
            ADMIN_ID,
            "withdrawal_rejected",
            {
                "request_id": request_id,
                "user_id": request["user_id"],
                "amount": request["amount"],
            },
        )
    else:
        action, user_id, *extra = call.data.split("_")
        user_id = int(user_id)
        if action == "approve":
            task_id = extra[0]
            tasks = get_bot_data().get("tasks", [])
            task = None
            for t in tasks:
                if t["id"] == task_id:
                    task = t
                    break
            if not task:
                bot.edit_message_text(
                    "❌ Task not found", call.message.chat.id, call.message.message_id
                )
                return
            add_user_balance(user_id, task["reward"])
            add_completed_task(user_id, task_id)
            clear_user_current_task(user_id)
            bot_data = get_bot_data()
            tasks = bot_data.get("tasks", [])
            for i, t in enumerate(tasks):
                if t["id"] == task_id:
                    tasks[i]["completed_count"] = t.get("completed_count", 0) + 1
                    break
            bot_data["tasks"] = tasks
            save_bot_data(bot_data)
            bot.edit_message_caption(
                caption=f"✅ **Task Approved**\n\nUser: {user_id}\nTask: {task['title']}\nReward: ₹{task['reward']}\nStatus: Approved",
                chat_id=call.message.chat.id,
                message_id=call.message.message_id,
                parse_mode="Markdown",
            )
            try:
                bot.send_message(
                    user_id,
                    f"✅ **कार्य स्वीकृत / Task Approved**\n\n🎯 कार्य: {task['title']}\n💰 रिवॉर्ड: ₹{task['reward']}\n✨ आपके खाते में राशि जोड़ दी गई है!",
                    parse_mode="Markdown",
                )
            except:
                pass
            log_activity(
                user_id,
                "task_approved",
                {"task_id": task_id, "reward": task["reward"], "approved_by": ADMIN_ID},
            )
        elif action == "reject":
            task_id = extra[0]
            tasks = get_bot_data().get("tasks", [])
            task = None
            for t in tasks:
                if t["id"] == task_id:
                    task = t
                    break
            if not task:
                bot.edit_message_text(
                    "❌ Task not found", call.message.chat.id, call.message.message_id
                )
                return
            # Don't deduct balance - user never received the reward
            clear_user_current_task(user_id)
            bot.edit_message_caption(
                caption=f"❌ **Task Rejected**\n\nUser: {user_id}\nTask: {task['title']}\nStatus: Rejected",
                chat_id=call.message.chat.id,
                message_id=call.message.message_id,
                parse_mode="Markdown",
            )
            try:
                bot.send_message(
                    user_id,
                    f"❌ **कार्य अस्वीकृत / Task Rejected**\n\n🎯 कार्य: {task['title']}\n⚠️ कृपया सही स्क्रीनशॉट के साथ पुनः प्रयास करें",
                    parse_mode="Markdown",
                )
            except:
                pass
            log_activity(
                user_id, "task_rejected", {"task_id": task_id, "rejected_by": ADMIN_ID}
            )
        elif action == "block":
            block_user(user_id)
            bot.edit_message_caption(
                caption=f"🚫 **User Blocked**\n\nUser ID: {user_id}\nStatus: Blocked by admin",
                chat_id=call.message.chat.id,
                message_id=call.message.message_id,
                parse_mode="Markdown",
            )
            try:
                bot.send_message(
                    user_id,
                    "🚫 **खाता बंद / Account Blocked**\n\nआपका खाता नकली स्क्रीनशॉट भेजने के कारण बंद कर दिया गया है।",
                )
            except:
                pass
            log_activity(user_id, "user_blocked", {"blocked_by": ADMIN_ID})


@bot.message_handler(
    func=lambda message: message.text.startswith("/")
    and message.text
    not in [
        "/start",
        "/newtask",
        "/balance",
        "/withdrawal",
        "/refer",
        "/help",
        "/admin",
    ]
)
def handle_unknown_commands(message):
    log_activity(message.from_user.id, "unknown_command", {"text": message.text})
    bot.reply_to(
        message,
        bot.reply_to(
            message,
            "❌ यह कमांड मान्य नहीं है / This command is not valid\\n\\n✅ वैध कमांड / Valid commands:\\n• /start - मेनू / Menu\\n• 📝 कार्य / Tasks\\n• 💰 बैलेंस / Balance\\n• 💸 निकासी / Withdrawal\\n• 🔗 रेफर / Refer\\n• ❓ सहायता / Help",
        ),
    )


@bot.message_handler(content_types=["text"])
def handle_text_messages(message):
    if not message.text.startswith("/"):
        log_activity(message.from_user.id, "text_message", {"text": message.text[:50]})
        bot.reply_to(
            message,
            "📋 मेनू के लिए /start दबाएं या नीचे दिए गए बटन का उपयोग करें\nPress /start for menu or use the buttons below",
        )


def self_ping_loop():
    while True:
        try:
            time.sleep(120)
            try:
                endpoints = ["/ping", "/status", "/alive"]
                for endpoint in endpoints:
                    requests.get(f"http://127.0.0.1:5000{endpoint}", timeout=10)
                    time.sleep(1)
                print(f"Deployment ping: {time.strftime('%H:%M:%S')}")
            except:
                pass
        except:
            pass


def heartbeat_loop():
    while True:
        try:
            time.sleep(240)
            print(f"Heartbeat: {time.strftime('%H:%M:%S')}")
        except:
            time.sleep(60)


def scheduled_backup_loop():
    """Create backups every hour to protect against data loss"""
    while True:
        try:
            time.sleep(3600)  # Run every hour
            if os.path.exists(USERS_DATA_FILE):
                create_backup(USERS_DATA_FILE)
                print(f"🔄 Scheduled backup created: {time.strftime('%H:%M:%S')}")
        except Exception as e:
            print(f"❌ Scheduled backup error: {e}")
            time.sleep(300)


if __name__ == "__main__":
    print("🤖 Bot starting...")
    log_activity(0, "bot_started", {"timestamp": time.time()})
    print("🌐 Starting keep-alive server...")
    keep_alive()
    time.sleep(3)
    ping_thread = threading.Thread(target=self_ping_loop, daemon=True)
    ping_thread.start()
    heartbeat_thread = threading.Thread(target=heartbeat_loop, daemon=True)
    heartbeat_thread.start()
    backup_thread = threading.Thread(target=scheduled_backup_loop, daemon=True)
    backup_thread.start()
    print("🔄 Scheduled backup system started")
    try:
        bot.delete_webhook(drop_pending_updates=True)
        print("✅ Webhook deleted successfully")
        time.sleep(5)
    except Exception as e:
        print(f"⚠️ Webhook deletion failed: {e}")
    while True:
        try:
            print("🔄 Starting bot polling...")
            bot.polling(none_stop=True, interval=2, timeout=30)
            break
        except Exception as e:
            error_msg = str(e).lower()
            print(f"❌ Bot error: {e}")
            if "409" in error_msg or "conflict" in error_msg:
                print("🔄 Resolving conflict...")
                try:
                    for i in range(3):
                        bot.delete_webhook(drop_pending_updates=True)
                        time.sleep(3)
                        requests.get(
                            f"https://api.telegram.org/bot{BOT_TOKEN}/getUpdates?offset=-1&limit=1",
                            timeout=10,
                        )
                        time.sleep(2)
                    print("✅ Conflict resolved, restarting...")
                    time.sleep(15)
                except Exception as clear_error:
                    print(f"Clear error: {clear_error}")
                    time.sleep(20)
            else:
                log_activity(0, "bot_error", {"error": str(e)})
                time.sleep(15)

import json
import os
import shutil
import time
from datetime import datetime

BACKUP_DIR = "data/backups"
MAX_BACKUPS = 50  # Keep last 50 backups

def ensure_backup_directory():
    """Create backup directory if it doesn't exist"""
    if not os.path.exists(BACKUP_DIR):
        os.makedirs(BACKUP_DIR)
        print(f"✅ Created backup directory: {BACKUP_DIR}")

def create_backup(filepath):
    """Create a timestamped backup of a JSON file"""
    ensure_backup_directory()
    
    if not os.path.exists(filepath):
        return False
    
    try:
        # Create backup filename with timestamp
        filename = os.path.basename(filepath)
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        backup_filename = f"{filename}.{timestamp}.backup"
        backup_path = os.path.join(BACKUP_DIR, backup_filename)
        
        # Copy the file
        shutil.copy2(filepath, backup_path)
        
        # Clean old backups (keep only last MAX_BACKUPS)
        cleanup_old_backups(filename)
        
        return True
    except Exception as e:
        print(f"❌ Backup failed for {filepath}: {e}")
        return False

def cleanup_old_backups(filename):
    """Remove old backups, keep only the most recent MAX_BACKUPS"""
    try:
        # Get all backups for this file
        backups = [f for f in os.listdir(BACKUP_DIR) if f.startswith(filename)]
        backups.sort(reverse=True)  # Sort by timestamp (newest first)
        
        # Remove old backups
        for old_backup in backups[MAX_BACKUPS:]:
            os.remove(os.path.join(BACKUP_DIR, old_backup))
            
    except Exception as e:
        print(f"❌ Cleanup failed: {e}")

def restore_latest_backup(filepath):
    """Restore the latest backup of a file"""
    ensure_backup_directory()
    
    try:
        filename = os.path.basename(filepath)
        backups = [f for f in os.listdir(BACKUP_DIR) if f.startswith(filename)]
        
        if not backups:
            print(f"⚠️ No backups found for {filename}")
            return False
        
        # Get the most recent backup
        backups.sort(reverse=True)
        latest_backup = backups[0]
        backup_path = os.path.join(BACKUP_DIR, latest_backup)
        
        # Restore the backup
        shutil.copy2(backup_path, filepath)
        print(f"✅ Restored {filename} from backup: {latest_backup}")
        
        return True
    except Exception as e:
        print(f"❌ Restore failed for {filepath}: {e}")
        return False

def save_json_with_backup(filepath, data):
    """Save JSON file and create a backup"""
    try:
        # Create backup of existing file before overwriting
        if os.path.exists(filepath):
            create_backup(filepath)
        
        # Save the new data
        with open(filepath, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
        
        return True
    except Exception as e:
        print(f"❌ Save failed for {filepath}: {e}")
        return False

def load_json_with_restore(filepath):
    """Load JSON file, restore from backup if missing"""
    try:
        # If file doesn't exist, try to restore from backup
        if not os.path.exists(filepath):
            print(f"⚠️ {filepath} not found! Attempting to restore from backup...")
            if restore_latest_backup(filepath):
                print(f"✅ Successfully restored {filepath}")
            else:
                print(f"❌ Could not restore {filepath}")
                return {} if "users" in filepath else []
        
        # Load the file
        with open(filepath, 'r', encoding='utf-8') as f:
            return json.load(f)
            
    except Exception as e:
        print(f"❌ Load failed for {filepath}: {e}")
        return {} if "users" in filepath else []

# Scheduled backup function - run this periodically
def create_scheduled_backup():
    """Create backups of all important files"""
    files_to_backup = [
        "data/users_data.json",
        "data/bot_data.json",
        "data/blocked_users.json",
        "data/task_submissions.json"
    ]
    
    backed_up = 0
    for filepath in files_to_backup:
        if os.path.exists(filepath):
            if create_backup(filepath):
                backed_up += 1
    
    print(f"✅ Scheduled backup completed: {backed_up}/{len(files_to_backup)} files backed up")
    return backed_up

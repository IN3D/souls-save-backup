import json
import logging
import os
import re
import shutil
import string
from datetime import datetime
from pathlib import Path
from typing import Dict, List
from wintoast import ToastNotifier


def make_safe_filename(filename: str) -> str:
    """
    Convert a string into a safe filename or directory name for Windows.
    """

    # Step 1: Remove forbidden characters
    # Windows forbidden characters: < > : " / \ | ? *
    forbidden_chars = r'[<>:"/\\|?*]'
    safe_name = re.sub(forbidden_chars, '', filename)
    
    # Step 2: Remove control characters
    safe_name = "".join(char for char in safe_name if char in string.printable)
    
    # Step 3: Remove leading/trailing spaces and dots
    safe_name = safe_name.strip(". ")
    
    # Step 4: Handle Windows reserved names (CON, PRN, AUX, etc.)
    reserved_names = {
        'CON', 'PRN', 'AUX', 'NUL',
        'COM1', 'COM2', 'COM3', 'COM4', 'COM5', 'COM6', 'COM7', 'COM8', 'COM9',
        'LPT1', 'LPT2', 'LPT3', 'LPT4', 'LPT5', 'LPT6', 'LPT7', 'LPT8', 'LPT9'
    }
    name_without_ext = safe_name.split('.')[0].upper()
    if name_without_ext in reserved_names:
        safe_name = '_' + safe_name
    
    # Step 5: Handle empty filename
    if not safe_name:
        safe_name = '_empty_'
        
    # Step 6: Trim length (Windows MAX_PATH is 255 characters)
    safe_name = safe_name[:255]
    
    return safe_name

class SoulsSaveBackup:
    def __init__(self, config_path: str="config.json", state_file: str="backup_state.json"):
        self.load_failed = False
        self.backup_failed = False
        self.config_path = config_path
        self.state_file = state_file
        self.notifier = ToastNotifier()
        self.logger = self._setup_logger()
        self.logger.info("Starting backup process")
        self._init_state_and_config()

    def _init_state_and_config(self):
        self.state = self._load_state_file()
        config = self._load_config_file()
        if config is None:
            self.load_failed = True
            return
        self.config = config
        self.logger.info("Configuration loaded successfully")
        return
    
    def _load_config_file(self) -> Dict:
        """Loads the configuration from its JSON file."""
        try:
            with open(self.config_path, "r") as file:
                config = json.load(file)

                # validate required fields
                if not isinstance(config.get("source_directories"), List) or not config.get("backup_directory"):
                    error_msg = "Malformed config file: must contain a list of source directories and a backup directory"
                    self.logger.error(error_msg)
                    self.load_failed = True
                    return

                for entry in config["source_directories"]:
                    if not isinstance(entry, Dict) or not entry.get("path") or not entry.get("name"):
                        error_msg = "Malformed config file: source directories must contain a path and name"
                        self.logger.error(error_msg)
                        self.load_failed = True
                        return

                return config
        except FileNotFoundError:
            error_msg = f"Could not find config file: {self.config_path}"
            self.logger.error(error_msg)
            self._notify("Souls Backup", error_msg)
            return None
        except json.JSONDecodeError:
            error_msg = f"Could not parse config file: {self.config_path}"
            self.logger.error(error_msg)
            self._notify("Souls Backup", error_msg)
            return None
    
    def _load_state_file(self) -> Dict:
        """Load or initialize the state file."""
        try:
            with open(self.state_file, "r") as file:
                return json.load(file)
        except FileNotFoundError:
            return {}

    def _save_state_file(self):
        """Creates or overwrites the state file."""
        with open(self.state_file, "w") as file:
            json.dump(self.state, file, indent=2)

    def _setup_logger(self) -> logging.Logger:
        try:
            current_time = datetime.now()
            formatted_time = current_time.strftime("%Y_%m")
            log_file = f"backup_{formatted_time}.log"

            # Ensure the log directory exists
            log_dir = "logs"
            os.makedirs(log_dir, exist_ok=True)

            log_path = os.path.join(log_dir, log_file)

            logging.basicConfig(
                filename=log_path,
                level=logging.INFO,
                format="%(asctime)s - %(levelname)s - %(message)s"
            )
            return logging.getLogger(__name__)
        except Exception as e:
            print(f"Failed to setup logging: {e}")
            raise
    
    def _notify(self, title: str, message: str):
        """Sends a windows notification."""
        try:
            self.notifier.show_toast(
                title,
                message,
                duration=5,
                threaded=True
            )
        except Exception as e:
            self.logger.error(f"Failed to send notification: {e}")
    
    def _get_last_modified(self, path: str) -> float:
        """Returns the last modified time of a file."""
        return os.path.getmtime(path)
    
    def _process_source_directory(self, source_path: Dict) -> int:
        file_count = 0
        path = source_path["path"]
        base_name = source_path["name"]

        # Ensure that variables are interpreted first
        path = os.path.expandvars(path)

        # make the game's name safe as a windows directory name
        name = make_safe_filename(base_name)

        backup_path = os.path.join(
            os.path.expandvars(self.config["backup_directory"]),
            name
        )

        for root, dirs, _files in os.walk(path):
            for dir_name in dirs:
                if dir_name.isdigit():
                    # Found a directory that is only digits, check if it has a .sl2 file
                    dir_path = os.path.join(root, dir_name)
                    for file in os.listdir(dir_path):
                        if file.endswith(".sl2"):
                            file_path = os.path.join(dir_path, file)
                            last_modified = self._get_last_modified(file_path)
                            if file not in self.state or last_modified > self.state[file]:
                                self.logger.info(f"{base_name}| {file} is new or modified")

                                # Ensure the base backup directory exists, create it if it doesn't
                                os.makedirs(backup_path, exist_ok=True)

                                # Make a subdirectory for this date and time
                                timestamp = datetime.now().strftime("%Y_%m_%d__%H%M%S")
                                backup_path = os.path.join(backup_path, timestamp)
                                os.makedirs(backup_path, exist_ok=True)

                                self.logger.info(f"Copying {file} to {backup_path}")
                                shutil.copy2(file_path, backup_path)
                                self.state[file] = last_modified
                                file_count += 1
                            else:
                                self.logger.info(f"Skipping {file} as it has not been modified")
        return file_count

    def perform_backup(self):
        if self.load_failed:
            return

        try:
            backup_success = False
            files_processed = 0
            files_backed_up = 0

            for source_path in self.config["source_directories"]:
                try:
                    files_backed = self._process_source_directory(source_path)
                    files_backed_up += files_backed
                    files_processed += 1
                except Exception as e:
                    self.logger.error(f"Failed to process {source_path['name']} with error {str(e)}")
                    continue # Don't hold the whole process up for a single directory
            
            if files_processed > 0:
                self._save_state_file()
                backup_success = True
                self.logger.info(f"Process complete. {files_backed_up} files backed up from {files_processed} directories.")
            
            return backup_success
        except Exception as e:
            error_msg = f"Backup failed: {str(e)}"
            self.logger.error(error_msg)
            self._notify("Souls Backup", error_msg)
            self.backup_failed = True
            return False


if __name__ == "__main__":
    service = SoulsSaveBackup()
    service.perform_backup()
# Souls Save Backup

I lost a SL200+ character to the save file going missing in `appdata\roaming`

never again...

# Usage

1. Check the `config.json`, make sure the values are correct. `source_directories` will likely not need updating, those save directories are standard. But ensure the `backup_directory` is going to the right place.
2. Ensure the Windows notification library is installed by running `pip3.exe install -r requirements.txt`
3. Run it either manually like `python3.exe main.py` or put it into the Task Scheduler
4. The script is designed to check if a file has been modified since it last ran to reduce bloat.
5. If a change is detected it will copy the save file to a timestamped directory

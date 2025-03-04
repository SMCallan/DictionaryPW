# Password Dictionary Generation App

## Overview
This Python application generates a dictionary of passwords for brute-force attacks or security research. It uses a system wordlist, applies character substitutions, and enhances passwords with numbers and symbols. The generated passwords are stored in an SQLite database to prevent duplicates and improve efficiency.

## How It Works
1. **Loads a Dictionary**
   - Reads words from a system dictionary (`/usr/share/dict/words`).
   - Filters words based on length (default: 4-8 characters).
   - Falls back to basic words if no dictionary is found.

2. **Generates Password Variations**
   - Applies common character substitutions (e.g., `a → @, 4`, `e → 3`).
   - Generates uppercase variations for each word.
   - Uses `itertools.product()` to create all possible combinations.

3. **Enhances Passwords**
   - Ensures at least one uppercase letter.
   - Adds a random number and symbol if missing.
   - Randomly inserts extra characters for complexity.

4. **Stores Passwords in SQLite**
   - Uses an SQLite database (`passwords.db`) to store unique passwords.
   - Uses a Bloom filter approximation to minimize duplicate checks.
   - Stores passwords in batches for efficiency.

5. **Parallel Processing**
   - Uses multiple worker processes for password generation.
   - A separate writer process inserts passwords into the database.
   - Queue-based communication ensures smooth data flow.

## Customization
- **Change Dictionary Source:** Modify `config.dictionary_path` to use a custom wordlist.
- **Adjust Password Rules:** Modify `config.substitutions` to change character replacements.
- **Change Password Length:** Adjust `config.min_word_length` and `config.max_word_length`.
- **Increase Performance:** Modify `config.max_workers` to use more CPU cores.

## Usage
Run the script:
```bash
python3 password_generator.py
```
Stop the process with `Ctrl+C`, which triggers a graceful shutdown.

## Disclaimer
This tool is intended for security research and ethical hacking. Use responsibly and only with explicit permission.


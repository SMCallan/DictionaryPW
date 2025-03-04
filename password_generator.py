import sqlite3
import random
import logging
import signal
import sys
import time
from pathlib import Path
from itertools import product
from multiprocessing import Process, Queue, Manager, cpu_count
from typing import List, Set, Generator

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class PasswordDB:
    """SQLite database handler with connection pooling"""
    def __init__(self, db_path: str):
        self.db_path = Path(db_path)
        self._init_db()
        
    def _init_db(self):
        with self.connection() as conn:
            conn.execute('''
                CREATE TABLE IF NOT EXISTS passwords (
                    password TEXT PRIMARY KEY,
                    created TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            ''')
            conn.execute('CREATE INDEX IF NOT EXISTS idx_created ON passwords(created)')

    def connection(self):
        return sqlite3.connect(self.db_path, check_same_thread=False)

    def exists(self, password: str) -> bool:
        with self.connection() as conn:
            return conn.execute(
                'SELECT 1 FROM passwords WHERE password = ?', 
                (password,)
            ).fetchone() is not None

    def insert_batch(self, passwords: List[str]):
        with self.connection() as conn:
            conn.executemany(
                'INSERT OR IGNORE INTO passwords (password) VALUES (?)',
                [(pwd,) for pwd in passwords]
            )
            conn.commit()

class PasswordConfig:
    """Configuration class for password generation rules"""
    def __init__(self):
        self.db_path = Path.home() / 'Desktop/passwords.db'
        self.dictionary_path = Path('/usr/share/dict/words')
        self.substitutions = {
            'a': ['@', '4'],
            'b': ['8'],
            'e': ['3'],
            'g': ['9'],
            'i': ['1', '!'],
            'o': ['0'],
            's': ['$', '5'],
            't': ['7'],
        }
        self.common_numbers = ['0', '1', '2', '3', '4', '5', '6', '7', '8', '9']
        self.common_symbols = ['!', '@', '#', '$', '%', '&']
        self.min_word_length = 4
        self.max_word_length = 8
        self.batch_size = 10000
        self.max_workers = cpu_count() - 1 or 1

config = PasswordConfig()

def load_dictionary() -> List[str]:
    """Load and filter dictionary words"""
    try:
        with open(config.dictionary_path, 'r') as f:
            return [
                word.strip().lower()
                for word in f
                if config.min_word_length <= len(word.strip()) <= config.max_word_length
            ]
    except FileNotFoundError:
        logger.warning("System dictionary not found, using fallback words")
        return ['cat', 'dog', 'sun', 'bird', 'password', 'hello']

def generate_variations(word: str) -> Generator[str, None, None]:
    """Generate password variations with substitutions"""
    char_options = []
    for char in word.lower():
        substitutions = config.substitutions.get(char, [char])
        char_options.append(substitutions + [char.upper()])
    
    for combo in product(*char_options):
        yield ''.join(combo)

def enhance_password(password: str) -> str:
    """Ensure password meets complexity requirements"""
    pwd = list(password)
    
    # Add uppercase
    if not any(c.isupper() for c in pwd):
        pwd[random.randint(0, len(pwd)-1)] = random.choice(config.common_symbols).upper()
    
    # Add number
    if not any(c.isdigit() for c in pwd):
        pwd.insert(random.randint(1, len(pwd)), random.choice(config.common_numbers))
    
    # Add symbol
    if not any(c in config.common_symbols for c in pwd):
        pwd.insert(random.randint(1, len(pwd)), random.choice(config.common_symbols))
    
    return ''.join(pwd)

def worker_process(word_chunk: List[str], output_queue: Queue, stop_event):
    """Password generation worker process"""
    db = PasswordDB(config.db_path)
    bloom_filter = set()
    
    while not stop_event.is_set():
        random.shuffle(word_chunk)
        for word in word_chunk:
            for variation in generate_variations(word):
                enhanced = enhance_password(variation)
                
                # Bloom filter approximation
                if enhanced not in bloom_filter:
                    if not db.exists(enhanced):
                        output_queue.put(enhanced)
                        bloom_filter.add(enhanced)
                        
                if stop_event.is_set():
                    return

def writer_process(output_queue: Queue, stop_event):
    """Database writer process"""
    db = PasswordDB(config.db_path)
    batch = []
    
    while not stop_event.is_set() or not output_queue.empty():
        try:
            while len(batch) < config.batch_size:
                pwd = output_queue.get(timeout=1)
                batch.append(pwd)
                
            db.insert_batch(batch)
            logger.info(f"Inserted {len(batch)} passwords")
            batch = []
            
        except Exception as e:
            if not stop_event.is_set():
                logger.error(f"Writer error: {e}")
    
    # Final flush
    if batch:
        db.insert_batch(batch)

def main():
    """Main controller function"""
    # Initialize database
    db = PasswordDB(config.db_path)
    
    # Load dictionary
    words = load_dictionary()
    logger.info(f"Loaded {len(words)} base words")
    
    # Create shared objects
    manager = Manager()
    stop_event = manager.Event()
    output_queue = manager.Queue(maxsize=100000)
    
    # Signal handling
    def shutdown(signum, frame):
        logger.info("\nShutting down gracefully...")
        stop_event.set()
        
    signal.signal(signal.SIGINT, shutdown)
    signal.signal(signal.SIGTERM, shutdown)
    
    # Split word list for workers
    chunk_size = len(words) // config.max_workers
    word_chunks = [words[i:i+chunk_size] for i in range(0, len(words), chunk_size)]
    
    # Start processes
    workers = []
    for chunk in word_chunks:
        p = Process(target=worker_process, args=(chunk, output_queue, stop_event))
        p.start()
        workers.append(p)
    
    writer = Process(target=writer_process, args=(output_queue, stop_event))
    writer.start()
    
    # Monitor processes
    try:
        while not stop_event.is_set():
            time.sleep(1)
            logger.info(f"Queue size: {output_queue.qsize()} | Workers active: {sum(p.is_alive() for p in workers)}")
            
    finally:
        for p in workers:
            p.join()
        writer.join()
        
    logger.info("Shutdown complete")

if __name__ == '__main__':
    main()

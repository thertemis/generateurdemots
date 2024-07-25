import os
import re
import sqlite3
import json
import random
from http.server import HTTPServer, SimpleHTTPRequestHandler

class RequestHandler(SimpleHTTPRequestHandler):
    def do_GET(self):
        if self.path == '/':
            self.path = '/index.html'
        elif self.path == '/get_custom_files':
            self.send_response(200)
            self.send_header('Content-type', 'application/json')
            self.end_headers()
            custom_files = self.get_custom_files()
            self.wfile.write(json.dumps(custom_files).encode())
            return
        return SimpleHTTPRequestHandler.do_GET(self)

    def do_POST(self):
        content_length = int(self.headers['Content-Length'])
        post_data = self.rfile.read(content_length)
        data = json.loads(post_data.decode('utf-8'))

        if self.path == '/get_words':
            noun_count = data['noun_count']
            adj_count = data['adj_count']
            verb_count = data['verb_count']
            rarity_min = data['rarity_min']
            rarity_max = data['rarity_max']
            exclude_communes = data['exclude_communes']
            locked_words = data.get('locked_words', [])
            custom_files = data.get('custom_files', [])

            words = self.get_random_words(noun_count, adj_count, verb_count, rarity_min, rarity_max, exclude_communes, locked_words, custom_files)

            self.send_response(200)
            self.send_header('Content-type', 'application/json')
            self.end_headers()
            self.wfile.write(json.dumps(words).encode())
        elif self.path == '/get_word':
            word = data['word']
            custom_files = data.get('custom_files', [])
            word_info = self.get_word_info(word, custom_files)

            self.send_response(200)
            self.send_header('Content-type', 'application/json')
            self.end_headers()
            self.wfile.write(json.dumps(word_info).encode())
        else:
            self.send_error(404)

    def get_custom_files(self):
        custom_dir = 'custom'
        if not os.path.exists(custom_dir):
            os.makedirs(custom_dir)
        return [f for f in os.listdir(custom_dir) if f.endswith(('.txt', '.md'))]

    def get_word_frequencies(self, custom_files):
        word_freq = {}
        for file in custom_files:
            db_file = os.path.splitext(file)[0] + '.db'
            if not os.path.exists(db_file):
                self.create_custom_db(file, db_file)
            
            conn = sqlite3.connect(db_file)
            c = conn.cursor()
            c.execute("SELECT word, frequency_relative FROM words")
            for word, freq in c.fetchall():
                if word in word_freq:
                    word_freq[word] = max(word_freq[word], freq)
                else:
                    word_freq[word] = freq
            conn.close()
        
        return word_freq

    def create_custom_db(self, text_file, db_file):
        word_freq = {}
        total_words = 0
        with open(os.path.join('custom', text_file), 'r', encoding='utf-8') as f:
            content = f.read()
            words = re.findall(r'\b\w+\b', content.lower())
            for word in words:
                word_freq[word] = word_freq.get(word, 0) + 1
                total_words += 1
        
        conn = sqlite3.connect(db_file)
        c = conn.cursor()
        c.execute('''CREATE TABLE words
                     (word TEXT PRIMARY KEY, frequency INTEGER, frequency_relative REAL)''')
        
        sorted_words = sorted(word_freq.items(), key=lambda x: x[1], reverse=True)
        for i, (word, freq) in enumerate(sorted_words):
            freq_relative = 1 - i / (len(sorted_words) - 1)
            c.execute("INSERT INTO words VALUES (?, ?, ?)", (word, freq, freq_relative))
        
        conn.commit()
        conn.close()

    def get_random_words(self, noun_count, adj_count, verb_count, rarity_min, rarity_max, exclude_communes, locked_words, custom_files):
        if custom_files:
            word_freq = self.get_word_frequencies(custom_files)
            return self.get_random_words_from_custom(noun_count, adj_count, verb_count, rarity_min, rarity_max, locked_words, word_freq)
        else:
            return self.get_random_words_from_db(noun_count, adj_count, verb_count, rarity_min, rarity_max, exclude_communes, locked_words)

    def get_random_words_from_custom(self, noun_count, adj_count, verb_count, rarity_min, rarity_max, locked_words, word_freq):
        conn = sqlite3.connect('french_words.db')
        c = conn.cursor()

        words = []
        categories = {
            'verb': verb_count,
            'noun': noun_count,
            'adjective': adj_count
        }

        for category, count in categories.items():
            locked_category_words = [w for w in locked_words if w['category'] == category]
            remaining_count = count - len(locked_category_words)

            if remaining_count > 0:
                category_words = []
                for word, freq in word_freq.items():
                    if rarity_min <= freq <= rarity_max:
                        c.execute("SELECT category, definition FROM words WHERE word = ? AND category = ?", (word, category))
                        result = c.fetchone()
                        if result:
                            category_words.append((word, category, result[1], freq))

                category_words.sort(key=lambda x: x[3], reverse=True)
                selected_words = random.sample(category_words, min(remaining_count, len(category_words)))
                words.extend([(word, cat, def_) for word, cat, def_, _ in selected_words])

            words.extend([(w['word'], w['category'], w['definition']) for w in locked_category_words])

        random.shuffle(words)
        conn.close()
        return words

    def get_random_words_from_db(self, noun_count, adj_count, verb_count, rarity_min, rarity_max, exclude_communes, locked_words):
        conn = sqlite3.connect('french_words.db')
        c = conn.cursor()

        words = []
        categories = {
            'verb': verb_count,
            'noun': noun_count,
            'adjective': adj_count
        }

        for category, count in categories.items():
            locked_category_words = [w for w in locked_words if w['category'] == category]
            remaining_count = count - len(locked_category_words)

            if remaining_count > 0:
                query = """
                    SELECT word, category, definition, frequency_relative
                    FROM words 
                    WHERE category = ? AND frequency_relative BETWEEN ? AND ?
                """
                params = [category, rarity_min, rarity_max]

                if exclude_communes:
                    query += " AND definition NOT LIKE '%commune française%'"

                query += " ORDER BY RANDOM() LIMIT ?"
                params.append(remaining_count)

                c.execute(query, tuple(params))
                category_words = c.fetchall()
                
                words.extend([(word, cat, def_) for word, cat, def_, _ in category_words])

            words.extend([(w['word'], w['category'], w['definition']) for w in locked_category_words])

        random.shuffle(words)
        conn.close()
        return words

    def get_word_info(self, word, custom_files):
        if custom_files:
            word_freq = self.get_word_frequencies(custom_files)
            if word.lower() in word_freq:
                conn = sqlite3.connect('french_words.db')
                c = conn.cursor()
                c.execute("SELECT category, definition FROM words WHERE word = ? COLLATE NOCASE LIMIT 1", (word,))
                result = c.fetchone()
                conn.close()
                if result:
                    return {
                        'word': word,
                        'category': result[0],
                        'definition': result[1]
                    }
        else:
            conn = sqlite3.connect('french_words.db')
            c = conn.cursor()

            c.execute("SELECT word, category, definition FROM words WHERE word = ? COLLATE NOCASE LIMIT 1", (word,))
            result = c.fetchone()

            if not result:
                c.execute("SELECT word, category, definition FROM words WHERE word LIKE ? COLLATE NOCASE LIMIT 1", (f"%{word}%",))
                result = c.fetchone()

            conn.close()

            if result:
                return {
                    'word': result[0],
                    'category': result[1],
                    'definition': result[2]
                }

        return None

def run(server_class=HTTPServer, handler_class=RequestHandler, port=6060):
    server_address = ('', port)
    httpd = server_class(server_address, handler_class)
    print(f"Serveur démarré sur le port {port}")
    httpd.serve_forever()

if __name__ == '__main__':
    run()
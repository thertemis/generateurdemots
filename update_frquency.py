import sqlite3
import math

def add_harmonious_relative_frequency():
    conn = sqlite3.connect('french_words.db')
    c = conn.cursor()

    # Vérifier si la colonne frequency_relative existe déjà
    c.execute("PRAGMA table_info(words)")
    columns = [column[1] for column in c.fetchall()]
    if 'frequency_relative' not in columns:
        print("Ajout de la colonne frequency_relative...")
        c.execute("ALTER TABLE words ADD COLUMN frequency_relative REAL")
    else:
        print("La colonne frequency_relative existe déjà.")

    # Compter le nombre total de mots
    c.execute("SELECT COUNT(*) FROM words")
    total_words = c.fetchone()[0]
    print(f"Nombre total de mots: {total_words}")

    # Créer un index temporaire sur la fréquence pour accélérer le processus
    print("Création d'un index temporaire...")
    c.execute("CREATE INDEX IF NOT EXISTS temp_freq_index ON words(frequency)")

    # Mettre à jour la colonne frequency_relative
    print("Mise à jour de la colonne frequency_relative...")
    c.execute("""
    WITH ranked AS (
        SELECT word, frequency, ROW_NUMBER() OVER (ORDER BY frequency DESC) as rank
        FROM words
    )
    UPDATE words
    SET frequency_relative = 1.0 - (
        (SELECT CAST(rank AS REAL) FROM ranked WHERE ranked.word = words.word) - 1
    ) / ?
    """, (total_words - 1,))

    # Supprimer l'index temporaire
    print("Suppression de l'index temporaire...")
    c.execute("DROP INDEX IF EXISTS temp_freq_index")

    # Vérifier les résultats
    c.execute("SELECT MIN(frequency_relative), MAX(frequency_relative) FROM words")
    min_rel, max_rel = c.fetchone()
    print(f"Fréquence relative minimale: {min_rel}")
    print(f"Fréquence relative maximale: {max_rel}")

    # Valider et enregistrer les changements
    conn.commit()
    print("Mise à jour terminée.")

    # Vérification supplémentaire
    for i in range(0, 11):
        threshold = i / 10
        c.execute("SELECT COUNT(*) FROM words WHERE frequency_relative <= ?", (threshold,))
        count = c.fetchone()[0]
        percentage = (count / total_words) * 100
        print(f"Mots avec frequency_relative <= {threshold:.1f}: {percentage:.2f}%")

    # Fermer la connexion
    conn.close()

if __name__ == "__main__":
    add_harmonious_relative_frequency()
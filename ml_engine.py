import sqlite3
import os
import pickle
import numpy as np
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.linear_model import LogisticRegression

DB_FILE = "jobs.db"
MODEL_FILE = "rf_model.pkl"
VEC_FILE = "tfidf.pkl"

def init_db():
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute('''
        CREATE TABLE IF NOT EXISTS jobs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            raw_text TEXT,
            score_initial INTEGER,
            user_label INTEGER DEFAULT NULL
        )
    ''')
    conn.commit()
    conn.close()

def save_job(raw_text, score_initial):
    """Saves a job analysis and returns the unique job_id."""
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute('INSERT INTO jobs (raw_text, score_initial) VALUES (?, ?)', (raw_text, score_initial))
    job_id = c.lastrowid
    conn.commit()
    conn.close()
    return job_id

def get_duplicate_count(raw_text):
    """Returns how many times this exact text has been scanned before."""
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute('SELECT COUNT(*) FROM jobs WHERE raw_text = ?', (raw_text,))
    count = c.fetchone()[0]
    conn.close()
    return count

def submit_feedback(job_id, is_scam):
    """Updates a job with a ground-truth label (1 for scam, 0 for safe) and retrains the ML model."""
    label = 1 if is_scam else 0
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute('UPDATE jobs SET user_label = ? WHERE id = ?', (label, job_id))
    conn.commit()
    conn.close()
    
    # Retrain model with new data
    retrain_model()

def retrain_model():
    """Fetches all labeled data and trains a TF-IDF + Random Forest Pipeline."""
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute('SELECT raw_text, user_label FROM jobs WHERE user_label IS NOT NULL')
    rows = c.fetchall()
    conn.close()
    
    # Need at least 5 examples of both classes to train a meaningful model
    labels = [r[1] for r in rows]
    if len(rows) < 5 or (0 not in labels) or (1 not in labels):
        # Not enough diverse data to train safely yet
        return False
        
    texts = [r[0] for r in rows]
    
    vectorizer = TfidfVectorizer(max_features=1000, stop_words='english', ngram_range=(1, 2))
    X = vectorizer.fit_transform(texts)
    y = np.array(labels)
    
    model = LogisticRegression(class_weight='balanced', random_state=42)
    model.fit(X, y)
    
    with open(VEC_FILE, 'wb') as f:
        pickle.dump(vectorizer, f)
    with open(MODEL_FILE, 'wb') as f:
        pickle.dump(model, f)
        
    return True

def predict_ml(text):
    """Returns ML scam probability (0.0 to 1.0) or None if model hasn't been trained yet."""
    if not os.path.exists(MODEL_FILE) or not os.path.exists(VEC_FILE):
        return None
        
    try:
        with open(VEC_FILE, 'rb') as f:
            vectorizer = pickle.load(f)
        with open(MODEL_FILE, 'rb') as f:
            model = pickle.load(f)
            
        X = vectorizer.transform([text])
        proba = model.predict_proba(X)[0]
        
        # Depending on scikit-learn classes, usually Index 1 is probability of '1' (Scam)
        class_1_idx = list(model.classes_).index(1) if 1 in model.classes_ else -1
        if class_1_idx >= 0:
            return float(proba[class_1_idx])
        return 0.0
    except Exception as e:
        print("ML Prediction Error:", e)
        return None

# Seed the database on first import to ensure it exists
if not os.path.exists(DB_FILE):
    init_db()
    
    # Optional: We could seed it with the TEST_DATASET from evaluate.py to give the model a hot start!
    try:
        from evaluate import TEST_DATASET
        for txt, label in TEST_DATASET:
            jid = save_job(txt, 50) # dummy initial score
            submit_feedback(jid, is_scam=(label==1))
    except Exception as e:
        print("Could not seed DB:", e)

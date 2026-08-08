"""
ml_engine_bert.py — ScamShield Part 3 ML Inference
====================================================
Loads the pre-trained BERT + TF-IDF + ExtraTreesClassifier and
provides a single predict_bert(text) function for use in api.py.

Model files required (generate with train_bert_model.py):
    fake_job_model.pkl       — ExtraTrees classifier
    tfidf_vectorizer.pkl     — TF-IDF vectorizer (5000 features)

Lazy loading: BERT is loaded on first prediction call so that
api.py starts up quickly even without GPU hardware.
"""

import os
import pickle
import numpy as np

# ── File paths ────────────────────────────────────────────────────────────────
_BASE_DIR   = os.path.dirname(os.path.abspath(__file__))
MODEL_FILE  = os.path.join(_BASE_DIR, "fake_job_model.pkl")
VEC_FILE    = os.path.join(_BASE_DIR, "tfidf_vectorizer.pkl")

# ── Lazy-loaded BERT state (avoids slow startup) ──────────────────────────────
_bert_tokenizer = None
_bert_model     = None
_device         = None
_classifier     = None
_vectorizer     = None

# ── Status flag (set to False if BERT fails to load) ─────────────────────────
_bert_available = True


def _load_bert():
    """Load BERT tokenizer + model once. Subsequent calls are no-ops."""
    global _bert_tokenizer, _bert_model, _device, _bert_available
    if _bert_model is not None or not _bert_available:
        return
    try:
        import torch
        from transformers import BertTokenizer, BertModel

        _device         = torch.device("cuda" if torch.cuda.is_available() else "cpu")
        _bert_tokenizer = BertTokenizer.from_pretrained("bert-base-uncased")
        _bert_model     = BertModel.from_pretrained("bert-base-uncased").to(_device)
        _bert_model.eval()
        print(f"[ScamShield BERT] Loaded on {_device}")
    except Exception as e:
        _bert_available = False
        print(f"[ScamShield BERT] Failed to load BERT — predictions disabled: {e}")


def _load_sklearn_model():
    """Load TF-IDF vectorizer + ExtraTrees classifier once."""
    global _classifier, _vectorizer
    if _classifier is not None:
        return True
    if not os.path.exists(MODEL_FILE) or not os.path.exists(VEC_FILE):
        return False
    try:
        with open(VEC_FILE, "rb") as f:
            _vectorizer = pickle.load(f)
        with open(MODEL_FILE, "rb") as f:
            _classifier = pickle.load(f)
        return True
    except Exception as e:
        print(f"[ScamShield BERT] Could not load model files: {e}")
        return False


def _get_embedding(sentence: str) -> np.ndarray:
    """
    Tokenise a sentence and return the BERT CLS mean-pool embedding.
    Returns shape (768,) numpy array.
    Text is capped at 512 chars before tokenisation for speed.
    """
    import torch
    inputs = _bert_tokenizer(
        sentence[:512],
        return_tensors="pt",
        truncation=True,
        padding=True,
        max_length=128,
    )
    inputs = {k: v.to(_device) for k, v in inputs.items()}
    with torch.no_grad():
        outputs = _bert_model(**inputs)
    # Mean pool over token dimension → (1, 768) → (768,)
    return outputs.last_hidden_state.mean(dim=1).cpu().numpy()[0]


def predict_bert(text: str) -> float | None:
    """
    Returns scam probability (0.0 – 1.0) using the BERT + ExtraTrees model.
    Returns None if the model files don't exist yet (run train_bert_model.py first).

    Args:
        text: Raw job post text (will be internally truncated for speed).

    Returns:
        float probability of scam, or None if unavailable.
    """
    global _bert_available

    # Guard: model files must exist
    if not _load_sklearn_model():
        return None  # Model not trained yet

    # Guard: BERT must be available
    if not _bert_available:
        return None

    _load_bert()
    if not _bert_available:
        return None

    try:
        # TF-IDF features (5000-dim)
        tfidf_feat = _vectorizer.transform([text]).toarray()   # (1, 5000)

        # BERT embedding (768-dim)
        bert_feat = _get_embedding(text).reshape(1, -1)         # (1, 768)

        # Stack → (1, 5768)
        X = np.hstack((tfidf_feat, bert_feat))

        # Predict probability of class 1 (scam)
        proba = _classifier.predict_proba(X)[0]
        classes = list(_classifier.classes_)
        class_1_idx = classes.index(1) if 1 in classes else -1
        if class_1_idx >= 0:
            return float(proba[class_1_idx])
        return 0.0

    except Exception as e:
        print(f"[ScamShield BERT] Prediction error: {e}")
        return None


def is_model_ready() -> bool:
    """Returns True if both model files exist and can be loaded."""
    return os.path.exists(MODEL_FILE) and os.path.exists(VEC_FILE)

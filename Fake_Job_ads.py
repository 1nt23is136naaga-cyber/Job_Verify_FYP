#!/usr/bin/env python
# coding: utf-8
"""
Fake Job Ad Detector
====================
Model  : ExtraTrees + TF-IDF + BERT embeddings (hybrid)
Dataset: fake_job_postings.csv  (Kaggle EMSCAD dataset)
Author : AntiGravity / ScamShield FYP
"""

# ─────────────────────────────────────────────────────────────────────────────
# 1.  Imports
# ─────────────────────────────────────────────────────────────────────────────
import os, re, json, pickle, warnings
import numpy as np
import pandas as pd
import torch
import matplotlib
matplotlib.use("Agg")          # non-interactive backend (safe on headless servers)
import matplotlib.pyplot as plt
import seaborn as sns

from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.model_selection import train_test_split, StratifiedKFold, cross_val_score
from sklearn.ensemble import ExtraTreesClassifier
from sklearn.metrics import (
    classification_report,
    confusion_matrix,
    roc_auc_score,
    roc_curve,
    average_precision_score,
    precision_recall_curve,
    matthews_corrcoef,
    balanced_accuracy_score,
    f1_score,
    accuracy_score,
)
from imblearn.over_sampling import ADASYN
from transformers import BertTokenizer, BertModel
from tqdm import tqdm

warnings.filterwarnings("ignore")

# ─────────────────────────────────────────────────────────────────────────────
# 2.  Config
# ─────────────────────────────────────────────────────────────────────────────
RANDOM_STATE   = 42
TEST_SIZE      = 0.20
TFIDF_FEATURES = 5000
BERT_MAX_LEN   = 128
TREE_N         = 300
RESULTS_DIR    = "results"
os.makedirs(RESULTS_DIR, exist_ok=True)

device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
print(f"[INFO] Device : {device}")
if device.type == "cuda":
    print(f"[INFO] GPU    : {torch.cuda.get_device_name(0)}")

# ─────────────────────────────────────────────────────────────────────────────
# 3.  Text Preprocessing
# ─────────────────────────────────────────────────────────────────────────────
def clean_text(text: str) -> str:
    """Lowercase, strip HTML tags, collapse whitespace, remove non-ASCII junk."""
    text = str(text).lower()
    text = re.sub(r"<[^>]+>", " ", text)                     # strip HTML
    text = re.sub(r"http\S+|www\.\S+", " ", text)            # remove URLs
    text = re.sub(r"[^a-z0-9\s]", " ", text)                 # keep alphanum
    text = re.sub(r"\s+", " ", text).strip()
    return text


def build_corpus(df: pd.DataFrame) -> pd.Series:
    cols = ["title", "company_profile", "description", "requirements", "benefits"]
    available = [c for c in cols if c in df.columns]
    corpus = df[available].fillna("").apply(lambda r: " ".join(r.values), axis=1)
    return corpus.apply(clean_text)


# ─────────────────────────────────────────────────────────────────────────────
# 4.  Load & Explore Data
# ─────────────────────────────────────────────────────────────────────────────
print("\n[INFO] Loading dataset …")
data = pd.read_csv("fake_job_postings.csv")
print(f"       Shape  : {data.shape}")
print(f"       Labels :\n{data['fraudulent'].value_counts().to_string()}")
print(f"\n       Null counts :\n{data.isnull().sum().to_string()}")

corpus = build_corpus(data)
labels = data["fraudulent"]

fraud_pct = labels.mean() * 100
print(f"\n[INFO] Fraud rate : {fraud_pct:.2f}%  ({labels.sum()} / {len(labels)})")

# ─────────────────────────────────────────────────────────────────────────────
# 5.  Train / Test Split
# ─────────────────────────────────────────────────────────────────────────────
X_train_text, X_test_text, y_train, y_test = train_test_split(
    corpus, labels,
    test_size=TEST_SIZE,
    random_state=RANDOM_STATE,
    stratify=labels,        # preserve class ratio
)
print(f"\n[INFO] Train : {len(X_train_text)}  |  Test : {len(X_test_text)}")

# ─────────────────────────────────────────────────────────────────────────────
# 6.  TF-IDF Features
# ─────────────────────────────────────────────────────────────────────────────
print("\n[INFO] Fitting TF-IDF …")
tfidf = TfidfVectorizer(max_features=TFIDF_FEATURES, sublinear_tf=True, ngram_range=(1, 2))
X_train_tfidf = tfidf.fit_transform(X_train_text).toarray()
X_test_tfidf  = tfidf.transform(X_test_text).toarray()
print(f"       Train TF-IDF : {X_train_tfidf.shape}")
print(f"       Test  TF-IDF : {X_test_tfidf.shape}")

# ─────────────────────────────────────────────────────────────────────────────
# 7.  BERT Embeddings
# ─────────────────────────────────────────────────────────────────────────────
print("\n[INFO] Loading BERT …")
tokenizer  = BertTokenizer.from_pretrained("bert-base-uncased")
bert_model = BertModel.from_pretrained("bert-base-uncased").to(device)
bert_model.eval()


def get_bert_embedding(sentence: str) -> np.ndarray:
    inputs = tokenizer(
        sentence,
        return_tensors="pt",
        truncation=True,
        padding=True,
        max_length=BERT_MAX_LEN,
    )
    inputs = {k: v.to(device) for k, v in inputs.items()}
    with torch.no_grad():
        outputs = bert_model(**inputs)
    return outputs.last_hidden_state.mean(dim=1).cpu().numpy()[0]


def embed_corpus(texts, desc="BERT embeddings"):
    return np.array([get_bert_embedding(s) for s in tqdm(texts, desc=desc)])


train_bert = embed_corpus(X_train_text, "Train BERT embeddings")
test_bert  = embed_corpus(X_test_text,  "Test  BERT embeddings")
print(f"\n       train_bert : {train_bert.shape}")
print(f"       test_bert  : {test_bert.shape}")

# ─────────────────────────────────────────────────────────────────────────────
# 8.  Combine Features
# ─────────────────────────────────────────────────────────────────────────────
X_train = np.hstack((X_train_tfidf, train_bert))
X_test  = np.hstack((X_test_tfidf,  test_bert))
print(f"\n[INFO] Combined X_train : {X_train.shape}")
print(f"       Combined X_test  : {X_test.shape}")

# ─────────────────────────────────────────────────────────────────────────────
# 9.  ADASYN Oversampling
# ─────────────────────────────────────────────────────────────────────────────
print("\n[INFO] ADASYN balancing …")
adasyn = ADASYN(random_state=RANDOM_STATE)
X_train_bal, y_train_bal = adasyn.fit_resample(X_train, y_train)
print(f"       Balanced shape  : {X_train_bal.shape}")
print(f"       Class counts    :\n{pd.Series(y_train_bal).value_counts().to_string()}")

# ─────────────────────────────────────────────────────────────────────────────
# 10. Train ExtraTreesClassifier
# ─────────────────────────────────────────────────────────────────────────────
print("\n[INFO] Training ExtraTreesClassifier …")
model = ExtraTreesClassifier(
    n_estimators=TREE_N,
    max_features="sqrt",
    min_samples_leaf=2,
    class_weight="balanced",
    random_state=RANDOM_STATE,
    n_jobs=-1,
)
model.fit(X_train_bal, y_train_bal)
print("       Model trained ✓")

# ─────────────────────────────────────────────────────────────────────────────
# 11. Predictions & Probabilities
# ─────────────────────────────────────────────────────────────────────────────
y_pred      = model.predict(X_test)
y_prob      = model.predict_proba(X_test)[:, 1]   # probability of fraud

# ─────────────────────────────────────────────────────────────────────────────
# 12. Comprehensive Metrics
# ─────────────────────────────────────────────────────────────────────────────
accuracy    = accuracy_score(y_test, y_pred)
bal_acc     = balanced_accuracy_score(y_test, y_pred)
f1_macro    = f1_score(y_test, y_pred, average="macro")
f1_weighted = f1_score(y_test, y_pred, average="weighted")
f1_fraud    = f1_score(y_test, y_pred, pos_label=1)
roc_auc     = roc_auc_score(y_test, y_prob)
avg_prec    = average_precision_score(y_test, y_prob)
mcc         = matthews_corrcoef(y_test, y_pred)

print("\n" + "═" * 55)
print("  EVALUATION METRICS")
print("═" * 55)
print(f"  Accuracy              : {accuracy:.4f}  ({accuracy*100:.2f}%)")
print(f"  Balanced Accuracy     : {bal_acc:.4f}")
print(f"  F1-Score (Fraud)      : {f1_fraud:.4f}")
print(f"  F1-Score (Macro)      : {f1_macro:.4f}")
print(f"  F1-Score (Weighted)   : {f1_weighted:.4f}")
print(f"  ROC-AUC               : {roc_auc:.4f}")
print(f"  Average Precision     : {avg_prec:.4f}")
print(f"  Matthews Corr. Coef.  : {mcc:.4f}")
print("═" * 55)

print("\n  Classification Report:")
print(classification_report(y_test, y_pred, target_names=["Legitimate", "Fraudulent"]))

cm = confusion_matrix(y_test, y_pred)
tn, fp, fn, tp = cm.ravel()
print(f"  Confusion Matrix:")
print(f"    True Negatives  : {tn}   (Legit correctly classified)")
print(f"    False Positives : {fp}   (Legit flagged as Fraud)")
print(f"    False Negatives : {fn}   (Fraud missed)")
print(f"    True Positives  : {tp}   (Fraud correctly caught)")
print(f"\n    Precision (Fraud): {tp/(tp+fp):.4f}")
print(f"    Recall    (Fraud): {tp/(tp+fn):.4f}")

# ─────────────────────────────────────────────────────────────────────────────
# 13. Visualisations
# ─────────────────────────────────────────────────────────────────────────────
sns.set_theme(style="darkgrid", palette="muted")
fig, axes = plt.subplots(1, 3, figsize=(18, 6))
fig.suptitle("Fake Job Ad Detector — Model Evaluation", fontsize=15, fontweight="bold")

# — 13a. Confusion Matrix Heatmap ——————————————————————————————————————————
ax = axes[0]
sns.heatmap(
    cm, annot=True, fmt="d", cmap="Blues",
    xticklabels=["Legit", "Fraud"],
    yticklabels=["Legit", "Fraud"],
    ax=ax, linewidths=0.5, linecolor="gray",
)
ax.set_title("Confusion Matrix", fontsize=13)
ax.set_xlabel("Predicted")
ax.set_ylabel("Actual")

# — 13b. ROC Curve ————————————————————————————————————————————————————————
ax = axes[1]
fpr, tpr, _ = roc_curve(y_test, y_prob)
ax.plot(fpr, tpr, color="#4C72B0", lw=2, label=f"ROC curve (AUC = {roc_auc:.4f})")
ax.plot([0, 1], [0, 1], "k--", lw=1, label="Random classifier")
ax.fill_between(fpr, tpr, alpha=0.15, color="#4C72B0")
ax.set_xlim([0.0, 1.0])
ax.set_ylim([0.0, 1.05])
ax.set_xlabel("False Positive Rate")
ax.set_ylabel("True Positive Rate")
ax.set_title("ROC Curve", fontsize=13)
ax.legend(loc="lower right", fontsize=9)

# — 13c. Precision-Recall Curve ——————————————————————————————————————————
ax = axes[2]
precision, recall, _ = precision_recall_curve(y_test, y_prob)
ax.plot(recall, precision, color="#DD8452", lw=2, label=f"AP = {avg_prec:.4f}")
ax.fill_between(recall, precision, alpha=0.15, color="#DD8452")
baseline = labels.mean()
ax.axhline(y=baseline, color="k", linestyle="--", lw=1, label=f"Baseline (fraud rate = {baseline:.2f})")
ax.set_xlabel("Recall")
ax.set_ylabel("Precision")
ax.set_title("Precision-Recall Curve", fontsize=13)
ax.legend(loc="upper right", fontsize=9)
ax.set_xlim([0.0, 1.0])
ax.set_ylim([0.0, 1.05])

plt.tight_layout()
plot_path = os.path.join(RESULTS_DIR, "evaluation_plots.png")
plt.savefig(plot_path, dpi=150)
plt.close()
print(f"\n[INFO] Plots saved → {plot_path}")

# — 13d. Metrics Summary Bar Chart ————————————————————————————————————————
metric_names  = ["Accuracy", "Balanced\nAccuracy", "F1\n(Fraud)", "F1\n(Macro)", "ROC-AUC", "Avg\nPrecision", "MCC"]
metric_values = [accuracy, bal_acc, f1_fraud, f1_macro, roc_auc, avg_prec, (mcc + 1) / 2]  # MCC normalised to [0,1]

fig2, ax2 = plt.subplots(figsize=(10, 5))
bars = ax2.bar(metric_names, metric_values, color=sns.color_palette("muted", len(metric_names)), edgecolor="white", linewidth=0.5)
for bar, val in zip(bars, metric_values):
    ax2.text(bar.get_x() + bar.get_width() / 2, bar.get_height() + 0.01,
             f"{val:.3f}", ha="center", va="bottom", fontsize=10, fontweight="bold")
ax2.set_ylim(0, 1.15)
ax2.set_ylabel("Score", fontsize=12)
ax2.set_title("Model Performance Summary  (MCC normalised to [0,1])", fontsize=13, fontweight="bold")
ax2.axhline(y=0.9, color="green", linestyle="--", alpha=0.5, label="0.90 target")
ax2.legend(fontsize=9)
sns.despine()
bar_path = os.path.join(RESULTS_DIR, "metrics_bar.png")
plt.tight_layout()
plt.savefig(bar_path, dpi=150)
plt.close()
print(f"[INFO] Bar chart saved → {bar_path}")

# ─────────────────────────────────────────────────────────────────────────────
# 14. Cross-Validation (TF-IDF only, fast sanity check)
# ─────────────────────────────────────────────────────────────────────────────
print("\n[INFO] 5-Fold Stratified CV on TF-IDF features (quick sanity check) …")
cv_model = ExtraTreesClassifier(n_estimators=100, random_state=RANDOM_STATE, n_jobs=-1)
cv_scores = cross_val_score(cv_model, X_train_tfidf, y_train, cv=5, scoring="roc_auc")
print(f"       CV ROC-AUC : {cv_scores.mean():.4f} ± {cv_scores.std():.4f}")

# ─────────────────────────────────────────────────────────────────────────────
# 15. Save Metrics to JSON
# ─────────────────────────────────────────────────────────────────────────────
metrics_dict = {
    "accuracy":           round(float(accuracy),    4),
    "balanced_accuracy":  round(float(bal_acc),     4),
    "f1_fraud":           round(float(f1_fraud),    4),
    "f1_macro":           round(float(f1_macro),    4),
    "f1_weighted":        round(float(f1_weighted), 4),
    "roc_auc":            round(float(roc_auc),     4),
    "average_precision":  round(float(avg_prec),    4),
    "mcc":                round(float(mcc),         4),
    "cv_roc_auc_mean":    round(float(cv_scores.mean()), 4),
    "cv_roc_auc_std":     round(float(cv_scores.std()),  4),
    "confusion_matrix": {
        "TN": int(tn), "FP": int(fp),
        "FN": int(fn), "TP": int(tp),
    },
}
metrics_path = os.path.join(RESULTS_DIR, "metrics.json")
with open(metrics_path, "w") as f:
    json.dump(metrics_dict, f, indent=2)
print(f"[INFO] Metrics saved → {metrics_path}")

# ─────────────────────────────────────────────────────────────────────────────
# 16. Save Model Artifacts
# ─────────────────────────────────────────────────────────────────────────────
pickle.dump(model, open("fake_job_model.pkl", "wb"))
pickle.dump(tfidf, open("tfidf_vectorizer.pkl", "wb"))
print("\n[INFO] Model artifacts saved:")
print("       → fake_job_model.pkl")
print("       → tfidf_vectorizer.pkl")

print("\n✅  Done.")

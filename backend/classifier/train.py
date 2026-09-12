"""Train TF-IDF + LogisticRegression on Mathur et al. dark-pattern strings.

Downloads the public CSV when online; falls back to the bundled sample.

Run:
    cd backend && python -m classifier.train
"""

from __future__ import annotations

from pathlib import Path

import joblib
import pandas as pd
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import classification_report
from sklearn.model_selection import train_test_split
from sklearn.pipeline import Pipeline

DATA_DIR = Path(__file__).resolve().parent / "data"
MODEL_DIR = Path(__file__).resolve().parent / "models"
SAMPLE_CSV = DATA_DIR / "dark-patterns.sample.csv"
FULL_CSV = DATA_DIR / "dark-patterns.csv"
MODEL_PATH = MODEL_DIR / "dark_patterns.joblib"

MATHUR_URL = (
    "https://raw.githubusercontent.com/aruneshmathur/dark-patterns/"
    "master/data/final-dark-patterns/dark-patterns.csv"
)


def load_dataset() -> pd.DataFrame:
    path = FULL_CSV if FULL_CSV.exists() else SAMPLE_CSV
    if not FULL_CSV.exists():
        try:
            import urllib.request

            DATA_DIR.mkdir(parents=True, exist_ok=True)
            urllib.request.urlretrieve(MATHUR_URL, FULL_CSV)
            path = FULL_CSV
            print(f"Downloaded Mathur dataset -> {FULL_CSV}")
        except Exception as exc:
            print(f"Download failed ({exc}); using bundled sample {SAMPLE_CSV}")
            path = SAMPLE_CSV

    df = pd.read_csv(path)
    text_col = "Pattern String" if "Pattern String" in df.columns else df.columns[0]
    label_col = "Pattern Category" if "Pattern Category" in df.columns else df.columns[2]
    df = df[[text_col, label_col]].rename(columns={text_col: "text", label_col: "label"})
    df["text"] = df["text"].astype(str).str.strip()
    df["label"] = df["label"].astype(str).str.strip()
    df = df[(df["text"].str.len() > 0) & (df["label"].str.len() > 0) & (df["label"] != "nan")]
    df = df.drop_duplicates(subset=["text"])
    return df


def train(test_size: float = 0.2, random_state: int = 42) -> Path:
    df = load_dataset()
    print(f"Training on {len(df)} rows, labels={sorted(df['label'].unique())}")

    pipeline = Pipeline(
        [
            (
                "tfidf",
                TfidfVectorizer(
                    ngram_range=(1, 2),
                    min_df=1,
                    max_features=15_000,
                    lowercase=True,
                ),
            ),
            (
                "clf",
                LogisticRegression(
                    max_iter=2000,
                    class_weight="balanced",
                    solver="lbfgs",
                ),
            ),
        ]
    )

    stratify = df["label"] if df["label"].value_counts().min() >= 2 else None
    X_train, X_test, y_train, y_test = train_test_split(
        df["text"],
        df["label"],
        test_size=test_size,
        random_state=random_state,
        stratify=stratify,
    )
    pipeline.fit(X_train, y_train)
    y_pred = pipeline.predict(X_test)
    print(classification_report(y_test, y_pred, zero_division=0))

    MODEL_DIR.mkdir(parents=True, exist_ok=True)
    joblib.dump(
        {
            "pipeline": pipeline,
            "labels": sorted(df["label"].unique().tolist()),
            "source_rows": int(len(df)),
        },
        MODEL_PATH,
    )
    print(f"Saved model -> {MODEL_PATH}")
    return MODEL_PATH


if __name__ == "__main__":
    train()

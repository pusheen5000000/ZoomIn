"""Yamana e-commerce dark-pattern TSV (Apache-2.0). See data/NOTICE.txt."""

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
TSV_PATH = DATA_DIR / "yamana-ec-darkpattern.tsv"
MODEL_PATH = MODEL_DIR / "dark_patterns.joblib"

YAMANA_URL = (
    "https://raw.githubusercontent.com/yamanalab/ec-darkpattern/"
    "master/dataset/dataset.tsv"
)


def load_dataset() -> pd.DataFrame:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    if not TSV_PATH.exists():
        import urllib.request

        urllib.request.urlretrieve(YAMANA_URL, TSV_PATH)
        print(f"Downloaded Yamana dataset -> {TSV_PATH}")

    df = pd.read_csv(TSV_PATH, sep="\t")
    # Columns: page_id, text, label (0/1), Pattern Category
    text_col = "text" if "text" in df.columns else df.columns[1]
    cat_col = "Pattern Category" if "Pattern Category" in df.columns else df.columns[-1]
    df = df[[text_col, cat_col]].rename(columns={text_col: "text", cat_col: "label"})
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
    print(classification_report(y_test, pipeline.predict(X_test), zero_division=0))

    MODEL_DIR.mkdir(parents=True, exist_ok=True)
    joblib.dump(
        {
            "pipeline": pipeline,
            "labels": sorted(df["label"].unique().tolist()),
            "source": "yamanalab/ec-darkpattern",
            "source_rows": int(len(df)),
        },
        MODEL_PATH,
    )
    print(f"Saved model -> {MODEL_PATH}")
    return MODEL_PATH


if __name__ == "__main__":
    train()

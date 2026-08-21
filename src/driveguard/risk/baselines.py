"""Snapshot classifiers vs the rolling-window scorer.

Random Forest, SVM, Logistic Regression, and a Decision Tree are trained on
window aggregates so the eval report can sit next to the temporal gate.
They are not used on the live path.
"""

from __future__ import annotations

from typing import Any

import numpy as np
from sklearn.ensemble import RandomForestClassifier
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import accuracy_score, f1_score, precision_score, recall_score
from sklearn.model_selection import train_test_split
from sklearn.svm import LinearSVC
from sklearn.tree import DecisionTreeClassifier

from driveguard.risk.temporal import aggregate_features


def compare_snapshot_models(
    windows: list[np.ndarray],
    labels: list[int],
    seed: int = 42,
) -> list[dict[str, Any]]:
    x = np.vstack([aggregate_features(w) for w in windows])
    y = np.array(labels)
    x_train, x_test, y_train, y_test = train_test_split(
        x, y, test_size=0.3, random_state=seed, stratify=y
    )
    models: dict[str, Any] = {
        "random_forest": RandomForestClassifier(
            n_estimators=40, max_depth=6, random_state=seed, n_jobs=1
        ),
        "linear_svm": LinearSVC(random_state=seed, max_iter=4000),
        "logistic_regression": LogisticRegression(max_iter=400, random_state=seed),
        "decision_tree": DecisionTreeClassifier(max_depth=6, random_state=seed),
    }
    rows: list[dict[str, Any]] = []
    for name, clf in models.items():
        clf.fit(x_train, y_train)
        pred = clf.predict(x_test)
        rows.append(
            {
                "model": name,
                "accuracy": round(float(accuracy_score(y_test, pred)), 4),
                "precision": round(float(precision_score(y_test, pred, zero_division=0)), 4),
                "recall": round(float(recall_score(y_test, pred, zero_division=0)), 4),
                "f1": round(float(f1_score(y_test, pred, zero_division=0)), 4),
            }
        )
    return rows

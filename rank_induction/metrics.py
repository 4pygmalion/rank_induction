from __future__ import annotations

import math
import warnings
from typing import List, Tuple
from itertools import cycle
from dataclasses import dataclass, asdict, field


import numpy as np
import seaborn as sns
from matplotlib import pyplot as plt
from scipy.interpolate import interp1d
from sklearn.metrics import (
    f1_score,
    auc,
    roc_curve,
    roc_auc_score,
    average_precision_score,
    confusion_matrix,
    precision_recall_curve,
)


class AverageMeter:
    """Computes and stores the average and current value"""

    name: str

    def __init__(self, name: str):
        self.name = name
        self.val: float = 0
        self.avg: float = 0
        self.sum: float = 0
        self.count: float = 0

    def reset(self):
        self.val = 0
        self.avg = 0
        self.sum = 0
        self.count = 0

    def update(self, val, n=1):
        self.val = val
        self.sum += val * n
        self.count += n
        if self.count > 0:
            self.avg = self.sum / self.count

    def __repr__(self) -> str:
        return f"AverageMeter(name={self.name}, avg={self.avg:.4f}, count={self.count})"


@dataclass
class MetricsMeter:
    """
    Computes and stores the average and current value

    Example:
        >>> metrics = MetricsMeter("train")
        >>> metrics_meter.update(
                model_confidence[:, 1].detach().cpu().numpy().tolist(),
                ys[:, 1].cpu().numpy().tolist(),
            )
        >>> metrics.probs
        [0.983, 0.928, ...]

        >>> metrics.labels
        [1, 0, ...]

    """

    name: str = None

    accuracy_threshold: float = 0.5
    probs: List[float] = field(default_factory=list)
    labels: List[float] = field(default_factory=list)

    def update(self, probs: List[float], labels=List[float]) -> None:
        if len(probs) != len(labels):
            raise ValueError(
                f"probs and labels must have same length, "
                f"len probs({len(probs)}), len labels({len(labels)})"
            )

        self.probs.extend(probs)
        self.labels.extend(labels)

        return

    @property
    def accuracy(self) -> float:
        if len(self.labels) == 0:
            return math.nan

        acc = 0
        for label, prob in zip(self.labels, self.probs):
            pred_label = float(prob > self.accuracy_threshold)
            if label == pred_label:
                acc += 1

        return acc / len(self.labels)

    @property
    def auroc(self) -> float:
        if len(self.labels) == 0:
            return math.nan

        if len(set(self.labels)) < 2:
            return math.nan

        return roc_auc_score(self.labels, self.probs)

    @property
    def prauc(self) -> float:
        if len(self.labels) == 0:
            return math.nan

        if len(set(self.labels)) < 2:
            return math.nan

        precision, recall, threshold = precision_recall_curve(self.labels, self.probs)
        return auc(recall, precision)

    @property
    def confusion_matrix_values(self) -> Tuple[int, int, int, int]:
        """Returns confusion matrix values

        Exception:
            - In cases where there is less than 2 labels,
            it should return 0,0,0,0 by default since it may not return four values

            >>> y_true = [False, False, False, False]
            >>> y_pred = [False, False, False, False]
            >>> mat = confusion_matrix(y_true, y_pred)
            >>> print(mat)
            array([[4]])

            >>> tn, fp, fn, tp = confusion_matrix(y_true, y_pred)
            ValueError: not enough values to unpack (expected 4, got 1)
        """
        if len(np.unique(self.labels)) < 2:
            return 0, 0, 0, 0

        preds = [int(prob > self.accuracy_threshold) for prob in self.probs]
        tn, fp, fn, tp = confusion_matrix(y_true=self.labels, y_pred=preds).ravel()

        return tp, fn, tn, fp

    @property
    def sensitivity(self) -> float:
        """Sensitivity or True Positive Rate"""
        tp, fn, _, _ = self.confusion_matrix_values

        if tp + fn == 0:
            return math.nan

        return tp / (tp + fn)

    @property
    def specificity(self) -> float:
        """Specificity or True Negative Rate"""
        _, _, tn, fp = self.confusion_matrix_values

        if tn + fp == 0:
            return math.nan

        return tn / (tn + fp)

    def __repr__(self) -> str:
        return (
            f"MetricsMeter(N=({len(self.labels)})), ACC({self.accuracy}), "
            f"AUROC({self.auroc}), PRAUC({self.prauc}, "
            f"Sensitivity({self.sensitivity}), Specificity({self.specificity})"
        )

    def to_dict(self) -> dict:
        with warnings.catch_warnings():
            warnings.simplefilter("ignore", UserWarning)
            metrics = {
                "accuracy": self.accuracy,
                "auroc": self.auroc,
                "prauc": self.prauc,
                "sensitivity": self.sensitivity,
                "specificity": self.specificity,
            }

        if self.name:
            metrics = {self.name + "_" + key: val for key, val in metrics.items()}

        return metrics


def plot_auroc(y_true: np.ndarray, y_prob: np.ndarray) -> Tuple[plt.Figure, plt.Axes]:
    """그림을 사용하여 AUROC (Area Under the Receiver Operating Characteristic Curve)를 시각화

    Args:
        y_true (np.ndarray): 실제 라벨 값의 배열.
        y_prob (np.ndarray): 모델의 예측 확률 값의 배열.

    Returns:
        Tuple[plt.Figure, plt.Axes]: Matplotlib의 Figure와 Axes 객체를 반환

    Example:
        >>> fig, axes = plot_auroc(bag_labels, bag_probs)
        >>> plt.savefig("auroc.png")
        >>> mlflow.log_artifact("auroc.png")
        >>> os.remove("auroc.png")
        >>> plt.clf()
    """
    fpr, tpr, _ = roc_curve(y_true, y_prob)
    roc_auc = auc(fpr, tpr)

    fig, axes = plt.subplots()
    axes.plot(fpr, tpr, color="darkorange", lw=2, label=f"AUROC = {roc_auc:.3f}")
    axes.plot([0, 1], [0, 1], color="navy", lw=2, linestyle="--")
    axes.set_xlim([0.0, 1.0])
    axes.set_ylim([0.0, 1.05])
    axes.set_xlabel("False Positive Rate")
    axes.set_ylabel("True Positive Rate")
    axes.set_title("Receiver Operating Characteristic (ROC)")
    axes.legend(loc="lower right")

    return fig, axes


def plot_prauc(y_true: np.ndarray, y_prob: np.ndarray) -> Tuple[plt.Figure, plt.Axes]:
    """그림을 사용하여 AUROC (Area Under the Receiver Operating Characteristic Curve)를 시각화

    Args:
        y_true (np.ndarray): 실제 라벨 값의 배열.
        y_prob (np.ndarray): 모델의 예측 확률 값의 배열.

    Returns:
        Tuple[plt.Figure, plt.Axes]: Matplotlib의 Figure와 Axes 객체를 반환

    Example:
        >>> fig, axes = plot_auroc(bag_labels, bag_probs)
        >>> plt.savefig("auroc.png")
        >>> mlflow.log_artifact("auroc.png")
        >>> os.remove("auroc.png")
        >>> plt.clf()
    """
    precision, recall, threshold = precision_recall_curve(y_true, y_prob)
    roc_auc = auc(recall, precision)

    fig, axes = plt.subplots()
    axes.plot(
        recall, precision, color="darkorange", lw=2, label=f"PRAUC = {roc_auc:.3f}"
    )
    axes.plot([0, 1], [0, 1], color="navy", lw=2, linestyle="--")
    axes.set_xlim([0.0, 1.0])
    axes.set_ylim([0.0, 1.05])
    axes.set_xlabel("Recall")
    axes.set_ylabel("Precision")
    axes.set_title("Receiver Operating Characteristic (PRAUC)")
    axes.legend(loc="lower right")

    return fig, axes


def plot_confusion_matrix(
    y_true,
    y_pred,
    labels: List[str],
) -> Tuple[plt.Figure, plt.Axes]:
    """Confusion Matrix를 시각화하는 함수

    Args:
        y_true (np.ndarray): 실제 라벨 값의 배열.
        y_pred (np.ndarray): 모델의 예측 라벨 값의 배열.
        labels (List[str]): 클래스 라벨의 리스트(Ascending order).

    Returns:
        Tuple[plt.Figure, plt.Axes]: Matplotlib의 Figure와 Axes 객체를 반환

    Example:
        >>> fig, axes = plot_confusion_matrix(true_labels, predicted_labels, ["Class 0", "Class 1"])
        >>> plt.savefig("confusion_matrix.png")
        >>> mlflow.log_artifact("confusion_matrix.png")
        >>> os.remove("confusion_matrix.png")
        >>> plt.clf()
    """
    cm = confusion_matrix(y_true, y_pred)

    fig, axes = plt.subplots()
    sns.heatmap(
        cm,
        annot=True,
        fmt="d",
        cmap="Blues",
        xticklabels=labels,
        yticklabels=labels,
        ax=axes,
    )

    axes.set_xlabel("Predicted labels")
    axes.set_ylabel("True labels")
    axes.set_title("Confusion Matrix")

    return fig, axes


def plot_cv_auroc(
    fold_y_trues: List[np.ndarray],
    fold_y_probs: List[np.ndarray],
) -> None:
    """CV결과를 담은 AUROC를 시각화

    Args:
        y_true (List[np.ndarray]): 실제 라벨 값의 배열.
        y_prob (List[np.ndarray]): 모델의 예측 확률 값의 배열.

    Returns:
        None: Matplotlib의 Figure와 Axes 객체를 반환

    Example:
        >>> fold_bag_y_trues = list()
        >>> fold_bag_y_probs = list()
        >>> for fold in ...
                ...
        >>>     fold_bag_y_trues.append(bag_labels)
        >>>     fold_bag_y_probs.append(bag_probs)

        >>> plot_cv_auroc(fold_bag_y_trues, fold_bag_y_probs)
        >>> plt.savefig("cv_auroc.png")
        >>> mlflow.log_artifact("cv_auroc.png")
        >>> os.remove("cv_auroc.png")
        >>> plt.clf()
    """
    plt.figure(figsize=(8, 6))
    lw = 2
    colors = cycle(["aqua", "darkorange", "cornflowerblue", "red", "purple"])

    # Initialize lists to store individual fold's FPR, TPR, and AUROC
    all_fpr = []
    all_tpr = []
    all_roc_auc = []

    # Calculate AUROC for each fold and plot the ROC curve
    for i, (y_true, y_prob) in enumerate(zip(fold_y_trues, fold_y_probs)):
        fpr, tpr, _ = roc_curve(y_true, y_prob)
        roc_auc = auc(fpr, tpr)
        all_fpr.append(fpr)
        all_tpr.append(tpr)
        all_roc_auc.append(roc_auc)

        plt.plot(
            fpr,
            tpr,
            color=next(colors),
            lw=lw,
            label="ROC curve (fold %d) (area = %0.2f)" % (i + 1, roc_auc),
        )

    # Calculate the mean FPR and TPR across folds
    max_length = max(len(arr) for arr in all_fpr)
    interp_fpr = [
        interp1d(np.arange(len(fpr)), fpr)(np.linspace(0, len(fpr) - 1, max_length))
        for fpr in all_fpr
    ]
    interp_tpr = [
        interp1d(np.arange(len(tpr)), tpr)(np.linspace(0, len(tpr) - 1, max_length))
        for tpr in all_tpr
    ]
    mean_fpr = np.mean(interp_fpr, axis=0)
    mean_tpr = np.mean(interp_tpr, axis=0)
    mean_roc_auc = auc(mean_fpr, mean_tpr)

    # Average ROC curve
    plt.plot(
        mean_fpr,
        mean_tpr,
        color="navy",
        linestyle="--",
        label="Mean ROC curve (area = %0.2f)" % mean_roc_auc,
    )

    plt.xlim([0.0, 1.0])
    plt.ylim([0.0, 1.05])
    plt.xlabel("False Positive Rate")
    plt.ylabel("True Positive Rate")
    plt.title("Receiver Operating Characteristic")
    plt.legend(loc="lower right")


def plot_cv_prauc(
    fold_y_trues: List[np.ndarray],
    fold_y_probs: List[np.ndarray],
) -> None:
    """CV결과를 담은 PRAUC를 시각화

    Args:
        fold_y_trues (List[np.ndarray]): 실제 라벨 값의 배열.
        fold_y_probs (List[np.ndarray]): 모델의 예측 확률 값의 배열.

    Returns:
        None: Matplotlib의 Figure와 Axes 객체를 반환

    Example:
        >>> fold_bag_y_trues = list()
        >>> fold_bag_y_probs = list()
        >>> for fold in ...
                ...
        >>>     fold_bag_y_trues.append(bag_labels)
        >>>     fold_bag_y_probs.append(bag_probs)

        >>> plot_cv_prauc(fold_bag_y_trues, fold_bag_y_probs)
        >>> plt.savefig("cv_prauc.png")
        >>> mlflow.log_artifact("cv_prauc.png")
        >>> os.remove("cv_prauc.png")
        >>> plt.clf()
    """
    plt.figure(figsize=(8, 6))
    lw = 2
    colors = cycle(["aqua", "darkorange", "cornflowerblue", "red", "purple"])

    # Initialize lists to store individual fold's precision, recall, and PRAUC
    all_precision = []
    all_recall = []
    all_prauc = []

    # Calculate PRAUC for each fold and plot the Precision-Recall curve
    for i, (y_true, y_prob) in enumerate(zip(fold_y_trues, fold_y_probs)):
        precision, recall, _ = precision_recall_curve(y_true, y_prob)
        pr_auc = auc(recall, precision)
        all_precision.append(precision)
        all_recall.append(recall)
        all_prauc.append(pr_auc)

        plt.plot(
            recall,
            precision,
            color=next(colors),
            lw=lw,
            label="PR curve (fold %d) (area = %0.2f)" % (i + 1, pr_auc),
        )

    # Calculate the mean precision and recall across folds
    max_length = max(len(arr) for arr in all_recall)
    interp_precision = [
        interp1d(np.arange(len(precision)), precision)(
            np.linspace(0, len(precision) - 1, max_length)
        )
        for precision in all_precision
    ]
    interp_recall = [
        interp1d(np.arange(len(recall)), recall)(
            np.linspace(0, len(recall) - 1, max_length)
        )
        for recall in all_recall
    ]
    mean_precision = np.mean(interp_precision, axis=0)
    mean_recall = np.mean(interp_recall, axis=0)
    mean_prauc = auc(mean_recall, mean_precision)

    # Average Precision-Recall curve
    plt.plot(
        mean_recall,
        mean_precision,
        color="navy",
        linestyle="--",
        label="Mean PR curve (area = %0.2f)" % mean_prauc,
    )

    plt.xlim([0.0, 1.0])
    plt.ylim([0.0, 1.05])
    plt.xlabel("Recall")
    plt.ylabel("Precision")
    plt.title("Precision-Recall Curve")
    plt.legend(loc="lower left")

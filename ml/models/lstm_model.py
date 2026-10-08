"""LSTM / GRU sequence model (PyTorch) for sequential engineered features.

Input is a window of the last ``sequence_length`` feature rows; output is the
future return. Training is only ever started explicitly through the training
pipeline — constructing or importing this module never trains anything and never
imports torch.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Optional

import numpy as np
import pandas as pd

from ml.models.base_model import BasePredictionModel, ModelDependencyError, Preprocessor


def _torch():
    try:
        import torch  # type: ignore
        import torch.nn as nn  # type: ignore
    except ImportError as exc:
        raise ModelDependencyError("torch is not installed (see backend/requirements.txt).") from exc
    return torch, nn


def make_windows(Z: np.ndarray, seq_len: int) -> np.ndarray:
    """(n, f) -> (n - seq_len + 1, seq_len, f); window i ends at row i + seq_len - 1."""
    n = Z.shape[0]
    if n < seq_len:
        return np.empty((0, seq_len, Z.shape[1]))
    idx = np.arange(seq_len)[None, :] + np.arange(n - seq_len + 1)[:, None]
    return Z[idx]


class LSTMModel(BasePredictionModel):
    model_type = "lstm"

    def __init__(self, params=None):
        super().__init__(params)
        self.seq_len = int(self.params.get("sequence_length", 24))
        self.required_context = self.seq_len - 1
        self.pre = Preprocessor()
        self._net = None
        self.y_scale: float = 1.0
        self.train_history: dict[str, list[float]] = {"train_loss": [], "val_loss": []}

    # ---- network ----
    def _build(self, n_features: int):
        torch, nn = _torch()
        p = self.params
        cell = str(p.get("cell", "lstm")).lower()
        if cell not in ("lstm", "gru"):
            raise ValueError("cell must be 'lstm' or 'gru'")
        hidden, layers = int(p.get("hidden_size", 32)), int(p.get("num_layers", 1))
        dropout = float(p.get("dropout", 0.2))

        class Net(nn.Module):
            def __init__(self):
                super().__init__()
                rnn_cls = nn.LSTM if cell == "lstm" else nn.GRU
                self.rnn = rnn_cls(n_features, hidden, num_layers=layers, batch_first=True,
                                   dropout=dropout if layers > 1 else 0.0)
                self.drop = nn.Dropout(dropout)
                self.head = nn.Linear(hidden, 1)

            def forward(self, x):
                out, _ = self.rnn(x)
                return self.head(self.drop(out[:, -1, :])).squeeze(-1)

        return Net()

    def fit(self, X_train, y_train, X_val=None, y_val=None):
        torch, nn = _torch()
        if len(X_train) != len(y_train):
            raise ValueError("X_train and y_train must have the same length.")
        if len(X_train) < self.seq_len + 50:
            raise ValueError("Too few training rows for the configured sequence length.")
        p = self.params
        seed = int(p.get("random_state", 42))
        torch.manual_seed(seed)
        np.random.seed(seed)

        self.feature_names = list(X_train.columns)
        self.pre.fit(X_train)                      # statistics from TRAIN rows only
        Z_tr = self.pre.transform(X_train)
        y_tr = np.asarray(y_train, dtype="float64")[self.seq_len - 1:]
        self.y_scale = float(np.std(y_tr)) or 1.0  # scale targets for stable optimisation
        W_tr = make_windows(Z_tr, self.seq_len)

        has_val = X_val is not None and y_val is not None and len(X_val) >= self.seq_len + 5
        if has_val:
            # validation windows may use the tail of train rows as context (earlier = no leakage)
            ctx = pd.concat([X_train.iloc[-(self.seq_len - 1):], X_val[self.feature_names]]) if self.seq_len > 1 else X_val
            W_va = make_windows(self.pre.transform(ctx), self.seq_len)
            y_va = np.asarray(y_val, dtype="float64")

        net = self._build(Z_tr.shape[1])
        opt = torch.optim.Adam(net.parameters(), lr=float(p.get("learning_rate", 1e-3)),
                               weight_decay=float(p.get("weight_decay", 0.0)))
        loss_fn = nn.MSELoss()
        batch = int(p.get("batch_size", 64))
        epochs, patience = int(p.get("epochs", 30)), int(p.get("patience", 5))

        Xt = torch.tensor(W_tr, dtype=torch.float32)
        yt = torch.tensor(y_tr / self.y_scale, dtype=torch.float32)
        best, best_state, bad = float("inf"), None, 0
        self.train_history = {"train_loss": [], "val_loss": []}
        for _ in range(epochs):
            net.train()
            perm = torch.randperm(Xt.shape[0])  # shuffling WINDOWS inside the training segment is fine; windows are already formed
            total = 0.0
            for i in range(0, len(perm), batch):
                sel = perm[i:i + batch]
                opt.zero_grad()
                loss = loss_fn(net(Xt[sel]), yt[sel])
                loss.backward()
                opt.step()
                total += float(loss) * len(sel)
            self.train_history["train_loss"].append(total / len(perm))
            if has_val:
                net.eval()
                with torch.no_grad():
                    v = float(loss_fn(net(torch.tensor(W_va, dtype=torch.float32)),
                                      torch.tensor(y_va / self.y_scale, dtype=torch.float32)))
                self.train_history["val_loss"].append(v)
                if v < best - 1e-6:
                    best, bad = v, 0
                    best_state = {k: t.detach().clone() for k, t in net.state_dict().items()}
                else:
                    bad += 1
                    if bad >= patience:
                        break
        if best_state is not None:
            net.load_state_dict(best_state)
        net.eval()
        self._net = net
        self.fitted = True
        return self

    def predict(self, X):
        self._check_fitted()
        torch, _ = _torch()
        Xc = self._check_columns(X)
        out = np.full(len(Xc), np.nan, dtype="float64")
        if len(Xc) < self.seq_len:
            return out
        W = make_windows(self.pre.transform(Xc), self.seq_len)
        with torch.no_grad():
            pred = self._net(torch.tensor(W, dtype=torch.float32)).numpy().astype("float64") * self.y_scale
        out[self.seq_len - 1:] = pred
        return out

    def _save_impl(self, directory: Path) -> None:
        torch, _ = _torch()
        torch.save(self._net.state_dict(), directory / "weights.pt")
        (directory / "lstm_meta.json").write_text(json.dumps({
            "preprocessor": self.pre.to_dict(), "y_scale": self.y_scale,
            "n_features": len(self.feature_names), "history": self.train_history,
        }))

    def _load_impl(self, directory: Path) -> None:
        torch, _ = _torch()
        meta = json.loads((directory / "lstm_meta.json").read_text())
        self.pre = Preprocessor.from_dict(meta["preprocessor"])
        self.y_scale = float(meta["y_scale"])
        self.train_history = meta.get("history", self.train_history)
        self.seq_len = int(self.params.get("sequence_length", self.seq_len))
        self.required_context = self.seq_len - 1
        net = self._build(int(meta["n_features"]))
        # weights_only=True: refuse to unpickle arbitrary objects from an artifact file.
        net.load_state_dict(torch.load(directory / "weights.pt", map_location="cpu", weights_only=True))
        net.eval()
        self._net = net

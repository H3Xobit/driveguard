"""Optional PyTorch LSTM. Imported only when torch extra is installed."""

from __future__ import annotations

import numpy as np

try:
    import torch
    from torch import nn
except Exception as exc:  # pragma: no cover
    raise ImportError("torch extra is not installed") from exc


class SessionLSTM(nn.Module):
    def __init__(self, n_in: int = 6, hidden: int = 16) -> None:
        super().__init__()
        self.lstm = nn.LSTM(n_in, hidden, batch_first=True)
        self.head = nn.Linear(hidden, 1)

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        out, _ = self.lstm(x)
        last = out[:, -1]
        return torch.sigmoid(self.head(last)).squeeze(-1)


_MODEL: SessionLSTM | None = None


def score_lstm(window: np.ndarray) -> float:
    global _MODEL
    torch.manual_seed(42)
    if _MODEL is None:
        _MODEL = SessionLSTM()
        _MODEL.eval()
    with torch.no_grad():
        x = torch.tensor(window, dtype=torch.float32).unsqueeze(0)
        y = float(_MODEL(x).item())
    return max(0.0, min(1.0, y))

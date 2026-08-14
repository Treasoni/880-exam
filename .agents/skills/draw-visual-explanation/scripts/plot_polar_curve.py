#!/usr/bin/env python3
"""Plot a basic polar curve for study notes.

Example:
  python3 plot_polar_curve.py \\
    --expr '1 + cos(theta)' \\
    --output workspace/wrong-book/心形线-弧长示意图.png \\
    --title 'Cardioid'
"""

from __future__ import annotations

import argparse
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--expr", required=True, help="r(theta), e.g. '1 + cos(theta)'")
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--theta-min", type=float, default=0.0)
    parser.add_argument("--theta-max", type=float, default=2 * np.pi)
    parser.add_argument("--samples", type=int, default=1200)
    parser.add_argument("--title", default="")
    parser.add_argument("--label", default="")
    args = parser.parse_args()

    if args.samples < 2:
        parser.error("--samples must be at least 2")
    if args.theta_max <= args.theta_min:
        parser.error("--theta-max must be greater than --theta-min")

    theta = np.linspace(args.theta_min, args.theta_max, args.samples)
    namespace = {
        "theta": theta,
        "pi": np.pi,
        "sin": np.sin,
        "cos": np.cos,
        "tan": np.tan,
        "sqrt": np.sqrt,
        "abs": np.abs,
        "exp": np.exp,
        "log": np.log,
    }
    try:
        radius = eval(args.expr, {"__builtins__": {}}, namespace)
    except Exception as exc:
        raise SystemExit(f"无法解析极坐标表达式 {args.expr!r}: {exc}") from exc

    radius = np.asarray(radius, dtype=float)
    if radius.ndim == 0:
        radius = np.full_like(theta, float(radius))
    if radius.shape != theta.shape:
        raise SystemExit("表达式结果必须是与 theta 同长度的一维数组")
    x = radius * np.cos(theta)
    y = radius * np.sin(theta)
    finite = np.isfinite(x) & np.isfinite(y)
    if not finite.any():
        raise SystemExit("表达式没有产生有效的有限点")

    fig, ax = plt.subplots(figsize=(7, 5), dpi=180)
    ax.plot(x[finite], y[finite], linewidth=2.6, color="#2f6690",
            label=args.label or rf"$r={args.expr}$")
    ax.axhline(0, color="#666666", linewidth=0.8)
    ax.axvline(0, color="#999999", linewidth=0.7, linestyle="--")
    ax.set_aspect("equal", adjustable="box")
    ax.set_xlabel("x")
    ax.set_ylabel("y")
    if args.title:
        ax.set_title(args.title)
    ax.grid(alpha=0.18)
    ax.legend(loc="best", frameon=True)

    x_valid, y_valid = x[finite], y[finite]
    x_span = max(float(x_valid.max() - x_valid.min()), 1.0)
    y_span = max(float(y_valid.max() - y_valid.min()), 1.0)
    ax.set_xlim(float(x_valid.min() - 0.08 * x_span),
                float(x_valid.max() + 0.08 * x_span))
    ax.set_ylim(float(y_valid.min() - 0.08 * y_span),
                float(y_valid.max() + 0.08 * y_span))

    args.output.parent.mkdir(parents=True, exist_ok=True)
    fig.tight_layout()
    fig.savefig(args.output, bbox_inches="tight")
    plt.close(fig)
    print(f"已生成示意图：{args.output}")


if __name__ == "__main__":
    main()

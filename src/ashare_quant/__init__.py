"""A 股量化学习项目：研究、回测、验证与模拟盘。"""

from .backtest import BacktestConfig, BacktestResult, run_backtest
from .metrics import performance_summary

__all__ = ["BacktestConfig", "BacktestResult", "performance_summary", "run_backtest"]

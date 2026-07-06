# Backtest Report

Command:

```bash
python -m backtest.engine --symbols BTCUSDT ETHUSDT SOLUSDT --months 12
```

Run date: 2026-07-06 · Data: Bybit USDT Perpetual, 12 months of 15M candles
(34 559 per symbol) with 4H/1H context · Fees + slippage deducted per trade ·
Conservative fills (stop counted first when a candle touches both stop and
target).

## Results (aggregate, 3 symbols)

| Metric | Value |
|---|---|
| Trades | 627 |
| Win rate | 38.0% |
| Profit factor | 0.58 |
| Total result | −221.07 R |
| Avg per trade | −0.353 R |
| Max drawdown | 226.55 R |
| Avg planned R/R | 1:2.5 |
| Long win rate | 29.5% |
| Short win rate | 41.2% |

## Honest verdict

The bundled `trend_pullback` strategy is **not profitable** on this period
with these default parameters — profit factor 0.58 means it loses money after
fees and slippage. It is included as a **reference implementation** of the
plugin API, not as a trading edge.

That is exactly the point of this backtester: same code path as live,
conservative fills, no lookahead — so a weak strategy *shows up as weak*
instead of producing a beautiful fake equity curve. Notable detail: shorts
(41.2% WR) meaningfully outperform longs (29.5% WR) on this window, which is
where parameter/regime tuning would start.

Full trade log is written to `state/backtest_report.json` on every run
(gitignored).

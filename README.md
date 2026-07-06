# Bybit Signal Bot — Multi-Timeframe Crypto Signal Engine

24/7 analytical system that scans all liquid Bybit USDT Perpetual pairs, scores
trade setups through a multi-factor confluence engine, and publishes only
high-quality signals to a Telegram channel — with full lifecycle tracking
(TP1/TP2/TP3, stop loss, breakeven, cancellation).

**No trade execution. Pure analytics + signal delivery.**

> Built as a production-grade, plugin-based architecture: new strategies are
> added as standalone modules via a config file — zero changes to core code.

---

## What it does

- **Universe selection** — auto-filters pairs by 24h turnover, open interest
  and spread; refreshes hourly.
- **Multi-timeframe analysis** — 4H global trend, 1H main analysis,
  15M entry, 5M confirmation.
- **Confluence scoring** — EMA 50/100/200, RSI (Wilder), MACD, ATR, volume
  spikes, market structure (HH/HL, LH/LL), funding rate, open interest delta.
  Each factor adds or subtracts points; a signal is published only above a
  configurable quality threshold.
- **Market regime filter** — trend / flat / high-volatility detection; no
  signals in flat markets, no chasing after extended moves (anti-FOMO veto).
- **Signal lifecycle management** — statuses Active → TP1 → TP2 → TP3 / SL /
  Breakeven / Cancelled; stop moved to breakeven after TP1; Telegram message
  edited in place on every status change; per-symbol cooldown.
- **Wick-accurate tracking** — triggers computed from 1-minute candle
  highs/lows, not from a single last price; stop is checked first
  (conservative), identical to the backtest rules.
- **Backtesting engine** — replays the *same strategy code* over 12 months of
  history, with taker fees + slippage deducted per trade, proper EMA200
  warm-up on every timeframe, and no overlapping trades. Outputs Win Rate,
  Profit Factor, Max Drawdown (R), avg RR, long/short breakdown.
- **Paper-trading stats** — `python -m monitoring.stats` aggregates the live
  signal history into the same report format as the backtest.
- **Monitoring** — admin alerts on Bybit API loss, Telegram errors and loop
  failures (throttled); rotating logs; rejection journal with reasons.

## Sample signal

```
🟩 LONG — SOLUSDT

Entry: 166.7600
Stop Loss: 165.0610
TP1: 169.3100
TP2: 171.0090
TP3: 173.5580

Risk/Reward (TP2): 1:2.5
Signal strength: 8/10

Reasons:
  • Global LONG trend: price above EMA200, EMA50 > EMA100 (4H)
  • Pullback to EMA50 zone (1H)
  • RSI(1H) 54 — reset after pullback
  • 5M momentum in trade direction
  • Elevated volume (15M)
  • Funding in favor (-0.08%)
  • Open Interest +3.2% in 4h
```

## Architecture

```
core/        models, config loader, strategy registry (plugins via YAML)
data/        Bybit v5 public API client, multi-TF market snapshots
indicators/  EMA, RSI (Wilder), MACD, ATR (Wilder) — pandas/numpy, no TA-Lib
analysis/    market regime (trend/flat/vol), structure (swings, HH/HL)
strategies/  BaseStrategy + trend_pullback; add a file = add a strategy
filters/     liquidity filter (turnover, OI, spread)
scoring/     factor summation, min_score / min_RR gates
signals/     lifecycle manager (statuses, breakeven, cooldown), formatter
tg/          Telegram Bot API (send / edit-in-place / admin alerts)
monitoring/  rotating logs, rejection journal, alert throttling, stats CLI
backtest/    historical replay of the exact live strategy code
tests/       15 unit tests: indicators, scoring, structure, lifecycle
```

Every parameter — coin filters, timeframes, indicator periods, factor
weights, score threshold, long/short toggles — lives in `config/config.yaml`.

## Quick start

```bash
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp config/.env.example config/.env    # bot token, channel id, admin id
pytest tests/ -q                      # 15 tests
python -m backtest.engine --symbols BTCUSDT ETHUSDT --months 12
python scripts/demo_signal.py         # sends a demo signal to your channel
python main.py                        # live scanning
```

## Design decisions worth noting

- **Live and backtest share one strategy codebase** — what you test is what
  runs. Divergent logic between backtest and production is the #1 source of
  fake edge in retail bots.
- **Conservative fills** — if a candle touches both stop and target, the stop
  is counted. Fees and slippage are subtracted from every backtested trade.
- **Honest limitations are documented** — funding/OI history is not available
  in the backtest (making it *more* conservative than live), and entries are
  simulated at 15M closes.

## Backtest results

See [BACKTEST.md](BACKTEST.md) — 627 trades over 12 months with real
fees, slippage and conservative fills, including an honest "no edge"
verdict for the reference strategy. This backtester is built to tell
the truth, not to draw pretty equity curves.

## Stack

Python 3.10+, pandas, numpy, requests, PyYAML, pytest. No paid APIs, no
TA-Lib build headaches — indicators are implemented directly and unit-tested.

## Disclaimer

This is an analytical tool, not financial advice. Signal quality depends
entirely on the configured strategy; validate with the included backtester
and paper trading before relying on any output.

---

*Built by a Python developer specializing in crypto exchange automation:
Bybit/Binance bots, Telegram integrations, backtesting frameworks.
Available for freelance work — see profile for contact.*

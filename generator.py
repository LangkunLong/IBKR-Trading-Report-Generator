import requests
import pandas as pd
import yaml
from datetime import datetime, timedelta
import os

MAX_SIZE_PER_TRADE = 1000

with open("config.yaml", "r") as f:
    cfg = yaml.safe_load(f)

requests.packages.urllib3.disable_warnings()

# Fetch Net Liquidation Value from account summary
def get_net_liq():
    url = f"{BASE_URL}/v1/api/iserver/account/accounts"
    resp = requests.get(url, verify=False)
    resp.raise_for_status()
    data = resp.json()
    for item in data:
        if item.get("tag") == "NetLiquidation":
            return float(item.get("value", 0))
    return 1.0

# Get transactions from past 7 days
def get_transactions(period = 7):
    end_date = datetime.today()
    start_date = end_date - timedelta(days=period)
    params = {
        "start": start_date.strftime("%Y%m%d"),
        "end": end_date.strftime("%Y%m%d")
    }
    url = f"{BASE_URL}/v1/api/iserver/account/transactions"
    resp = requests.get(url, params=params, verify=False)
    resp.raise_for_status()
    return resp.json()

# Convert IBKR transactions into report format
def build_trade_log(transactions, net_liq):
    trades = []
    for tx in transactions:
        try:
            # Basic fields
            symbol = tx.get("symbol")
            open_ts = tx.get("tradeDate")
            close_ts = tx.get("settleDate")
            qty = abs(float(tx.get("quantity", 0)))
            price = float(tx.get("tradePrice", 0))
            multiplier = float(tx.get("multiplier", 1))  # for options, default 1

            # Dates
            open_date = datetime.strptime(open_ts, "%Y%m%d") if open_ts else None
            close_date = datetime.strptime(close_ts, "%Y%m%d") if close_ts else None
            duration = (close_date - open_date).days if open_date and close_date else 0

            # Sizing and PnL
            sizing = qty * price * multiplier
            outcome = float(tx.get("proceeds", 0))  # realized PnL
            per_trade_pct = (outcome / sizing * 100) if sizing > 0 else 0
            net_trade_pct = (outcome / MAX_SIZE_PER_TRADE * 100)
            net_pct = (outcome / net_liq * 100) if net_liq > 0 else 0

            trades.append({
                "TRADE": symbol,
                "DATE (OPEN)": open_date.strftime("%Y-%m-%d") if open_date else "",
                "DATE (CLOSE)": close_date.strftime("%Y-%m-%d") if close_date else "",
                "DURATION": duration,
                "ENTRY": "",
                "STOP": "",
                "TARGET": "",
                "Sizing": round(sizing, 2),
                "OUTCOME": round(outcome, 2),
                "Per Trade % Gain/Loss": round(per_trade_pct, 2),
                "Net Trade % Gain/Loss": round(net_trade_pct, 2),
                "Account % Gain/Loss": round(net_pct, 4),
                "TAKEAWAYS": "",
                "Would I take this trade again?": "",
                "Verdict": "",
                "Reasoning": "",
                "Psychology": ""
            })
        except Exception as e:
            print(f"⚠️ Skipping transaction due to error: {e}")
    return trades

ACCOUNT_ID = cfg["account_id"]
OUTPUT_FILE = cfg.get("output_file", "ibkr_trade_log.csv")
BASE_URL = f"https://localhost:5000"


if __name__ == "__main__":
    print(f"🔍 Using IBKR Gateway at port 5000")
    net_liq = get_net_liq()
    transactions = get_transactions()
    trades = build_trade_log(transactions, net_liq)

    df = pd.DataFrame(trades)
    df.to_csv("ibkr_trade_log.csv", index=False)
    print("Trade log exported to ibkr_trade_log.csv")
    #print(df.head())

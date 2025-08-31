import requests
import pandas as pd
from datetime import datetime

# Fetch Net Liquidation Value from account summary
def get_net_liq():
    url = f"{BASE_URL}/portfolio/{ACCOUNT_ID}/summary"
    resp = requests.get(url, verify=False)
    resp.raise_for_status()
    data = resp.json()
    for item in data:
        if item.get("tag") == "NetLiquidation":
            return float(item.get("value", 0))
    return 1.0

# Get trades 
def get_transactions():
    url = f"{BASE_URL}/portfolio/{ACCOUNT_ID}/transactions"
    resp = requests.get(url, verify=False)
    resp.raise_for_status()
    return resp.json()

# Convert IBKR transactions into report format
def build_trade_log(transactions, net_liq):
    trades = []
    for tx in transactions:
        try:
            symbol = tx.get("symbol")
            open_ts = tx.get("tradeDate")
            close_ts = tx.get("settleDate")

            open_date = datetime.strptime(open_ts, "%Y%m%d") if open_ts else None
            close_date = datetime.strptime(close_ts, "%Y%m%d") if close_ts else None
            duration = (close_date - open_date).days if open_date and close_date else 0

            qty = abs(float(tx.get("quantity", 0)))
            price = float(tx.get("tradePrice", 0))
            sizing = qty * price

            outcome = float(tx.get("proceeds", 0))  # IBKR reports realized PnL as "proceeds"
            per_trade_pct = (outcome / sizing * 100) if sizing > 0 else 0
            net_pct = (outcome / net_liq * 100) if net_liq > 0 else 0

            trades.append({
                "TRADE": symbol,
                "DATE (OPEN)": open_date.strftime("%Y-%m-%d") if open_date else "",
                "TIME (CLOSE)": close_date.strftime("%Y-%m-%d") if close_date else "",
                "DURATION": duration,
                "ENTRY": "",
                "STOP": "",
                "TARGET": "",
                "Sizing": round(sizing, 2),
                "OUTCOME": round(outcome, 2),
                "Per Trade % Gain/Loss": round(per_trade_pct, 2),
                "Net % Gain/Loss": round(net_pct, 4),
                "TAKEAWAYS": "",
                "Would I take this trade again?": "",
                "Verdict": "",
                "Reasoning": "",
                "Psychology": ""
            })
        except Exception as e:
            print(f"⚠️ Skipping transaction due to error: {e}")
    return trades

if __name__ == "__main__":
    print(f"🔍 Using IBKR Gateway at port {PORT}")
    net_liq = get_net_liq()
    transactions = get_transactions()
    trades = build_trade_log(transactions, net_liq)

    df = pd.DataFrame(trades)
    df.to_csv("ibkr_trade_log.csv", index=False)
    print("✅ Trade log exported to ibkr_trade_log.csv")
    #print(df.head())

import requests
import pandas as pd
from datetime import datetime

# Example: Replace with your IBKR gateway URL
BASE_URL = "https://localhost:5000/v1/api"
ACCOUNT_ID = "your_account_id"

# 1. Get Net Liquidation Value
summary = requests.get(f"{BASE_URL}/portfolio/{ACCOUNT_ID}/summary", verify=False).json()
net_liq = float(summary.get("netLiquidation", 1))

# 2. Get Transaction History
transactions = requests.get(f"{BASE_URL}/portfolio/{ACCOUNT_ID}/transactions", verify=False).json()

trades = []
for tx in transactions:
    # Basic info
    symbol = tx.get("symbol")
    open_date = datetime.fromtimestamp(tx.get("openDate")/1000).strftime("%Y-%m-%d")
    close_date = datetime.fromtimestamp(tx.get("closeDate")/1000).strftime("%Y-%m-%d")
    
    duration = (datetime.fromtimestamp(tx.get("closeDate")/1000) - 
                datetime.fromtimestamp(tx.get("openDate")/1000)).days
    
    qty = abs(float(tx.get("quantity", 0)))
    entry_price = float(tx.get("price", 0))
    sizing = qty * entry_price
    
    outcome = float(tx.get("realizedPNL", 0))
    per_trade_pct = (outcome / sizing * 100) if sizing > 0 else 0
    net_pct = (outcome / net_liq * 100) if net_liq > 0 else 0

    trades.append({
        "TRADE": symbol,
        "DATE (OPEN)": open_date,
        "TIME (CLOSE)": close_date,
        "DURATION": duration,
        "ENTRY": "",
        "STOP": "",
        "TARGET": "",
        "Sizing": sizing,
        "OUTCOME": outcome,
        "Per Trade % Gain/Loss": per_trade_pct,
        "Net % Gain/Loss": net_pct,
        "TAKEAWAYS": "",
        "Would I take this trade again?": "",
        "Verdict": "",
        "Reasoning": "",
        "Psychology": ""
    })

# 3. Save to CSV
df = pd.DataFrame(trades)
df.to_csv("trade_log.csv", index=False)
print("Trade log exported to trade_log.csv")

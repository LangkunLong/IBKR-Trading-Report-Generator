import pandas as pd
from datetime import datetime, timedelta

# Mock transaction data (simulating what IBKR API would return)
mock_transactions = [
    {
        "symbol": "AAPL",
        "openDate": datetime(2025, 8, 1, 9, 30).timestamp() * 1000,
        "closeDate": datetime(2025, 8, 5, 15, 59).timestamp() * 1000,
        "quantity": 100,
        "price": 190.0,
        "realizedPNL": 500.0
    },
    {
        "symbol": "TSLA",
        "openDate": datetime(2025, 8, 2, 10, 0).timestamp() * 1000,
        "closeDate": datetime(2025, 8, 3, 15, 59).timestamp() * 1000,
        "quantity": 50,
        "price": 250.0,
        "realizedPNL": -300.0
    },
    {
        "symbol": "MSFT",
        "openDate": datetime(2025, 8, 10, 9, 30).timestamp() * 1000,
        "closeDate": datetime(2025, 8, 15, 16, 0).timestamp() * 1000,
        "quantity": 200,
        "price": 320.0,
        "realizedPNL": 1000.0
    }
]

# Mock Net Liquidation Value (account size)
net_liq = 100000.0

trades = []
for tx in mock_transactions:
    symbol = tx["symbol"]
    open_date = datetime.fromtimestamp(tx["openDate"] / 1000)
    close_date = datetime.fromtimestamp(tx["closeDate"] / 1000)
    duration = (close_date - open_date).days

    qty = abs(float(tx["quantity"]))
    entry_price = float(tx["price"])
    sizing = qty * entry_price

    outcome = float(tx["realizedPNL"])
    per_trade_pct = (outcome / sizing * 100) if sizing > 0 else 0
    net_pct = (outcome / net_liq * 100) if net_liq > 0 else 0

    trades.append({
        "TRADE": symbol,
        "DATE (OPEN)": open_date.strftime("%Y-%m-%d"),
        "TIME (CLOSE)": close_date.strftime("%Y-%m-%d"),
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

# Create DataFrame & export to CSV
df = pd.DataFrame(trades)
df.to_csv("mock_trade_log.csv", index=False)

print("✅ Mock trade log exported to mock_trade_log.csv")
print(df)

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
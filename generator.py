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
    url = f"{BASE_URL}/v1/api/iserver/account/{ACCOUNT_ID}/summary"
    resp = requests.get(url, verify=False)
    resp.raise_for_status()
    data = resp.json()
    #print(data)
    return data["netLiquidationValue"]

# Get completed trades/executions from the past period
def get_trades_and_orders(period=7):
    trades = []
    
    try:
        url = f"{BASE_URL}/v1/api/iserver/account/trades"
        params = {
            "days": period,  
            "accountId": ACCOUNT_ID   
        }
        
        print(f"📡 Fetching trades for last {params['days']} days for account {ACCOUNT_ID}")
        resp = requests.get(url, params=params, verify=False, timeout=15)
        resp.raise_for_status()
        data = resp.json()
        print(data)
        trades.extend(data)
        #print(f"✅ Got {len(trades)} recent trades")
    except Exception as e:
        print(f"⚠️ Could not get recent trades: {e}")
    
    return trades

#Get current positions to help match closing trades
def get_positions():
    try:
        url = f"{BASE_URL}/v1/api/iserver/account/{ACCOUNT_ID}/positions/0"
        resp = requests.get(url, verify=False, timeout=10)
        resp.raise_for_status()
        return resp.json()
    except Exception as e:
        print(f"⚠️ Could not get positions: {e}")
        return []

# name is different for option / stocks
def parse_instrument_name(trade):

    symbol = trade.get('symbol') or trade.get('ticker') or str(trade.get('conid', 'Unknown'))
    sec_type = trade.get('secType', '')
    
    # Options: Get strike, expiry, and call/put
    if sec_type == 'OPT':
        strike = trade.get('strike', '')
        expiry = trade.get('lastTradingDay', trade.get('expiry', ''))
        right = trade.get('right', '')  # C or P
        
        if expiry and len(str(expiry)) == 8:
            try:
                expiry_date = datetime.strptime(str(expiry), "%Y%m%d")
                expiry = expiry_date.strftime("%m/%d/%Y")
            except:
                pass
        
        return f"{symbol} {expiry} ${strike}{right}"
    
    elif sec_type == 'STK':
        # Stocks: Just return the symbol
        return symbol

# Calculate all the metrics for both stock and options trades
def calculate_trade_metrics(trade, net_liq):
    try:
        quantity = abs(float(trade.get('quantity', trade.get('filledQuantity', 0))))
        price = float(trade.get('price', trade.get('avgPrice', trade.get('lastPrice', 0))))
        sec_type = trade.get('secType', '')
        
        # Set multiplier based on security type
        if sec_type == 'OPT':
            multiplier = 100 
        else:
            multiplier = float(trade.get('multiplier', 1))
        
        # Position sizing in dollars
        sizing = quantity * price * multiplier
        
        # Try to get realized PnL (for closed positions)
        outcome = 0
        pnl_fields = ['realizedPnl', 'pnl', 'unrealizedPnl', 'rpnl', 'upnl']
        for field in pnl_fields:
            if field in trade and trade[field] is not None:
                outcome = float(trade[field])
                break
        
        # For stocks, if we have buy/sell info, calculate P&L differently
        side = trade.get('side', '').upper()
        if outcome == 0 and side:
            # This might be a single leg, need to match with opposite side
            # For now, just use the trade value as sizing
            pass
        
        # Calculate percentages
        per_trade_pct = (outcome / sizing * 100) if sizing > 0 else 0
        net_trade_pct = (outcome / MAX_SIZE_PER_TRADE * 100)
        account_pct = (outcome / net_liq * 100) if net_liq > 0 else 0
        
        return {
            'sizing': round(sizing, 2),
            'outcome': round(outcome, 2),
            'per_trade_pct': round(per_trade_pct, 2),
            'net_trade_pct': round(net_trade_pct, 2),
            'account_pct': round(account_pct, 4),
            'sec_type': sec_type,
            'quantity': quantity,
            'price': price,
            'multiplier': multiplier
        }
        
    except Exception as e:
        print(f"⚠️ Error calculating metrics: {e}")
        return {
            'sizing': 0,
            'outcome': 0,
            'per_trade_pct': 0,
            'net_trade_pct': 0,
            'account_pct': 0,
            'sec_type': '',
            'quantity': 0,
            'price': 0,
            'multiplier': 1
        }

# Convert IBKR transactions into report format
def build_trade_log(transactions, net_liq):
    trade_log = []
    
    for trade in trades:
        try:
            instrument = parse_instrument_name(trade)
            open_date = None
            close_date = None
            
            for date_field in ['tradeTime', 'lastTradeDate', 'orderTime', 'time']:
                if date_field in trade and trade[date_field]:
                    try:
                        date_str = str(trade[date_field])
                        if len(date_str) == 8:  # YYYYMMDD
                            date_obj = datetime.strptime(date_str, "%Y%m%d")
                        elif 'T' in date_str:  # ISO format
                            date_obj = datetime.fromisoformat(date_str.replace('Z', '+00:00'))
                        else:
                            date_obj = datetime.fromtimestamp(int(date_str) / 1000)
                        
                        if not open_date:
                            open_date = date_obj
                        else:
                            close_date = date_obj
                        break
                    except:
                        continue
            
            if open_date and not close_date:
                close_date = open_date
            elif not open_date:
                open_date = close_date = datetime.now()
            
            duration = (close_date - open_date).days if open_date and close_date else 0
            metrics = calculate_trade_metrics(trade, net_liq)
            trade_record = {
                "TRADE": instrument,
                "DATE (OPEN)": open_date.strftime("%Y-%m-%d") if open_date else "",
                "DATE (CLOSE)": close_date.strftime("%Y-%m-%d") if close_date else "",
                "DURATION": duration,
                "Security Type": metrics['sec_type'],  # Added for tracking
                "Quantity": metrics['quantity'],       # Added for reference
                "Price": metrics['price'],             # Added for reference
                "ENTRY": "", 
                "STOP": "",   
                "TARGET": "", 
                "Sizing": metrics['sizing'],
                "OUTCOME": metrics['outcome'],
                "Per Trade % Gain/Loss": metrics['per_trade_pct'],
                "Net Trade % Gain/Loss": metrics['net_trade_pct'],
                "Account % Gain/Loss": metrics['account_pct'],
                "TAKEAWAYS": "",  
                "Would I take this trade again?": "",  
                "Verdict": "",    
                "Reasoning": "",  
                "Psychology": ""  
            }
            
            trade_log.append(trade_record)
            
        except Exception as e:
            print(f"⚠️ Skipping trade due to error: {e}")
            print(f"Trade data: {trade}")
    
    return trade_log

ACCOUNT_ID = cfg["account_id"]
OUTPUT_FILE = cfg.get("output_file", "ibkr_trade_log.csv")
BASE_URL = f"https://localhost:5000"


if __name__ == "__main__":
    print(f"🔍 Using IBKR Gateway at port 5000")
    print("📊 Getting account net liquidation value...")
    net_liq = get_net_liq()
    print(f"Net Liquidation: ${net_liq:,.2f}")
    
    print("📈 Getting trades and executions...")
    trades = get_trades_and_orders()
    print(f"🔄 Processing {len(trades)} trades...")
    trade_log = build_trade_log(trades, net_liq)

    df = pd.DataFrame(trade_log)
    df.to_csv("ibkr_trade_log.csv", index=False)
    print("Trade log exported to ibkr_trade_log.csv")

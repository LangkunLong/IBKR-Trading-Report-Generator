import requests
import pandas as pd
import yaml
from datetime import datetime, timedelta
import os
import time

MAX_SIZE_PER_TRADE = 1000

with open("config.yaml", "r") as f:
    cfg = yaml.safe_load(f)

requests.packages.urllib3.disable_warnings()

BASE_URL = "https://localhost:5000"
ACCOUNT_ID = cfg["account_id"]
OUTPUT_FILE = cfg.get("output_file", "ibkr_trade_log.xlsx")


"""Fetch Net Liquidation Value from account summary"""
def get_net_liq():
    url = f"{BASE_URL}/v1/api/iserver/account/{ACCOUNT_ID}/summary"
    resp = requests.get(url, verify=False, timeout=10)
    resp.raise_for_status()
    data = resp.json()
    return data["netLiquidationValue"]

"""Get completed trades/executions from the past period using correct IBKR endpoint"""
def get_trades_and_orders(period=7):
    trades = []
    
    try:
        url = f"{BASE_URL}/v1/api/iserver/account/trades"
        params = {
            "days": 7,  
            "accountId": ACCOUNT_ID   
        }
        
        print(f"📡 Fetching trades for last {params['days']} days for account {ACCOUNT_ID}")
        resp = requests.get(url, params=params, verify=False, timeout=15)
        resp.raise_for_status()
        
        data = resp.json()
        
        # Handle different response formats
        if isinstance(data, list):
            trades = data
        elif isinstance(data, dict):
            # Sometimes the response is wrapped in an object
            trades = data.get('trades', data.get('executions', [data] if data else []))
        
        print(f"✅ Successfully retrieved {len(trades)} trades")
        
        # # Debug: Show structure of first trade if available
        # if trades and len(trades) > 0:
        #     print(f"📋 Sample trade structure: {list(trades[0].keys())}")
        
        return trades
        
    except Exception as e:
        print(f"❌ Error fetching trades: {e}")
        print(f"   URL: {url}")
        print(f"   Params: {params}")
        
        # Fallback: try without account filter
        try:
            print("🔄 Trying without account filter...")
            params_fallback = {"days": min(period, 7)}
            resp = requests.get(url, params=params_fallback, verify=False, timeout=15)
            resp.raise_for_status()
            data = resp.json()
            
            if isinstance(data, list):
                trades = data
            elif isinstance(data, dict):
                trades = data.get('trades', data.get('executions', []))
            
            print(f"✅ Fallback successful: {len(trades)} trades")
            return trades
            
        except Exception as fallback_error:
            print(f"❌ Fallback also failed: {fallback_error}")
            return []

def match_buy_sell_pairs(trades):
    """Match buy/sell executions to create complete round-trip trades with P&L"""
    from collections import defaultdict
    import copy
    
    # Group trades by instrument
    trades_by_instrument = defaultdict(list)
    
    for trade in trades:
        instrument = parse_instrument_name(trade)
        trades_by_instrument[instrument].append(trade)
    
    matched_trades = []
    unmatched_executions = []
    
    #print(f"🔄 Matching buy/sell pairs across {len(trades_by_instrument)} instruments...")
    
    for instrument, instrument_trades in trades_by_instrument.items():
        # Sort by trade time to match chronologically
        instrument_trades.sort(key=lambda x: x.get('trade_time', ''))
        
        # Separate buys and sells
        buys = [t for t in instrument_trades if t.get('side') == 'B']
        sells = [t for t in instrument_trades if t.get('side') == 'S']
        
        #print(f"📊 {instrument}: {len(buys)} buys, {len(sells)} sells")
        
        # Match trades using FIFO (First In, First Out)
        buy_queue = copy.deepcopy(buys)
        sell_queue = copy.deepcopy(sells)
        
        while buy_queue and sell_queue:
            buy_trade = buy_queue.pop(0)
            sell_trade = sell_queue.pop(0)
            
            buy_qty = float(buy_trade.get('size', 0))
            sell_qty = float(sell_trade.get('size', 0))
            
            # Match the smaller quantity
            matched_qty = min(buy_qty, sell_qty)
            
            if matched_qty > 0:
                matched_trade = create_matched_trade(buy_trade, sell_trade, matched_qty)
                matched_trades.append(matched_trade)
                
                #print(f"✅ Matched {instrument}: {matched_qty} units - Buy @${float(buy_trade.get('price', 0)):.2f} → Sell @${float(sell_trade.get('price', 0)):.2f}")
                
                # Handle partial fills
                if buy_qty > matched_qty:
                    # Partial buy remains
                    remaining_buy = copy.deepcopy(buy_trade)
                    remaining_buy['size'] = buy_qty - matched_qty
                    remaining_buy['net_amount'] = float(remaining_buy['net_amount']) * (remaining_buy['size'] / buy_qty)
                    buy_queue.insert(0, remaining_buy)
                
                if sell_qty > matched_qty:
                    # Partial sell remains
                    remaining_sell = copy.deepcopy(sell_trade)
                    remaining_sell['size'] = sell_qty - matched_qty
                    remaining_sell['net_amount'] = float(remaining_sell['net_amount']) * (remaining_sell['size'] / sell_qty)
                    sell_queue.insert(0, remaining_sell)
        
        # Add unmatched trades to the unmatched list
        unmatched_executions.extend(buy_queue + sell_queue)
    
    # print(f"✅ Created {len(matched_trades)} complete round-trip trades")
    # print(f"⚠️ {len(unmatched_executions)} unmatched executions (open positions)")
    
    return matched_trades, unmatched_executions

def create_matched_trade(buy_trade, sell_trade, quantity):
    """Create a complete trade record from matched buy/sell executions"""
    try:
        # Basic info
        instrument = parse_instrument_name(buy_trade)
        sec_type = buy_trade.get('sec_type', '')
        
        # Trade details
        buy_price = float(buy_trade.get('price', 0))
        sell_price = float(sell_trade.get('price', 0))
        buy_commission = float(buy_trade.get('commission', 0))
        sell_commission = float(sell_trade.get('commission', 0))
        total_commission = buy_commission + sell_commission
        
        # Dates
        buy_time = buy_trade.get('trade_time', '')
        sell_time = sell_trade.get('trade_time', '')
        
        buy_date = datetime.strptime(buy_time, "%Y%m%d-%H:%M:%S") if buy_time else datetime.now()
        sell_date = datetime.strptime(sell_time, "%Y%m%d-%H:%M:%S") if sell_time else datetime.now()
        
        duration = (sell_date - buy_date).days
        
        # Calculate P&L
        multiplier = 100 if sec_type == 'OPT' else 1
        
        # Position sizing (cost basis)
        sizing = quantity * buy_price * multiplier
        
        # Gross P&L (before commission)
        gross_pnl = (sell_price - buy_price) * quantity * multiplier
        
        # Net P&L (after commission)
        net_pnl = gross_pnl - total_commission
        
        # Calculate percentages
        per_trade_pct = (net_pnl / sizing * 100) if sizing > 0 else 0
        net_trade_pct = (net_pnl / MAX_SIZE_PER_TRADE * 100)
        
        return {
            'instrument': instrument,
            'buy_date': buy_date,
            'sell_date': sell_date,
            'duration': duration,
            'sec_type': sec_type,
            'quantity': quantity,
            'buy_price': buy_price,
            'sell_price': sell_price,
            'sizing': sizing,
            'gross_pnl': gross_pnl,
            'net_pnl': net_pnl,
            'total_commission': total_commission,
            'per_trade_pct': per_trade_pct,
            'net_trade_pct': net_trade_pct,
            'buy_trade': buy_trade,
            'sell_trade': sell_trade
        }
        
    except Exception as e:
        print(f"❌ Error creating matched trade: {e}")
        return None

def parse_instrument_name(trade):
    """Extract clean instrument name from IBKR trade data for both stocks and options"""
    symbol = trade.get('symbol', 'Unknown')
    sec_type = trade.get('sec_type', '')
    
    if sec_type == 'OPT':
        # Options: Get info from contract_description_2
        contract_desc = trade.get('contract_description_2', '')
        put_or_call = trade.get('put_or_call', '')
        
        if contract_desc:
            # Format: "Sep19 '25 95 Call" -> "EBAY Sep19 '25 $95C"
            parts = contract_desc.split()
            if len(parts) >= 3:
                expiry = f"{parts[0]} {parts[1]}"  # "Sep19 '25"
                strike = parts[2]  # "95"
                option_type = put_or_call  # "C" or "P"
                return f"{symbol} {expiry} ${strike}{option_type}"
        
        # Fallback for options without proper description
        return f"{symbol} Option ({put_or_call})"
    
    elif sec_type == 'STK':
        # Stocks: Just return the symbol
        return symbol
    
    else:
        # Other securities
        return f"{symbol} ({sec_type})"

def calculate_trade_metrics(trade, net_liq):
    """Calculate all the metrics for both stock and options trades using IBKR data format"""
    try:
        # Get basic trade info from IBKR format
        size = float(trade.get('size', 0))  # quantity
        price = float(trade.get('price', 0))  # execution price
        sec_type = trade.get('sec_type', '')
        side = trade.get('side', '')  # 'B' for Buy, 'S' for Sell
        commission = float(trade.get('commission', 0))
        net_amount = float(trade.get('net_amount', 0))  # This includes commission
        
        # Set multiplier based on security type
        if sec_type == 'OPT':
            multiplier = 100  # Options contracts represent 100 shares
        else:
            multiplier = 1  # Stocks are 1:1
        
        # Position sizing in dollars (absolute value of the trade)
        sizing = size * price * multiplier
        
        # For individual executions, we can't easily calculate P&L since we need both buy and sell
        # However, we can show the trade value and let user calculate P&L manually when matching trades
        
        # The net_amount already includes commission, so the trade cost/proceeds is:
        trade_value = net_amount if side == 'S' else -net_amount  # Positive for sells, negative for buys
        
        # For now, set outcome to 0 since individual executions don't show P&L
        # User will need to match buy/sell pairs manually or we'd need additional logic
        outcome = 0
        
        # Calculate percentages (will be 0 for individual executions)
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
            'quantity': size,
            'price': price,
            'multiplier': multiplier,
            'side': side,
            'commission': commission,
            'net_amount': net_amount,
            'trade_value': trade_value
        }
        
    except Exception as e:
        print(f"⚠️ Error calculating metrics for trade: {e}")
        return {
            'sizing': 0,
            'outcome': 0,
            'per_trade_pct': 0,
            'net_trade_pct': 0,
            'account_pct': 0,
            'sec_type': '',
            'quantity': 0,
            'price': 0,
            'multiplier': 1,
            'side': '',
            'commission': 0,
            'net_amount': 0,
            'trade_value': 0
        }

def build_trade_log_from_matched(matched_trades, net_liq):
    """Convert matched trades into the final report format"""
    trade_log = []
    
    for matched_trade in matched_trades:
        if not matched_trade:
            continue
            
        try:
            # Calculate account percentage
            account_pct = (matched_trade['net_pnl'] / net_liq * 100) if net_liq > 0 else 0
            
            trade_record = {
                "TRADE": matched_trade['instrument'],
                "DATE (OPEN)": matched_trade['buy_date'].strftime("%Y-%m-%d %H:%M:%S"),
                "DATE (CLOSE)": matched_trade['sell_date'].strftime("%Y-%m-%d %H:%M:%S"),
                "DURATION": matched_trade['duration'],
                "Security Type": matched_trade['sec_type'],
                "Quantity": matched_trade['quantity'],
                "Buy Price": f"${matched_trade['buy_price']:.2f}",
                "Sell Price": f"${matched_trade['sell_price']:.2f}",
                "Commission": f"${matched_trade['total_commission']:.2f}",
                "ENTRY": "",  # To be filled manually
                "STOP": "",   # To be filled manually
                "TARGET": "", # To be filled manually
                "Sizing": round(matched_trade['sizing'], 2),
                "Gross P&L": round(matched_trade['gross_pnl'], 2),
                "OUTCOME": round(matched_trade['net_pnl'], 2),  # Net P&L after commission
                "Per Trade % Gain/Loss": round(matched_trade['per_trade_pct'], 2),
                "Net Trade % Gain/Loss": round(matched_trade['net_trade_pct'], 2),
                "Account % Gain/Loss": round(account_pct, 4),
                "TAKEAWAYS": "",  # To be filled manually
                "Would I take this trade again?": "",  # To be filled manually
                "Verdict": "",    # To be filled manually
                "Reasoning": "",  # To be filled manually
                "Psychology": ""  # To be filled manually
            }
            
            trade_log.append(trade_record)
            
        except Exception as e:
            print(f"⚠️ Error building trade record: {e}")
    
    return trade_log

def build_unmatched_executions_log(unmatched_executions):
    """Create a log of unmatched executions (open positions)"""
    execution_log = []
    
    for trade in unmatched_executions:
        try:
            instrument = parse_instrument_name(trade)
            trade_time = trade.get('trade_time', '')
            trade_date = datetime.strptime(trade_time, "%Y%m%d-%H:%M:%S") if trade_time else datetime.now()
            
            sec_type = trade.get('sec_type', '')
            quantity = float(trade.get('size', 0))
            price = float(trade.get('price', 0))
            side = trade.get('side', '')
            commission = float(trade.get('commission', 0))
            net_amount = float(trade.get('net_amount', 0))
            
            multiplier = 100 if sec_type == 'OPT' else 1
            sizing = quantity * price * multiplier
            
            execution_record = {
                "TRADE": instrument,
                "DATE": trade_date.strftime("%Y-%m-%d %H:%M:%S"),
                "Security Type": sec_type,
                "Side": side,
                "Quantity": quantity,
                "Price": f"${price:.2f}",
                "Sizing": round(sizing, 2),
                "Commission": f"${commission:.2f}",
                "Net Amount": f"${net_amount:.2f}",
                "Status": "OPEN POSITION"
            }
            
            execution_log.append(execution_record)
            
        except Exception as e:
            print(f"⚠️ Error processing unmatched execution: {e}")
    
    return execution_log

"""Consolidate trades in the final report by ticker, summing metrics"""
def consolidate_final_trades(trade_log):
    if not trade_log:
        return []

    df = pd.DataFrame(trade_log)
    
    # Check if there are multiple trades for the same instrument
    duplicates = df[df.duplicated(subset=['TRADE'], keep=False)]
    if duplicates.empty:
        return trade_log

    # Group by the TRADE column and aggregate metrics
    consolidated_df = df.groupby('TRADE').agg(
        **{
            'DATE (OPEN)': ('DATE (OPEN)', 'first'),  # Keep first open date
            'DATE (CLOSE)': ('DATE (CLOSE)', 'last'),   # Keep last close date
            'DURATION': ('DURATION', 'sum'),        # Sum durations
            'Security Type': ('Security Type', 'first'), # Keep first security type
            'Quantity': ('Quantity', 'sum'),        # Sum quantities
            'Buy Price': ('Buy Price', lambda x: f"${(pd.to_numeric(x.str.replace('$', '', regex=False)) * df.loc[x.index, 'Quantity']).sum() / df.loc[x.index, 'Quantity'].sum():.2f}"), # Weighted average buy price
            'Sell Price': ('Sell Price', lambda x: f"${(pd.to_numeric(x.str.replace('$', '', regex=False)) * df.loc[x.index, 'Quantity']).sum() / df.loc[x.index, 'Quantity'].sum():.2f}"), # Weighted average sell price
            'Commission': ('Commission', lambda x: f"${pd.to_numeric(x.str.replace('$', '', regex=False)).sum():.2f}"), # Sum commission
            'Sizing': ('Sizing', 'sum'),
            'Gross P&L': ('Gross P&L', 'sum'),
            'OUTCOME': ('OUTCOME', 'sum'),
            'Per Trade % Gain/Loss': ('Per Trade % Gain/Loss', 'mean'), 
            'Net Trade % Gain/Loss': ('Net Trade % Gain/Loss', 'sum'),
            'Account % Gain/Loss': ('Account % Gain/Loss', 'sum'),
            'TAKEAWAYS': ('TAKEAWAYS', lambda x: '; '.join(x.dropna())),
            'Would I take this trade again?': ('Would I take this trade again?', lambda x: '; '.join(x.dropna())),
            'Verdict': ('Verdict', lambda x: '; '.join(x.dropna())),
            'Reasoning': ('Reasoning', lambda x: '; '.join(x.dropna())),
            'Psychology': ('Psychology', lambda x: '; '.join(x.dropna()))
        }
    ).reset_index()

    return consolidated_df.to_dict('records')


def consolidate_open_positions(unmatched_log):
    """Consolidate open positions by ticker, summing metrics"""
    if not unmatched_log:
        return []

    df = pd.DataFrame(unmatched_log)
    
    # Check if there are multiple trades for the same instrument
    duplicates = df[df.duplicated(subset=['TRADE'], keep=False)]
    if duplicates.empty:
        return unmatched_log

    # Group by the TRADE column and aggregate metrics
    consolidated_df = df.groupby('TRADE').agg(
        **{
            'DATE': ('DATE', 'first'),  # Keep first open date
            'Security Type': ('Security Type', 'first'),
            'Side': ('Side', lambda x: '; '.join(x.dropna())),
            'Quantity': ('Quantity', 'sum'),
            'Price': ('Price', lambda x: f"${(pd.to_numeric(x.str.replace('$', '', regex=False)) * df.loc[x.index, 'Quantity']).sum() / df.loc[x.index, 'Quantity'].sum():.2f}"),
            'Sizing': ('Sizing', 'sum'),
            'Commission': ('Commission', lambda x: f"${pd.to_numeric(x.str.replace('$', '', regex=False)).sum():.2f}"),
            'Net Amount': ('Net Amount', lambda x: f"${pd.to_numeric(x.str.replace('$', '', regex=False)).sum():.2f}"),
            'Status': ('Status', 'first')
        }
    ).reset_index()

    return consolidated_df.to_dict('records')

if __name__ == "__main__":
    print(f"🔌 Using IBKR Gateway at https://localhost:5000")
    
    # Get data
    print("📊 Getting account net liquidation value...")
    net_liq = get_net_liq()
    print(f"Net Liquidation: ${net_liq:,.2f}")
    
    print("📈 Getting trades and executions from past 7 days...")
    trades = get_trades_and_orders(7)  # Get up to 7 days as per API limit
    
    if not trades:
        print("⚠️ No trades found. This could mean:")
        print("   - No trades in the recent period")
        print("   - Need to use different API endpoints")
        print("   - Try checking positions endpoint for current holdings")
    
    # Matching buy/sell pairs to calculate P&L
    matched_trades, unmatched_executions = match_buy_sell_pairs(trades)
    
    # Build complete trade log from matched trades
    trade_log = build_trade_log_from_matched(matched_trades, net_liq)

    # Add the new consolidation step here
    trade_log_consolidated = consolidate_final_trades(trade_log)

    # Build unmatched executions log (open positions)
    unmatched_log = build_unmatched_executions_log(unmatched_executions)

    # Add the new consolidation step for open positions here
    unmatched_log_consolidated = consolidate_open_positions(unmatched_log)
    
    # Export complete trades to excel
    if trade_log_consolidated:
        df = pd.DataFrame(trade_log_consolidated)
        
        # Select the desired columns for the final report
        report_cols = [
            "TRADE",
            "DATE (OPEN)",
            "DATE (CLOSE)",
            "DURATION",
            "Sizing",
            "OUTCOME",
            "Per Trade % Gain/Loss",
            "Net Trade % Gain/Loss",
            "Account % Gain/Loss",
            "TAKEAWAYS",
            "Would I take this trade again?",
            "Verdict",
            "Reasoning",
            "Psychology"
        ]
        
        # Ensure only columns that exist are included to prevent errors
        final_df = df[[col for col in report_cols if col in df.columns]]
        
        # Export the final DataFrame to Excel using openpyxl engine
        final_df.to_excel(OUTPUT_FILE, index=False, engine='openpyxl')
        print(f"✅ Consolidated trades exported to {OUTPUT_FILE}")
        
        # Show breakdown by security type
        if 'Security Type' in df.columns:
            type_breakdown = df['Security Type'].value_counts()
            print(f"\n📊 Consolidated trades by security type:")
            for sec_type, count in type_breakdown.items():
                print(f"   {sec_type}: {count} trades")
        
        # Show P&L summary
        total_pnl = df['OUTCOME'].sum()
        winning_trades = df[df['OUTCOME'] > 0]
        losing_trades = df[df['OUTCOME'] < 0]
        
        print(f"\n💰 P&L Summary:")
        print(f"   Total P&L: ${total_pnl:.2f}")
        print(f"   Winning trades: {len(winning_trades)} (avg: ${winning_trades['OUTCOME'].mean():.2f})")
        print(f"   Losing trades: {len(losing_trades)} (avg: ${losing_trades['OUTCOME'].mean():.2f})")
        print(f"   Win rate: {len(winning_trades)/(len(winning_trades)+len(losing_trades))*100:.1f}%")
        
    else:
        print("❌ No complete trades found after consolidation")
    
    # Export unmatched executions (open positions) to separate file
    if unmatched_log_consolidated:
        unmatched_df = pd.DataFrame(unmatched_log_consolidated)
        
        # Select the desired columns for the open positions report
        unmatched_cols = [
            "TRADE",
            "DATE",
            "Side",
            "Quantity",
            "Price",
            "Sizing"
        ]
        
        # Ensure only columns that exist are included to prevent errors
        final_unmatched_df = unmatched_df[[col for col in unmatched_cols if col in unmatched_df.columns]]
        
        unmatched_file = OUTPUT_FILE.replace('.xlsx', '_open_positions.xlsx')
        final_unmatched_df.to_excel(unmatched_file, index=False, engine='openpyxl')
        print(f"\n📈 Open positions exported to {unmatched_file}")
        print(f"📋 Found {len(unmatched_log_consolidated)} open positions")
        
        print("\n📝 Open positions:")
        display_cols = ['TRADE', 'DATE', 'Side', 'Quantity', 'Price', 'Sizing']
        print(final_df[[col for col in display_cols if col in final_df.columns]].head(10))
    
    if not trade_log_consolidated and not unmatched_log_consolidated:
        print("❌ No trades or positions were processed successfully")
        print("Consider checking the API endpoints or trade data structure")
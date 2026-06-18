#!/usr/bin/env python3
"""
Profit/Loss Outcome Analysis for AI Trading Decisions
"""

import sqlite3
import json
import re
from datetime import datetime, timedelta
import pandas as pd

from trading.symbols import from_exchange_symbol


def _symbol_search_token(symbol: str) -> str:
    """Build a loose SQL LIKE token from logical or legacy symbols."""
    return from_exchange_symbol(symbol)

def connect_db():
    return sqlite3.connect("data/trading.db")

def extract_pnl_and_position_size(reasoning_text):
    """Extract P&L and position size from reasoning"""
    pnl = None
    position_size = None
    
    # P&L patterns
    pnl_patterns = [
        r'盈亏[:：]?\$?([-+]?\d+\.?\d*)',
        r'\(盈亏\$?([-+]?\d+\.?\d*)\)',
        r'[\$￥]([-+]?\d+\.?\d*)',
        r'亏损\$?([-+]?\d+\.?\d*)',
        r'盈利\$?([-+]?\d+\.?\d*)'
    ]
    
    for pattern in pnl_patterns:
        match = re.search(pattern, reasoning_text)
        if match:
            try:
                pnl = float(match.group(1))
                break
            except:
                continue
    
    # Position size patterns
    pos_patterns = [
        r'持有[^(]*?(\d+\.?\d*)[^)]*仓位',
        r'仓位[\(（](\d+\.?\d*)[\)）]',
        r'LONG\s+(\d+\.?\d*)',
        r'SHORT\s+(\d+\.?\d*)'
    ]
    
    for pattern in pos_patterns:
        match = re.search(pattern, reasoning_text)
        if match:
            try:
                position_size = float(match.group(1))
                break
            except:
                continue
    
    return pnl, position_size

def get_price_data_around_decision(symbol, timestamp, conn):
    """Get price context around decision time"""
    # Look for recent price data in order records
    query = """
    SELECT average_price, filled_time 
    FROM order_records 
    WHERE symbol LIKE ? AND filled_time BETWEEN ? AND ?
    ORDER BY ABS(strftime('%s', filled_time) - strftime('%s', ?))
    LIMIT 1
    """
    
    # Create time window around decision
    decision_time = datetime.fromisoformat(timestamp.replace('Z', '+00:00'))
    start_time = decision_time - timedelta(minutes=30)
    end_time = decision_time + timedelta(minutes=30)
    
    cursor = conn.execute(query, (
        f"%{_symbol_search_token(symbol)}%",
        start_time.isoformat(),
        end_time.isoformat(),
        timestamp
    ))
    
    result = cursor.fetchone()
    return result[0] if result else None

def analyze_decision_outcomes():
    """Analyze actual outcomes vs AI reasoning quality"""
    
    conn = connect_db()
    
    # Get decisions with execution results
    query = """
    SELECT ta.timestamp, ta.symbol_decisions, ta.analysis_id
    FROM trading_analyses ta
    WHERE ta.symbol_decisions LIKE '%CLOSE_%' 
    ORDER BY ta.timestamp DESC
    """
    
    decisions_with_outcomes = []
    cursor = conn.execute(query)
    
    for row in cursor:
        timestamp, symbol_decisions_json, analysis_id = row
        
        try:
            symbol_decisions = json.loads(symbol_decisions_json)
            
            for symbol, decision_data in symbol_decisions.items():
                if decision_data.get('action', '').startswith('CLOSE_'):
                    reasoning = decision_data.get('reasoning', '')
                    pnl_mentioned, position_size = extract_pnl_and_position_size(reasoning)
                    
                    # Get corresponding order if exists
                    order_query = """
                    SELECT symbol, amount, average_price, cost, fee, filled_time
                    FROM order_records 
                    WHERE analysis_id = ? AND symbol LIKE ? AND side = 'SELL' AND status = 'closed'
                    """
                    
                    order_cursor = conn.execute(order_query, (analysis_id, f"%{_symbol_search_token(symbol)}%"))
                    order_result = order_cursor.fetchone()
                    
                    decision_record = {
                        'timestamp': timestamp,
                        'symbol': symbol,
                        'action': decision_data.get('action'),
                        'reasoning': reasoning,
                        'pnl_mentioned': pnl_mentioned,
                        'position_size_mentioned': position_size,
                        'execution_status': decision_data.get('execution_status', ''),
                        'analysis_id': analysis_id
                    }
                    
                    if order_result:
                        symbol_order, amount, avg_price, cost, fee, filled_time = order_result
                        decision_record.update({
                            'actual_amount': amount,
                            'exit_price': avg_price,
                            'total_cost': cost,
                            'fee_paid': fee,
                            'filled_time': filled_time
                        })
                    
                    decisions_with_outcomes.append(decision_record)
                    
        except Exception as e:
            continue
    
    conn.close()
    return decisions_with_outcomes

def categorize_decision_reasoning(reasoning):
    """Categorize the main reason for closing position"""
    if '超买' in reasoning and ('回调' in reasoning or '风险' in reasoning):
        return "Overbought_Risk_Management"
    elif '超卖' in reasoning and ('反弹' in reasoning or '锁定' in reasoning):
        return "Oversold_Profit_Taking"
    elif '趋势' in reasoning and ('反转' in reasoning or '弱势' in reasoning):
        return "Trend_Reversal"
    elif 'MACD' in reasoning and ('死叉' in reasoning or '看跌' in reasoning):
        return "MACD_Bearish_Signal"
    elif '止损' in reasoning or '亏损' in reasoning:
        return "Stop_Loss"
    elif '锁定' in reasoning and '利润' in reasoning:
        return "Profit_Taking"
    elif '风险' in reasoning:
        return "Risk_Management"
    else:
        return "Other"

def main_analysis():
    print("=== AI POSITION CLOSURE PROFIT/LOSS ANALYSIS ===\n")
    
    decisions = analyze_decision_outcomes()
    
    print(f"Total closure decisions with data: {len(decisions)}")
    decisions_with_orders = [d for d in decisions if 'actual_amount' in d]
    print(f"Decisions with corresponding order data: {len(decisions_with_orders)}")
    print(f"Decisions with mentioned P&L: {len([d for d in decisions if d['pnl_mentioned'] is not None])}\n")
    
    # 1. P&L Accuracy Analysis
    print("=== 1. P&L MENTION ACCURACY ===\n")
    
    profitable_mentioned = len([d for d in decisions if d['pnl_mentioned'] and d['pnl_mentioned'] > 0])
    losing_mentioned = len([d for d in decisions if d['pnl_mentioned'] and d['pnl_mentioned'] < 0])
    breakeven_mentioned = len([d for d in decisions if d['pnl_mentioned'] and d['pnl_mentioned'] == 0])
    
    print(f"Profitable positions (AI mentioned): {profitable_mentioned}")
    print(f"Losing positions (AI mentioned): {losing_mentioned}")  
    print(f"Breakeven positions (AI mentioned): {breakeven_mentioned}")
    print(f"No P&L mentioned: {len(decisions) - profitable_mentioned - losing_mentioned - breakeven_mentioned}")
    
    # Calculate P&L statistics
    if decisions:
        total_mentioned_pnl = sum(d['pnl_mentioned'] for d in decisions if d['pnl_mentioned'])
        avg_mentioned_pnl = total_mentioned_pnl / len([d for d in decisions if d['pnl_mentioned']])
        print(f"\nTotal mentioned P&L: ${total_mentioned_pnl:.2f}")
        print(f"Average mentioned P&L per decision: ${avg_mentioned_pnl:.3f}")
    
    # 2. Decision Quality by P&L Status
    print("\n=== 2. REASONING QUALITY BY P&L STATUS ===\n")
    
    profitable_decisions = [d for d in decisions if d['pnl_mentioned'] and d['pnl_mentioned'] > 0]
    losing_decisions = [d for d in decisions if d['pnl_mentioned'] and d['pnl_mentioned'] < 0]
    
    def analyze_reasoning_quality(decision_list, category_name):
        if not decision_list:
            return
            
        print(f"{category_name} Decisions ({len(decision_list)}):")
        
        # Technical indicator usage
        macd_count = len([d for d in decision_list if 'MACD' in d['reasoning']])
        rsi_count = len([d for d in decision_list if 'RSI' in d['reasoning']])
        ema_count = len([d for d in decision_list if 'EMA' in d['reasoning']])
        
        print(f"  MACD mentioned: {macd_count} ({macd_count/len(decision_list)*100:.1f}%)")
        print(f"  RSI mentioned: {rsi_count} ({rsi_count/len(decision_list)*100:.1f}%)")
        print(f"  EMA mentioned: {ema_count} ({ema_count/len(decision_list)*100:.1f}%)")
        
        # Risk management patterns
        risk_mgmt = len([d for d in decision_list if any(term in d['reasoning'] for term in ['风险', '控制', '规避'])])
        profit_taking = len([d for d in decision_list if any(term in d['reasoning'] for term in ['锁定', '获利'])])
        
        print(f"  Risk management: {risk_mgmt} ({risk_mgmt/len(decision_list)*100:.1f}%)")
        print(f"  Profit taking: {profit_taking} ({profit_taking/len(decision_list)*100:.1f}%)")
        
        # Average P&L
        avg_pnl = sum(d['pnl_mentioned'] for d in decision_list) / len(decision_list)
        print(f"  Average P&L: ${avg_pnl:.3f}")
        
        # Sample reasoning
        print(f"  Sample reasoning:")
        for i, decision in enumerate(decision_list[:2]):
            print(f"    {i+1}. {decision['symbol']}: {decision['reasoning'][:120]}...")
        print()
    
    analyze_reasoning_quality(profitable_decisions, "PROFITABLE")
    analyze_reasoning_quality(losing_decisions, "LOSING")
    
    # 3. Decision Categories Analysis
    print("=== 3. DECISION CATEGORY ANALYSIS ===\n")
    
    categories = {}
    for decision in decisions:
        category = categorize_decision_reasoning(decision['reasoning'])
        if category not in categories:
            categories[category] = []
        categories[category].append(decision)
    
    print("Decision categories:")
    for category, category_decisions in sorted(categories.items(), key=lambda x: len(x[1]), reverse=True):
        count = len(category_decisions)
        profitable = len([d for d in category_decisions if d['pnl_mentioned'] and d['pnl_mentioned'] > 0])
        losing = len([d for d in category_decisions if d['pnl_mentioned'] and d['pnl_mentioned'] < 0])
        
        if profitable + losing > 0:
            success_rate = profitable / (profitable + losing) * 100
        else:
            success_rate = 0
            
        avg_pnl = sum(d['pnl_mentioned'] for d in category_decisions if d['pnl_mentioned']) / len([d for d in category_decisions if d['pnl_mentioned']]) if any(d['pnl_mentioned'] for d in category_decisions) else 0
        
        print(f"  {category}: {count} decisions")
        print(f"    Success rate: {success_rate:.1f}% ({profitable}W/{losing}L)")
        print(f"    Avg P&L: ${avg_pnl:.3f}")
        print()
    
    # 4. Timing Analysis
    print("=== 4. EXIT TIMING PATTERNS ===\n")
    
    # RSI-based timing
    rsi_exits = []
    for decision in decisions:
        rsi_match = re.search(r'RSI[^(]*\(?([\d.]+)', decision['reasoning'])
        if rsi_match:
            try:
                rsi_value = float(rsi_match.group(1))
                rsi_exits.append({
                    'rsi': rsi_value,
                    'pnl': decision['pnl_mentioned'],
                    'symbol': decision['symbol'],
                    'reasoning': decision['reasoning']
                })
            except:
                continue
    
    if rsi_exits:
        print(f"RSI-based exits analyzed: {len(rsi_exits)}")
        
        oversold_exits = [r for r in rsi_exits if r['rsi'] < 30]
        overbought_exits = [r for r in rsi_exits if r['rsi'] > 70]
        
        if oversold_exits:
            oversold_pnl = [r['pnl'] for r in oversold_exits if r['pnl'] is not None]
            if oversold_pnl:
                print(f"Oversold exits (RSI < 30): {len(oversold_exits)}")
                print(f"  Average P&L: ${sum(oversold_pnl)/len(oversold_pnl):.3f}")
                profitable_oversold = len([p for p in oversold_pnl if p > 0])
                print(f"  Success rate: {profitable_oversold/len(oversold_pnl)*100:.1f}%")
        
        if overbought_exits:
            overbought_pnl = [r['pnl'] for r in overbought_exits if r['pnl'] is not None]
            if overbought_pnl:
                print(f"Overbought exits (RSI > 70): {len(overbought_exits)}")
                print(f"  Average P&L: ${sum(overbought_pnl)/len(overbought_pnl):.3f}")
                profitable_overbought = len([p for p in overbought_pnl if p > 0])
                print(f"  Success rate: {profitable_overbought/len(overbought_pnl)*100:.1f}%")
    
    # 5. Best and Worst Decisions
    print("\n=== 5. BEST AND WORST DECISIONS ===\n")
    
    decisions_with_pnl = [d for d in decisions if d['pnl_mentioned'] is not None]
    
    if decisions_with_pnl:
        best_decisions = sorted(decisions_with_pnl, key=lambda x: x['pnl_mentioned'], reverse=True)[:3]
        worst_decisions = sorted(decisions_with_pnl, key=lambda x: x['pnl_mentioned'])[:3]
        
        print("BEST DECISIONS (Highest P&L):")
        for i, decision in enumerate(best_decisions):
            timestamp = datetime.fromisoformat(decision['timestamp'].replace('Z', '+00:00'))
            print(f"  {i+1}. {decision['symbol']} - ${decision['pnl_mentioned']:.2f} - {timestamp.strftime('%Y-%m-%d %H:%M')}")
            print(f"     Reasoning: {decision['reasoning'][:150]}...")
            print()
        
        print("WORST DECISIONS (Most negative P&L):")
        for i, decision in enumerate(worst_decisions):
            timestamp = datetime.fromisoformat(decision['timestamp'].replace('Z', '+00:00'))
            print(f"  {i+1}. {decision['symbol']} - ${decision['pnl_mentioned']:.2f} - {timestamp.strftime('%Y-%m-%d %H:%M')}")
            print(f"     Reasoning: {decision['reasoning'][:150]}...")
            print()

if __name__ == "__main__":
    main_analysis()

#!/usr/bin/env python3
"""
Analysis of AI Position Closure Decisions
This script extracts and analyzes the AI's reasoning patterns when closing positions
"""

import sqlite3
import json
import re
from datetime import datetime
import pandas as pd

from trading.symbols import from_exchange_symbol

def connect_db():
    return sqlite3.connect("data/trading.db")

def extract_pnl_from_reasoning(reasoning_text):
    """Extract profit/loss mentions from reasoning text"""
    # Look for patterns like "$0.11", "$-0.37", "盈亏$0.11", "亏损$-0.37"
    pnl_patterns = [
        r'盈亏\$?([-+]?\d+\.?\d*)',
        r'亏损\$?([-+]?\d+\.?\d*)', 
        r'盈利\$?([-+]?\d+\.?\d*)',
        r'\(\$?([-+]?\d+\.?\d*)\)',
        r'[\$￥]([-+]?\d+\.?\d*)'
    ]
    
    for pattern in pnl_patterns:
        match = re.search(pattern, reasoning_text)
        if match:
            try:
                return float(match.group(1))
            except:
                continue
    return None

def analyze_reasoning_factors(reasoning_text):
    """Analyze what factors the AI mentions in its reasoning"""
    factors = {
        'technical_indicators': [],
        'risk_management': False,
        'profit_taking': False,
        'stop_loss': False,
        'trend_analysis': False,
        'oversold_overbought': False
    }
    
    # Technical indicators
    if 'MACD' in reasoning_text:
        factors['technical_indicators'].append('MACD')
    if 'RSI' in reasoning_text:
        factors['technical_indicators'].append('RSI')
    if 'EMA' in reasoning_text:
        factors['technical_indicators'].append('EMA')
    
    # Risk management terms
    risk_terms = ['止损', '风险', '控制', '规避']
    if any(term in reasoning_text for term in risk_terms):
        factors['risk_management'] = True
        
    # Profit taking terms  
    profit_terms = ['锁定利润', '获利', '盈利']
    if any(term in reasoning_text for term in profit_terms):
        factors['profit_taking'] = True
        
    # Stop loss terms
    stop_terms = ['止损', '平仓']
    if any(term in reasoning_text for term in stop_terms):
        factors['stop_loss'] = True
        
    # Trend analysis
    trend_terms = ['趋势', '下跌', '上涨', '反转']
    if any(term in reasoning_text for term in trend_terms):
        factors['trend_analysis'] = True
        
    # Oversold/overbought
    if '超买' in reasoning_text or '超卖' in reasoning_text:
        factors['oversold_overbought'] = True
        
    return factors

def get_position_closure_decisions():
    """Extract all position closure decisions with reasoning"""
    conn = connect_db()
    
    query = """
    SELECT timestamp, symbol_decisions, overall_summary, model_name
    FROM trading_analyses 
    WHERE symbol_decisions LIKE '%CLOSE_%' 
    ORDER BY timestamp DESC
    """
    
    cursor = conn.execute(query)
    decisions = []
    
    for row in cursor:
        timestamp, symbol_decisions_json, overall_summary, model_name = row
        
        try:
            symbol_decisions = json.loads(symbol_decisions_json)
            
            for symbol, decision_data in symbol_decisions.items():
                action = decision_data.get('action', '')
                if action.startswith('CLOSE_'):
                    reasoning = decision_data.get('reasoning', '')
                    execution_result = decision_data.get('execution_result', {})
                    
                    # Extract P&L from reasoning
                    pnl_mentioned = extract_pnl_from_reasoning(reasoning)
                    
                    # Analyze reasoning factors
                    factors = analyze_reasoning_factors(reasoning)
                    
                    decision = {
                        'timestamp': timestamp,
                        'symbol': symbol,
                        'action': action,
                        'reasoning': reasoning,
                        'pnl_mentioned': pnl_mentioned,
                        'factors': factors,
                        'execution_status': decision_data.get('execution_status', ''),
                        'execution_result': execution_result,
                        'model_name': model_name
                    }
                    decisions.append(decision)
                    
        except json.JSONDecodeError:
            continue
    
    conn.close()
    return decisions

def get_order_outcomes():
    """Get actual order outcomes for correlation with decisions"""
    conn = connect_db()
    
    query = """
    SELECT o.analysis_id, o.symbol, o.side, o.amount, o.average_price, 
           o.filled_time, o.cost, o.fee, o.order_type_detail
    FROM order_records o 
    WHERE o.side = 'SELL' AND o.status = 'closed'
    ORDER BY o.filled_time DESC
    """
    
    cursor = conn.execute(query)
    orders = []
    
    for row in cursor:
        analysis_id, symbol, side, amount, avg_price, filled_time, cost, fee, order_type = row
        orders.append({
            'analysis_id': analysis_id,
            # Normalize legacy exchange-formatted symbols for historical analysis only.
            'symbol': from_exchange_symbol(symbol),
            'side': side,
            'amount': amount,
            'average_price': avg_price,
            'filled_time': filled_time,
            'cost': cost,
            'fee': fee,
            'order_type': order_type
        })
    
    conn.close()
    return orders

def analyze_decision_quality():
    """Main analysis function"""
    print("=== AI POSITION CLOSURE DECISION ANALYSIS ===\n")
    
    # Get decisions and orders
    decisions = get_position_closure_decisions()
    orders = get_order_outcomes()
    
    print(f"Total position closure decisions found: {len(decisions)}")
    print(f"Total completed SELL orders found: {len(orders)}\n")
    
    # 1. Recent position closures with reasoning
    print("=== 1. RECENT POSITION CLOSURE DECISIONS ===\n")
    
    for i, decision in enumerate(decisions[:10]):  # Show last 10
        timestamp = datetime.fromisoformat(decision['timestamp'].replace('Z', '+00:00'))
        pnl_text = f" (P&L mentioned: ${decision['pnl_mentioned']:.2f})" if decision['pnl_mentioned'] else ""
        
        print(f"Decision #{i+1}")
        print(f"Time: {timestamp.strftime('%Y-%m-%d %H:%M:%S')}")
        print(f"Symbol: {decision['symbol']}")
        print(f"Action: {decision['action']}{pnl_text}")
        print(f"Status: {decision['execution_status']}")
        print(f"Reasoning: {decision['reasoning'][:200]}...")
        print("-" * 80)
    
    # 2. Factor analysis
    print("\n=== 2. REASONING FACTOR ANALYSIS ===\n")
    
    factor_counts = {
        'MACD': 0, 'RSI': 0, 'EMA': 0,
        'risk_management': 0, 'profit_taking': 0, 
        'stop_loss': 0, 'trend_analysis': 0, 
        'oversold_overbought': 0
    }
    
    for decision in decisions:
        factors = decision['factors']
        for indicator in factors['technical_indicators']:
            factor_counts[indicator] += 1
        
        for factor_name in ['risk_management', 'profit_taking', 'stop_loss', 
                           'trend_analysis', 'oversold_overbought']:
            if factors[factor_name]:
                factor_counts[factor_name] += 1
    
    print("Factors mentioned in AI reasoning:")
    for factor, count in factor_counts.items():
        percentage = (count / len(decisions)) * 100 if decisions else 0
        print(f"  {factor}: {count} times ({percentage:.1f}%)")
    
    # 3. Profitable vs losing exits analysis
    print("\n=== 3. PROFITABLE VS LOSING EXITS ===\n")
    
    profitable_decisions = [d for d in decisions if d['pnl_mentioned'] and d['pnl_mentioned'] > 0]
    losing_decisions = [d for d in decisions if d['pnl_mentioned'] and d['pnl_mentioned'] < 0]
    
    print(f"Decisions with profit mentioned: {len(profitable_decisions)}")
    print(f"Decisions with losses mentioned: {len(losing_decisions)}")
    print(f"Decisions with no P&L mentioned: {len(decisions) - len(profitable_decisions) - len(losing_decisions)}")
    
    if profitable_decisions:
        print("\nSample profitable exit reasoning:")
        for decision in profitable_decisions[:3]:
            print(f"  {decision['symbol']}: {decision['reasoning'][:150]}...")
    
    if losing_decisions:
        print("\nSample losing exit reasoning:")
        for decision in losing_decisions[:3]:
            print(f"  {decision['symbol']}: {decision['reasoning'][:150]}...")
    
    # 4. Decision quality issues
    print("\n=== 4. DECISION QUALITY ANALYSIS ===\n")
    
    # Check for contradictory reasoning
    contradictory_patterns = []
    for decision in decisions:
        reasoning = decision['reasoning']
        if '但是' in reasoning or '虽然' in reasoning:
            contradictory_patterns.append(decision)
    
    print(f"Decisions with contradictory language: {len(contradictory_patterns)}")
    
    if contradictory_patterns:
        print("\nSample contradictory reasoning:")
        for decision in contradictory_patterns[:3]:
            print(f"  {decision['symbol']}: {decision['reasoning'][:200]}...")
    
    # 5. Risk management patterns
    print("\n=== 5. RISK MANAGEMENT PATTERNS ===\n")
    
    risk_mgmt_decisions = [d for d in decisions if d['factors']['risk_management']]
    profit_taking_decisions = [d for d in decisions if d['factors']['profit_taking']]
    stop_loss_decisions = [d for d in decisions if d['factors']['stop_loss']]
    
    print(f"Decisions mentioning risk management: {len(risk_mgmt_decisions)}")
    print(f"Decisions mentioning profit taking: {len(profit_taking_decisions)}")
    print(f"Decisions mentioning stop losses: {len(stop_loss_decisions)}")
    
    # 6. Technical indicator reliance
    print("\n=== 6. TECHNICAL INDICATOR USAGE ===\n")
    
    decisions_with_indicators = [d for d in decisions if d['factors']['technical_indicators']]
    print(f"Decisions using technical indicators: {len(decisions_with_indicators)} ({len(decisions_with_indicators)/len(decisions)*100:.1f}%)")
    
    # Most common indicator combinations
    indicator_combos = {}
    for decision in decisions:
        indicators = sorted(decision['factors']['technical_indicators'])
        if indicators:
            combo = '+'.join(indicators)
            indicator_combos[combo] = indicator_combos.get(combo, 0) + 1
    
    print("\nMost common indicator combinations:")
    for combo, count in sorted(indicator_combos.items(), key=lambda x: x[1], reverse=True)[:5]:
        print(f"  {combo}: {count} times")

if __name__ == "__main__":
    analyze_decision_quality()

#!/usr/bin/env python3
"""
Detailed Analysis of AI Position Closure Decision Quality
"""

import sqlite3
import json
import re
from datetime import datetime

from trading.symbols import from_exchange_symbol
import pandas as pd

def connect_db():
    return sqlite3.connect("data/trading.db")

def extract_detailed_metrics(reasoning_text):
    """Extract specific technical indicator values mentioned"""
    metrics = {}
    
    # RSI values
    rsi_match = re.search(r'RSI[^(]*\(?([\d.]+)', reasoning_text)
    if rsi_match:
        metrics['rsi_value'] = float(rsi_match.group(1))
    
    # P&L amounts
    pnl_match = re.search(r'盈亏[:：]?\$?([-+]?\d+\.?\d*)', reasoning_text)
    if not pnl_match:
        pnl_match = re.search(r'\(盈亏\$?([-+]?\d+\.?\d*)\)', reasoning_text)
    if not pnl_match:
        pnl_match = re.search(r'[\$￥]([-+]?\d+\.?\d*)', reasoning_text)
    
    if pnl_match:
        try:
            metrics['pnl_amount'] = float(pnl_match.group(1))
        except:
            pass
    
    return metrics

def classify_decision_quality(decision):
    """Classify decision quality based on reasoning patterns"""
    reasoning = decision['reasoning']
    factors = decision['factors']
    
    quality_score = 0
    issues = []
    
    # Positive factors
    if len(factors['technical_indicators']) >= 2:
        quality_score += 2  # Multiple technical indicators
    
    if factors['risk_management']:
        quality_score += 1  # Risk awareness
        
    if decision['pnl_mentioned'] is not None:
        quality_score += 1  # P&L awareness
    
    # Negative factors
    if '虽然' in reasoning or '但是' in reasoning or '但' in reasoning:
        quality_score -= 1  # Contradictory signals
        issues.append("contradictory_signals")
    
    # Check for specific quality patterns
    if '超买' in reasoning or '超卖' in reasoning:
        if '反弹' in reasoning or '回调' in reasoning:
            quality_score += 1  # Good reversal awareness
        else:
            issues.append("missing_reversal_context")
    
    # Check if mentions specific timeframes
    timeframes = ['3分钟', '1小时', '4小时', '日线']
    timeframe_count = sum(1 for tf in timeframes if tf in reasoning)
    if timeframe_count >= 2:
        quality_score += 1  # Multi-timeframe analysis
    
    return quality_score, issues

def analyze_symbol_performance():
    """Analyze performance by symbol"""
    conn = connect_db()
    
    # Get all closure decisions with outcomes
    query = """
    SELECT ta.timestamp, ta.symbol_decisions, 
           o.symbol, o.amount, o.average_price, o.cost, o.fee
    FROM trading_analyses ta
    LEFT JOIN order_records o ON ta.analysis_id = o.analysis_id 
    WHERE ta.symbol_decisions LIKE '%CLOSE_%' 
    AND o.side = 'SELL' AND o.status = 'closed'
    ORDER BY ta.timestamp DESC
    """
    
    symbol_stats = {}
    cursor = conn.execute(query)
    
    for row in cursor:
        timestamp, symbol_decisions_json, symbol, amount, avg_price, cost, fee = row
        
        try:
            symbol_decisions = json.loads(symbol_decisions_json)
            # Normalize legacy exchange-formatted symbols for historical analysis only.
            symbol_clean = from_exchange_symbol(symbol) if symbol else None
            
            for sym, decision_data in symbol_decisions.items():
                if decision_data.get('action', '').startswith('CLOSE_') and sym == symbol_clean:
                    reasoning = decision_data.get('reasoning', '')
                    pnl_mentioned = extract_detailed_metrics(reasoning).get('pnl_amount')
                    
                    if sym not in symbol_stats:
                        symbol_stats[sym] = {
                            'total_closes': 0,
                            'profitable_closes': 0,
                            'losing_closes': 0,
                            'total_mentioned_pnl': 0,
                            'decisions': []
                        }
                    
                    symbol_stats[sym]['total_closes'] += 1
                    symbol_stats[sym]['decisions'].append({
                        'timestamp': timestamp,
                        'reasoning': reasoning,
                        'pnl_mentioned': pnl_mentioned,
                        'amount': amount,
                        'avg_price': avg_price
                    })
                    
                    if pnl_mentioned is not None:
                        symbol_stats[sym]['total_mentioned_pnl'] += pnl_mentioned
                        if pnl_mentioned > 0:
                            symbol_stats[sym]['profitable_closes'] += 1
                        else:
                            symbol_stats[sym]['losing_closes'] += 1
                            
        except Exception as e:
            continue
    
    conn.close()
    return symbol_stats

def main_analysis():
    print("=== DETAILED AI POSITION CLOSURE ANALYSIS ===\n")
    
    # Get all closure decisions
    conn = connect_db()
    query = """
    SELECT timestamp, symbol_decisions, model_name
    FROM trading_analyses 
    WHERE symbol_decisions LIKE '%CLOSE_%' 
    ORDER BY timestamp DESC
    """
    
    cursor = conn.execute(query)
    all_decisions = []
    
    for row in cursor:
        timestamp, symbol_decisions_json, model_name = row
        try:
            symbol_decisions = json.loads(symbol_decisions_json)
            
            for symbol, decision_data in symbol_decisions.items():
                if decision_data.get('action', '').startswith('CLOSE_'):
                    reasoning = decision_data.get('reasoning', '')
                    metrics = extract_detailed_metrics(reasoning)
                    
                    # Analyze factors
                    factors = {
                        'technical_indicators': [],
                        'risk_management': any(term in reasoning for term in ['风险', '控制', '规避', '止损']),
                        'profit_taking': any(term in reasoning for term in ['锁定', '获利', '盈利']),
                        'trend_analysis': any(term in reasoning for term in ['趋势', '下跌', '上涨']),
                        'oversold_overbought': '超买' in reasoning or '超卖' in reasoning
                    }
                    
                    if 'MACD' in reasoning: factors['technical_indicators'].append('MACD')
                    if 'RSI' in reasoning: factors['technical_indicators'].append('RSI')
                    if 'EMA' in reasoning: factors['technical_indicators'].append('EMA')
                    
                    quality_score, issues = classify_decision_quality({
                        'reasoning': reasoning,
                        'factors': factors,
                        'pnl_mentioned': metrics.get('pnl_amount')
                    })
                    
                    decision = {
                        'timestamp': timestamp,
                        'symbol': symbol,
                        'action': decision_data.get('action'),
                        'reasoning': reasoning,
                        'pnl_mentioned': metrics.get('pnl_amount'),
                        'rsi_value': metrics.get('rsi_value'),
                        'factors': factors,
                        'quality_score': quality_score,
                        'quality_issues': issues,
                        'execution_status': decision_data.get('execution_status', '')
                    }
                    all_decisions.append(decision)
        except:
            continue
    
    conn.close()
    
    print(f"Total closure decisions analyzed: {len(all_decisions)}\n")
    
    # 1. Decision Quality Distribution
    print("=== 1. DECISION QUALITY DISTRIBUTION ===\n")
    
    quality_distribution = {}
    for decision in all_decisions:
        score = decision['quality_score']
        quality_distribution[score] = quality_distribution.get(score, 0) + 1
    
    print("Quality Score Distribution:")
    for score in sorted(quality_distribution.keys()):
        count = quality_distribution[score]
        percentage = (count / len(all_decisions)) * 100
        print(f"  Score {score}: {count} decisions ({percentage:.1f}%)")
    
    avg_quality = sum(d['quality_score'] for d in all_decisions) / len(all_decisions)
    print(f"\nAverage Quality Score: {avg_quality:.2f}")
    
    # 2. High vs Low Quality Decision Examples
    print("\n=== 2. DECISION QUALITY EXAMPLES ===\n")
    
    high_quality = sorted([d for d in all_decisions if d['quality_score'] >= 3], 
                         key=lambda x: x['quality_score'], reverse=True)
    low_quality = sorted([d for d in all_decisions if d['quality_score'] <= 0], 
                        key=lambda x: x['quality_score'])
    
    print(f"HIGH QUALITY DECISIONS (Score >= 3): {len(high_quality)}")
    if high_quality:
        for i, decision in enumerate(high_quality[:3]):
            timestamp = datetime.fromisoformat(decision['timestamp'].replace('Z', '+00:00'))
            pnl_text = f" (P&L: ${decision['pnl_mentioned']:.2f})" if decision['pnl_mentioned'] else ""
            print(f"\nExample {i+1} - Score: {decision['quality_score']}{pnl_text}")
            print(f"  {decision['symbol']} - {timestamp.strftime('%Y-%m-%d %H:%M')}")
            print(f"  Indicators: {', '.join(decision['factors']['technical_indicators'])}")
            print(f"  Reasoning: {decision['reasoning'][:200]}...")
    
    print(f"\nLOW QUALITY DECISIONS (Score <= 0): {len(low_quality)}")
    if low_quality:
        for i, decision in enumerate(low_quality[:3]):
            timestamp = datetime.fromisoformat(decision['timestamp'].replace('Z', '+00:00'))
            print(f"\nExample {i+1} - Score: {decision['quality_score']}")
            print(f"  {decision['symbol']} - {timestamp.strftime('%Y-%m-%d %H:%M')}")
            print(f"  Issues: {', '.join(decision['quality_issues'])}")
            print(f"  Reasoning: {decision['reasoning'][:200]}...")
    
    # 3. RSI-based Exit Timing Analysis
    print("\n=== 3. RSI-BASED EXIT TIMING ANALYSIS ===\n")
    
    rsi_decisions = [d for d in all_decisions if d['rsi_value'] is not None]
    print(f"Decisions with specific RSI values: {len(rsi_decisions)}")
    
    if rsi_decisions:
        rsi_ranges = {
            'Oversold (< 30)': [d for d in rsi_decisions if d['rsi_value'] < 30],
            'Neutral (30-70)': [d for d in rsi_decisions if 30 <= d['rsi_value'] <= 70],
            'Overbought (> 70)': [d for d in rsi_decisions if d['rsi_value'] > 70]
        }
        
        for range_name, decisions in rsi_ranges.items():
            if decisions:
                avg_pnl = sum(d['pnl_mentioned'] for d in decisions if d['pnl_mentioned']) / len([d for d in decisions if d['pnl_mentioned']])
                profitable_count = len([d for d in decisions if d['pnl_mentioned'] and d['pnl_mentioned'] > 0])
                print(f"\n{range_name}: {len(decisions)} decisions")
                print(f"  Average mentioned P&L: ${avg_pnl:.3f}")
                print(f"  Profitable exits: {profitable_count}/{len(decisions)} ({profitable_count/len(decisions)*100:.1f}%)")
    
    # 4. Symbol Performance Analysis
    print("\n=== 4. SYMBOL PERFORMANCE ANALYSIS ===\n")
    
    symbol_stats = analyze_symbol_performance()
    
    print("Performance by Symbol:")
    for symbol, stats in sorted(symbol_stats.items(), key=lambda x: x[1]['total_closes'], reverse=True):
        total = stats['total_closes']
        profitable = stats['profitable_closes']
        losing = stats['losing_closes']
        total_pnl = stats['total_mentioned_pnl']
        
        success_rate = (profitable / (profitable + losing)) * 100 if (profitable + losing) > 0 else 0
        
        print(f"\n{symbol}:")
        print(f"  Total closes: {total}")
        print(f"  Profitable: {profitable}, Losing: {losing}")
        print(f"  Success rate: {success_rate:.1f}%")
        print(f"  Total mentioned P&L: ${total_pnl:.2f}")
    
    # 5. Common Decision Patterns
    print("\n=== 5. COMMON DECISION PATTERNS ===\n")
    
    # Pattern analysis
    patterns = {
        'Trend Reversal': len([d for d in all_decisions if '反转' in d['reasoning']]),
        'Overbought/Oversold': len([d for d in all_decisions if d['factors']['oversold_overbought']]),
        'Risk Management': len([d for d in all_decisions if d['factors']['risk_management']]),
        'Profit Taking': len([d for d in all_decisions if d['factors']['profit_taking']]),
        'Technical Divergence': len([d for d in all_decisions if 'MACD' in d['reasoning'] and ('死叉' in d['reasoning'] or '背离' in d['reasoning'])]),
        'Multi-timeframe Analysis': len([d for d in all_decisions if len(re.findall(r'[13日4]\s*[小时分钟]', d['reasoning'])) >= 2])
    }
    
    print("Common decision patterns:")
    for pattern, count in sorted(patterns.items(), key=lambda x: x[1], reverse=True):
        percentage = (count / len(all_decisions)) * 100
        print(f"  {pattern}: {count} decisions ({percentage:.1f}%)")

if __name__ == "__main__":
    main_analysis()

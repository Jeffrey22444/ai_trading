import assert from 'node:assert/strict';
import test from 'node:test';

import { normalizeDecision, normalizeTradeAction } from './decision-normalizer';

test('normalizes legacy OPEN_LONG', () => {
  const action = normalizeTradeAction({ action: 'OPEN_LONG', symbol: 'BTC' });

  assert.equal(action.action, 'OPEN_LONG');
  assert.equal(action.symbol, 'BTC');
});

test('normalizes legacy ENTRY_HOLD', () => {
  const action = normalizeTradeAction({ action: 'ENTRY_HOLD', symbol: 'ETH' });

  assert.equal(action.action, 'ENTRY_HOLD');
});

test('missing action becomes no action, not entry hold', () => {
  const action = normalizeTradeAction({ symbol: 'SOL' });

  assert.equal(action.action, 'NO_ACTION');
});

test('empty action payload does not crash', () => {
  const decision = normalizeDecision({
    id: 1,
    analysis_id: 'a1',
    timestamp: '2026-06-22T00:00:00Z',
    symbol_decisions: { BTC: {} },
  });

  assert.equal(decision.actions[0].action, 'NO_ACTION');
});

test('missing quant guardrail is allowed', () => {
  const action = normalizeTradeAction({ action: 'ENTRY_HOLD', symbol: 'BTC' });

  assert.equal(action.quantGuardrail, null);
});

test('partial quant guardrail is preserved safely', () => {
  const action = normalizeTradeAction({
    action: 'ENTRY_HOLD',
    symbol: 'BTC',
    quant_guardrail: { direction_bias: 'LONG' },
  });

  assert.equal(action.quantGuardrail?.total_score, undefined);
  assert.equal(action.quantGuardrail?.direction_bias, 'LONG');
});

test('prompt mismatch becomes explicit status', () => {
  const decision = normalizeDecision({
    id: 2,
    analysis_id: 'a2',
    timestamp: '2026-06-22T00:00:00Z',
    error: 'PROMPT_CONTRACT_MISMATCH',
    symbol_decisions: {},
    strategy_runtime: { compatible: false },
  });

  assert.equal(decision.actions[0].action, 'PROMPT_CONTRACT_MISMATCH');
});

test('cycle 479 style hold wins over legacy allowed open', () => {
  const action = normalizeTradeAction({
    action: 'ENTRY_HOLD',
    symbol: 'SOL',
    position_size_usd: 0,
    reasoning: 'Deterministic entry blocked: regime=RANGE; Q below threshold.',
    execution_status: 'completed',
    execution_result: { status: 'success', message: '无需执行交易' },
    quant_guardrail: {
      action_allowed: true,
      allowed_action: 'OPEN_LONG',
      total_score: 10,
      sizing: { position_size_usd: 109.15 },
    },
  });

  assert.equal(action.action, 'ENTRY_HOLD');
  assert.equal(action.positionSizeUsd, 0);
  assert.equal(action.quantGuardrail?.allowed_action, 'OPEN_LONG');
  assert.equal(action.executionMessage, '无需执行交易');
});

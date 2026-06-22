import type { Decision, TradeAction, TradeActionKind } from './types';

const ACTIONS = new Set<TradeActionKind>([
  'OPEN_LONG',
  'OPEN_SHORT',
  'CLOSE_LONG',
  'CLOSE_SHORT',
  'ENTRY_HOLD',
  'POSITION_HOLD',
  'NO_ACTION',
  'ENTRY_BLOCK',
  'PROMPT_CONTRACT_MISMATCH',
  'REGIME_ONLY',
  'UNKNOWN_ACTION',
]);

function isRecord(value: unknown): value is Record<string, unknown> {
  return Boolean(value && typeof value === 'object' && !Array.isArray(value));
}

function numberOrNull(value: unknown): number | null | undefined {
  return typeof value === 'number' && Number.isFinite(value) ? value : value === null ? null : undefined;
}

function numberOrUndefined(value: unknown): number | undefined {
  return typeof value === 'number' && Number.isFinite(value) ? value : undefined;
}

function stringOrNull(value: unknown): string | null | undefined {
  return typeof value === 'string' ? value : value === null ? null : undefined;
}

export function getSafeAction(action: unknown): TradeActionKind {
  if (typeof action !== 'string' || !action) return 'NO_ACTION';
  if (ACTIONS.has(action as TradeActionKind)) return action as TradeActionKind;
  return 'UNKNOWN_ACTION';
}

export function isOpenAction(action: TradeActionKind) {
  return action === 'OPEN_LONG' || action === 'OPEN_SHORT';
}

export function isCloseAction(action: TradeActionKind) {
  return action === 'CLOSE_LONG' || action === 'CLOSE_SHORT';
}

export function isLongAction(action: TradeActionKind) {
  return action === 'OPEN_LONG' || action === 'CLOSE_LONG';
}

export function isShortAction(action: TradeActionKind) {
  return action === 'OPEN_SHORT' || action === 'CLOSE_SHORT';
}

export function normalizeTradeAction(raw: unknown, fallbackSymbol = 'UNKNOWN'): TradeAction {
  const value = isRecord(raw) ? raw : {};
  const quantGuardrail = isRecord(value.quant_guardrail)
    ? value.quant_guardrail
    : isRecord(value.quantGuardrail)
      ? value.quantGuardrail
      : null;
  const executionResult = isRecord(value.execution_result) ? value.execution_result : {};
  const strategyRuntime = value.strategyRuntime ?? value.strategy_runtime ?? value.promptStatus ?? value.prompt_status;
  const action = strategyRuntime && isRecord(strategyRuntime) && strategyRuntime.compatible === false
    ? 'PROMPT_CONTRACT_MISMATCH'
    : getSafeAction(value.action);

  return {
    action,
    symbol: stringOrNull(value.symbol) ?? fallbackSymbol,
    reasoning: stringOrNull(value.reasoning),
    quantity: numberOrUndefined(value.quantity) ?? numberOrUndefined(executionResult.quantity),
    price: numberOrUndefined(value.price) ?? numberOrUndefined(executionResult.price),
    pnl: numberOrUndefined(value.pnl),
    holdingTime: stringOrNull(value.holdingTime) ?? stringOrNull(value.holding_time) ?? undefined,
    positionSizeUsd: numberOrNull(value.positionSizeUsd) ?? numberOrNull(value.position_size_usd),
    stopLossPrice: numberOrNull(value.stopLossPrice) ?? numberOrNull(value.stop_loss_price),
    takeProfitPrice: numberOrNull(value.takeProfitPrice) ?? numberOrNull(value.take_profit_price),
    leverage: numberOrNull(value.leverage),
    quantGuardrail: quantGuardrail as TradeAction['quantGuardrail'],
    regime: stringOrNull(value.regime),
    confidence: numberOrNull(value.confidence),
    setup: stringOrNull(value.setup),
    decision: stringOrNull(value.decision),
    blockReason: stringOrNull(value.blockReason) ?? stringOrNull(value.block_reason) ?? stringOrNull(value.reason),
    regimeClassification: value.regimeClassification ?? value.regime_classification,
    deterministicDecision: value.deterministicDecision ?? value.deterministic_decision,
    strategyRuntime,
    promptStatus: value.promptStatus ?? value.prompt_status,
    executionStatus: stringOrNull(value.executionStatus) ?? stringOrNull(value.execution_status),
    executionResultStatus: stringOrNull(executionResult.status),
    executionMessage: stringOrNull(executionResult.message),
    executionError: stringOrNull(executionResult.error),
  };
}

export function normalizeDecision(raw: unknown): Decision {
  const value = isRecord(raw) ? raw : {};
  const symbolDecisions = isRecord(value.symbol_decisions) ? value.symbol_decisions : {};
  const metadata = isRecord(symbolDecisions._metadata) ? symbolDecisions._metadata : {};
  const actionEntries = Object.entries(symbolDecisions).filter(([symbol]) => symbol !== '_metadata');
  const actions = actionEntries.length
    ? actionEntries.map(([symbol, action]) => normalizeTradeAction(action, symbol))
    : [normalizeTradeAction({
        action: value.error === 'PROMPT_CONTRACT_MISMATCH' ? 'PROMPT_CONTRACT_MISMATCH' : 'NO_ACTION',
        symbol: 'SYSTEM',
        block_reason: typeof value.error === 'string' ? value.error : undefined,
        strategy_runtime: value.strategy_runtime ?? metadata.strategy_runtime,
      })];

  return {
    id: typeof value.analysis_id === 'string' ? value.analysis_id : String(value.id ?? 'unknown'),
    sequence: typeof value.id === 'number' ? value.id : 0,
    timestamp: typeof value.timestamp === 'string' ? value.timestamp : new Date().toISOString(),
    reasoning: typeof value.overall_summary === 'string' ? value.overall_summary : 'Analysis completed',
    actions,
    status: typeof value.error === 'string' ? 'FAILED' : 'EXECUTED',
    strategyRuntime: value.strategy_runtime ?? metadata.strategy_runtime,
    regimeClassification: metadata.regime_classification,
    deterministicDecision: metadata.deterministic_decisions,
  };
}

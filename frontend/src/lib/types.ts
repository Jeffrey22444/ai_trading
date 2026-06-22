// API Response Types
export interface AccountValue {
  timestamp: string;
  value: number;
}

export type TradeActionKind =
  | 'OPEN_LONG'
  | 'OPEN_SHORT'
  | 'CLOSE_LONG'
  | 'CLOSE_SHORT'
  | 'ENTRY_HOLD'
  | 'POSITION_HOLD'
  | 'NO_ACTION'
  | 'ENTRY_BLOCK'
  | 'PROMPT_CONTRACT_MISMATCH'
  | 'REGIME_ONLY'
  | 'UNKNOWN_ACTION';

export interface TradeAction {
  action: TradeActionKind;
  symbol: string;
  reasoning?: string | null;
  quantity?: number;
  price?: number;
  pnl?: number;
  holdingTime?: string;
  positionSizeUsd?: number | null;
  stopLossPrice?: number | null;
  takeProfitPrice?: number | null;
  leverage?: number | null;
  quantGuardrail?: QuantGuardrail | null;
  regime?: string | null;
  confidence?: number | null;
  setup?: string | null;
  decision?: string | null;
  blockReason?: string | null;
  regimeClassification?: unknown;
  deterministicDecision?: unknown;
  strategyRuntime?: unknown;
  promptStatus?: unknown;
  executionStatus?: string | null;
  executionResultStatus?: string | null;
  executionMessage?: string | null;
  executionError?: string | null;
}

export interface QuantGuardrail {
  direction_bias?: 'LONG' | 'SHORT' | 'NEUTRAL' | string | null;
  total_score?: number | null;
  action_allowed?: boolean | null;
  allowed_action?: string | null;
  hold_reason?: string | null;
  sizing?: {
    position_size_usd?: number | null;
    leverage?: number | null;
    winrate?: number | null;
    margin_used_usd?: number | null;
  };
  stops?: {
    long?: QuantStopSide;
    short?: QuantStopSide;
  };
}

export interface QuantStopSide {
  stop_loss?: number | null;
  take_profit?: number | null;
  stop_source?: string | null;
  risk_reward?: number | null;
}

export interface Decision {
  id: string; // analysis_id (UUID)
  sequence: number; // numeric database id, newer decisions have larger numbers
  timestamp: string;
  reasoning: string;
  actions: TradeAction[]; // Multiple actions per cycle
  status: 'PENDING' | 'EXECUTED' | 'CANCELLED' | 'FAILED';
  strategyRuntime?: unknown;
  regimeClassification?: unknown;
  deterministicDecision?: unknown;
}

export interface Position {
  id: string;
  symbol: string;
  side: 'LONG' | 'SHORT';
  leverage: number;
  notional: number;
  unrealizedPnl: number;
  entryPrice: number;
  currentProfitPct: number;
  peakProfitPct: number;
  drawdownPct: number;
  trailingStop?: number | null;
  regime: string;
  holdingTimeSeconds: number;
  timestamp: string;
}

export interface TradeStats {
  totalTrades: number;
  totalVolume: number;
  totalPnl: number;
  totalPnlPercent: number;
  winRate: number;
  profitLossRatio: number;
  expectancy: number;
  avgTradeSize: number;
  activePositions: number;
}

// Component Props
export interface AccountChartProps {
  data: AccountValue[];
}

export interface DecisionsListProps {
  decisions: Decision[];
  onLoadMore?: () => void;
  hasMore?: boolean;
  isLoadingMore?: boolean;
}

export interface PositionsListProps {
  positions: Position[];
}

export interface StatsCardProps {
  title: string;
  value: string | number;
  change?: number;
  changeType?: 'positive' | 'negative' | 'neutral';
}

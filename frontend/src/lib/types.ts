// API Response Types
export interface AccountValue {
  timestamp: string;
  value: number;
}

export interface TradeAction {
  action: 'OPEN_LONG' | 'OPEN_SHORT' | 'CLOSE_LONG' | 'CLOSE_SHORT' | 'ENTRY_HOLD' | 'POSITION_HOLD';
  symbol: string;
  quantity?: number;
  price?: number;
  pnl?: number;
  holdingTime?: string;
  positionSizeUsd?: number | null;
  stopLossPrice?: number | null;
  takeProfitPrice?: number | null;
  leverage?: number | null;
  quantGuardrail?: QuantGuardrail | null;
}

export interface QuantGuardrail {
  direction_bias: 'LONG' | 'SHORT' | 'NEUTRAL';
  total_score: number;
  action_allowed: boolean;
  allowed_action: string;
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

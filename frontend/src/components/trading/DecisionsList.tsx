import React from 'react';
import { ScrollArea } from '@/components/ui/scroll-area';
import type { DecisionsListProps, TradeAction } from '@/lib/types';

const DecisionsList: React.FC<DecisionsListProps> = ({
  decisions,
  onLoadMore,
  hasMore = false,
  isLoadingMore = false,
}) => {
  const scrollAreaRef = React.useRef<HTMLDivElement | null>(null);
  const sentinelRef = React.useRef<HTMLDivElement | null>(null);
  const loadingRef = React.useRef(isLoadingMore);

  React.useEffect(() => {
    loadingRef.current = isLoadingMore;
  }, [isLoadingMore]);

  React.useEffect(() => {
    if (!hasMore || !onLoadMore) {
      return;
    }

    const viewport = scrollAreaRef.current?.querySelector('[data-radix-scroll-area-viewport]') as HTMLElement | null;
    if (!viewport || !sentinelRef.current) {
      return;
    }

    const observer = new IntersectionObserver(
      (entries) => {
        const entry = entries[0];
        if (entry.isIntersecting && !loadingRef.current) {
          onLoadMore();
        }
      },
      {
        root: viewport,
        rootMargin: '200px',
        threshold: 0.1,
      }
    );

    observer.observe(sentinelRef.current);

    return () => {
      observer.disconnect();
    };
  }, [hasMore, onLoadMore]);
  const getActionColor = (action: TradeAction['action']) => {
    switch (action) {
      case 'OPEN_LONG':
      case 'CLOSE_SHORT':
        return 'text-green-600';
      case 'OPEN_SHORT':
      case 'CLOSE_LONG':
        return 'text-red-600';
      case 'HOLD':
        return 'text-gray-600';
      default:
        return 'text-gray-600';
    }
  };

  const formatActionText = (action: TradeAction['action']) => {
    switch (action) {
      case 'OPEN_LONG':
        return 'Open a long trade on';
      case 'OPEN_SHORT':
        return 'Open a short trade on';
      case 'CLOSE_LONG':
        return 'Close a long trade on';
      case 'CLOSE_SHORT':
        return 'Close a short trade on';
      case 'HOLD':
        return 'Hold position on';
      default:
        return 'Action on';
    }
  };

  const getPnlColor = (pnl?: number) => {
    if (pnl === undefined) return 'text-gray-600';
    return pnl >= 0 ? 'text-green-600' : 'text-red-600';
  };

  const displaySymbol = (symbol: string) => {
    return symbol.replace('/USDC:USDC', '').replace('USDC', '').replace('USDT', '').replace('USD', '');
  };

  const formatPnl = (pnl?: number) => {
    if (pnl === undefined) return '-';
    return pnl >= 0 ? `$${pnl.toFixed(2)}` : `-$${Math.abs(pnl).toFixed(2)}`;
  };

  const formatCurrency = (value?: number | null) => {
    if (value === undefined || value === null) return '-';
    return `$${value.toFixed(2)}`;
  };

  const formatPercent = (value?: number | null) => {
    if (value === undefined || value === null) return '-';
    return `${(value * 100).toFixed(1)}%`;
  };

  const getCoinIcon = (symbol: string) => {
    const coin = displaySymbol(symbol);
    switch (coin) {
      case 'BTC':
        return '₿';
      case 'ETH':
        return '⟠';
      case 'SOL':
        return '◎';
      case 'XRP':
        return '✕';
      case 'DOGE':
        return 'Ð';
      case 'BNB':
        return '⬢';
      default:
        return coin.charAt(0);
    }
  };

  const formatTimestamp = (timestamp: string) => {
    const date = new Date(timestamp);
    return date.toLocaleString('en-US', {
      month: '2-digit',
      day: '2-digit',
      hour: '2-digit',
      minute: '2-digit',
      hour12: true
    });
  };

  return (
    <div className="h-full flex flex-col">
      <ScrollArea ref={scrollAreaRef} className="flex-1">
        <div className="p-6 space-y-6">
          {decisions.map((decision, index) => (
            <div key={decision.id} className="pb-6 border-b border-gray-200 last:border-b-0 last:pb-0 w-full overflow-hidden">
              <div className="px-2 space-y-3 w-full">
                {/* Header */}
                <div className="flex items-center justify-between">
                  <span className="text-black font-medium text-sm font-mono">
                    {decision.sequence ? `Cycle #${decision.sequence}` : `Cycle #${decisions.length - index}`}
                  </span>
                  <div className="text-gray-400 text-xs font-mono">
                    {formatTimestamp(decision.timestamp)}
                  </div>
                </div>

                {/* Reasoning */}
                {decision.reasoning && (
                  <div className="text-xs text-gray-600 leading-relaxed bg-gray-50 p-3 border-l-2 border-gray-200 font-mono max-h-24 overflow-y-auto overflow-x-hidden w-full min-w-0">
                    <div 
                      className="break-words break-all" 
                      style={{ 
                        wordWrap: 'break-word', 
                        overflowWrap: 'anywhere',
                        wordBreak: 'break-all',
                        hyphens: 'auto'
                      }}
                    >
                      {decision.reasoning}
                    </div>
                  </div>
                )}

                {/* Actions */}
                <div className="space-y-2">
                  {decision.actions.map((tradeAction, actionIndex) => (
                    <div key={actionIndex} className="space-y-1">
                      <div className="flex items-center space-x-2 text-sm">
                        {tradeAction.action === 'HOLD' ? (
                          <>
                            <span className="text-gray-500">Hold position on</span>
                            <span className="text-lg">{getCoinIcon(tradeAction.symbol)}</span>
                            <span className="font-bold text-black">
                              {displaySymbol(tradeAction.symbol)}
                            </span>
                          </>
                        ) : (
                          <>
                            <span className="text-gray-500">
                              {tradeAction.action.includes('OPEN') ? 'Open a' : 'Close a'}
                            </span>
                            <span className={`font-bold ${getActionColor(tradeAction.action)}`}>
                              {tradeAction.action.includes('LONG') ? 'long' : 'short'}
                            </span>
                            <span className="text-gray-500">trade on</span>
                            <span className="text-lg">{getCoinIcon(tradeAction.symbol)}</span>
                            <span className="font-bold text-black">
                              {displaySymbol(tradeAction.symbol)}
                            </span>
                          </>
                        )}
                        {tradeAction.pnl !== undefined && (
                          <span className={`font-bold ${getPnlColor(tradeAction.pnl)} ml-2`}>
                            {formatPnl(tradeAction.pnl)}
                          </span>
                        )}
                      </div>

                      {tradeAction.quantGuardrail && (
                        <div className="ml-1 grid grid-cols-2 gap-x-3 gap-y-1 text-[11px] leading-4 text-gray-600 font-mono sm:grid-cols-4">
                          <div>
                            <span className="text-gray-400">Score</span>{' '}
                            <span className="text-black font-semibold">
                              {tradeAction.quantGuardrail.total_score.toFixed(1)}
                            </span>
                          </div>
                          <div>
                            <span className="text-gray-400">Bias</span>{' '}
                            <span className="text-black font-semibold">
                              {tradeAction.quantGuardrail.direction_bias}
                            </span>
                          </div>
                          <div>
                            <span className="text-gray-400">Size</span>{' '}
                            <span className="text-black font-semibold">
                              {formatCurrency(tradeAction.positionSizeUsd ?? tradeAction.quantGuardrail.sizing?.position_size_usd)}
                            </span>
                          </div>
                          <div>
                            <span className="text-gray-400">Lev</span>{' '}
                            <span className="text-black font-semibold">
                              {tradeAction.leverage ?? tradeAction.quantGuardrail.sizing?.leverage ?? '-'}x
                            </span>
                          </div>
                          <div>
                            <span className="text-gray-400">SL</span>{' '}
                            <span className="text-black font-semibold">
                              {formatCurrency(tradeAction.stopLossPrice)}
                            </span>
                          </div>
                          <div>
                            <span className="text-gray-400">TP</span>{' '}
                            <span className="text-black font-semibold">
                              {formatCurrency(tradeAction.takeProfitPrice)}
                            </span>
                          </div>
                          <div>
                            <span className="text-gray-400">p</span>{' '}
                            <span className="text-black font-semibold">
                              {formatPercent(tradeAction.quantGuardrail.sizing?.winrate)}
                            </span>
                          </div>
                          <div>
                            <span className="text-gray-400">Allowed</span>{' '}
                            <span className="text-black font-semibold">
                              {tradeAction.quantGuardrail.allowed_action}
                            </span>
                          </div>
                          {tradeAction.quantGuardrail.hold_reason && (
                            <div className="col-span-2 text-gray-500 sm:col-span-4">
                              {tradeAction.quantGuardrail.hold_reason}
                            </div>
                          )}
                        </div>
                      )}
                    </div>
                  ))}
                </div>
              </div>
            </div>
          ))}
          
          {decisions.length === 0 && (
            <div className="text-center py-8 text-gray-500 font-mono text-sm">
              No trading decisions recorded yet
            </div>
          )}

          {decisions.length > 0 && (
            <div className="pt-2">
              {hasMore && onLoadMore ? (
                <div
                  ref={sentinelRef}
                  className="text-center text-xs text-gray-500 font-mono py-2"
                >
                  {isLoadingMore ? 'Loading more cycles...' : 'Keep scrolling to load more cycles'}
                </div>
              ) : (
                <div className="text-center text-xs text-gray-400 font-mono py-2">
                  No more cycles to display
                </div>
              )}
            </div>
          )}
        </div>
      </ScrollArea>
    </div>
  );
};

export default DecisionsList;

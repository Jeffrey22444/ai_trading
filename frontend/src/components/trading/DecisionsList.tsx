import React from 'react';
import { ScrollArea } from '@/components/ui/scroll-area';
import {
  isCloseAction,
  isLongAction,
  isOpenAction,
  isShortAction,
} from '@/lib/decision-normalizer';
import { formatBeijingCycleTimestamp } from '@/lib/time';
import type { DecisionsListProps, TradeAction, TradeActionKind } from '@/lib/types';

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
  const getActionColor = (action: TradeActionKind) => {
    switch (action) {
      case 'OPEN_LONG':
      case 'CLOSE_SHORT':
        return 'text-green-600';
      case 'OPEN_SHORT':
      case 'CLOSE_LONG':
        return 'text-red-600';
      case 'ENTRY_HOLD':
      case 'POSITION_HOLD':
        return 'text-gray-600';
      default:
        return 'text-gray-600';
    }
  };

  const formatActionText = (action: TradeActionKind) => {
    switch (action) {
      case 'OPEN_LONG':
        return 'Open a long trade on';
      case 'OPEN_SHORT':
        return 'Open a short trade on';
      case 'CLOSE_LONG':
        return 'Close a long trade on';
      case 'CLOSE_SHORT':
        return 'Close a short trade on';
      case 'ENTRY_HOLD':
        return 'No entry on';
      case 'POSITION_HOLD':
        return 'Hold position on';
      case 'ENTRY_BLOCK':
        return 'Entry blocked on';
      case 'PROMPT_CONTRACT_MISMATCH':
        return 'Prompt contract mismatch';
      case 'REGIME_ONLY':
        return 'Regime classified only';
      case 'NO_ACTION':
        return 'No executable action';
      case 'UNKNOWN_ACTION':
        return 'Unknown action';
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
    if (typeof value !== 'number' || !Number.isFinite(value)) return '-';
    return `$${value.toFixed(2)}`;
  };

  const formatNumber = (value?: number | null) => {
    if (typeof value !== 'number' || !Number.isFinite(value)) return '-';
    return value.toFixed(1);
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
                    {formatBeijingCycleTimestamp(decision.timestamp)}
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
                        {!isOpenAction(tradeAction.action) && !isCloseAction(tradeAction.action) ? (
                          <>
                            <span className="text-gray-500">
                              {formatActionText(tradeAction.action)}
                            </span>
                            {tradeAction.symbol !== 'SYSTEM' && (
                              <>
                                <span className="text-lg">{getCoinIcon(tradeAction.symbol)}</span>
                                <span className="font-bold text-black">
                                  {displaySymbol(tradeAction.symbol)}
                                </span>
                              </>
                            )}
                          </>
                        ) : (
                          <>
                            <span className="text-gray-500">
                              {isOpenAction(tradeAction.action) ? 'Open a' : 'Close a'}
                            </span>
                            <span className={`font-bold ${getActionColor(tradeAction.action)}`}>
                              {isLongAction(tradeAction.action) ? 'long' : isShortAction(tradeAction.action) ? 'short' : 'trade'}
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

                      {(tradeAction.regime || tradeAction.confidence !== undefined || tradeAction.setup || tradeAction.decision || tradeAction.blockReason) && (
                        <div className="ml-1 grid grid-cols-2 gap-x-3 gap-y-1 text-[11px] leading-4 text-gray-600 font-mono sm:grid-cols-4">
                          {tradeAction.regime && (
                            <div>
                              <span className="text-gray-400">Regime</span>{' '}
                              <span className="text-black font-semibold">{tradeAction.regime}</span>
                            </div>
                          )}
                          {tradeAction.confidence !== undefined && (
                            <div>
                              <span className="text-gray-400">Conf</span>{' '}
                              <span className="text-black font-semibold">{formatNumber(tradeAction.confidence)}</span>
                            </div>
                          )}
                          {tradeAction.setup && (
                            <div>
                              <span className="text-gray-400">Setup</span>{' '}
                              <span className="text-black font-semibold">{tradeAction.setup}</span>
                            </div>
                          )}
                          {tradeAction.decision && (
                            <div>
                              <span className="text-gray-400">Decision</span>{' '}
                              <span className="text-black font-semibold">{tradeAction.decision}</span>
                            </div>
                          )}
                          {tradeAction.blockReason && (
                            <div className="col-span-2 text-gray-500 sm:col-span-4">
                              {tradeAction.blockReason}
                            </div>
                          )}
                        </div>
                      )}

                      {(tradeAction.reasoning || tradeAction.executionStatus || tradeAction.executionResultStatus || tradeAction.executionMessage || tradeAction.executionError) && (
                        <div className="ml-1 space-y-1 text-[11px] leading-4 text-gray-600 font-mono">
                          {tradeAction.reasoning && (
                            <div className="break-words">
                              {tradeAction.reasoning}
                            </div>
                          )}
                          {(tradeAction.executionStatus || tradeAction.executionResultStatus || tradeAction.executionMessage || tradeAction.executionError) && (
                            <div className="grid grid-cols-2 gap-x-3 gap-y-1 sm:grid-cols-4">
                              {tradeAction.executionStatus && (
                                <div>
                                  <span className="text-gray-400">Exec</span>{' '}
                                  <span className="text-black font-semibold">{tradeAction.executionStatus}</span>
                                </div>
                              )}
                              {tradeAction.executionResultStatus && (
                                <div>
                                  <span className="text-gray-400">Result</span>{' '}
                                  <span className="text-black font-semibold">{tradeAction.executionResultStatus}</span>
                                </div>
                              )}
                              {(tradeAction.executionMessage || tradeAction.executionError) && (
                                <div className="col-span-2 text-gray-500 sm:col-span-4">
                                  {tradeAction.executionMessage ?? tradeAction.executionError}
                                </div>
                              )}
                            </div>
                          )}
                        </div>
                      )}

                      {(tradeAction.positionSizeUsd || tradeAction.stopLossPrice || tradeAction.takeProfitPrice || tradeAction.leverage) && (
                        <div className="ml-1 grid grid-cols-2 gap-x-3 gap-y-1 text-[11px] leading-4 text-gray-600 font-mono sm:grid-cols-4">
                          {tradeAction.positionSizeUsd ? (
                            <div>
                            <span className="text-gray-400">Size</span>{' '}
                            <span className="text-black font-semibold">
                              {formatCurrency(tradeAction.positionSizeUsd)}
                            </span>
                            </div>
                          ) : null}
                          {tradeAction.leverage ? (
                            <div>
                            <span className="text-gray-400">Lev</span>{' '}
                            <span className="text-black font-semibold">
                              {tradeAction.leverage}x
                            </span>
                            </div>
                          ) : null}
                          {tradeAction.stopLossPrice ? (
                            <div>
                            <span className="text-gray-400">SL</span>{' '}
                            <span className="text-black font-semibold">
                              {formatCurrency(tradeAction.stopLossPrice)}
                            </span>
                            </div>
                          ) : null}
                          {tradeAction.takeProfitPrice ? (
                            <div>
                            <span className="text-gray-400">TP</span>{' '}
                            <span className="text-black font-semibold">
                              {formatCurrency(tradeAction.takeProfitPrice)}
                            </span>
                            </div>
                          ) : null}
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

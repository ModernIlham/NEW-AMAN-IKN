/**
 * usePullToRefresh - Handles pull-to-refresh gesture on mobile.
 */
import { useReducer, useRef, useCallback } from "react";

const PULL_THRESHOLD = 80;

export function usePullToRefresh({ onRefresh }) {
  const [pull, dispatchPull] = useReducer((state, action) => {
    switch(action.type) {
      case 'START': return { ...state, isPulling: true };
      case 'MOVE': return { ...state, pullDistance: action.distance };
      case 'REFRESH': return { ...state, isRefreshing: true };
      case 'DONE': return { isPulling: false, pullDistance: 0, isRefreshing: false };
      case 'CANCEL': return { ...state, isPulling: false, pullDistance: 0 };
      default: return state;
    }
  }, { isPulling: false, pullDistance: 0, isRefreshing: false });

  const pullStartY = useRef(0);
  const mainContentRef = useRef(null);

  const handleTouchStart = useCallback((e) => {
    if (mainContentRef.current && mainContentRef.current.scrollTop <= 0) {
      pullStartY.current = e.touches[0].clientY;
      dispatchPull({ type: 'START' });
    }
  }, []);

  const handleTouchMove = useCallback((e) => {
    if (!pull.isPulling || pull.isRefreshing) return;
    const currentY = e.touches[0].clientY;
    const diff = currentY - pullStartY.current;
    if (diff > 0 && mainContentRef.current && mainContentRef.current.scrollTop <= 0) {
      const resistance = 0.4;
      const distance = Math.min(diff * resistance, 120);
      dispatchPull({ type: 'MOVE', distance });
      if (distance > 10) e.preventDefault();
    }
  }, [pull.isPulling, pull.isRefreshing]);

  const handleTouchEnd = useCallback(async () => {
    if (!pull.isPulling) return;
    if (pull.pullDistance >= PULL_THRESHOLD && !pull.isRefreshing) {
      dispatchPull({ type: 'REFRESH' });
      dispatchPull({ type: 'MOVE', distance: 50 });
      try {
        await onRefresh();
      } finally {
        dispatchPull({ type: 'DONE' });
      }
    } else {
      dispatchPull({ type: 'CANCEL' });
    }
  }, [pull.isPulling, pull.pullDistance, pull.isRefreshing, onRefresh]);

  return {
    pull,
    mainContentRef,
    handleTouchStart,
    handleTouchMove,
    handleTouchEnd,
    PULL_THRESHOLD,
  };
}

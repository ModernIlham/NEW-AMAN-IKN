import React, { useState, useEffect, useCallback, memo } from "react";
import { ArrowUp, ChevronUp } from "lucide-react";

// ============================================================================
// SCROLL TO TOP BUTTON + POSITION INDICATOR
// Shows floating button when scrolled down, with position indicator
// ============================================================================
const ScrollToTop = memo(({ scrollRef }) => {
  const [visible, setVisible] = useState(false);
  const [scrollPercent, setScrollPercent] = useState(0);
  const [showJumpBack, setShowJumpBack] = useState(false);
  const savedPositionRef = React.useRef(null);

  useEffect(() => {
    const el = scrollRef?.current;
    if (!el) return;

    let ticking = false;
    const handleScroll = () => {
      if (!ticking) {
        window.requestAnimationFrame(() => {
          const scrollTop = el.scrollTop;
          const scrollHeight = el.scrollHeight - el.clientHeight;
          const percent = scrollHeight > 0 ? Math.round((scrollTop / scrollHeight) * 100) : 0;

          setVisible(scrollTop > 300);
          setScrollPercent(percent);
          ticking = false;
        });
        ticking = true;
      }
    };

    el.addEventListener("scroll", handleScroll, { passive: true });
    return () => el.removeEventListener("scroll", handleScroll);
  }, [scrollRef]);

  const scrollToTop = useCallback(() => {
    const el = scrollRef?.current;
    if (!el) return;

    // Save current position before scrolling to top
    savedPositionRef.current = el.scrollTop;
    setShowJumpBack(true);

    el.scrollTo({ top: 0, behavior: "smooth" });

    // Auto-hide jump back button after 10 seconds
    setTimeout(() => setShowJumpBack(false), 10000);
  }, [scrollRef]);

  const jumpBack = useCallback(() => {
    const el = scrollRef?.current;
    if (!el || savedPositionRef.current === null) return;

    el.scrollTo({ top: savedPositionRef.current, behavior: "smooth" });
    setShowJumpBack(false);
    savedPositionRef.current = null;
  }, [scrollRef]);

  if (!visible && !showJumpBack) return null;

  return (
    <>
      {/* Scroll to Top Button */}
      {visible && (
        <button
          onClick={scrollToTop}
          className="fixed bottom-20 right-6 z-40 w-10 h-10 rounded-full bg-blue-600 hover:bg-blue-700 text-white shadow-lg hover:shadow-xl flex items-center justify-center transition-all duration-200 group print:hidden"
          title={`Kembali ke atas (${scrollPercent}%)`}
          aria-label="Scroll ke atas"
        >
          <ArrowUp className="w-5 h-5 group-hover:-translate-y-0.5 transition-transform" />
          {/* Progress ring */}
          <svg className="absolute inset-0 w-full h-full -rotate-90" viewBox="0 0 40 40">
            <circle cx="20" cy="20" r="18" fill="none" stroke="rgba(255,255,255,0.2)" strokeWidth="2" />
            <circle
              cx="20" cy="20" r="18" fill="none" stroke="rgba(255,255,255,0.8)" strokeWidth="2"
              strokeDasharray={`${(scrollPercent / 100) * 113} 113`}
              strokeLinecap="round"
            />
          </svg>
        </button>
      )}

      {/* Jump Back Button - appears after scrolling to top */}
      {showJumpBack && !visible && (
        <button
          onClick={jumpBack}
          className="fixed bottom-20 right-6 z-40 h-9 px-3 rounded-full bg-amber-500 hover:bg-amber-600 text-white shadow-lg hover:shadow-xl flex items-center gap-1.5 transition-all duration-200 text-xs font-medium print:hidden animate-in fade-in slide-in-from-bottom-2"
          title="Kembali ke posisi terakhir"
        >
          <ChevronUp className="w-4 h-4 rotate-180" />
          Kembali ke posisi tadi
        </button>
      )}
    </>
  );
});

ScrollToTop.displayName = "ScrollToTop";
export default ScrollToTop;

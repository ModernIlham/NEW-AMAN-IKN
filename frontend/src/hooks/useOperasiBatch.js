import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { buatKlienOperasiBatch, pesanGalatBatch } from "@/lib/operasiBatch";

export function useOperasiBatch({ owner, satker, activityId, sessionId }) {
  const [operation, setOperation] = useState(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState(null);
  const pendingCalls = useRef(0);
  const scope = JSON.stringify([owner, satker]);
  const live = useRef(scope);
  live.current = scope;
  const client = useMemo(() => buatKlienOperasiBatch({ owner, satker, sessionId,
    onChange: value => { if (live.current === scope) setOperation(value); },
  }), [owner, satker, sessionId, scope]);
  const run = useCallback(async action => {
    pendingCalls.current++; setBusy(true); setError(null);
    try { return await action(); }
    catch (e) { if (live.current === scope) setError(pesanGalatBatch(e)); throw e; }
    finally { pendingCalls.current--; if (live.current === scope) setBusy(pendingCalls.current > 0); }
  }, [scope]);
  useEffect(() => {
    let mounted = true;
    const previous = client.read();
    setOperation(previous); setError(null); setBusy(false);
    if (!previous) return undefined;
    const check = () => {
      const current = client.read();
      // Ringkasan yang sudah ditutup tidak dihidupkan lagi saat koneksi pulih.
      if (current) run(() => client.refresh(current)).catch(() => {});
    };
    check();
    const onOnline = () => { if (mounted) check(); };
    window.addEventListener("online", onOnline);
    return () => { mounted = false; window.removeEventListener("online", onOnline); };
  }, [client, run]);
  return { operation, busy, error,
    plan: (ids, updates, versions) => run(() => client.plan(ids, updates, versions, activityId)),
    start: value => run(() => client.start(value)),
    refresh: () => run(() => client.refresh(client.read() || operation)),
    resume: () => run(() => client.resume(client.read() || operation)),
    clear: (expected = operation) => client.clear(expected),
    abandonPreparation: () => run(() => client.abandonPreparation(operation)),
  };
}

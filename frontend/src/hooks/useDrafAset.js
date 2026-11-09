import { useCallback, useEffect, useRef, useState } from "react";
import { bacaDraf, tulisDraf, hapusDraf } from "../lib/drafAset";

// Draf dan media berada di IndexedDB. Jangan stringify foto setiap ketikan.
export function useDrafAset({ scope, value, enabled, dirty, onRestore, resetToken }) {
  const current = useRef(null);
  const restoreRef = useRef(onRestore);
  restoreRef.current = onRestore;
  const [state, setState] = useState({ scope, status: "loading", candidate: null });
  useEffect(() => {
    let mounted = true;
    const session = { scope, revision: 0, candidate: null, pending: null, timer: null,
      loaded: false, done: false, busy: false, writing: Promise.resolve() };
    current.current = session;
    const publish = (status, candidate = session.candidate) => {
      if (mounted) setState({ scope, status, candidate });
    };
    session.flush = () => {
      clearTimeout(session.timer);
      session.writing = session.writing.catch(() => {}).then(async () => {
        if (!session.loaded || session.done || !session.pending) return;
        if (session.candidate) throw new Error("Tinjau draf sebelumnya terlebih dahulu");
        const captured = session.pending;
        session.pending = null;
        session.busy = true;
        publish("saving");
        try {
          const record = await tulisDraf(scope, captured, session.revision);
          session.revision = record.revision;
          publish("saved");
        } catch (error) {
          if (!session.pending) session.pending = captured;
          publish("error");
          throw error;
        } finally { session.busy = false; }
      });
      return session.writing;
    };
    session.load = () => scope ? bacaDraf(scope).then(record => {
      session.revision = record?.revision || 0;
      session.candidate = record || null;
      session.loaded = true;
      publish(record ? "recover" : "idle");
      if (!record) session.flush().catch(() => {});
    }).catch(() => { publish("error"); }) : Promise.resolve();
    session.ready = session.load();
    const flush = () => { session.flush().catch(() => {}); };
    const visibility = () => { if (document.visibilityState === "hidden") flush(); };
    const beforeUnload = event => {
      if (session.pending || session.candidate || session.busy) { event.preventDefault(); event.returnValue = ""; }
      flush();
    };
    const beforeBack = event => {
      if (event.defaultPrevented || session.done || (!session.pending && !session.busy)) return;
      event.preventDefault();
      if (session.leaving) return;
      session.leaving = true;
      session.ready.then(async () => {
        if (!session.loaded) throw new Error("Penyimpanan tidak tersedia");
        do { await session.flush(); } while (session.pending && !session.candidate && !session.done);
        event.detail.proceed();
      }).catch(() => publish("error")).finally(() => { session.leaving = false; });
    };
    window.addEventListener("aman:before-back", beforeBack);
    window.addEventListener("pagehide", flush);
    window.addEventListener("beforeunload", beforeUnload);
    document.addEventListener("visibilitychange", visibility);
    return () => {
      mounted = false;
      flush();
      window.removeEventListener("aman:before-back", beforeBack);
      window.removeEventListener("pagehide", flush);
      window.removeEventListener("beforeunload", beforeUnload);
      document.removeEventListener("visibilitychange", visibility);
    };
  }, [scope, resetToken]);

  useEffect(() => {
    const session = current.current;
    if (!scope || !enabled || !dirty || session?.scope !== scope || session.done) return;
    session.pending = value;
    clearTimeout(session.timer);
    session.timer = setTimeout(() => session.flush().catch(() => {}), 300);
  }, [scope, value, enabled, dirty]);

  const flush = useCallback(async () => {
    const session = current.current;
    await session?.ready;
    if (session && !session.loaded) await session.load();
    if (!session?.loaded) throw new Error("Penyimpanan draf tidak tersedia");
    do { await session.flush(); } while (session.pending && !session.candidate && !session.done);
  }, []);
  const clearCurrent = useCallback(() => {
    const session = current.current;
    return async () => {
      if (!session?.scope) return;
      session.done = true;
      session.pending = null;
      clearTimeout(session.timer);
      await session.ready;
      await session.writing.catch(() => {});
      await hapusDraf(session.scope, session.revision);
      session.candidate = null;
      if (current.current === session) setState({ scope: session.scope, status: "idle", candidate: null });
    };
  }, []);
  const clear = useCallback(async () => {
    const session = current.current;
    await clearCurrent()();
    if (session) session.done = false;
  }, [clearCurrent]);
  const restore = useCallback(() => {
    const session = current.current;
    if (!session?.candidate) return;
    if (restoreRef.current(session.candidate.value) === false) return;
    session.pending = null;
    session.candidate = null;
    setState({ scope: session.scope, status: "saved", candidate: null });
  }, []);
  return { ...((state.scope === scope) ? state : { status: "loading", candidate: null }), flush, clear, clearCurrent, restore };
}

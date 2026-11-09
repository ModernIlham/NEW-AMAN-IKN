// Request failures normally abort IDB automatically; synchronous exceptions
// (DataCloneError, validation, serialization) do not. Roll back those too.
export async function abortOnFailure(tx, work) {
  tx.done.catch(() => {});
  try { return await work(); }
  catch (error) {
    try { tx.abort(); } catch { /* already completed/aborted */ }
    await tx.done.catch(() => {});
    throw error;
  }
}

// Faithful IDB transactions in Jest; the browser harness also tests native IDB.
import "fake-indexeddb/auto";
import { serialize, deserialize } from "v8";
if (!globalThis.structuredClone) globalThis.structuredClone = value => deserialize(serialize(value));

import "fake-indexeddb/auto";
import { Blob } from "node:buffer";
// jsdom's Blob does not survive fake-indexeddb's structured clone (read-back loses .text()).
// Node's Blob does. Tests that store blobs in IndexedDB depend on this shim.
globalThis.Blob = Blob as unknown as typeof globalThis.Blob;

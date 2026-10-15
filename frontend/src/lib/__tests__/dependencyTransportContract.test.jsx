import http from "http";
import React from "react";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import axios from "axios";
import { TextEncoder } from "util";
global.TextEncoder = TextEncoder;
const { BrowserRouter, Link, Navigate, Route, Routes, useLocation } = require("react-router-dom");
import { terapkanHeaderSatker } from "../satkerAktif";
import { pesanGalatRespons } from "../downloadFile";

jest.mock("sonner", () => ({ toast: { loading: jest.fn(), error: jest.fn(), success: jest.fn() } }));

// Exercise the installed Axios XHR adapter over real localhost HTTP. Most app
// suites mock axios; these contracts also cover the dependency upgrade boundary.
let server;
let origin;
let receivedSlow;
const sockets = new Set();
beforeAll(async () => {
  server = http.createServer((req, res) => {
    res.setHeader("Access-Control-Allow-Origin", "http://localhost");
    res.setHeader("Access-Control-Allow-Headers", "authorization,content-type,x-satker-aktif,if-match,idempotency-key,x-audit-user");
    res.setHeader("Access-Control-Allow-Methods", "GET,POST,PATCH,PUT,OPTIONS");
    if (req.method === "OPTIONS") { res.writeHead(204); res.end(); return; }
    if (req.url === "/slow") { receivedSlow?.(); return; }
    if (req.url === "/denied") {
      res.writeHead(403, { "Content-Type": "application/json" });
      res.end(JSON.stringify({ detail: "Akses satker ditolak" }));
      return;
    }
    let body = "";
    req.on("data", (chunk) => { body += chunk; });
    req.on("end", () => {
      res.writeHead(200, { "Content-Type": "application/json" });
      res.end(JSON.stringify({ method: req.method, url: req.url, headers: req.headers, body }));
    });
  });
  server.on("connection", (socket) => { sockets.add(socket); socket.on("close", () => sockets.delete(socket)); });
  await new Promise((resolve) => server.listen(0, "127.0.0.1", resolve));
  origin = `http://127.0.0.1:${server.address().port}`;
});
afterAll(async () => {
  for (const socket of sockets) socket.destroy();
  await new Promise((resolve) => server.close(resolve));
});
afterEach(() => { localStorage.clear(); receivedSlow = null; });

function client() {
  const api = axios.create({ baseURL: origin, adapter: axios.getAdapter("xhr"), timeout: 20000 });
  api.interceptors.request.use(terapkanHeaderSatker);
  return api;
}

test("JSON mutation retains auth, scoped satker, OCC/idempotency headers and custom queue config", async () => {
  localStorage.setItem("satker_aktif", "satker-A");
  const api = client();
  let customConfig;
  api.interceptors.request.use((config) => { customConfig = config.saOverride; return config; });
  const response = await api.patch("/asset?draft=1", { nama: "Kendaraan", photos: ["__existing__:0"] }, {
    saOverride: "satker-queued", timeout: 120000,
    headers: { Authorization: "Bearer request-token", "If-Match": '"7"', "Idempotency-Key": "operation-stable", "X-Audit-User": "Operator" },
  });
  expect(response.data.method).toBe("PATCH");
  expect(response.data.headers).toMatchObject({ authorization: "Bearer request-token", "x-satker-aktif": "satker-A", "if-match": '"7"', "idempotency-key": "operation-stable", "x-audit-user": "Operator" });
  expect(JSON.parse(response.data.body)).toEqual({ nama: "Kendaraan", photos: ["__existing__:0"] });
  expect(customConfig).toBe("satker-queued");
  expect(response.config.timeout).toBe(120000);
});

test("satker is read at request time and explicit replay header wins", async () => {
  const api = client();
  localStorage.setItem("satker_aktif", "A");
  expect((await api.get("/one")).data.headers["x-satker-aktif"]).toBe("A");
  localStorage.setItem("satker_aktif", "B");
  expect((await api.get("/two")).data.headers["x-satker-aktif"]).toBe("B");
  expect((await api.get("/replay", { headers: { "X-Satker-Aktif": "queued-A" } })).data.headers["x-satker-aktif"]).toBe("queued-A");
});

test("multipart body receives a browser boundary and preserves file bytes", async () => {
  const form = new FormData();
  form.append("document", new Blob(["%PDF-contract"], { type: "application/pdf" }), "dokumen.pdf");
  const { data } = await client().post("/upload", form);
  expect(data.headers["content-type"]).toMatch(/^multipart\/form-data; boundary=/);
  expect(data.body).toContain('filename="dokumen.pdf"');
  expect(data.body).toContain("%PDF-contract");
});

test("in-flight abort remains a recognized cancellation instead of offline data fallback", async () => {
  const controller = new AbortController();
  const entered = new Promise((resolve) => { receivedSlow = resolve; });
  const outcome = client().get("/slow", { signal: controller.signal }).catch((error) => error);
  await entered;
  controller.abort();
  const error = await outcome;
  expect(axios.isCancel(error)).toBe(true);
  expect(error.code).toBe("ERR_CANCELED");
});

test("blob downloads emit progress and backend 403 keeps readable detail", async () => {
  const progress = jest.fn();
  const response = await client().get("/download", { responseType: "blob", onDownloadProgress: progress, timeout: 0 });
  expect(response.data).toBeInstanceOf(Blob);
  expect(response.config.timeout).toBe(0);
  expect(progress).toHaveBeenCalledWith(expect.objectContaining({ loaded: expect.any(Number) }));
  const error = await client().get("/denied", { responseType: "blob" }).catch((caught) => caught);
  expect(error.response.status).toBe(403);
  await expect(pesanGalatRespons(error)).resolves.toBe("Akses satker ditolak");
});

function Location() { return <output aria-label="Lokasi">{useLocation().pathname}</output>; }
test("declarative browser routes replace login redirect and keep history navigation", async () => {
  window.history.replaceState({}, "", "/private");
  const user = userEvent.setup();
  const beforeRedirectLength = window.history.length;
  render(<BrowserRouter><Location /><Routes>
    <Route path="/private" element={<Navigate to="/login" replace />} />
    <Route path="/login" element={<Link to="/">Masuk</Link>} />
    <Route path="/" element={<Link to="/login">Keluar</Link>} />
  </Routes></BrowserRouter>);
  await waitFor(() => expect(screen.getByLabelText("Lokasi")).toHaveTextContent("/login"));
  expect(window.history.length).toBe(beforeRedirectLength);
  await user.click(screen.getByRole("link", { name: "Masuk" }));
  expect(screen.getByLabelText("Lokasi")).toHaveTextContent(/^\/$/);
  window.history.back();
  await waitFor(() => expect(screen.getByLabelText("Lokasi")).toHaveTextContent("/login"));
});

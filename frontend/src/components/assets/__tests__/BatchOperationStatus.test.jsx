import React from "react";
import { act, fireEvent, render, screen } from "@testing-library/react";
import BatchOperationStatus from "../BatchOperationStatus";

const operation = (response = {}, extra = {}) => ({ total: 2, children: [{
  operation_id: "operasi-a", prepared: true, asset_ids: ["a", "b"],
  response: { applied: 1, unchanged: 1, pending: 0, ...response },
}], ...extra });
const originalMatchMedia = window.matchMedia;
beforeEach(() => { jest.useFakeTimers(); window.matchMedia = jest.fn(() => ({ matches: false })); });
afterEach(() => { jest.useRealTimers(); window.matchMedia = originalMatchMedia; });
const wait = ms => act(() => jest.advanceTimersByTime(ms));

test("hasil berhasil tertutup setelah 10 detik, callback baru tidak mengulang timer", () => {
  const onDismiss = jest.fn(), value = operation();
  const { rerender } = render(<BatchOperationStatus operation={value} onDismiss={jest.fn()} />);
  wait(9000);
  rerender(<BatchOperationStatus operation={value} onDismiss={onDismiss} />);
  expect(onDismiss).not.toHaveBeenCalled();
  wait(1000);
  expect(onDismiss).toHaveBeenCalledWith(value);
});

test("tombol tutup tersedia untuk hasil final termasuk konflik", () => {
  const onDismiss = jest.fn(), value = operation({ applied: 1, unchanged: 0, conflicts: 1 });
  render(<BatchOperationStatus operation={value} onDismiss={onDismiss} />);
  wait(30000);
  expect(onDismiss).not.toHaveBeenCalled();
  fireEvent.click(screen.getByTestId("batch-status-dismiss"));
  expect(onDismiss).toHaveBeenCalledWith(value);
});

test.each([
  [operation({ applied: 0, unchanged: 0, pending: 2 }), {}],
  [operation({ applied: 1, unchanged: 0, failed: 1 }), {}],
  [operation({ applied: 1, unchanged: 0, missing: 1 }), {}],
  [operation({}, { error: "Belum pasti" }), {}],
  [operation(), { error: "Gangguan jaringan" }],
  [operation(), { busy: true }],
  [operation({}, { children: [] }), {}],
])("hasil belum aman tidak hilang otomatis %#", (value, props) => {
  const onDismiss = jest.fn();
  render(<BatchOperationStatus operation={value} onDismiss={onDismiss} {...props} />);
  wait(30000);
  expect(onDismiss).not.toHaveBeenCalled();
});

test("proses belum selesai dapat diringkas tanpa kehilangan akses melanjutkan", () => {
  const onDismiss = jest.fn(), onResume = jest.fn();
  render(<BatchOperationStatus operation={operation({ pending: 1 })} onResume={onResume} onDismiss={onDismiss} />);
  expect(screen.queryByTestId("batch-status-dismiss")).not.toBeInTheDocument();
  fireEvent.click(screen.getByTestId("batch-status-collapse"));
  expect(screen.queryByText("Lanjutkan yang menunggu")).not.toBeInTheDocument();
  fireEvent.click(screen.getByTestId("batch-status-collapse"));
  fireEvent.click(screen.getByText("Lanjutkan yang menunggu"));
  expect(onResume).toHaveBeenCalledTimes(1);
});

test("timer dibatalkan saat operasi berganti dan saat dilepas", () => {
  const onDismiss = jest.fn();
  const { rerender, unmount } = render(<BatchOperationStatus operation={operation()} onDismiss={onDismiss} />);
  wait(9000);
  rerender(<BatchOperationStatus operation={operation({ pending: 2 }, { createdAt: 2 })} onDismiss={onDismiss} />);
  wait(10000);
  expect(onDismiss).not.toHaveBeenCalled();
  rerender(<BatchOperationStatus operation={operation()} onDismiss={onDismiss} />);
  unmount(); wait(10000);
  expect(onDismiss).not.toHaveBeenCalled();
});

test("membaca panel dengan fokus atau pointer menjeda penutupan", () => {
  const media = jest.spyOn(window, "matchMedia").mockReturnValue({ matches: true });
  const onDismiss = jest.fn();
  render(<BatchOperationStatus operation={operation()} onDismiss={onDismiss} />);
  const panel = screen.getByTestId("batch-operation-status");
  const hover = jest.spyOn(panel, "matches").mockReturnValue(true);
  fireEvent.mouseEnter(panel); wait(20000);
  expect(onDismiss).not.toHaveBeenCalled();
  hover.mockReturnValue(false); fireEvent.mouseLeave(panel); wait(5000);
  act(() => screen.getByTestId("batch-status-dismiss").focus()); wait(20000);
  expect(onDismiss).not.toHaveBeenCalled();
  act(() => screen.getByTestId("batch-status-dismiss").blur()); wait(10000);
  expect(onDismiss).toHaveBeenCalledTimes(1);
  hover.mockRestore();
  media.mockRestore();
});

test("hover semu layar sentuh tidak menahan penutupan", () => {
  const media = jest.spyOn(window, "matchMedia").mockReturnValue({ matches: false });
  const onDismiss = jest.fn();
  render(<BatchOperationStatus operation={operation()} onDismiss={onDismiss} />);
  jest.spyOn(screen.getByTestId("batch-operation-status"), "matches").mockReturnValue(true);
  wait(10000);
  expect(onDismiss).toHaveBeenCalledTimes(1);
  media.mockRestore();
});

test("tab tersembunyi tidak menghabiskan waktu membaca hasil", () => {
  const onDismiss = jest.fn();
  const hidden = jest.spyOn(document, "hidden", "get").mockReturnValue(true);
  render(<BatchOperationStatus operation={operation()} onDismiss={onDismiss} />);
  wait(20000);
  expect(onDismiss).not.toHaveBeenCalled();
  hidden.mockReturnValue(false);
  fireEvent(document, new Event("visibilitychange")); wait(10000);
  expect(onDismiss).toHaveBeenCalledTimes(1);
  hidden.mockRestore();
});

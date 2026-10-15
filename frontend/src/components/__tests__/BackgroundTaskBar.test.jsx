import React from "react";
import { fireEvent, render, screen } from "@testing-library/react";
import axios from "axios";
import BackgroundTaskBar from "../BackgroundTaskBar";
jest.mock("axios");
beforeEach(() => {
  jest.clearAllMocks();
  localStorage.setItem("token", "synthetic-test-token");
  jest.spyOn(HTMLAnchorElement.prototype, "click").mockImplementation(() => {});
});
afterEach(() => { jest.restoreAllMocks(); localStorage.removeItem("token"); });
test.each(["archive_failed", "archived", "not_requested"])("backup %s membedakan unduhan dan arsip tahan lama", async archive_state => {
  axios.get.mockResolvedValue({ data: { job_id: "backup-1", type: "backup", status: "completed", progress: 100,
    download_ready: true, archive_state, durable_verified: archive_state === "archived", archive_error: archive_state === "archive_failed" ? "Disk penuh" : undefined } });
  render(<BackgroundTaskBar isAdmin />);
  const label = await screen.findByTestId("backup-archive-state");
  if (archive_state === "archive_failed") {
    expect(label).toHaveTextContent("penyimpanan arsip server gagal");
    expect(label).toHaveTextContent("Disk penuh");
    expect(label).not.toHaveTextContent("arsip server telah diverifikasi");
  } else if (archive_state === "archived") expect(label).toHaveTextContent("arsip server telah diverifikasi");
  else expect(label).toHaveTextContent("Arsip server tidak diminta");
  expect(screen.getByTestId("bg-task-download")).toBeEnabled();
  expect(HTMLAnchorElement.prototype.click).toHaveBeenCalledTimes(1);
});

test("recovery_required tetap merah dan tidak dapat ditutup sebagai hasil selesai", async () => {
  axios.get.mockResolvedValue({ data: { job_id: "restore-1", type: "restore", status: "failed", progress: 60,
    recovery_required: true, error: "restore gagal", rollback_error: "rollback gagal" } });
  render(<BackgroundTaskBar isAdmin />);
  expect(await screen.findByTestId("restore-recovery-required")).toHaveTextContent("Layanan tetap ditahan");
  expect(screen.queryByTestId("bg-task-dismiss")).not.toBeInTheDocument();
  fireEvent.click(screen.getByTestId("bg-task-minimize"));
  expect(screen.getByTestId("bg-task-minimized")).toHaveTextContent("Pemulihan memerlukan tindakan");
  expect(axios.post).not.toHaveBeenCalled();
});

import React from "react";
import { fireEvent, render, screen } from "@testing-library/react";
import SignatureCapture from "../SignatureCapture";

jest.mock("axios", () => ({ post: jest.fn() }));

jest.mock("react-signature-canvas", () => {
  const ReactMock = require("react");
  return ReactMock.forwardRef(function KanvasTtdPalsu(props, ref) {
    ReactMock.useImperativeHandle(ref, () => ({
      clear: jest.fn(),
      fromData: jest.fn(),
      getCanvas: () => null,
      isEmpty: () => true,
      toData: () => [],
    }));
    return <canvas data-testid={props.canvasProps?.["data-testid"] || "ttd-canvas"} />;
  });
});

describe("pemilihan sumber foto tanda tangan", () => {
  function bukaModeFoto() {
    render(<SignatureCapture onSave={jest.fn()} />);
    fireEvent.click(screen.getByTestId("ttd-mode-foto"));
  }

  test("galeri tidak memaksa browser membuka kamera", () => {
    bukaModeFoto();
    expect(screen.getByTestId("ttd-foto-input")).not.toHaveAttribute("capture");
    expect(screen.getByTestId("ttd-foto-pilih")).toHaveTextContent("Pilih file / galeri");
  });

  test("kamera memakai input capture tersendiri", () => {
    bukaModeFoto();
    expect(screen.getByTestId("ttd-kamera-input")).toHaveAttribute("capture", "environment");
    expect(screen.getByTestId("ttd-foto-kamera")).toHaveTextContent("Ambil foto kamera");
  });

  test("setiap tombol membuka input sumbernya sendiri", () => {
    bukaModeFoto();
    const galeri = screen.getByTestId("ttd-foto-input");
    const kamera = screen.getByTestId("ttd-kamera-input");
    const klikGaleri = jest.spyOn(galeri, "click");
    const klikKamera = jest.spyOn(kamera, "click");

    fireEvent.click(screen.getByTestId("ttd-foto-pilih"));
    expect(klikGaleri).toHaveBeenCalledTimes(1);
    expect(klikKamera).not.toHaveBeenCalled();

    fireEvent.click(screen.getByTestId("ttd-foto-kamera"));
    expect(klikKamera).toHaveBeenCalledTimes(1);
  });
});

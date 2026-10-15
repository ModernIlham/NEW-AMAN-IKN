#!/usr/bin/env python3
"""Actual Chromium smoke; explicitly local synthetic accounts, no production.

Run the isolated backend and a frontend production build first. Credentials are
read from a private seed output and never included in the result or screenshots.
"""
import argparse
import base64
import contextlib
from io import BytesIO
import json
import os
from pathlib import Path
import re
import signal
import subprocess
import tempfile
import time
from urllib.parse import urlparse

import requests
from PIL import Image
from websockets.sync.client import connect

HTTP = requests.Session()
HTTP.trust_env = False


def local_target(value):
    parsed = urlparse(value)
    if (parsed.scheme != "http" or parsed.hostname not in {"127.0.0.1", "localhost", "::1"}
            or parsed.username or parsed.password or parsed.path not in {"", "/"} or parsed.query or parsed.fragment):
        raise ValueError("Browser smoke hanya HTTP loopback dengan data sintetis")
    _ = parsed.port
    return value.rstrip("/")


class Browser:
    def __init__(self, chromium, state_file=None):
        self.state_file = Path(state_file) if state_file else None
        self.state = None
        self.profile = tempfile.TemporaryDirectory(prefix="aman-browser-")
        try:
            self._start(chromium)
        except BaseException:
            self.close()
            raise

    def _start(self, chromium):
        self.chromium_log = (self.state_file.parent / "chromium.log").open("w") if self.state_file else None
        self.process = subprocess.Popen([chromium, "--headless=new", "--no-sandbox",
            "--disable-dev-shm-usage", "--remote-debugging-port=0",
            "--proxy-server=http://127.0.0.1:9",
            "--proxy-bypass-list=localhost;127.0.0.1;[::1]",
            "--remote-allow-origins=http://localhost", "--no-first-run",
            "--user-data-dir=" + self.profile.name, "about:blank"],
            stdout=subprocess.DEVNULL, stderr=self.chromium_log or subprocess.DEVNULL,
            start_new_session=True)
        self.state = {"pid": self.process.pid, "profile": self.profile.name,
            "process_start": Path(f"/proc/{self.process.pid}/stat").read_text().rsplit(")", 1)[1].split()[19], "closed": False}
        self._save_state()
        active = Path(self.profile.name) / "DevToolsActivePort"
        deadline = time.monotonic() + 20
        while not active.exists():
            if self.process.poll() is not None or time.monotonic() > deadline:
                self.close()
                raise RuntimeError("Chromium tidak siap")
            time.sleep(.1)
        port = active.read_text().splitlines()[0]
        pages = HTTP.get(f"http://127.0.0.1:{port}/json/list", timeout=5, allow_redirects=False).json()
        page = next(page for page in pages if page["type"] == "page")
        self.ws = connect(page["webSocketDebuggerUrl"], origin="http://localhost",
                          open_timeout=10, max_size=30 * 1024 * 1024)
        self.sequence = 0
        self.call("Page.enable")
        self.call("Runtime.enable")

    def _save_state(self):
        if self.state_file and self.state:
            descriptor = os.open(self.state_file, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
            with os.fdopen(descriptor, "w") as stream:
                json.dump(self.state, stream)

    def call(self, method, params=None):
        self.sequence += 1
        number = self.sequence
        self.ws.send(json.dumps({"id": number, "method": method, "params": params or {}}))
        while True:
            message = json.loads(self.ws.recv(timeout=45))
            if message.get("id") == number:
                if "error" in message:
                    raise RuntimeError(f"CDP {method} gagal")
                return message.get("result", {})

    def js(self, expression):
        result = self.call("Runtime.evaluate", {"expression": expression,
            "returnByValue": True, "awaitPromise": True})
        if result.get("exceptionDetails"):
            # Expressions can contain credentials. Never echo them on failure.
            raise RuntimeError("Eksekusi browser gagal")
        return result.get("result", {}).get("value")

    def wait(self, expression, timeout=30):
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            if self.js(expression):
                return
            time.sleep(.15)
        raise RuntimeError("Tenggat kondisi browser terlampaui")

    def click(self, selector):
        self.wait("(() => {const el=document.querySelector(" + json.dumps(selector)
            + ");return Boolean(el&&!el.disabled&&el.getClientRects().length);})()")
        self.js(f"document.querySelector({json.dumps(selector)}).click()")

    def visible(self, selector):
        return self.js("(() => {const el=document.querySelector(" + json.dumps(selector)
            + ");return Boolean(el&&el.getClientRects().length);})()")

    def press(self, selector, key, code, number):
        self.js(f"document.querySelector({json.dumps(selector)}).focus()")
        for kind in ("keyDown", "keyUp"):
            event = {"type": kind, "key": key,
                "code": code, "windowsVirtualKeyCode": number, "nativeVirtualKeyCode": number}
            if kind == "keyDown":
                event["text"] = "\r" if key == "Enter" else key
            self.call("Input.dispatchKeyEvent", event)

    def input(self, selector, value):
        self.wait(f"Boolean(document.querySelector({json.dumps(selector)}))")
        self.js("(() => {const el=document.querySelector(" + json.dumps(selector) + ");"
            "Object.getOwnPropertyDescriptor(HTMLInputElement.prototype,'value').set.call(el,"
            + json.dumps(value) + ");el.dispatchEvent(new Event('input',{bubbles:true}));})()")

    def screenshot(self, path):
        result = self.call("Page.captureScreenshot", {"captureBeyondViewport": False})
        path.write_bytes(base64.b64decode(result["data"]))

    def wait_images(self, selector):
        self.wait("(() => {const images=Array.from(document.querySelectorAll(" + json.dumps(selector) + "))"
            ".filter(el=>{const r=el.getBoundingClientRect();return el.getClientRects().length&&r.width>0&&r.height>0&&r.bottom>0&&r.top<innerHeight&&r.right>0&&r.left<innerWidth;});"
            "return images.length>0&&images.every(el=>el.complete&&el.naturalWidth>0);})()")

    def close(self):
        errors = []
        def cleanup(action, callback):
            try:
                callback()
            except Exception as exc:
                errors.append({"action": action, "error_class": type(exc).__name__})
        if getattr(self, "ws", None):
            cleanup("cdp_connection", self.ws.close)
        if getattr(self, "process", None) and self.process.poll() is None:
            def stop():
                os.killpg(self.process.pid, signal.SIGTERM)
                try:
                    self.process.wait(timeout=10)
                except subprocess.TimeoutExpired:
                    os.killpg(self.process.pid, signal.SIGKILL)
                    self.process.wait(timeout=5)
            cleanup("chromium_process", stop)
        if getattr(self, "profile", None):
            # Render children can finish writing after the browser exits.
            for attempt in range(10):
                try:
                    self.profile.cleanup()
                    break
                except OSError:
                    if attempt == 9:
                        errors.append({"action": "chromium_profile", "error_class": "OSError"})
                    time.sleep(.1)
        if self.state:
            self.state["closed"] = not errors
            cleanup("browser_state", self._save_state)
        if getattr(self, "chromium_log", None):
            cleanup("chromium_log", self.chromium_log.close)
        return errors


def testid(value):
    return f'[data-testid="{value}"]'


def run(args):
    frontend, backend = local_target(args.frontend), local_target(args.backend)
    accounts_path = Path(args.accounts)
    if os.name != "nt" and accounts_path.stat().st_mode & 0o077:
        raise ValueError("Berkas akun wajib privat")
    raw = json.loads(accounts_path.read_text())
    assert re.fullmatch(r"[a-f0-9]{8,32}", raw.get("run_id", "")) and raw["accounts"], "Wajib akun seed sintetis"
    account = raw["accounts"][0]
    assert account["username"].startswith("loadtest-" + raw["run_id"] + "-"), "Akun non-sintetis ditolak"
    assert account["activity_id"].startswith("loadtest-" + raw["run_id"] + "-activity-")
    output = Path(args.output)
    output.mkdir(parents=True, exist_ok=True)
    if accounts_path.resolve().is_relative_to(output.resolve()):
        raise ValueError("Akun privat tidak boleh berada dalam direktori artifact")
    browser = None
    report = {"checks": [], "viewports": [], "synthetic": True, "run_id": raw["run_id"],
              "stage": "fixture_identity", "ok": False, "cleanup_errors": []}
    started = time.monotonic()
    headers = {"Authorization": "Bearer " + account["access_token"]}
    originals = {}
    created_ids = []
    created_category = None
    failure = None
    fixture_name = "Browser smoke fixture " + raw["run_id"][:8]
    def asset(aid):
        response = HTTP.get(backend + "/api/assets/" + aid, headers=headers, timeout=15, allow_redirects=False)
        assert response.status_code == 200, "Baca aset sintetis gagal"
        return response.json()
    try:
        identity = HTTP.get(backend + "/__browser_fixture__", timeout=5, allow_redirects=False)
        assert identity.status_code == 200, "Backend bukan fixture browser terisolasi"
        identity = identity.json()
        assert identity.get("synthetic") is True and identity.get("run_id") == raw["run_id"]
        assert re.fullmatch(r"aman_ci_browser_[a-f0-9]{32}", identity.get("database", ""))
        assert identity.get("rate_limit_storage") == "memory" and identity.get("private_filesystem") is True
        report["stage"] = "browser_startup"
        browser = Browser(args.chromium, getattr(args, "browser_state", None))
        report["stage"] = "create_fixtures"
        # Normal fixtures are separate from the load dataset's adversarial
        # legacy records. They still go through real auth and the create API.
        image_bytes = BytesIO()
        Image.new("RGB", (16, 16), (20, 140, 120)).save(image_bytes, "PNG")
        photo = "data:image/png;base64," + base64.b64encode(image_bytes.getvalue()).decode()
        category = "Browser fixture " + raw["run_id"][:8]
        response = HTTP.post(backend + "/api/categories", headers=headers,
            json={"label": category, "kode_aset": ""}, timeout=15)
        assert response.status_code == 200, "Pembuatan kategori fixture gagal"
        created_category = response.json()["id"]
        for index in range(2):
            response = HTTP.post(backend + "/api/assets", headers=headers, json={
                "asset_code": "3999" + str((int(raw["run_id"][:6], 16) + index) % 1000000).zfill(6),
                "asset_name": fixture_name + " " + str(index), "NUP": "1",
                "activity_id": account["activity_id"], "category": category,
                "condition": "Baik", "status": "Aktif", "purchase_price": "1000",
                "inventory_status": "Belum Diinventarisasi", "brand": "Sintetis",
                "photos": [photo], "document_checklist": [{"name": "STNK", "checked": True,
                    "notes": "", "photos": [photo], "documents": []}],
            }, timeout=30)
            assert response.status_code == 200, "Pembuatan fixture browser gagal"
            created_ids.append(response.json()["id"])
        browser.call("Emulation.setDeviceMetricsOverride", {"width": 1440,
            "height": 1000, "deviceScaleFactor": 1, "mobile": False})
        browser.call("Page.navigate", {"url": frontend})
        report["stage"] = "login"
        browser.input(testid("username-input"), account["username"])
        browser.input(testid("password-input"), account["password"])
        browser.click(testid("submit-button"))
        browser.wait("!document.querySelector('[data-testid=login-form]')", 45)
        report["checks"].append("login_ui")
        # Login screenshots are intentionally never captured.
        browser.click(testid("module-card-inventarisasi-aset"))
        browser.click(testid("activity-card-" + account["activity_id"]))
        browser.wait("Boolean(document.querySelector('[data-testid=asset-main-content]'))")
        browser.wait("Boolean(document.querySelector('[data-scroll-asset-id]'))", 45)
        browser.input(testid("search-input"), fixture_name)
        browser.wait("document.querySelectorAll('[data-scroll-asset-id]').length===2", 45)
        report["checks"].append("module_activity_list")
        report["stage"] = "dashboard_viewports"
        for width in (320, 360, 768, 1440):
            browser.call("Emulation.setDeviceMetricsOverride", {"width": width,
                "height": 1000, "deviceScaleFactor": 1, "mobile": width < 768})
            time.sleep(.3)
            for theme in ("light", "dark"):
                browser.js(f"document.documentElement.classList.toggle('dark',{str(theme == 'dark').lower()});document.documentElement.style.colorScheme='{theme}'")
                time.sleep(.3)
                browser.js("document.fonts.ready")
                geometry = browser.js("({viewport:innerWidth,width:document.documentElement.scrollWidth,height:innerHeight})")
                assert geometry["width"] <= geometry["viewport"] + 1, f"Overflow pada {width}/{theme}"
                report["viewports"].append({"width": width, "theme": theme,
                    "horizontal_overflow": False})
                browser.wait_images('[data-scroll-asset-id] img')
                browser.screenshot(output / f"dashboard-{width}-{theme}.png")
        browser.call("Emulation.setDeviceMetricsOverride", {"width": 1440,
            "height": 1000, "deviceScaleFactor": 1, "mobile": False})
        browser.js("document.documentElement.classList.remove('dark')")
        browser.click(testid("view-mode-list"))
        report["stage"] = "keyboard"
        browser.wait("document.querySelectorAll('[data-testid^=select-asset-]').length>=2")
        ids = browser.js("Array.from(document.querySelectorAll('[data-testid^=select-asset-]')).slice(0,2).map(e=>e.dataset.testid.slice('select-asset-'.length))")
        for aid in ids:
            assert aid in created_ids
            originals[aid] = asset(aid)
        browser.press(testid("select-asset-" + ids[0]), " ", "Space", 32)
        browser.wait("document.querySelector(" + json.dumps(testid("select-asset-" + ids[0])) + ").checked")
        assert not browser.js("document.querySelector('[data-testid=asset-form-submit]')?.textContent.includes('Update')")
        browser.press(testid("select-asset-" + ids[0]), " ", "Space", 32)
        browser.wait("!document.querySelector(" + json.dumps(testid("select-asset-" + ids[0])) + ").checked")
        browser.press(testid("row-photo-" + ids[0]), "Enter", "Enter", 13)
        browser.wait("Boolean(document.querySelector('[data-testid=gallery-lightbox]'))")
        browser.wait_images('[data-testid=gallery-lightbox] img')
        browser.click(testid("lightbox-close"))
        assert not browser.js("document.querySelector('[data-testid=asset-form-submit]')?.textContent.includes('Update')")
        report["checks"].append("nested_checkbox_and_photo_keyboard_do_not_edit_row")
        # Actual edit/save through the form, then authoritative HTTP readback.
        report["stage"] = "form_save"
        browser.press('[data-scroll-asset-id="' + ids[0] + '"]', "Enter", "Enter", 13)
        browser.wait("document.querySelector('[data-testid=asset-form-submit]')?.textContent.includes('Update')")
        browser.wait("document.querySelector('input[name=brand]')?.value==='Sintetis'")
        browser.input('input[name="brand"]', "Browser smoke")
        browser.click(testid("asset-form-submit"))
        deadline = time.monotonic() + 30
        while asset(ids[0]).get("brand") != "Browser smoke":
            assert time.monotonic() < deadline, "Form save tidak terkonfirmasi"
            time.sleep(.2)
        report["checks"].append("form_edit_save_readback")
        browser.click('[data-scroll-asset-id="' + ids[0] + '"]')
        report["stage"] = "document_edit"
        browser.wait("document.querySelector('input[name=brand]')?.value==='Browser smoke'")
        browser.js("Array.from(document.querySelectorAll('aside button')).find(el=>el.textContent.trim()==='Dokumen').click()")
        browser.wait("Boolean(document.querySelector('[aria-label=\"Kelengkapan STNK\"]'))")
        browser.click('[aria-label="Kelengkapan STNK"]')
        browser.wait("document.querySelector('[aria-label=\"Kelengkapan STNK\"]').getAttribute('aria-pressed')==='false'")
        browser.wait("Boolean(document.querySelector('[aria-label=\"Lihat foto 1 STNK\"]'))")
        browser.wait_images('[aria-label="Lihat foto 1 STNK"] img')
        browser.click('[aria-label="Lihat foto 1 STNK"]')
        browser.wait_images('img[alt="Preview"]')
        browser.click('[aria-label="Tutup pratinjau foto"]')
        report["checks"].append("checklist_thumbnail_and_full_photo_decoded")
        report["checks"].append("unchecked_checklist_retains_visible_media")
        browser.input('[aria-label="Nama item kelengkapan baru"]', "Uji dokumen")
        browser.click('[aria-label="Tambah item kelengkapan"]')
        browser.wait("Boolean(document.querySelector('[aria-label=\"Kelengkapan Uji dokumen\"]'))")
        for width in (320, 360, 768, 1440):
            browser.call("Emulation.setDeviceMetricsOverride", {"width": width,
                "height": 1000, "deviceScaleFactor": 1, "mobile": width < 768})
            time.sleep(.35)
            for theme in ("light", "dark"):
                browser.js(f"document.documentElement.classList.toggle('dark',{str(theme == 'dark').lower()});document.documentElement.style.colorScheme='{theme}'")
                time.sleep(.3)
                geometry = browser.js("(() => {const p=Array.from(document.querySelectorAll('[data-testid=document-checklist]')).find(el=>el.getClientRects().length);if(!p)return {width:0};const i=p.querySelector('[aria-label=\"Nama item kelengkapan baru\"]');const b=p.querySelector('[aria-label=\"Tambah item kelengkapan\"]');return {width:p.clientWidth,scroll:p.scrollWidth,inputHeight:i.getBoundingClientRect().height,buttonHeight:b.getBoundingClientRect().height};})()")
                assert geometry["width"] > 0, "Tab/draf dokumen hilang setelah resize"
                assert geometry["scroll"] <= geometry["width"] + 1, "Checklist overflow"
                assert abs(geometry["inputHeight"] - geometry["buttonHeight"]) <= 1, "Tombol tambah tidak sejajar"
                browser.wait_images('[aria-label="Lihat foto 1 STNK"] img')
                browser.screenshot(output / f"documents-{width}-{theme}.png")
        browser.call("Emulation.setDeviceMetricsOverride", {"width": 1440,
            "height": 1000, "deviceScaleFactor": 1, "mobile": False})
        browser.js("document.documentElement.classList.remove('dark')")
        browser.js("document.documentElement.style.colorScheme='light'")
        browser.click(testid("asset-form-submit"))
        deadline = time.monotonic() + 30
        def stnk(value):
            return next(item for item in value["document_checklist"] if item["name"] == "STNK")
        while stnk(asset(ids[0]))["checked"]:
            assert time.monotonic() < deadline, "Checklist save tidak terkonfirmasi"
            time.sleep(.2)
        current = asset(ids[0])
        assert any(item.get("name") == "Uji dokumen" for item in current["document_checklist"]), "Item kelengkapan baru tidak tersimpan"
        assert stnk(current)["photos"] == stnk(originals[ids[0]])["photos"]
        originals[ids[0]] = current
        report["checks"].append("compact_documents_four_viewports_save_preserves_photo")
        report["stage"] = "batch_edit"
        for aid in ids:
            browser.click(testid("select-asset-" + aid))
        browser.wait("Boolean(document.querySelector('[data-testid=batch-edit-panel]'))")
        location = "Browser smoke " + raw["run_id"][:8]
        browser.input('[data-testid=batch-edit-panel] input[placeholder="—"]', location)
        browser.click(testid("toggle-batch-panel-btn"))
        browser.wait("!document.querySelector('[data-testid=batch-edit-panel]')?.getClientRects().length")
        browser.click(testid("toggle-batch-panel-btn"))
        browser.wait("Boolean(document.querySelector('[data-testid=batch-edit-panel]')?.getClientRects().length)")
        assert browser.js("document.querySelector('[data-testid=batch-edit-panel] input[placeholder=\"—\"]').value") == location
        report["checks"].append("hide_preserves_batch_draft")
        browser.click(testid("batch-apply-btn"))
        browser.wait("Boolean(document.querySelector('[data-testid=confirm-dialog-confirm]'))")
        assert all(asset(aid).get("location") == originals[aid].get("location") for aid in ids), "Mutasi terjadi sebelum konfirmasi"
        report["checks"].append("batch_preflight_before_mutation")
        browser.click(testid("confirm-dialog-confirm"))
        deadline = time.monotonic() + 30
        while not all(asset(aid).get("location") == location for aid in ids):
            assert time.monotonic() < deadline, "Batch tidak terkonfirmasi"
            time.sleep(.2)
        assert all(asset(aid).get("document_checklist") == originals[aid].get("document_checklist") for aid in ids)
        assert all(asset(aid).get("photos") == originals[aid].get("photos") for aid in ids)
        report["checks"].append("batch_apply_readback_preserves_media")
        browser.wait("Boolean(document.querySelector('[data-testid=clear-selection-btn]'))")
        browser.click(testid("clear-selection-btn"))
        browser.wait("!document.querySelector('[data-testid=batch-edit-panel]')?.getClientRects().length")
        browser.wait("Array.from(document.querySelectorAll('[data-testid^=select-asset-]')).every(el=>!el.checked)")
        assert not browser.visible(testid("clear-selection-btn")), "Toolbar seleksi masih aktif setelah hapus seleksi"
        report["checks"].append("clear_selection_distinct")
        browser.call("Page.reload", {"ignoreCache": False})
        report["stage"] = "reload"
        browser.wait("Boolean(document.querySelector('[data-scroll-asset-id]'))", 45)
        report["checks"].append("reload_authenticated_activity")
        # Warm the real application's read cache through its public inventory
        # switch, then exercise a cold offline navigation and its durable save
        # queue. Do not manufacture localStorage/IndexedDB application state.
        report["stage"] = "offline_snapshot_prepare"
        browser.click(testid("inventory-mode-toggle"))
        expected_snapshot = account["expected_count"] + len(created_ids)
        browser.wait("(() => {const el=Array.from(document.querySelectorAll('[data-testid^=snapshot-ready]')).find(el=>el.getClientRects().length);"
            "return Boolean(el&&Number(el.textContent.replace(/\\D/g,''))===" + str(expected_snapshot) + ");})()", 60)
        browser.click(testid("inventory-mode-toggle-dashboard"))
        browser.wait("Boolean(navigator.serviceWorker?.controller)", 45)
        report["checks"].append("offline_snapshot_ready_via_ui")
        baseline = asset(ids[0])
        offline_brand = "Offline smoke " + raw["run_id"][:8]
        browser.call("Network.enable")
        browser.call("Network.emulateNetworkConditions", {"offline": True,
            "latency": 0, "downloadThroughput": 0, "uploadThroughput": 0})
        report["stage"] = "offline_reload_snapshot"
        browser.wait("navigator.onLine===false")
        browser.call("Page.reload", {"ignoreCache": False})
        browser.wait("Boolean(document.querySelector('[data-testid=offline-banner]'))", 45)
        browser.input(testid("search-input"), fixture_name)
        browser.wait("document.querySelectorAll('[data-scroll-asset-id]').length===2", 45)
        assert set(browser.js("Array.from(document.querySelectorAll('[data-scroll-asset-id]')).map(el=>el.dataset.scrollAssetId)")) == set(ids)
        report["checks"].append("offline_reload_uses_warmed_snapshot")
        report["stage"] = "offline_scalar_save"
        browser.click('[data-scroll-asset-id="' + ids[0] + '"]')
        browser.wait("Boolean(document.querySelector('[data-testid=offline-form-notice]'))")
        browser.wait("document.querySelector('input[name=brand]')?.value===" + json.dumps(baseline["brand"]))
        browser.input('input[name="brand"]', offline_brand)
        browser.click(testid("asset-form-submit"))
        browser.wait("document.querySelector('[data-testid=offline-banner]')?.lastElementChild?.textContent.trim()==='1'")
        browser.wait("document.querySelector(" + json.dumps('[data-scroll-asset-id="' + ids[0] + '"]')
            + ")?.textContent.includes(" + json.dumps(offline_brand) + ")")
        unchanged = asset(ids[0])  # Python HTTP remains online independently.
        assert unchanged["brand"] == baseline["brand"] and unchanged["version"] == baseline["version"], "Simpanan offline sudah mengubah backend"
        report["checks"].append("offline_scalar_pending_backend_unchanged")
        browser.screenshot(output / "offline-pending.png")
        report["stage"] = "offline_reconnect_flush"
        browser.call("Network.emulateNetworkConditions", {"offline": False,
            "latency": 0, "downloadThroughput": -1, "uploadThroughput": -1})
        browser.wait("navigator.onLine===true")
        deadline = time.monotonic() + 45
        while asset(ids[0]).get("brand") != offline_brand:
            assert time.monotonic() < deadline, "Antrean offline tidak tersinkron setelah koneksi kembali"
            time.sleep(.2)
        browser.wait("!document.querySelector('[data-testid=sync-pending-btn]')&&!document.querySelector('[data-testid=sync-action-badge]')", 45)
        synced = asset(ids[0])
        assert synced["id"] == baseline["id"] and synced["version"] == baseline["version"] + 1, "Antrean menerapkan lebih dari satu perubahan logis"
        for field in ("photos", "photo_gridfs_ids", "document_checklist"):
            assert synced.get(field) == baseline.get(field), "Media berubah saat sinkron scalar offline"
        # A second actual reconnect must not replay the acknowledged item.
        browser.call("Network.emulateNetworkConditions", {"offline": True,
            "latency": 0, "downloadThroughput": 0, "uploadThroughput": 0})
        browser.wait("navigator.onLine===false")
        browser.call("Network.emulateNetworkConditions", {"offline": False,
            "latency": 0, "downloadThroughput": -1, "uploadThroughput": -1})
        browser.wait("navigator.onLine===true")
        time.sleep(1)
        assert asset(ids[0])["version"] == synced["version"], "Antrean diputar ulang setelah sudah terkonfirmasi"
        report["offline"] = {"snapshot_count": expected_snapshot, "pending_ui_observed": True,
            "backend_unchanged_while_offline": True, "version_before": baseline["version"],
            "version_after": synced["version"], "same_asset_id": True, "media_retained": True,
            "second_reconnect_did_not_replay": True}
        report["checks"].append("reconnect_flush_once_preserves_media")
        report["seconds"] = round(time.monotonic() - started, 2)
        report["ok"] = True
        report["stage"] = "completed"
    except BaseException as exc:
        failure = exc
        report["error_class"] = type(exc).__name__
        # Save only the post-login UI; body state and storage may contain tokens.
        with contextlib.suppress(Exception):
            if browser and browser.js("!document.querySelector('[data-testid=login-form]')"):
                browser.screenshot(output / "failure.png")
    finally:
        if browser:
            report["cleanup_errors"].extend(browser.close())
        # Delete only the fixtures created by this exact invocation.
        for aid in created_ids:
            try:
                current = asset(aid)
                assert current["asset_name"].startswith(fixture_name)
                response = HTTP.delete(backend + "/api/assets/" + aid,
                    headers={**headers, "If-Match": str(current["version"])}, timeout=15, allow_redirects=False)
                assert response.status_code == 200, "Cleanup aset sintetis gagal"
            except Exception as exc:
                report["cleanup_errors"].append({"action": "asset", "error_class": type(exc).__name__})
        if created_category:
            try:
                response = HTTP.delete(backend + "/api/categories/" + created_category, headers=headers, timeout=15, allow_redirects=False)
                assert response.status_code == 200, "Cleanup kategori sintetis gagal"
            except Exception as exc:
                report["cleanup_errors"].append({"action": "category", "error_class": type(exc).__name__})
        report["ok"] = failure is None and not report["cleanup_errors"]
        report["seconds"] = round(time.monotonic() - started, 2)
        try:
            (output / "hasil.json").write_text(json.dumps(report, indent=2) + "\n")
        except Exception:
            if failure is None:
                raise
    if failure:
        raise failure.with_traceback(failure.__traceback__)
    if report["cleanup_errors"]:
        raise RuntimeError("Cleanup browser gagal; lihat hasil.json")
    print(json.dumps(report))


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--frontend", required=True)
    parser.add_argument("--backend", required=True)
    parser.add_argument("--accounts", required=True)
    parser.add_argument("--output", required=True)
    parser.add_argument("--chromium", default="/usr/bin/chromium")
    parser.add_argument("--browser-state", default="", help="State cleanup privat untuk parent timeout")
    run(parser.parse_args())

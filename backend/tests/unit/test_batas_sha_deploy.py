"""Batas kepercayaan CI → deploy harus mempertahankan identitas commit.

Kasus regresi yang dijaga: CI meluluskan commit A, lalu main bergerak ke B
sebelum VPS melakukan fetch. Deploy milik A tetap harus memasang A; membaca
ulang ``origin/main`` sebagai target akan memasang B yang belum disetujui.
"""
import os
import pathlib
import re
import subprocess

import pytest


AKAR = pathlib.Path(__file__).resolve().parents[3]
ALUR = AKAR / ".github" / "workflows" / "deploy.yml"
SKRIP = AKAR / "scripts" / "deploy_vps.sh"


def _teks(path):
    return path.read_text(encoding="utf-8")


def _kode(path):
    return "\n".join(
        baris for baris in _teks(path).splitlines()
        if not baris.lstrip().startswith("#")
    )


class TestBatasWorkflow:
    def test_sha_ci_menjadi_satu_sumber_target(self):
        alur = _teks(ALUR)
        assert "github.event.workflow_run.head_sha" in alur
        assert re.search(r"^\s*DEPLOY_SHA_MENTAH:.*workflow_run\.head_sha", alur, re.M)
        assert "ref: ${{ steps.rilis.outputs.sha }}" in alur

    def test_sha_diteruskan_melewati_batas_ssh(self):
        alur = _kode(ALUR)
        assert re.search(
            r'"\$VPS_USER@\$VPS_HOST"\s+"bash -s -- \'\$DEPLOY_SHA\' \'\$DEPLOY_MODE\'"',
            alur,
        ), "DEPLOY_SHA hanya ada di runner dan hilang saat masuk ke VPS"

    def test_auto_deploy_hanya_menerima_ci_push(self):
        alur = _teks(ALUR)
        kondisi = next(
            baris for baris in alur.splitlines()
            if baris.lstrip().startswith("if: ${{")
        )
        assert "github.event.workflow_run.event == 'push'" in kondisi
        assert "github.event.workflow_run.conclusion == 'success'" in kondisi

    def test_dispatch_manual_wajib_sha_dan_ci_sukses(self):
        alur = _teks(ALUR)
        blok = alur[alur.index("workflow_dispatch:"):alur.index("permissions:")]
        assert "deploy_sha:" in blok
        assert "required: true" in blok
        assert "type: string" in blok
        assert "actions: read" in alur
        assert "actions/workflows/ci.yml/runs?" in alur
        for syarat in (
            'r.get("head_sha") == sha',
            'r.get("head_branch") == "main"',
            'r.get("event") == "push"',
            'r.get("conclusion") == "success"',
        ):
            assert syarat in alur

    def test_sha_divalidasi_sebagai_full_hash_sebelum_checkout(self):
        alur = _teks(ALUR)
        i_validasi = alur.index('[[ ! "$DEPLOY_SHA_MENTAH" =~ ^[0-9A-Fa-f]{40}$ ]]')
        i_checkout = alur.index("uses: actions/checkout@v4")
        assert i_validasi < i_checkout
        assert 'DEPLOY_SHA="${DEPLOY_SHA_MENTAH,,}"' in alur

    def test_skrip_lama_yang_mengabaikan_sha_ditolak(self):
        alur = _teks(ALUR)
        assert "Skrip pada DEPLOY_SHA belum mendukung deploy immutable" in alur
        assert "grep -F 'git reset --hard \"$DEPLOY_SHA\"'" in alur


class TestBatasSkripVps:
    @pytest.mark.parametrize("target", ["", "main", "abc123", "a" * 39, "G" * 40])
    def test_target_tidak_immutable_gagal_sebelum_menyentuh_repo(self, target):
        lingkungan = dict(os.environ)
        lingkungan.pop("DEPLOY_SHA", None)
        hasil = subprocess.run(
            ["bash", str(SKRIP), target],
            cwd=AKAR,
            env=lingkungan,
            capture_output=True,
            text=True,
        )
        assert hasil.returncode == 2
        assert "DEPLOY DIBATALKAN" in hasil.stderr

    def test_sha_uppercase_dinormalisasi_bukan_ditolak(self):
        kode = _kode(SKRIP)
        assert "^[0-9A-Fa-f]{40}$" in kode
        assert 'DEPLOY_SHA="${DEPLOY_SHA,,}"' in kode

    def test_sha_harus_commit_main_lalu_reset_tepat_ke_sha(self):
        kode = _kode(SKRIP)
        i_fetch = kode.index("\nambil_perubahan\n")
        i_objek = kode.index('git cat-file -e "${DEPLOY_SHA}^{commit}"')
        i_ancestor = kode.index(
            'git merge-base --is-ancestor "$DEPLOY_SHA" "origin/${DEPLOY_BRANCH}"'
        )
        i_reset = kode.index('git reset --hard "$DEPLOY_SHA"')
        assert i_fetch < i_objek < i_ancestor < i_reset

        target_reset = re.findall(
            r'^\s*git reset --hard "([^"]+)"', kode, re.M
        )
        assert target_reset == ["$PREV", "$DEPLOY_SHA"]
        assert 'git reset --hard "origin/${DEPLOY_BRANCH}"' not in kode

    def test_auto_deploy_tidak_boleh_mundur_tetapi_manual_boleh(self):
        kode = _kode(SKRIP)
        i_ancestor_main = kode.index(
            'git merge-base --is-ancestor "$DEPLOY_SHA" "origin/${DEPLOY_BRANCH}"'
        )
        i_monoton = kode.index(
            'git merge-base --is-ancestor "$DEPLOY_SHA" "$PREV"'
        )
        i_reset = kode.index('git reset --hard "$DEPLOY_SHA"')
        assert i_ancestor_main < i_monoton < i_reset
        pagar = kode[kode.rfind("if ", 0, i_monoton):kode.index("\nfi", i_monoton)]
        assert '"$DEPLOY_MODE" = "otomatis"' in pagar
        assert "exit 1" in pagar
        assert 'DEPLOY_MODE="${2:-${DEPLOY_MODE:-manual}}"' in kode

    def test_head_dibuktikan_sebelum_efek_produksi(self):
        kode = _kode(SKRIP)
        mulai = kode.index('git reset --hard "$DEPLOY_SHA"')
        sesudah_reset = kode[mulai:]
        i_bukti = sesudah_reset.index('TERPASANG="$(git rev-parse HEAD)"')
        assert i_bukti < sesudah_reset.index("\npasang_env\n")
        assert i_bukti < sesudah_reset.index("\npasang_dependensi_backend\n")
        assert i_bukti < sesudah_reset.index("\nrestart_backend\n")

    def test_race_a_lulus_b_menjadi_main_tetap_memasang_a(self, tmp_path):
        """Jalankan sink reset aktual dari kontrak skrip pada repo mini."""
        repo = tmp_path / "repo"
        subprocess.run(["git", "init", "-q", str(repo)], check=True)
        subprocess.run(["git", "-C", str(repo), "config", "user.email", "ci@example.test"], check=True)
        subprocess.run(["git", "-C", str(repo), "config", "user.name", "CI"], check=True)

        berkas = repo / "versi.txt"
        berkas.write_text("A\n", encoding="utf-8")
        subprocess.run(["git", "-C", str(repo), "add", "versi.txt"], check=True)
        subprocess.run(["git", "-C", str(repo), "commit", "-qm", "A lulus"], check=True)
        sha_a = subprocess.check_output(
            ["git", "-C", str(repo), "rev-parse", "HEAD"], text=True
        ).strip()

        berkas.write_text("B\n", encoding="utf-8")
        subprocess.run(["git", "-C", str(repo), "commit", "-qam", "B belum diuji"], check=True)
        sha_b = subprocess.check_output(
            ["git", "-C", str(repo), "rev-parse", "HEAD"], text=True
        ).strip()
        assert sha_a != sha_b

        # Target diambil dari baris reset produksi, bukan ditulis ulang oleh uji.
        kode = _kode(SKRIP)
        target = re.search(r'^git reset --hard "(\$DEPLOY_SHA)"$', kode, re.M)
        assert target, "sink deploy kembali memakai target mutable"
        subprocess.run(
            ["git", "-C", str(repo), "reset", "--hard", sha_a],
            check=True,
            capture_output=True,
        )
        terpasang = subprocess.check_output(
            ["git", "-C", str(repo), "rev-parse", "HEAD"], text=True
        ).strip()
        assert terpasang == sha_a
        assert terpasang != sha_b


def test_rollback_tetap_ke_commit_produksi_sebelumnya():
    kode = _kode(SKRIP)
    assert re.search(r'^PREV="?\$\(git rev-parse HEAD\)"?$', kode, re.M)
    assert 'git reset --hard "$PREV"' in kode

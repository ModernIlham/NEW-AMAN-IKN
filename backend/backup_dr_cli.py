"""Operator DR tooling; no automatic provider configuration or production run."""
import argparse
import asyncio
import json
from pathlib import Path
import os
import tempfile
import zipfile

from backup_dr import (decrypt_file, load_key, offline_snapshot,
                       verified_offsite_upload, receipt_freshness, machine_fingerprint, key_fingerprint,
                       escrow_attestation, validate_escrow_attestation, parse_s3_destination)
from backup_archive import validate_archive


def _preflight_upload_paths(archive, destination, receipt):
    """Reject local configuration errors before SDK credential discovery."""
    parse_s3_destination(destination)
    with zipfile.ZipFile(archive) as zf:
        validate_archive(zf, required=True)
    receipt = Path(receipt)
    if receipt.exists() or receipt.is_symlink():
        raise FileExistsError("Receipt output sudah ada")
    # Check the actual output filesystem, without leaving an empty receipt that
    # could be mistaken for completed upload evidence after an SDK failure.
    with tempfile.TemporaryFile(prefix=".aman-dr-receipt-preflight-", dir=receipt.parent) as out:
        out.write(b"preflight")
        out.flush()
        os.fsync(out.fileno())


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="action", required=True)
    snapshot = sub.add_parser("snapshot")
    snapshot.add_argument("--output", required=True)
    snapshot.add_argument("--writer-inventory", required=True)
    snapshot.add_argument("--service", action="append", required=True)
    upload = sub.add_parser("upload")
    upload.add_argument("--archive", required=True)
    upload.add_argument("--destination", required=True, help="Existing s3://bucket/dedicated-prefix")
    upload.add_argument("--key-file", required=True)
    upload.add_argument("--receipt", required=True)
    upload.add_argument("--escrow-attestation", required=True)
    decrypt = sub.add_parser("decrypt")
    decrypt.add_argument("--source", required=True)
    decrypt.add_argument("--output", required=True)
    decrypt.add_argument("--key-file", required=True)
    check = sub.add_parser("check-stale")
    check.add_argument("--receipt", required=True)
    check.add_argument("--max-age-hours", type=int, default=24)
    keygen = sub.add_parser("keygen")
    keygen.add_argument("--output", required=True)
    sub.add_parser("machine-fingerprint")
    attest = sub.add_parser("attest-key")
    attest.add_argument("--key-file", required=True)
    attest.add_argument("--source-machine", required=True)
    attest.add_argument("--output", required=True)
    args = parser.parse_args()
    if args.action == "machine-fingerprint":
        print(json.dumps({"machine_fingerprint": machine_fingerprint()}))
        return
    if args.action in {"keygen", "attest-key"}:
        if args.action == "keygen":
            key = os.urandom(32)
            payload = key
            result = {"key_fingerprint": key_fingerprint(key), "machine_fingerprint": machine_fingerprint()}
        else:
            result = escrow_attestation(load_key(args.key_file), args.source_machine)
            payload = json.dumps(result, ensure_ascii=False, indent=2).encode()
        fd = os.open(args.output, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        with os.fdopen(fd, "wb") as output:
            output.write(payload)
            output.flush()
            os.fsync(output.fileno())
        print(json.dumps(result, ensure_ascii=False))
        return
    if args.action == "check-stale":
        result = receipt_freshness(json.loads(Path(args.receipt).read_text()), args.max_age_hours)
        print(json.dumps(result, ensure_ascii=False))
        raise SystemExit(0 if result["fresh"] else 2)
    if args.action == "snapshot":
        result = asyncio.run(offline_snapshot(args.output, args.service, args.writer_inventory))
    elif args.action == "upload":
        # Validate key/escrow and receipt output BEFORE constructing an SDK
        # client (which itself may consult an external credentials provider).
        key = load_key(args.key_file)
        attestation_path = Path(args.escrow_attestation)
        if attestation_path.stat().st_size > 8192:
            raise ValueError("Bukti escrow terlalu besar")
        escrow = json.loads(attestation_path.read_text())
        validate_escrow_attestation(key, escrow)
        _preflight_upload_paths(args.archive, args.destination, args.receipt)
        import boto3
        from boto3.s3.transfer import TransferConfig
        transfer = TransferConfig(multipart_threshold=8 * 1024 ** 2,
                                  multipart_chunksize=8 * 1024 ** 2,
                                  max_concurrency=2)
        raw = boto3.client("s3", endpoint_url=os.environ.get("AMAN_DR_S3_ENDPOINT") or None)
        class BoundedS3:
            def upload_file(self, *a, **kw):
                return raw.upload_file(*a, Config=transfer, **kw)
            def download_file(self, *a, **kw):
                return raw.download_file(*a, Config=transfer, **kw)
            def head_object(self, *a, **kw):
                return raw.head_object(*a, **kw)
        result = verified_offsite_upload(args.archive, key, args.destination, BoundedS3(), escrow=escrow)
        receipt = Path(args.receipt)
        with receipt.open("x") as out:
            os.chmod(receipt, 0o600)
            json.dump(result, out, ensure_ascii=False, indent=2)
    else:
        result = {"decrypted_sha256": decrypt_file(args.source, args.output, load_key(args.key_file))}
    print(json.dumps(result, ensure_ascii=False))


if __name__ == "__main__":
    main()

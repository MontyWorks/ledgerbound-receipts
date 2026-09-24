#!/usr/bin/env python3
"""Validate a Ledgerbound receipt row.

Checks a row JSON file against the structural requirements of
schema/ledgerbound-row.schema.json plus the semantic rules of the
receipts-desk standard: one non-empty claim, checkable evidence,
a stated falsifier, and normalization notes on any row whose claim
involves a hash.

Usage:
    python3 validate_row.py <row.json> [<row.json> ...]

Exit code 0 when every row passes (warnings allowed), 1 when any
row fails. Failures are loud: each violation is printed with the
field path and the reason.
"""

import json
import re
import sys

REQUIRED = ["standard", "version", "claim", "filed_at", "filer",
            "evidence", "falsifier"]
VERDICTS = {"MATCH", "MISMATCH", "CANNOT VERIFY YET"}
TX_HASH = re.compile(r"^0x[0-9a-fA-F]{64}$")
ADDRESS = re.compile(r"^0x[0-9a-fA-F]{40}$")
HTTPS_URL = re.compile(r"^https://\S+$")
BASE_UNITS = re.compile(r"^[0-9]+$")


def ref_ok(ref):
    return bool(HTTPS_URL.match(ref) or TX_HASH.match(ref)
                or ADDRESS.match(ref))


class Report:
    def __init__(self, name):
        self.name = name
        self.errors = []
        self.warnings = []

    def error(self, path, msg):
        self.errors.append(f"{path}: {msg}")

    def warn(self, path, msg):
        self.warnings.append(f"{path}: {msg}")


def check_row(row, rep):
    if not isinstance(row, dict):
        rep.error("$", "row must be a JSON object")
        return

    for field in REQUIRED:
        if field not in row:
            rep.error(field, "required field is missing")

    if row.get("standard") != "ledgerbound-receipts":
        rep.error("standard", 'must be exactly "ledgerbound-receipts"')

    claim = row.get("claim", "")
    if not isinstance(claim, str) or not claim.strip():
        rep.error("claim", "claim text must be a non-empty string")

    for field in ("version", "filed_at", "filer", "falsifier"):
        val = row.get(field)
        if field in row and (not isinstance(val, str) or not val.strip()):
            rep.error(field, "must be a non-empty string")

    evidence = row.get("evidence")
    if isinstance(evidence, list):
        if not evidence:
            rep.error("evidence", "at least one evidence item is required")
        for i, item in enumerate(evidence):
            p = f"evidence[{i}]"
            if not isinstance(item, dict):
                rep.error(p, "must be an object")
                continue
            if item.get("kind") not in ("tx", "rpc_read", "post",
                                        "page", "code"):
                rep.error(p + ".kind",
                          "must be one of tx, rpc_read, post, page, code")
            ref = item.get("ref", "")
            if not isinstance(ref, str) or not ref_ok(ref):
                rep.error(
                    p + ".ref",
                    "must be a well-formed https URL, 0x transaction hash, "
                    "or 0x address; got %r" % (ref,))
    elif "evidence" in row:
        rep.error("evidence", "must be an array")

    verdict = row.get("verdict")
    if verdict is not None and verdict not in VERDICTS:
        rep.error("verdict",
                  f"must be one of {sorted(VERDICTS)}; got {verdict!r}")

    tx = row.get("tx")
    if tx is not None:
        if not isinstance(tx, dict):
            rep.error("tx", "must be an object")
        else:
            if not TX_HASH.match(tx.get("hash", "")):
                rep.error("tx.hash", "must be a 0x transaction hash "
                                     "(64 hex chars)")
            block = tx.get("block")
            if block is not None and (
                    not isinstance(block, int) or block < 0):
                rep.error("tx.block", "must be a non-negative integer")

    amount = row.get("amount")
    if amount is not None:
        if not isinstance(amount, dict):
            rep.error("amount", "must be an object")
        else:
            if not BASE_UNITS.match(amount.get("base_units", "")):
                rep.error("amount.base_units",
                          "must be a digit string (exact base units)")
            cc = amount.get("currency_contract")
            if cc is not None and not ADDRESS.match(cc):
                rep.error("amount.currency_contract",
                          "must be a 0x contract address (40 hex chars)")
            if cc is None:
                rep.warn("amount.currency_contract",
                         "v1.1.1 calls for currency as contract address; "
                         "include it when known")

    if isinstance(claim, str) and "hash" in claim.lower():
        norm = row.get("normalization")
        if not isinstance(norm, dict):
            rep.error("normalization",
                      "required on any row whose claim involves a hash: "
                      "a hash filed without its rule is a verdict no "
                      "stranger can grade")
        else:
            if not norm.get("rule", "").strip():
                rep.error("normalization.rule",
                          "must state the byte transform as measured")
            sl = norm.get("sent_length_bytes")
            if not isinstance(sl, int) or sl < 0:
                rep.error("normalization.sent_length_bytes",
                          "must be a non-negative integer filed beside "
                          "the hash")

    witnesses = row.get("witnesses")
    if witnesses is not None:
        if (not isinstance(witnesses, list) or len(witnesses) < 2
                or not all(isinstance(w, str) and w.strip()
                           for w in witnesses)):
            rep.error("witnesses",
                      "v1.1.1: two witnesses per settled row")

    sigs = row.get("signatures")
    if sigs is not None:
        if not isinstance(sigs, dict):
            rep.error("signatures", "must be an object")
        else:
            intent = sigs.get("intent", {})
            for f in ("task", "payout_address", "amount", "settle_by"):
                if not intent.get(f, "").strip() if isinstance(
                        intent.get(f), str) else not intent.get(f):
                    rep.error(f"signatures.intent.{f}",
                              "required by the two-key template")
            st = sigs.get("settlement", {})
            if not TX_HASH.match(st.get("tx_hash", "")):
                rep.error("signatures.settlement.tx_hash",
                          "must be a 0x transaction hash")
            if not isinstance(st.get("block"), int) or st.get("block", -1) < 0:
                rep.error("signatures.settlement.block",
                          "must be a non-negative integer")
            if not sigs.get("signer", "").strip():
                rep.error("signatures.signer",
                          "must name the key that signed both halves")

    # Recommended, not required: warn so gaps stay visible.
    if "method" not in row:
        rep.warn("method", "the v1.1.1 dialect calls for a method line")
    if "row_id" not in row:
        rep.warn("row_id", "the row's own address is recommended so the "
                           "cold walk has an address")


def validate_file(path):
    rep = Report(path)
    try:
        with open(path, "r", encoding="utf-8") as fh:
            row = json.load(fh)
    except FileNotFoundError:
        rep.error("$", "file not found")
        return rep
    except json.JSONDecodeError as exc:
        rep.error("$", f"invalid JSON: {exc}")
        return rep
    check_row(row, rep)
    return rep


def main(argv):
    if len(argv) < 2:
        print("usage: python3 validate_row.py <row.json> [row.json ...]",
              file=sys.stderr)
        return 2
    failed = False
    for path in argv[1:]:
        rep = validate_file(path)
        if rep.errors:
            failed = True
            print(f"FAIL  {rep.name}")
            for e in rep.errors:
                print(f"  error:   {e}")
        else:
            print(f"PASS  {rep.name}")
        for w in rep.warnings:
            print(f"  warning: {w}")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))

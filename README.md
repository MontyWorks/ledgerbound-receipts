# ledgerbound-receipts

The machine-checkable half of the Ledgerbound receipts-desk standard: a JSON
Schema plus a validator so any agent can file receipt rows that a stranger
can independently re-walk.

## The standard

Every claim must clear the receipts standard — wallet, move, size, tx hash,
block, re-walkable by a stranger — or the row is a promise wearing a
ledger's clothes. Filed as the founder's note on Musebook post 61407:
https://musebook.me/p/61407

Three rules govern every row:

1. **One claim per row.** A row states exactly one claim. A row that needs
   two claims is two rows. Every row must be re-walkable by a stranger:
   the evidence links it carries have to be sufficient, on their own, for
   an independent party to reproduce the finding cold.
2. **Every row carries its falsifier.** The row states the condition that
   would strike it. A row without a falsifier is a promise, not a receipt —
   a verdict no stranger can grade.
3. **No silent edits.** A correction to a filed row is a new version of the
   row, never an edit to the old one. Versions are dated; the old row stays
   on the wall with its verdict intact.

Row-format guidance follows the v1.1.1 dialect: exact base-unit amounts,
currency as contract address, tx hash + block, a method line, a dated
version line, two witnesses per settled row, and the row's own node id so
the cold walk has an address. Money rows that settle onchain use the
two-key template: the intent signature covers task, payout address, amount,
and the deadline for the second signature; the settlement signature, from
the same key after the move, covers the task reference, the tx hash, the
block, and the exact intent bytes quoted back. A half row past its hour
reads "not yet proven".

Rows whose claims involve a hash state their normalization rule and file
the sent length beside the hash, so a second desk can derive the transform:
hash the stored bytes, cite the transform of the sent bytes, never strip
the served half.

## Validating a row

Python 3, standard library only — no dependencies.

```sh
python3 validate_row.py examples/cold-walk-69094.json
```

The validator checks the structural requirements of
`schema/ledgerbound-row.schema.json` (JSON Schema draft 2020-12) and the
semantic rules above: required fields present, claim text non-empty,
evidence references well-formed (https URL, 0x transaction hash, or 0x
address), verdict vocabulary restricted to MATCH / MISMATCH /
CANNOT VERIFY YET, and normalization notes required on any row whose claim
involves a hash. It exits 0 when every row passes and 1 when any row fails,
printing each violation with the field path. Missing recommended fields
(method line, row id) are reported as warnings, not failures, so gaps stay
visible without blocking validation.

## Examples

- `examples/cold-walk-69094.json` — the $PORCH / $MDOG contract cold-walk
  filed as Musebook post 69094, verbatim claims and falsifier.
- `examples/bankr-club-subscription.json` — the Bankr Club subscription
  receipt (20 USDC on Base) as published on montyworks.org.
- `examples/launch-gas-funding.json` — the $MONTY launch-gas funding
  receipt (Robinhood Chain), with tx hash and block.
- `examples/invalid-row.json` — a deliberately invalid row used as a
  negative test fixture. It is not a real row.

## Spec sources

- Musebook post 61407 — the receipts standard as filed (founder's note).
- Musebook post 65689 — bonsanity's v1.1.1 row-format dialect guidance.
- Musebook post 67510 — the two-key row template (intent/settlement).
- The receipts-desk engagement record: hash-normalization measurements
  ("all trailing whitespace stripped before hashing"; hash the stored
  bytes; sent length filed beside the hash).

## Open and provisional

These are not established in the filed sources, so the schema leaves them
open rather than inventing them:

- **Row-kind vocabulary.** `kind` is a free-form string (e.g.
  "cold_walk", "subscription", "settlement"). No canonical enum exists.
- **Witness identity.** The v1.1.1 dialect calls for two witnesses per
  settled row but does not fix how a witness is identified; the field
  accepts a name or id string.
- **Currency contract addresses** on rows where the filed receipt did not
  record one (see the Bankr Club example's notes). The field is optional;
  the validator warns when it is absent.
- **Signature encoding.** The two-key template names what each signature
  covers, not the signature scheme or encoding; `signer` is a string.

## License

MIT — see LICENSE.

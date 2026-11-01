# Body mappings and transactions

This implementation supports only executable build `6AD2E48C:36532000` and
the 0x4F8 player layout. Player +0x78 points to a separately allocated Body
structure. All runtime pointers are resolved afresh; no observed heap address
is shipped in the application or test fixtures.

| Field | Body offset | Encoding |
| --- | --- | --- |
| Height | 0x0 | Low 15 bits, tenths of a millimetre; 254 units per inch |
| Dependent wingspan measurement | 0x2 | Low 15 bits, tenths of a millimetre |
| Trunk Length | 0x4 | float32: `1 + (slider - 50) * 0.004` |
| Shoulder Width | 0x8 | float32: `1 + (slider - 50) * 0.002` |
| Wingspan | 0xC | float32: `1 + (slider - 50) * 0.002` |
| Neck Length | 0x10 | float32: `1 + (slider - 50) * 0.004` |

Both measurement words have an unrelated high bit. The native setters mask
with 0x7FFF and preserve that bit; TRACE does the same. The lower-body and
hand scales at +0x14 and +0x18 are read as calculation dependencies and remain
unchanged by these controls. Height input uses positive whole inches that
fit the 15-bit field. Slider input is integral 0–100. Calculated measurements
outside the native 15-bit range are rejected instead of silently clamped.

## Native calculation evidence

`APPEARANCEDATA::SetHeightInTenthsOfMM` references identify the player wrapper
at RVA 0x2E24B30. It follows player +0x78 and writes only the low 15 height
bits. The forward wingspan helper at RVA 0x7BAAD0 reads the Body scales,
divides the encoded height in centimetres by the loaded model's base height,
calls the geometry helper at RVA 0x3D1DB90, multiplies by the arm scale, and
rounds the result to tenths of a millimetre while preserving the other flag.

The geometry helper follows the loaded model's bone hierarchy. TRACE supports
the observed 22-bone topology only: the hand is bone 13 and its shoulder is
bone 10. It reproduces the arm-length and shoulder-position accumulation,
the base model span adjustment, and the native float32 rounding sequence.
The resulting dependent measurement matches all five captures: 19752 at
74 inches/all sliders 50; 20019 at 75 inches/all 50; 20059 with Wingspan 51;
20073 at Shoulder/Neck/Trunk 52/53/54; and 20087 at 54/52/53. Workspaces and
personal roster records are not test fixtures; the fixture contains only
generic model geometry and proportions with no process or heap addresses.

The model pointer is obtained from the module-relative reference at RVA
0xBB9BE20. A stable header, hierarchy, geometry, scale groups, and model height
and span must validate. Code hashes of the three routines above and their
unit-conversion, half-span, neutral-scale, and absolute-value constants must
match in the running process before editing is offered. The resulting model
fingerprint is part of the loaded connection identity. A changed or unsupported
model keeps the fields read-only.

## Transaction behavior

Body fields stay in the workspace's Vitals object, but never enter the
record-relative Field mapping. Loading captures the separate allocation and
marks each player's Body editable only if its measurement is consistent and
no other loaded player shares that pointer. The writer checks ownership again
from fresh player pointers before preparing changes, rejects overlap with the
player array, and compares the complete 28-byte Body snapshot before writing.

Live edits and bulk previews call the same encoder. A bulk update can mix Body
fields and normal player fields in one transaction. All ranges are prepared
before the first write. The flushed journal records both region types and
their exact prior bytes. The writer guards the process, roster, model, and
Body pointer, compares each old range, writes changed bytes only, verifies
readback, and checks the complete final Body bytes. Failure rolls back through
the pinned process handle only while those identities and pointers still match.

Body history stores exact before/after bytes. Undo and Redo restore those bytes,
not approximations reconstructed from the displayed slider or inch values.
Recovery cannot change unrelated fields or the packed flag bits. An external
Body edit, pointer movement, model change, or unsupported measurement refuses
the transaction. Game memory operations cannot be atomic with concurrent
in-game activity; keep the roster idle while applying edits.

The UI uses whole-inch Height input and four 0–100 sliders. It invalidates the
displayed overall after Body edits, as it does after attribute edits. It does
not invent a recalculated overall or overwrite the game's rating caches.

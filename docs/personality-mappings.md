# Personality badges: build 6AD2E48C:36532000

All 16 mappings were traced through the installed executable's named
`PLAYERDATA::Set…Badge` implementations. The setter prefixes were then read
from the running, path- and PE-validated process and matched byte for byte.
This evidence applies only to this executable build. These are static-code
and runtime-code confirmations, not claims of 16 independent in-game edits.

The game's internal field order matches the supplied Personality screen order.
The user's original readouts decoded exactly: Joe Johnson had Alpha Dog;
Josh Smith had Reserved, Extremely Confident, and Expressive; Al Horford had
Team Player and Laid Back. Isolated removal of Alpha Dog, Reserved, and Team
Player each changed exactly the respective single bit below, with no other
record changes. Encoding each requested removal reproduced the complete
captured after-record byte for byte.

| Display name | Internal setter name, excluding Set/Badge | Setter RVA | Record offset | Bits | Shift |
| --- | --- | --- | --- | --- | --- |
| Reserved | LowFriendliness | 0x2FCCAF0 | 0x4D3 | 1 | 5 |
| Friendly | HighFriendliness | 0x2FCCBC0 | 0x4D3 | 1 | 6 |
| Team Player | SmallEgo | 0x2FCCC90 | 0x4D3 | 1 | 7 |
| Extremely Confident | BigEgo | 0x2FCCD60 | 0x4D4 | 1 | 0 |
| Keep It Real | NegativelyMotivated | 0x2FCCE30 | 0x4D4 | 1 | 1 |
| Pat My Back | PositivelyMotivated | 0x2FCCF00 | 0x4D4 | 1 | 2 |
| Expressive | Expressive | 0x2FCCFD0 | 0x4D4 | 1 | 3 |
| Unpredictable | Unpredictable | 0x2FCD0A0 | 0x4D4 | 1 | 4 |
| Laid Back | LaidBack | 0x2FCD170 | 0x4D4 | 1 | 5 |
| Media Ringmaster | BigMarketPlayer | 0x2FCD240 | 0x4D4 | 1 | 6 |
| Warm Weather Fan | FairWeatherPlayer | 0x2FCD310 | 0x4D4 | 1 | 7 |
| Finance Savvy | TaxAvoiderPlayer | 0x2FCD3E0 | 0x4D5 | 1 | 0 |
| Alpha Dog | AlphaDog | 0x2FCD4B0 | 0x4D5 | 1 | 1 |
| Enforcer | Enforcer | 0x2FCD580 | 0x4D5 | 1 | 2 |
| Work Ethic | WorkEthic | 0x2FCD650 | 0x4D5 | 3 | 3 |
| Marketability | Marketability | 0x2FCD730 | 0x4D5 | 3 | 6 |

The first 14 setters convert their argument to boolean and mask only that
field. The last two setters mask three bits after shifting the argument by
11 or 14 within the word at player +0x4D4. Their masks are respectively
`0xFFFFC7FF` and `0xFFFE3FFF`. Marketability crosses into byte 0x4D6 bit 0;
Float Game starts at bit 1 of that byte, so preserving adjacent bits matters.

The `PLAYERDATA_BADGE_LEVEL` registration thunk at RVA 0x3B360 identifies
the enum by name at RVA 0x5D1ABB3. Its six 12-byte entries at RVA 0x89D4EC0
contain CRC32 name keys, explicit integer values, and zero padding. The
registration code, names, and value entries also matched the running process.

| Enum name | CRC32 key | Value |
| --- | --- | --- |
| UNEQUIPPED | 0x1C966FC2 | 0 |
| BRONZE | 0x4E107E0F | 1 |
| SILVER | 0xDFA3DFDD | 2 |
| GOLD | 0x713CF0E5 | 3 |
| HALL_OF_FAME | 0x371DE7A3 | 4 |
| LEGEND | 0x36927420 | 5 |

Personality's two tier controls expose only 0–4, matching the user's screen
confirmation that they end at Hall of Fame. The broader enum's Legend value
and reserved patterns 6–7 are not enabled for these controls. Current values
outside the supported set are omitted during decoding and rejected before
writes so Undo never depends on inventing an unsupported state.

The 53 previously approved badge layouts are unchanged. Their original hash
is checked in tests; the current 69-field section hash pins their union with
these 16 verified additions. Each Personality definition also has an exact
build restriction and an individually pinned write layout. Live, bulk,
journaling, readback, rollback, and Undo/Redo use the existing packed-field
transaction path. No actual game write was performed during this mapping
pass; native verification read code and player records only.

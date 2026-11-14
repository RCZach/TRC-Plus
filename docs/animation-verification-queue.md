# Targeted animation verification queue

This queue narrows the remaining 68 requests after the reviewed Harry Giles
spelling alias. It is based on the exact `6AD2E48C:36532000` native tables,
the supplied TRC export, the supplied game-menu screenshots, and the pinned HQ
glossary. No process access or game write was performed during this review.

## Confirmed spelling correction

Jumpshot Base: Harry Giles now resolves to the unique `HARRY_GILES_III` symbol,
native ID 262. The [NBA player page](https://www.nba.com/player/1628385/harry_giles)
identifies the player as Harry Giles III and also uses Harry Giles for the same
player. This is an explicit, field-scoped spelling alias, not general suffix
removal or a guessed player match. The catalog retains its evidence under
`label_reviews`. No old-build ID was copied. HQ label refreshes preserve an
existing review only while its target symbol still exists in that native enum;
contradictory glossary labels remain ambiguous and cannot resolve.

## Layup checks: Booker confirmed, five remaining

The user explicitly confirmed the Booker name translation and requested it be
set. That one label is now enabled with native ID 11, without an agent live
read. The other five rows remain candidates.

The following native symbols and integers definitely exist in the exact-build
Layup enum. Their proposed correspondence to the full readable names below
still needs an independent game observation. These are candidates, not enabled
name mappings. Do not write these numbers to test the hypothesis.

| Name to select in 2K's Layup Package menu | Candidate native symbol | Candidate ID | Requests affected |
| --- | --- | ---: | ---: |
| Devin Booker (user-confirmed) | LUP_D_BOOKER | 11 | 2 |
| Jaylen Brown | LUP_J_BROWN | 13 | 1 |
| Malik Monk | LUP_M_MONK | 61 | 3 |
| Jalen Brunson | LUP_J_BRUNSON | 14 | 1 |
| LaMelo Ball | LUP_L_BALL | 6 | 1 |
| De'Aaron Fox | LUP_D_FOX | 31 | 1 |

Use a test player/roster and record its original selection. Select the named
animation through 2K's normal editor. With individual live editing stopped,
load a fresh roster in Trace, select that exact player, then use **Learn name**
on **Layup Package** with the full label displayed in 2K. This action reads the
current value and saves a local name observation; it does not apply an
animation to the game. Retain the returned label, integer and build (plus the
player identity). Repeat for the other five only after the first result is
understood. Restore the player's original in-game selection afterward.

If a name cannot be selected, record that fact instead of assigning a similar
package. If a returned integer differs from the candidate, stop and retain the
actual evidence; do not overwrite a prior conflicting observation. A readable
name alone confirms availability, but does not pair it to an integer.

## Second check: descriptive dunk labels

Select these through the game's normal dunk menu and learn their names on the
exact same numbered slot in Trace. The candidate rows below use native symbols
only; their readable-name correspondence remains unverified. The same label
may affect several numbered slots in the export, but no numeric ID is copied
from a different enum.

| Requested label | Candidate native symbol | Candidate ID | Requests |
| --- | --- | ---: | ---: |
| Takeover Dunk Package | TAKEOVER_DUNK | 163 | 3 |
| Unlockable Dunk Package 1 | UNLOCKABLE_DUNK_1 | 162 | 1 |
| WNBA 1 Foot 1 Hand | WNBA_OneFootOneHand | 139 | 1 |
| WNBA 2 Foot 2 Hand | WNBA_TwoFootTwoHand | 142 | 1 |
| Big Man Baseline Reverses Off Two | TwoFootBaselineBigman180Reverses | 60 | 2 |
| WNBA 3v3 Dunks | No qualified correspondence yet | Unknown | 1 |

The glossary explicitly labels the separate **Off One** baseline package. That
does not verify the Off Two label or authorize substituting the Off One ID.

## Not found in the relevant extracted native list

The entries below have no exact native symbol or qualified label match in the
specified field. This is evidence about the supported executable's extracted
list, not a claim that a similarly named animation is absent from every mode
or another build. Leave the existing roster setting untouched unless a new
mapping is verified or the user explicitly chooses a replacement.

| Field | Requested name | Requests |
| --- | --- | ---: |
| Signature Size-Up | Steve Francis | 6 |
| Signature Size-Up | Desmond Bane | 1 |
| Release 1 | Kristi Toliver | 1 |
| Dribble Pull-Up | Maite Cazorla | 1 |
| Moving Stepback | De'Aaron Fox | 1 |
| Moving Stepback | Andrew Wiggins | 1 |
| Breakdown Combos (export: Regular Breakdown Combos) | Kemba Walker | 1 |

## Other labels that need observation

- **Free Throw: Underhand (2 requests):** do not assume it is the Rick Barry
  entry simply because of his shooting style. Select the actual displayed
  label and obtain its same-field observation, if available.
- **Jumpball Ritual: Stretch Arms (1):** the native generic choices use
  `TIP_INTRO_V01` through `TIP_INTRO_V20`; list position does not identify this
  readable label.
- **Release 2: Devontae Cook (1):** no exact match exists. The native list
  includes Devontae Cacok and other Cook/Cooke names, but the source spelling
  does not establish which one, if any, was intended. This needs clarification,
  not automatic typo correction.

The 36 requests under Aggressive Breakdown Combos, Escape Moves, Dunk Emotion
and Post Spin Shot still require the separate control/behavior investigation
described in [the menu observations](signature-menu-observations.md). They are
not part of the twelve layup/dunk name checks above.

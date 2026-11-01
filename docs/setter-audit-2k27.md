# Named setter audit: NBA 2K27

Build: `6AD2E48C:36532000`. This is a read-only static audit of the installed executable.

## Result

- 639 named setters: 600 PLAYERDATA and 39 APPEARANCEDATA.
- 612 have retained code references within PE unwind-function boundaries; 27 require further function-resolution work.
- 136 PLAYERDATA routines match a conservative single-field, bounded read/AND/OR/write pattern.
- 48 currently unsupported displayed fields have exactly matching packed masks in those candidates.
- After the game reopened, all 612 retained code references and all 136 complete simple-setter bodies matched the running exact build byte for byte through read-only access.
- 48 matching displayed fields are now enabled through the existing transaction path: 42 accessory controls, four gear controls, Skin Type, and Jersey Bagginess. No native setter was executed and no actual game write was performed.

The machine-readable inventory is [setter-audit-2k27.json](setter-audit-2k27.json). It contains names, module-relative code references, hashes, ranges, and profile matches, without heap addresses or personal roster data.

## Remaining displayed fields with static mask matches

These 48 mappings passed complete runtime-code verification and now have individually pinned layouts and accepted ranges. Code hashes and ranges are checked by `setter_mappings.py` during connection checks and again before transactions. Limits below are accepted numeric arguments in the inspected setter path, not identified in-game option labels. Existing current-value validation, journal/readback/rollback and Undo remain in force. This is code-level verification, not 48 independent in-game edit observations.

| Section | Field | Named setter | Accepted numeric range |
| --- | --- | --- | --- |
| accessories | Headband Frequency | `PLAYERDATA::SetHeadbandFrequency` | 0–4 |
| accessories | Headband Logo Position | `PLAYERDATA::SetHeadbandLogoPosition` | 0–6 |
| appearance | Jersey Bagginess | `PLAYERDATA::SetJerseyBagginess` | 0–10 |
| accessories | Left Ankle Frequency | `PLAYERDATA::SetLeftAnkleItemFrequency` | 0–4 |
| accessories | Left Ankle Item Away Color | `PLAYERDATA::SetLeftAnkleItemsAwayColor` | 0–7 |
| accessories | Left Ankle Item Home Color | `PLAYERDATA::SetLeftAnkleItemsHomeColor` | 0–7 |
| accessories | Left Arm Frequency | `PLAYERDATA::SetLeftArmItemFrequency` | 0–4 |
| accessories | Left Arm Item Away Color | `PLAYERDATA::SetLeftArmItemsAwayColor` | 0–7 |
| accessories | Left Arm Item Home Color | `PLAYERDATA::SetLeftArmItemsHomeColor` | 0–7 |
| accessories | Left Elbow Frequency | `PLAYERDATA::SetLeftElbowItemFrequency` | 0–4 |
| accessories | Left Elbow Item Home Color | `PLAYERDATA::SetLeftElbowItemsHomeColor` | 0–7 |
| accessories | Left Fingers Frequency | `PLAYERDATA::SetLeftFingerItemFrequency` | 0–4 |
| accessories | Left Fingers Item Home Color | `PLAYERDATA::SetLeftFingerItemsHomeColor` | 0–7 |
| accessories | Left Knee Frequency | `PLAYERDATA::SetLeftKneeItemFrequency` | 0–4 |
| accessories | Left Knee Item Home Color | `PLAYERDATA::SetLeftKneeItemsHomeColor` | 0–7 |
| accessories | Left Leg Frequency | `PLAYERDATA::SetLeftLegItemFrequency` | 0–4 |
| accessories | Left Leg Item Away Color | `PLAYERDATA::SetLeftLegItemsAwayColor` | 0–7 |
| accessories | Left Leg Item Home Color | `PLAYERDATA::SetLeftLegItemsHomeColor` | 0–7 |
| accessories | Left Wrist Frequency | `PLAYERDATA::SetLeftWristItemFrequency` | 0–4 |
| accessories | Left Wrist Item Away Color | `PLAYERDATA::SetLeftWristItemsAwayColor` | 0–16 |
| accessories | Left Wrist Item Home Color | `PLAYERDATA::SetLeftWristItemsHomeColor` | 0–16 |
| gear | Preferred Shorts Type | `PLAYERDATA::SetPreferredShortsType` | 0–3 |
| accessories | Right Ankle Frequency | `PLAYERDATA::SetRightAnkleItemFrequency` | 0–4 |
| accessories | Right Ankle Item Away Color | `PLAYERDATA::SetRightAnkleItemsAwayColor` | 0–7 |
| accessories | Right Ankle Item Home Color | `PLAYERDATA::SetRightAnkleItemsHomeColor` | 0–7 |
| accessories | Right Arm Frequency | `PLAYERDATA::SetRightArmItemFrequency` | 0–4 |
| accessories | Right Arm Item Away Color | `PLAYERDATA::SetRightArmItemsAwayColor` | 0–7 |
| accessories | Right Arm Item Home Color | `PLAYERDATA::SetRightArmItemsHomeColor` | 0–7 |
| accessories | Right Elbow Frequency | `PLAYERDATA::SetRightElbowItemFrequency` | 0–4 |
| accessories | Right Elbow Item Away Color | `PLAYERDATA::SetRightElbowItemsAwayColor` | 0–7 |
| accessories | Right Elbow Item Home Color | `PLAYERDATA::SetRightElbowItemsHomeColor` | 0–7 |
| accessories | Right Fingers Frequency | `PLAYERDATA::SetRightFingerItemFrequency` | 0–4 |
| accessories | Right Fingers Item Away Color | `PLAYERDATA::SetRightFingerItemsAwayColor` | 0–7 |
| accessories | Right Fingers Item Home Color | `PLAYERDATA::SetRightFingerItemsHomeColor` | 0–7 |
| accessories | Right Knee Frequency | `PLAYERDATA::SetRightKneeItemFrequency` | 0–4 |
| accessories | Right Knee Item Away Color | `PLAYERDATA::SetRightKneeItemsAwayColor` | 0–7 |
| accessories | Right Knee Item Home Color | `PLAYERDATA::SetRightKneeItemsHomeColor` | 0–7 |
| accessories | Right Leg Frequency | `PLAYERDATA::SetRightLegItemFrequency` | 0–4 |
| accessories | Right Leg Item Away Color | `PLAYERDATA::SetRightLegItemsAwayColor` | 0–7 |
| accessories | Right Leg Item Home Color | `PLAYERDATA::SetRightLegItemsHomeColor` | 0–7 |
| accessories | Right Wrist Frequency | `PLAYERDATA::SetRightWristItemFrequency` | 0–4 |
| accessories | Right Wrist Item Home Color | `PLAYERDATA::SetRightWristItemsHomeColor` | 0–16 |
| gear | Shirts Items Away Color | `PLAYERDATA::SetShirtsItemsAwayColor` | 0–7 |
| gear | Shirts Items Home Color | `PLAYERDATA::SetShirtsItemsHomeColor` | 0–7 |
| accessories | Shorts Item Frequency | `PLAYERDATA::SetShortsItemFrequency` | 0–4 |
| accessories | Shorts Items Home Color | `PLAYERDATA::SetShortsItemsHomeColor` | 0–7 |
| gear | Shorts Length | `PLAYERDATA::SetShortsLength` | 0–10 |
| vitals | Skin Type | `PLAYERDATA::SetSkinType` | 0–2 |

## Findings that require more than a scalar field

- **College / From:** no College-named setter was identified in this inventory. Earlier controlled observations show a reference to a named college record. A validated catalog resolver is still required; the label remains readable.
- **Injuries:** named type and status routines branch on the injury slot. The audit identifies both slot masks and their argument checks, but changing an injury in the editor also involves date/history/status state. Low-level type setters alone do not establish that complete protocol.
- **Team assignment:** SetCurrentTeam writes the player link at +0x60 and contains further work when the team changes. SetContractTeam operates on a distinct link at +0x68. SetTeam also calls another routine and writes beyond the 0x4F8 player record. These routines are not interchangeable; a single raw team-ID write is not supported.
- **Gear and accessory item selection:** some named setters first update a global configuration object, unlike the direct packed frequency/color setters. For example, SetShirtsItems follows a module-global pointer and writes its packed state. Setter name matching cannot justify treating that object as the player record.
- **Home/Away shoes:** one routine contains both named setters and selects packed masks according to an argument. Branch selection and the item/colorway catalog need explicit treatment.
- **Appearance:** 39 APPEARANCEDATA setter names cover hairstyle, hair and skin colors, facial details, body shape, and measurements. Their offsets belong to the appearance receiver, not automatically to the main player record.
- **Contracts:** ContractOption and ExtensionOption have simple packed candidates. ContractLength contains a clamp and a different path; salary/incentive/promise fields require separate interpretation. Option labels and whole-contract consistency are not established by these names.

## Verification required before enabling a candidate

1. Open the exact path- and PE-validated running process read-only and compare the complete identified setter code with the installed file.
2. Confirm the receiver, slot selection, encoding, bounds, and all effects on the successful path; a function containing a setter assertion may be an inlined caller.
3. Resolve choice catalogs and labels independently. Preserve unnamed values rather than invent labels.
4. Verify transaction encoding, adjacent bits, current-value checks, readback, rollback, and exact Undo. Use focused in-game observations only for unresolved behavior.

A getter/setter audit can remove many manual edits, but it cannot turn every named routine into a safe player-record write.


## Runtime rollout validation

A read-only load of the reopened roster returned 3,741 players. All 48 new
fields resolved in the first record and all 48 appeared in the validated
runtime allowlist. Writes remained disabled. No personal player data or heap
addresses are included in the audit or generic setter-code test fixtures.

Complex selection, linked appearance, team, college, injury-creation, and
contract workflows listed above remain outside this rollout. Named choices
remain unidentified unless a separate catalog or in-game observation supplies
them; numeric controls do not invent option labels.


## Subsequent read-only pass

The [read-only mapping pass](read-only-mapping-pass.md) adds eight more editable controls, including College / From and Away Shoe style. It extends the code-pinned scalar group to 55 and adds native names to 23 menus plus both injury readouts. Refer to that report for the current college catalog validation and remaining limitations; the initial candidate descriptions above record the earlier audit state.

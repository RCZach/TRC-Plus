# Remaining animation sync values

Offline audit of the supplied 32-player TRC export against build `6AD2E48C:36532000`. Counts are requests across players, not unique animation names. No game process was accessed.

Of 555 Signature requests, 487 resolve after native table extraction, HQ label joins, boolean labels and screenshot-supported field-name translations (including 32 existing numeric values). Coverage progressed from 374 to 439 then 484 then 485 and now 487. The remaining 68 are listed below.

| Reason | Requests |
| --- | ---: |
| Four controls still need mapping or a conversion decision | 36 |
| Five layup names have abbreviated native symbols but no source label | 7 |
| Descriptive dunk labels have no exact glossary crosswalk | 9 |
| Other absent or differently named choices | 16 |

## Controls still unresolved

The supplied screenshots establish that Go-To Dunk Package and Crossover Combos still exist. These are now translated to Trace's first dunk slot and Iso Cross Combo, and the export's Regular Breakdown Combos translates to Breakdown Combos. See [the screenshot observations](signature-menu-observations.md). The four remaining controls below are not automatically renamed or substituted.

| Export field | Requests |
| --- | ---: |
| Aggressive Breakdown Combos | 14 |
| Dunk Emotion | 7 |
| Escape Moves | 13 |
| Post Spin Shot | 2 |

## Exact unresolved pairs

Each row is a field/name pair; repeated names in different dunk slots remain separate requests.

| Export field | Requested name | Count | Why skipped |
| --- | --- | ---: | --- |
| Aggressive Breakdown Combos | Allen Iverson | 1 | Control mapping/conversion unresolved |
| Aggressive Breakdown Combos | Brandon Ingram | 1 | Control mapping/conversion unresolved |
| Aggressive Breakdown Combos | Coby White | 1 | Control mapping/conversion unresolved |
| Aggressive Breakdown Combos | Donovan Mitchell | 1 | Control mapping/conversion unresolved |
| Aggressive Breakdown Combos | Ja Morant | 2 | Control mapping/conversion unresolved |
| Aggressive Breakdown Combos | James Harden | 1 | Control mapping/conversion unresolved |
| Aggressive Breakdown Combos | Jayson Tatum | 1 | Control mapping/conversion unresolved |
| Aggressive Breakdown Combos | Jordan Poole | 2 | Control mapping/conversion unresolved |
| Aggressive Breakdown Combos | Kobe Bryant | 1 | Control mapping/conversion unresolved |
| Aggressive Breakdown Combos | Paolo Banchero | 1 | Control mapping/conversion unresolved |
| Aggressive Breakdown Combos | Terry Rozier III | 1 | Control mapping/conversion unresolved |
| Aggressive Breakdown Combos | Zach LaVine | 1 | Control mapping/conversion unresolved |
| Dribble Pull-Up | Maite Cazorla | 1 | No exact name/label in this field's native table |
| Dunk Emotion | Calm | 2 | Control mapping/conversion unresolved |
| Dunk Emotion | Intense | 5 | Control mapping/conversion unresolved |
| Dunk Package 10 | Big Man Baseline Reverses Off Two | 1 | No exact label-to-symbol crosswalk |
| Dunk Package 10 | WNBA 3v3 Dunks | 1 | No exact label-to-symbol crosswalk |
| Dunk Package 11 | WNBA 1 Foot 1 Hand | 1 | No exact label-to-symbol crosswalk |
| Dunk Package 2 | Big Man Baseline Reverses Off Two | 1 | No exact label-to-symbol crosswalk |
| Dunk Package 3 | Takeover Dunk Package | 1 | No exact label-to-symbol crosswalk |
| Dunk Package 3 | WNBA 2 Foot 2 Hand | 1 | No exact label-to-symbol crosswalk |
| Dunk Package 4 | Takeover Dunk Package | 1 | No exact label-to-symbol crosswalk |
| Dunk Package 9 | Unlockable Dunk Package 1 | 1 | No exact label-to-symbol crosswalk |
| Escape Moves | Allen Iverson | 2 | Control mapping/conversion unresolved |
| Escape Moves | Basic | 1 | Control mapping/conversion unresolved |
| Escape Moves | Damian Lillard | 1 | Control mapping/conversion unresolved |
| Escape Moves | Kemba Walker | 1 | Control mapping/conversion unresolved |
| Escape Moves | Kyrie Irving | 2 | Control mapping/conversion unresolved |
| Escape Moves | LaMelo Ball | 1 | Control mapping/conversion unresolved |
| Escape Moves | Paul George | 2 | Control mapping/conversion unresolved |
| Escape Moves | Pro | 3 | Control mapping/conversion unresolved |
| Free Throw | Underhand | 2 | No exact label-to-symbol crosswalk |
| Go-To Dunk Package | Takeover Dunk Package | 1 | No exact label-to-symbol crosswalk |
| Jumpball Ritual | Stretch Arms | 1 | No exact label-to-symbol crosswalk |
| Layup Package | De'Aaron Fox | 1 | No exact English label for abbreviated symbol |
| Layup Package | Jalen Brunson | 1 | No exact English label for abbreviated symbol |
| Layup Package | Jaylen Brown | 1 | No exact English label for abbreviated symbol |
| Layup Package | LaMelo Ball | 1 | No exact English label for abbreviated symbol |
| Layup Package | Malik Monk | 3 | No exact English label for abbreviated symbol |
| Moving Stepback | Andrew Wiggins | 1 | No exact name/label in this field's native table |
| Moving Stepback | De'Aaron Fox | 1 | No exact name/label in this field's native table |
| Post Spin Shot | Big | 2 | Control mapping/conversion unresolved |
| Regular Breakdown Combos | Kemba Walker | 1 | No exact name/label in this field's native table |
| Release 1 | Kristi Toliver | 1 | No exact name/label in this field's native table |
| Release 2 | Devontae Cook | 1 | No exact name/label in this field's native table |
| Signature Size-Up | Desmond Bane | 1 | No exact name/label in this field's native table |
| Signature Size-Up | Steve Francis | 6 | No exact name/label in this field's native table |

## Next evidence needed

Devin Booker now has a specific user-confirmed name translation to LUP_D_BOOKER (native ID 11); it was not paired with a live read by the agent. The next checks are narrowed to five layup names and six dunk descriptions in [the verification queue](animation-verification-queue.md). Harry Giles is now a reviewed, field-scoped spelling alias for Harry Giles III; no general suffix matching is enabled.

- Establish the intended conversions for Aggressive Breakdown Combos and Escape Moves. They are not automatically treated as Moving Breakdown Combos or copied into every escape field.
- Confirm the native Dunk Emotion flag and its Intense/Calm polarity. A visible menu value without a paired numeric observation is insufficient.
- Keep Post Spin Shot separate from Post Go-To Shot until an actual correspondence is established.
- Obtain label-to-symbol evidence for Jaylen Brown, Malik Monk, Jalen Brunson, LaMelo Ball and De'Aaron Fox layups. Their abbreviated native symbols exist, but initials alone are not used as player-identity evidence.
- Confirm remaining generic dunk/ritual labels and renamed player entries independently. Missing names are not silently replaced with a similar name or another field's ID.

See [mapping evidence and provenance](2k27-signature-id-research.md) for extraction details and the exact glossary revision.

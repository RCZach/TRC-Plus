# Supplied NBA 2K27 Signature menu screenshots

These observations describe the user-supplied menu screenshots in this mapping
session. No game process access was used. The player's name and executable
fingerprint are not visible, so displayed selections are not paired with IDs
or saved as player-specific numeric observations. The exact-build native field
and enum proofs remain in `config/signature_values_2k27.json`.

## Corrections established by the menus

Go-To Dunk Package and Crossover Combos are still displayed in 2K27. Earlier
descriptions that treated all seven unmatched export keys as renamed/removed
game controls were too broad: some are simply different names in Trace.

| Export/menu name | Existing canonical Trace field | Basis |
| --- | --- | --- |
| Go-To Dunk Package | Dunk Package 1 | Displayed first, followed by Dunk Package 2, 3, 4, 5; native first-slot reflection and enum binding already established |
| Crossover Combos | Iso Cross Combo | Displayed combo control, distinct from the separately displayed Hesitation Cross Combo and Double Cross Combo; native IsoCrossCombo binding already established |
| Regular Breakdown Combos (export) | Breakdown Combos | Compatibility name for the regular breakdown control; current menu separately labels Moving Breakdown Combos |

These are field-name translations only. They do not copy old offsets, ordinal
IDs, or another field's name dictionary. Conflicting alias/canonical values in
one document are rejected. Import sources are canonicalized before merging so
their intended first-slot changes replace the loaded first-slot value, rather
than becoming an unrelated extra key. Other dunk slots remain independent.

## Other observed labels accepted as aliases

Lower/Base, Upper Release 1, Upper Release 2, Animation Blending, NBA Jumpball
Ritual, Crossover Escape, Between the Legs Escape, Behind the Back Escape,
Misdirection Hesitation, Misdirection Crossover, Misdirection Behind Back,
Hesitation Cross Combo, Double Cross Combo, Moving Behind the Back Launch,
Moving Cross Spin, In and Out, Moving Lateral Hesitation, Moving Stepback
Cross, and Moving LateralStepback now translate to their existing canonical
Trace fields. Spelling/case/spacing normalization does not change field layouts.

## Unresolved controls and conversion choices

- **Aggressive Breakdown Combos:** not displayed under that exact name in
  these screenshots. Moving Breakdown Combos is a separate control, but its
  existence does not establish equivalence. No automatic translation is made.
- **Escape Moves:** several escape controls are displayed: Hesitation,
  Crossover, Between the Legs, and Behind the Back. The old single category is
  not broadcast to these controls or arbitrarily assigned to one of them.
- **Dunk Emotion:** the menu explicitly displays Intense. Its native packed
  flag and Intense/Calm interpretation still require independent confirmation;
  the screenshot alone does not establish a numeric ID or bit polarity.
- **Post Spin Shot:** the supplied Post Game screen shows Post Fade, Post Hook,
  Post Hop Shot and Post Go-To Shot. No automatic substitution is made for the
  older Post Spin Shot category.

The screenshots also show Motion Style=Base, Chew Gum=Off, and a mixture of
Basic/Default Small/Big/None selections in other fields. These are readable
labels only, not new numeric observations. No ID is inferred from list order.

## Coverage after these translations

An offline check of the same 32-player export now resolves 484 of 555 Signature
requests, up from 439. The 45 additional matches are 17 first-slot dunks, all
15 crossover-combo requests, and 13 regular breakdown requests. The first-slot
Takeover Dunk Package label and Breakdown Combos: Kemba Walker still lack
qualified name mappings. The remaining 71 requests are inventoried in
[animation-sync-gaps.md](animation-sync-gaps.md).

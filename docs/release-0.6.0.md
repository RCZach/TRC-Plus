# TRACE 0.6.0

- Adds build-specific native animation names and IDs for 71 signature fields,
  plus Chew Gum, including support for existing installations.
- Matches signature menu field names to the corresponding roster fields and
  includes the reviewed Devin Booker layup and Harry Giles jumpshot spellings.
- Accepts accented and unaccented signature names, including Nikola Jokić/Jokic.
- TRC sync skips a conflicting field and explains both source values while
  continuing the other changes. This handles conflicting Dunk Package 1 and
  Go-To Dunk Package entries without choosing a value silently.
- Includes the animation catalog in the portable Windows package.

Unresolved names, unsupported fields, and ambiguous players still produce
warnings and remain skipped. Native animation IDs are restricted to the verified
executable build; learned mappings and saved workspaces are retained.

Extract the complete ZIP and launch `TRACE.exe` from the extracted `TRACE` folder.

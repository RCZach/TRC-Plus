# TRC 2K25 to NBA 2K27 field review

This review compares
the 24-player `export.json` supplied by the user, the TRC site's 2K25 badge
definitions, Trace's `config/offsets_2k27.json`, and 2K's published 2K27 badge
descriptions. It compares 2K25 directly with 2K27; no 2K26 data is used as a
migration step.

## Attributes and tendencies

| Category | TRC export fields | Exact names in Trace 2K27 | Trace fields absent from TRC export |
| --- | ---: | ---: | ---: |
| Attributes | 34 | 34 | 18 |
| Tendencies | 88 | 88 | 11 |

Every exported attribute and tendency name has a matching 2K27 Trace field.
The 18 additional Trace attributes are Stamina, Potential, and 16 durability
ratings. The 11 additional tendencies are Touches and five court zones each for
mid-range and 3-point shooting. Their absence from this export does not prove
that they were absent from 2K25; the export simply does not supply them.
Leave those 29 game fields untouched during TRC sync. Exact name agreement
establishes field coverage, but does not prove identical gameplay effects or
numeric calibration between releases.

## Gameplay badges

TRC exports the 40 2K25 gameplay badge names. Trace defines 53 2K27 gameplay
badges and 16 separate personality badges. Of the gameplay badges, 34 names
are identical. Six 2K25 names have no 2K27 field; 19 2K27 names have no 2K25
source. The 19 include ten plausible targets of the six old badges and nine
with no reliable 2K25 badge equivalent.

| 2K25 badge | Plausible 2K27 target(s) | Interpretation |
| --- | --- | --- |
| Boxout Beast | Boxout Boss | Strong one-to-one match for establishing a boxout. Breaker is a different skill: defeating an opponent's boxout. |
| On-Ball Menace | Seatbelt | Strong match for body-up perimeter defense. Ankle Braces covers ankle-break resistance and should remain independent. |
| Post-Up Poet | Ghost Stepper; Post Spin Catalyst | Plausible split of fakes/step-throughs and post spins/drives. Initial mapping uses Post Spin Catalyst only. |
| Rebound Chaser | Crasher; Possession Closer | Plausible offense/defense split. Initial mapping uses Possession Closer only. Do not infer Sync Snatcher, which rewards timing. |
| Set Shot Specialist | Set and Fire; Static Middy | Strong split of stationary 3-point and mid-range shooting; 2K explicitly describes this split. |
| Shifty Shooter | Arc Cadence; Smooth Operator | Strong split of moving 3-point and mid-range shooting by their published descriptions. |

No pair of the six removed 2K25 badges clearly consolidates into one 2K27
badge. The nine new 2K27 badges with no reliable 2K25 badge source are Quick
Trigger, Pace, Wall Up, Ankle Braces, Sync Snatcher, Breaker, Flash, Work Horse,
and Bruiser. Leave their loaded game values unchanged. Work Horse and Ankle
Braces may have existed in other game years, but they are absent from this
2K25 export and must not be inferred from another release.

## Selected initial mapping and sync rules

Trace now converts all six old badge names during TRC merge. The initial
single targets chosen by the user are Boxout Beast → Boxout Boss,
On-Ball Menace → Seatbelt, Post-Up Poet → Post Spin Catalyst,
Rebound Chaser → Possession Closer, Set Shot Specialist → Set and Fire, and
Shifty Shooter → Arc Cadence. The other half of each potential split stays
unchanged. An old zero does not clear an existing 2K27 badge; a positive old
tier cannot lower a higher existing 2K27 tier. This conversion is in Trace's
import path and does not change historical 2K25 data on the TRC website.
The 34 common badges and all 34 exported attributes and 88 tendencies retain
direct name matching. Conversion stays scoped to matched loaded-roster players.
The nine unrelated new badges keep their current game values. Import and
preview do not write to the game; applying a reviewed game plan remains opt-in.

## Closer look at the four splits

These counts use only the 24-player supplied export. They are evidence about
that sample, not proof of a general attribute threshold or a game rule.

| 2K25 badge | Players with a positive tier | Relevant observation | Possible later choice |
| --- | ---: | --- | --- |
| Set Shot Specialist | 21 | All 21 have 3pt Shot at least 85; one has Midrange Shot 55. | Allow Static Middy as an alternative to Set and Fire. |
| Shifty Shooter | 16 | All 16 have Midrange Shot at least 80 and 3pt Shot at least 85. Moving-shot tendencies vary, including zeros. | Allow Smooth Operator as an alternative to Arc Cadence. |
| Post-Up Poet | 3 | One has Post Spin tendency zero, while all three have positive Step Through Shot tendencies. | Allow Ghost Stepper as an alternative to Post Spin Catalyst. |
| Rebound Chaser | 16 | All 16 have Offensive Rebound at least 76 and Defensive Rebound at least 90. | Allow Crasher as an alternative to Possession Closer. Do not infer Sync Snatcher. |

For any target already equipped in the 2K27 roster, the suggested tier is the
higher of the existing tier and the positive old tier. Do not use shot or play
tendencies as hard eligibility gates: they measure how often an action is used,
not whether a player can perform it. The 2K27 MyPLAYER builder's badge
requirements also should not automatically be applied to MyNBA roster editing.

## Sources

- User-supplied `C:\Users\Zachary\Downloads\export.json` (24 players; field
  names and tier distribution, no player data reproduced here).
- TRC `simulation/scripts/badge.py` (2K25 badge names and descriptions).
- Trace `config/offsets_2k27.json` (2K27 field names and mapping profile).
- [2K's NBA 2K25 announcement](https://newsroom.2k.com/news/lead-the-next-great-dynasty-in-nbar-2k25-with-new-mycareer-and-myplayer-builder-updates-for-playstationr5-xbox-series-xs-and-pc) (40 badges).
- [2K's NBA 2K27 announcement](https://newsroom.2k.com/news/nbar-2k27-myplayer-builder-introduces-female-myplayers-badge-tokens-and-the-all-new-synergy-system) (53 badges, 19 new).
- [2K's full 2K27 badge descriptions](https://store.steampowered.com/news/posts/?enddate=1787076161&feed=steam_community_announcements) (publisher's Steam announcement).

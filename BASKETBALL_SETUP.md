# Basketball imports

Paste the D1 URL into the basketball game's Import League from URL box:

https://raw.githubusercontent.com/adriantorres211217-code/-cfb-2026-league-/main/basketball_2026_D1.json

The wider college dataset is available here:

https://raw.githubusercontent.com/adriantorres211217-code/-cfb-2026-league-/main/basketball_2026.json

## Format correction

Earlier files were valid JSON but contained football offense and defense enum
values. These files use the CBB Simulator community import structure, including
`motion` / `uptempo` offenses, `Man-to-Man` defense, integer prestige values,
East/Midwest/South/West regions, and `nationalChampionshipLogoURL`.

The basketball reference is https://raw.githubusercontent.com/john-loch/PGMB/refs/heads/main/CBB.json
shared by its author in https://www.reddit.com/r/cbbsimulator/comments/1q6qrnw/custom_league_file_thread/.
Community game settings and award names are used as reference data, not official
current rankings or measured team tactics. The game importer itself is not
available in this workspace, so an actual in-app import is still unverified.

## Contents and sources

- D1: 365 teams in 31 conferences from ESPN men's college basketball season
  2026 standings. This is the source's season snapshot, not a promise that every
  2026-27 realignment is reflected. Names, mascots, colors and logos come from
  ESPN; game prestige/tactics/regions are matched to the community reference
  where possible. Unmatched teams receive neutral game settings.
- 172 rivalries whose two names both resolve to the D1 roster.
- Ten basketball award customizations and the NCAA championship logo.
- Wider file retains 955 lower-division entries from the earlier supplied
  dataset and replaces its incomplete D1 block with the 365-team roster.
  Lower-division colors, generic mascots, ratings and campus image URLs have
  not been independently verified. Duplicate lower-division labels are
  qualified by conference rather than silently deleting distinct campuses.
- No fabricated players, rosters, stats, or unsupported game features.
- Subdivision slot list is empty: the wider file places the retained schools
  in their existing conferences. This avoids exceeding the guide's 32-slot
  subdivision limit. Large-universe runtime support is unverified.

ESPN source endpoints:
https://site.api.espn.com/apis/site/v2/sports/basketball/mens-college-basketball/teams?limit=1000
https://site.api.espn.com/apis/v2/sports/basketball/mens-college-basketball/standings?season=2026&group=50

## Rebuild

Run `python build_basketball.py`. The GitHub workflow performs the same build
and validates the envelope, enum values, numeric types, color syntax, distinct
team labels, rivalry references, conference game limits and JSON round-trip.
Previously shared D1 filenames are also rebuilt with the corrected format.
The workflow requires only the checked-in inputs, with no API key or live
external data dependency. External image availability can still change.

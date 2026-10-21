# N-Ways Guinea engine: specification

Status: **v1.0, issued on 20 October 2026**: 3,808,784 codes, one for every compound in Guinea, provisional until residents confirm them. The engine, its grid and its numbering are defined for Guinea alone. Since the first issue the frames, the name ids, the blocks and the area indexes are frozen; later runs only add.

The engine turns places in Guinea into codes and back, works offline from a few data files, and builds the published registry of compounds. `engine/reference/gn_codes.py` is the readable reference implementation (standard library only), and `engine/reference/vectors.json` holds the values every port must reproduce (the N-Ways backend's `internal/addressing/gn` does, value for value). Where the script and this text disagree, this text wins and the script has a bug.

## 1. Codes

| Code | Example | Names | Made |
|---|---|---|---|
| **Home code** (remembered) | `Hafia 3 · 1230` | a compound: a concession, fenced plot or house | assigned once, from the registry |
| where official street names exist | `Avenue de la République · Almamiya 2078` | the official street is primary; the N-Ways number only adds the door (§8.0) | derived |
| on plates and forms | `HAFIA 3 · 1230` · Dixinn, Conakry | same; no check digit, which is for systems only (§4.3) | derived |
| machine form | `GN-04261-1230-8` | same, 1:1, for QR codes, links and APIs | derived |
| structure | `Hafia 3 · 1230.2`, `GN-04261-1230.2-3` | building no. 2 of the compound (a case, an annex); its check digit covers the structure too | assigned with the compound |
| entrance | `Hafia 3 · 1230/1` | gate or door; `/1` is the main gate | added when confirmed |
| unit | `Hafia 3 · 1230#4` | flat no. 4 (Kaloum and Ratoma apartment blocks) | on request |
| **Spot code** | `0 22FQ V835` | any 3 m square, built on or not | computed from coordinates |
| **Bloc code** | `0 22FQ` | a 1.2 km square | the first five characters of a spot code |

There are two families:

- **Home codes** are what people remember and share. They are the area's plate name (the short name people already use: at most 12 characters and 2 words, §4.2a) plus 4 digits (5 digits for the most shared names, §4).
- **Spot codes** are computed anywhere in Guinea from coordinates alone: a field, a gold-panning site, a market stall, a landing on the Îles de Loos. Their first five characters, the **bloc code**, name a 1.2 km square. The bloc code is Guinea's first location code that no administrative reform can change. A village or a quartier can learn its bloc code the way people elsewhere learn a postcode.

## 2. Frames

The country is covered by **five frames**, numbered with the first digit of La Poste guinéenne's postal radical (UPU sheet, 2005):

| Digit | Frame | Regions (October 2026) | Extent | Radical example |
|---|---|---|---|---|
| 0 | Conakry | GN-C | 41 × 36 km | `001 BP … CONAKRY` |
| 1 | Basse-Guinée | Boké, Kindia | 356 × 403 km | `100 BP 75 KINDIA` |
| 2 | Moyenne-Guinée | Labé, Mamou | 212 × 286 km | `200 BP 125 LABE` |
| 3 | Haute-Guinée | Kankan, Faranah | 400 × 435 km | — |
| 4 | Guinée forestière | Nzérékoré | 338 × 265 km | — |

Each frame has a polygon (`model/frames.geojson`): the union of its regions as of October 2026, simplified to 0.0002° (about 22 m). These polygons are **frozen** when the first code is issued, and they are code boundaries, not administrative ones:

- The August 2026 decrees that created the Beyla and Siguiri regions, and the 11 new préfectures, move no point from one frame to another.
- Future reforms do not either.

A point inside two outlines takes the lower digit, because Conakry lies inside the Basse-Guinée box. A point outside every outline but within 0.01° (about 1.1 km) of one (an offshore islet, a sliver between outlines) belongs to the nearest outline; further out it is abroad or at sea and has no frame.

### 2.1 The border decides

A code is only ever issued for a building whose entrance lies inside the national border of Guinea, OpenStreetMap's admin_level=2 boundary (relation 192778, `ISO3166-1=GN`), or within 300 m of it (`gn_codes.BORDER_M`). A point further out is in a neighbouring country and is outside Guinea, whatever the frame rule above gives: the frame outlines, the 0.01° reach around them and outlines from other sources (geoBoundaries, GADM and the like) may cross the border, and they never decide. The rule applies to codes, not to spot codes: §3 gives a spot code to every point a frame holds, and a spot code issues nothing.

The border ships as `engine/data/border.geojson`, made by `tools/border.py` from the OpenStreetMap relation: assembled by osmium, simplified by Douglas-Peucker at 5 m, coordinates to 1e-5 degrees (under 1 MB). The file records the largest distance between the simplified line and the true one, measured both ways (`maxDeviationM`, 5.5 m for the current file). `gn_codes.Border` applies 300 m less that deviation, rounded up (294 m, `limitM`), so a point it accepts is never more than 300 m outside the true border: a point between 294 and 300 m outside may be refused, a point in a neighbouring country never accepted. Distances are measured on the local plane at the point (`m_lat`, `m_lon` of §3.2 at its latitude).

**Why frames and not préfectures.** A code that carries an administrative unit changes, or becomes misleading, when that unit is redrawn. Guinea has redrawn Conakry once (2024: 5 communes became 13) and the regions once (2026: 8 became 10, with 44 préfectures) in under three years. The postal regions are the oldest stable division people use: they match the four natural regions, which every Guinean knows, and the BP radicals on letters since at least 2005.

## 3. Spot grid (tessellation)

### 3.1 Why this grid

- **Metric and square.** Guinea runs from 7.2°N to 12.7°N, so a degree of longitude shrinks by 1.7% from south to north. Each frame computes its cell in degrees at its own reference latitude, so cells are 3 m squares to within ±1% across a frame. This needs no projection library: Dabola 1981 / UTM 28N is not used.
- **Same length everywhere.** Every frame is at most 480 km on a side, which is 400 blocs of 1.2 km, or 160,000 cells of 3 m. So every spot code in Guinea has exactly 8 grid characters, from the Îles de Loos to Diécké.
- **Nested squares, one row character and one column character at a time.** Each pair of characters names a square inside the previous one: secteur 24 km, bloc 1.2 km, carré 60 m, point 3 m. This can be explained with a draughtboard ("le damier"), which matters in a country where about 4 adults in 10 read.

### 3.2 Definition

- **Alphabet**: `23456789CFGHJMPQRVWX` (values 0–19). It has no vowels, so codes cannot spell words in French, Pular, Maninka or Susu, and no 0/O or 1/I/L.
- **Cell size** in degrees for a frame with SW corner (`west`, `south`) and reference latitude φ:
  - `dlat = 3 / m_lat(φ)` and `dlon = 3 / m_lon(φ)`
  - `m_lat(φ) = 111132.954 − 559.822 cos 2φ + 1.175 cos 4φ`
  - `m_lon(φ) = 111412.84 cos φ − 93.5 cos 3φ + 0.118 cos 5φ`
- **Cell indices**: `row = ⌊(lat − south)/dlat⌋` and `col = ⌊(lon − west)/dlon⌋`. Each runs from 0 to 159,999.
- **Encode**:
  1. Bloc indices: `bR = row div 400`, `bC = col div 400`.
  2. Positions inside the bloc: `pR = row mod 400`, `pC = col mod 400`.
  3. The 8 characters are `bR div 20, bC div 20, bR mod 20, bC mod 20, pR div 20, pC div 20, pR mod 20, pC mod 20`.
     - Characters 1–2 give the secteur (24 km).
     - Characters 1–4 give the bloc (1.2 km).
     - Characters 5–6 give the carré (60 m).
     - Characters 7–8 give the point (3 m).
- **Display**: `D BBBB PPPP`, i.e. frame digit, bloc, point. No check character is written, so a person has nothing extra to read or type; an older code `D BBBB PPPP-C` still decodes and its check is verified (3.3).
- **Decode** reverses the steps and returns the centre of the cell.

### 3.3 Check character

Each value v maps to (v mod 5, v div 5) in the group G = ℤ₅ × ℤ₂ × ℤ₂, which has 20 elements. Let σ = (×2 on ℤ₅, M on ℤ₂²) with M = [[0,1],[1,1]]. The check character c is chosen so that

  Σᵢ σⁱ(xᵢ) + σⁿ⁺¹(c) = 0,

where x is the frame digit followed by the 8 grid characters.

σ − 1, σ + 1 and σ² − 1 are all bijections. So the check catches:

- every single wrong character;
- every swap of two neighbours;
- every swap across one character;
- every twin error (aa → bb).

`gn_codes.py test` proves the first three exhaustively on all 8,000 three-character bodies. A spot code read with the wrong frame digit also fails the check.

### 3.4 Points beyond a frame's grid

Every point inside a frame outline lies in its frame's grid. A point in no outline but within 0.01° of one (§2) can lie just beyond the grid of the frame §2 gives it: Basse-Guinée's grid starts at 9.03°N while its outline reaches 9.0341°N, so a compound on the Sierra Leone side of a border village falls south of it. Such a point takes its spot code as follows:

1. The frame of §2, when its grid holds the point (rows and columns 0 to 159,999).
2. Else, among the other frames whose outline lies within 0.01° of the point and whose grid holds it, the one with the nearest outline (ties to the lower digit). The point takes its own cell there.
3. Else the frame of §2, at the cell of its grid nearest the point: `row` and `col` clamped to 0 … 159,999. No point within 0.01° of an outline lies more than 350 cells (1,050 m) beyond its frame's grid, measured on every outline vertex of the five frames, so this step always gives a code.

Distances are the ones of §2: in degrees, longitude unscaled. Of the 1,972 issued compounds that lie in no outline, every one is within 0.01° of one (the farthest at 0.0029°), and scaling longitude by cos latitude would give each the same nearest outline. Every one of them lies in its own frame's grid (step 1): no issued compound takes step 2 or step 3. A compound that took step 3 would keep its exact entrance in the registry beside the code, since its edge cell can lie up to 1,050 m from it.

Frames and grids never move. A code decodes in the frame its digit names, to the centre of its cell (§3.2), whatever step gave it. Abroad or at sea (§2) a point has no spot code.

## 4. Home codes

### 4.1 Areas

An area is a named place people already use. It is frozen as a polygon when its first code is issued.

1. **Official quartiers** where OpenStreetMap holds their polygon (`admin_level=10`): 128 of Conakry's quartiers (Hafia 1, Bonfi, Madina Marché, Kipé …), plus quartiers of Nzérékoré, Coyah and other towns. The official name is kept as written by the commune; the name in the code is its plate name (§4.2a).
2. **Elsewhere, the nearest named locality** (a Voronoi cell): OSM place nodes (town, village, hamlet, suburb, quarter, neighbourhood) plus GeoNames populated places that OSM lacks. This covers rural districts and secteurs, villages, and Fouta *missidé* (mosque villages) and *foulasso* (hamlets).
3. A town node is dropped where at least three quartier nodes lie within 5 km. The quartiers then name the town's parts.
4. An area belongs to the frame that holds most of its buildings, but the frame is **not** needed to decode its codes (§4.2).

**Reform rule.** If a commune renames a quartier, the new name is added as the area's display name and the old one stays valid. If a commune splits or merges quartiers, existing codes stay in the area that issued them, and new homes are numbered in the area whose polygon holds them.

### 4.2 One name, one national number range

**Rule.** A name plus a number must be unique across Guinea on its own, because people leave out whatever is not needed. "Madina 12345" must decode to exactly one place, with no frame, commune or préfecture needed. The name is the area's **plate name** (§4.2a).

1. **Normalise the plate name** (`normalise_name()`):
   - read Cyrillic look-alike letters as Latin (map data has "Сondetta" with a Cyrillic С);
   - remove accents and case;
   - treat hyphens, apostrophes, dots and underscores as spaces, and split a number glued to a word ("Soro2" = "Soro 2");
   - expand St/Ste to Saint/Sainte, so "St-Antonin" and "Saint-Antonin" are one key;
   - collapse doubled letters;
   - merge the usual variants: *iya → ia* (Hafiya = Hafia), *kh → k* (Dankharan = Dankaran);
   - drop a leading "quartier/village/secteur/district/cité".

   So Missidé = Misside = Missidè, and Tannérie = Tannerie. A trailing number stays part of the name: "Hafia 3" is a different name from "Hafia".
2. **All areas sharing a normalised plate name** draw from **one national range** for that name. The range is split into **blocks**, one per area:
   - block size = 2 × the area's compounds at first issue, rounded up to 50, minimum 50: `b(n) = max(50, 50 · ⌈2n / 50⌉)`;
   - block order = frame digit, then the Hilbert position of the area's point over Guinea (`national_order`, order 16 over the box 15.4°W–7.6°W, 7.1°N–12.7°N), then the area id;
   - areas with no compound at first issue get no block yet.

   The range is 1000–9999 when the blocks fit in 9,000 numbers, and 10000–99999 otherwise. Blocks follow one another from the range's first number.
3. **Qualifier.** If a name needs more than 90,000 numbers, its areas are regrouped once as "<name> (<préfecture or town>)". The qualifier is one that people already say, and the decision is recorded per name in `model/names.json`. At first issue no name needs one: the largest range is Kindiadi's, 30,200 numbers.
4. **Freezing.** Name ids, ranges, blocks and area indexes were frozen at the first issue, on 20 October 2026. After that:
   - an area that gets its first compound later takes the **next free block** of its name, sized for its compounds;
   - an area whose block fills up takes an **extra block** further along, sized for its compounds plus one;
   - a 4-digit name whose blocks pass 9999 continues into 5 digits, up to 99,999 (the number is the name's, so no other name is touched);
   - name ids and area indexes are append-only.
5. **Within a block**, compounds are numbered in Hilbert order and spread evenly (§5.2).

**Decoding "Name NNNN"** (`decode_home()`):

1. Split off the number: the last 4 or 5 digits, or whatever follows a `·` when present.
2. Normalise the name and find its national entry. If the name is not a plate name but an area's official name (an alias, §4.2a), use the plate name it maps to.
3. Find the block that holds the number. That block is the area. When the official name was typed, the block must be that area's, or the code is refused.
4. If a check digit is given, verify it.

If a name ends in a number ("Hafia 3"), the number is written after a `·` on plates and in shared text ("Hafia 3 · 1230"). Typed without it, the engine tries each split, and either exactly one is issued or it asks for the `·`.

Figures for the published registry (`model/stats/national-names.json`, `tools/name-stats.py`):

| Measure | Value |
|---|---|
| Places / places in use / plate names in use | 17,044 / 15,822 / 11,518 |
| Plate names used by more than one place | 2,209 (6,513 places), of which 1,137 span more than one préfecture |
| Plate names in use on 4 digits / on 5 digits | 11,416 / 102 |
| Compounds on 4 digits / on 5 digits | 3,048,246 / 760,538 |
| Most places on one name | Madina: 51 places, 13,565 compounds, 28,450 numbers, 5 digits |
| Largest range | Kindiadi: 3 places, 15,054 compounds, 30,200 numbers, 5 digits |
| Names needing a qualifier | 0 |

### 4.2a Plate names: the remembered name is short

**Rule.** Map names can be too long to remember or to fit on a plate ("Missidé Bhoundou Kalouma", "Madina Kagneguiri 2"). The name in the code is a **plate name**:

- at most **12 characters**, counting letters, spaces, hyphens and apostrophes, an accented letter as one;
- at most **2 words**. Linking words (de, du, des, la, le, l', d', à, es as in "Dar es Salam") do not count; a hyphen separates words.
- A quartier's own number stays ("Hafia 3", "Kagneguiri 2"). It counts in the 12 characters but not as a word. No other digit is allowed.

`plate_fits()` in the reference engine checks this, and `load_names()` refuses a registry with a plate name over the limit unless the area is marked as awaiting the commune's choice (`overLimit`).

Each area keeps both names in `model/names.json`: `name` (the plate name, in the code) and `officialName` (the full name, printed small on cards and plates for context, never required). `plateRule` says how the plate name was made.

**Derivation** (`tools/plates_gn.py`, using `engine/reference/plate_names.py`):

1. A documented short form with its source wins (`known`). None is asserted for Guinea yet.
2. Clean: drop text in brackets ("Gada Kolla (Ley Peloun)" → "Gada Kolla"), text after a slash, generic words (Quartier, Cité, Lotissement, Zone, Secteur, Village, Campement, District, Base vie) and a linking word left at an end. In an official quartier, a trailing Cité or Village is kept, because it tells sibling quartiers apart ("Coleah Cité", "Coleah Centre").
3. If the cleaned name fits, it is the plate name (`as-is` or `cleaned`). Saint/Sainte may be written St/Ste (`abbreviated`: "Saint-Antonin" → "St-Antonin").
4. Otherwise the most distinctive run of one or two whole words is taken (`distinctive`), with a preference for the end of the name: "Missidé Bhoundou Kalouma" → "Kalouma", "Matoto Khabitaya" → "Khabitaya". A word is never cut, and a title is never separated from its name (Tierno, Karamoko, Almamy, Thierno, Belle Vue, Dar es Salam, Château d'Eau).
5. The area is flagged `needsCouncilChoice`, with up to 3 `plateCandidates` and a `plateReason`, when:
   - no candidate is clearly ahead;
   - every short form drops a qualifier: Maninka *koura* (new) and *kôrô* (old), Foula, Malinké, Soussou and other people's names that tell two parts of a village apart, and the landmark words Conakry uses for sibling quartiers (Centre, Marché, Mosquée, École, Gare, Port, Plateau, Cité, Minière, Routière, Carrière, Permanence...). So "Siguiri Koura 2", "Dixinn Centre 1" and "Bonfi Routière" are flagged;
   - the short form equals a well-known town elsewhere: a préfecture or sous-préfecture seat, a region capital (with Beyla and Siguiri), a 2026 sous-préfecture, one of Conakry's 13 communes or a big city of the region. A town within 20 km of the area, or the area's own préfecture seat, is its own town and is allowed;
   - the name is hyphenated and too long to keep whole ("Souma-Hassania"), or doubled ("Kélou Kélou Foula"): it is never shortened automatically.

   A flagged area carries its first candidate as a provisional plate name, and its codes were issued with it. **The commune confirms or replaces it; the numbers never change**, and a replaced name stays valid as an alias. A flagged area with no candidate that fits (a single word over 12 letters, such as the many Maninka *-dougou* names) keeps its cleaned name provisionally and is marked `overLimit`.

**Aliases.** An official name that maps to one plate name is an alias in `model/names.json → aliases`: "Missidé Bhoundou Kalouma 1260" decodes to the same area as "Kalouma 1260". An alias claimed by two plate names, or equal to another plate name, is dropped and listed in `droppedAliases`.

**Shared ranges.** Areas whose plate names normalise alike share one range, exactly as in §4.2. "Madina Tossokere" (Fria) and "Koula Tossokèrè" (Labé) both become Tossokere; "Tossokere 1400" is in Fria and "Tossokèrè 2775" in Labé.

Figures over the 15,822 places in use (`model/stats/national-names.json → plateNames`):

| Measure | Value |
|---|---|
| Official names over 12 characters / over 2 words | 1,537 / 68 |
| Plate name = official name | 14,462 |
| Shortened automatically | 800: distinctive 738, cleaned 60, abbreviated 2 |
| Flagged for the commune | 746, of which 380 still over the limit provisionally; 304,656 codes issued with a provisional name |
| Aliases kept / dropped | 1,150 / 6 |

### 4.3 Check digit and machine form

- **Damm check digit** over the national name id (5 digits), the home number and, for a structure, its structure number: `c = Damm(F₅ ‖ N [‖ s])`. The area does not need to be in the check, because the number's block determines it.
  - It is in the machine form only (`GN-04261-1230-8`): never printed on plates or shown to people, never remembered or typed.
  - It catches every single wrong digit and every swap of neighbouring digits (`gn_codes.py test` proves this for 4-digit numbers).
- **Remembered form.** This is checked by the registry instead. About half of each block stays unissued, and the app shows the gate photo and the place before anyone sets off.
- **Machine form**: `GN-<name id, 5 digits>-<number>[.<structure>]-<check>`, e.g. `GN-04261-1230-8`, and links `nways.ng/a/GN-04261-1230-8`. There is no frame in it.

### 4.4 Spoken form

Numbers are said **in pairs**, as Guineans say phone numbers: 2471 is "vingt-quatre soixante et onze"; a pair starting with 0 is said digit by digit ("zéro cinq"); a 5-digit number starts with its first digit ("un, trente-quatre soixante et onze"). The app's voice also reads the digits in Pular, Maninka and Susu (`design.json → spoken`; the numerals are still to be checked with native speakers).

Spot codes are spelled letter by letter with French letter names. Where two letters sound alike, the app uses spelling words taken from Guinean place names (`design.json → spelling`): "G comme Gaoual", "J comme Jean", "C comme Conakry".

## 5. Compounds, structures, entrances

The unit an address names is the **compound**:

- in towns, a walled *concession* or *parcelle*;
- in Haute- and Moyenne-Guinée, a family concession of several round houses (*cases rondes*, Pular *suudu*) with granaries and a kitchen, often enclosed by a fence of woven stalks or a hedge, or by nothing;
- an apartment block;
- an institutional enclosure.

Its structures are numbered `.1`, `.2` …. Its entrances (`/1` main gate, `/2` …) have one of these kinds:

| Kind | Typical case |
|---|---|
| `gate` | gate of a walled compound |
| `door` | door of a house |
| `shopfront` | shop built into the wall |
| `landing` | landing on the Îles de Loos, Kassa or Kakossa |
| `service` | service or back entrance |

Navigation goes to the main entrance, never to a footprint centroid.

### 5.1 Grouping structures into compounds (registry build, before numbering)

The registry is built one area at a time. Inside an area the structures are first put in one fixed order (by their stable id), so the grouping never depends on the order the map data arrives in. Rules run in this order; the first that applies sets the grouping.

**Settlement.** A structure is *rural* when fewer than 4 structures stand per hectare in the 250 m square around it (the structures in its 50 m cell and the 24 around it, divided by 6.25 ha), else *town*.

**Gap** between two structures: `gap(a, b) = ‖cₐ − c_b‖ − ½√Aₐ − ½√A_b` (centroid distance less half the square root of each footprint's area), in metres.

| # | Rule | Condition |
|---|---|---|
| 1 | People said so: "these buildings are one home", "this is the gate" (later runs) | a resident plus one more confirmation, or two arrivals |
| 2 | Plot outline from a survey plan or from Add my home (§7) | |
| 3 | **Plot**: every structure whose centre is inside the smallest closed OSM wall, fence, hedge or retaining wall (40–20,000 m²), `landuse=farmyard` (≤ 10,000 m²) or `landuse=residential` plot (≤ 2,500 m²) | at most 25 structures; a fuller plot is grouped by rules 5–7 inside it |
| 4 | **Site**: every structure inside an institutional site (OSM school, hospital, clinic, place of worship, market, police, town hall, court, military, industrial, commercial or retail land; N-Ways government, military, police and site compounds) is one compound | at most 30 structures and 6 ha; a bigger site is only an outer enclosure, its compounds grouped by rules 5–7 |
| 5 | **Concession rule (rural).** Structures that are round (circularity 4πA/P² > 0.88 and under 60 m²) or small (under 40 m²) join one concession when each is within a gap of 10 m of another; a concession wider than 60 m is split again with half the distance. The concession then joins the nearest larger house (neither round nor small) within 10 m, when the whole stays within 60 m. Three or more round houses make a *family concession*. | |
| 6 | **Annex rule.** A structure under 40 m² joins the nearest structure at least twice its size within a gap of 8 m. | |
| 7 | Otherwise each structure is its own compound. | |

A compound never holds more than 12 structures from rules 5–6: a bigger group is regrouped with half the distances until every part fits.

Two further rules hold throughout:

- **Regrouping never changes an issued code.**
  - Two codes found to be one home: the second becomes an alias of the first.
  - One code found to cover two homes: the first keeps the code, and the other takes a number from the free gap next to it.
- **Two levels for cités.** In a cité or a mining camp with one main gate, the cité gate is the outer entrance on the route and the compound gate is the last one.

### 5.2 Numbering order

Inside an area:

1. Each compound's point is the footprint-weighted centre of its structures (its main gate once one is confirmed).
2. The point's 3 m cell in its area's frame grid (§3.2) gives `(row, col)`, and the cell's position along a **Hilbert curve of order 18** (2¹⁸ = 262,144 > 160,000 cells a side) is computed with `x = col`, `y = row`:
   ```
   d = 0
   for s = 2¹⁷, 2¹⁶, …, 1:
       rx = [x ∧ s ≠ 0],  ry = [y ∧ s ≠ 0]
       d ← d + s² · ((3 · rx) ⊕ ry)
       if ry = 0:
           if rx = 1:  (x, y) ← (s − 1 − x, s − 1 − y)
           (x, y) ← (y, x)
   ```
3. The n compounds, sorted by (d, stable id), are spread evenly over the area's block [start, start + size): number i (0-based) is
   ```
   Nᵢ = start + ⌊(2i + 1) · size / 2n⌋
   ```
   With size ≥ 2n, consecutive numbers differ by at least 1 and on average by size/n ≥ 2, so every gap between neighbours stays free for future homes.

Neighbours get nearby numbers, and every gap between neighbours stays free for future homes.

## 6. Building profile

Every compound and every structure carries a profile. The full schema is in `model/design.json → profile`.

- **Compound**:
  - `use`: one of `one-household | multi-household (family concession) | mixed | commercial | institutional | outbuildings-only`, with `confidence` and `source`
  - `plotAreaM2`, `plotSource`, `structures`, `floorAreaM2`, `entrances[]`
  - `name`: for businesses and public buildings only
  - `status`, `issued`, `lastConfirmed`
- **Structure**:
  - `class` and `sub` from the Guinean taxonomy (e.g. RES/case-ronde, RES/concession-maison-en-dur, AGR/grenier, IND/bauxite, IND/orpaillage, TRA/gare-voiture), each with `confidence` and `source`
  - `footprintM2`, `perimeterM`
  - `heightM` and `heightSource` (`osm:height | osm:building:levels | ml:h | people`)
  - `floors`: OSM levels, else ⌊(h + 0.5)/3⌋ with a minimum of 1
  - `floorAreaM2`
  - `footprintSource` (`osm | google-open-buildings | microsoft | people`)
  - `lastConfirmed`
- **Class inference**, in priority order:
  1. people
  2. OSM `building=*` (when not `yes`)
  3. OSM amenity, shop, office, tourism or healthcare tags
  4. N-Ways government, military or police compound
  5. official-name pattern (préfecture, sous-préfecture, mairie, gouvernorat, ministère …)
  6. N-Ways place (POI) inside the footprint
  7. shape: under 12 m² → annex; round and under 60 m² → case ronde; at least 1,500 m² with 1–2 floors → warehouse or hall
  8. default `RES` at confidence 0.3
- **Confidence by source**: people 0.95, OSM building 0.9, OSM tags 0.85, N-Ways compound or POI 0.7, shape 0.5, default 0.3.
- **Public**: codes, gates, footprints, size, class, the names of businesses and public buildings, and confirmation dates.
- **Never stored**: residents' names, the number of people, photos of people. A household may ask to be shown only as "residential"; its code stays.

## 7. Add my home

1. **Gate.** Stand at the gate. The phone averages GPS for 10 s and takes one photo of the gate, which becomes entrance `/1`.
2. **Outline.** Use one of:
   - tapping the corners on satellite imagery;
   - walking the boundary inside the wall. ARKit/ARCore world tracking gives the shape to centimetres relative to the start, and GPS averaged over the walk anchors it. Plain GPS (3–10 m) is too rough to draw a plot.
   - importing a survey plan: type in or photograph the coordinates of the bornes (boundary markers). WGS 84 / UTM 28N or 29N is converted directly. Dabola 1981 / UTM 28N needs the published transformation (about 25 m) and is marked *approximate*.
   The engine checks the outline against imagery and nearby footprints.
3. **Describe.** Number of households (no names), structures, floors and use. This fills the profile.
4. **Provisional code.** The engine finds the new home's neighbours along the area's numbering curve (§5.2): a, the issued number of the last compound at or before its curve position, and b, the first after it (the block's edges stand in for a missing neighbour; if b < a, a is dropped). It takes the free number nearest ⌊(a + b) / 2⌋ strictly between them; if there is none, the lowest free number of the block; if the block is full, the first number of an extra block (§4.2). The code can go on the gate the same day (`reserve_number()`).
5. **Confirmed** once deliveries or arrivals reach that gate with no neighbour dispute open, or once new imagery or footprints show the structures.

Safeguards:

- **A code is an address, not a land title.** The flow and the plate both say so, and the registry never states who owns a plot.
- Overlapping outlines are flagged, not issued.
- Checks: the gate lies on the outline; the plot is 30–20,000 m²; the loop is closed; GPS and AR agree within 5 m.
- Only the outline and one gate photo are kept.
- Offline, the spot code and bloc code appear at once. The home code comes from the registry at the next connection; the phone can hold its area's reserved numbers so it can issue one offline, with a server collision check afterwards.

## 8. Registry build

### 8.0 Official data first: import and precedence

Where the state has an address, the engine uses it as written and creates nothing that competes with it. It applies this rule before it numbers anything.

**Step 0, import.**
- Load every official addressing dataset available:
  - the street names of the presidential national addressing programme (Ministère de l'Urbanisme et de l'Habitat; Kaloum, 2024);
  - any door numbers;
  - the programme's announced geolocation app, if it publishes data.
- Store each record exactly as officially written: no rewording, no translation, no re-casing. Record its source and terms.
- **Source and terms:** no published dataset was found, and the terms are unknown. N-Ways is to request the data from the ministry and the commune of Kaloum.
- **Until the official list arrives:** street names are taken from OSM `name` tags of Kaloum's streets (which carry the programme's 2024 names: "Avenue du 5 Septembre 2021", the "Rue KA. 0xx" series) and from street plates that people photograph at gates in the app (two agreeing photos per street). A compound in Kaloum takes the name of the nearest named street within 30 m of its structures (the most common among them), shown first as "Avenue de la République, Kaloum". In the issue of 20 October 2026, 3,085 compounds have one.

**Coverage, street by street.** A street segment is *officially covered* when it has an official name (at least `plaque`-confirmed). A gate is *officially numbered* when its street has official door numbers and the gate's number is known.

**Precedence at each gate.**

| Situation | Primary address | N-Ways home code |
|---|---|---|
| Official street **and** official door number | `<number> <official street>, Kaloum` | not issued. If one was issued before, it becomes an **alias** that resolves to the official address |
| Official street, **no** door numbers (Kaloum today) | the official street name, written as is | issued as the **door-level complement only**: "Avenue de la République · Almamiya 2078". When official numbers arrive, it becomes an alias |
| Nothing official (rest of Guinea) | the N-Ways home code | issued (§4) |

**Other rules.**
- **P.O. boxes are not addresses.** A BP (`001 BP 457 CONAKRY`) is a mailbox. It is stored as free text on a compound only if the household asks. Its radical's first digit is used only as the frame number (§2).
- **Re-import.** Each import is re-run on release. A newly covered street switches its gates' primary address automatically. Codes keep resolving, and nothing is deleted.

The tools (`tools/README.md`, "Issue") run in this order:

1. `prepare-inputs.py`: the small inputs: enclosures, gates, N-Ways places, localities (OSM place nodes, then GeoNames populated places OSM lacks; a place over the border is dropped), quartier outlines, labels (préfectures; the communes of Kaloum, Dixinn and Matam) and Kaloum's streets.
2. `extract-buildings.py`: every footprint (OSM `data/detail/countries/guinea/buildings-src.geojsonseq`, ODbL; Google Open Buildings and Microsoft footprints OSM lacks, `data/detail/ml/GN.parquet`, CC BY 4.0 / ODbL), its frame (§2), its area (§4.1: the quartier holding its centre, else the Voronoi cell of its nearest locality), its enclosure, label and Kaloum street; written sorted by area.
3. `issue_registry.py group`: compounds (§5.1) and profiles (§6), one area at a time; the compound count of every area. The border decides (§2.1): every structure whose centre, and then every compound whose entrance, lies more than the limit outside the national border is dropped before any place or number is given.
4. `build-register.py --freeze`: plate names (§4.2a), national ranges and blocks (§4.2) from the real counts, area indexes: `model/names.json`, `engine/data/register.json`.
5. `issue_registry.py number`: numbers (§5.2), and the lotes file, frame by frame, for the registry server (the N-Ways backend, `homecodes issue -country GN`), which numbers every area again with its own port and refuses the run if any number differs.
6. The issuer exports `registry/`: `areas.csv.gz` (the frozen areas and blocks), one gzip CSV per frame (code, plate, zone, label, entrance, spot code, Plus Code, class, use, kind, structures, floor area, settlement, official street; nothing about people) and `MANIFEST.json` with the SHA-256 of every file. The issuer refuses any code whose entrance lies more than 300 m outside the national border.
7. `border.py check` counts the published codes whose entrance lies beyond the border (§2.1); with the unsimplified border (`border.py build --full`) the count is exact at 300 m.

An area's zone in the registry is `<frame>-<index, 5 digits>` ("0-00412"); its index orders areas by frame, then Hilbert position over Guinea, then id.

**Stability.**

- A code, once issued, never moves and is never reused.
- A demolished compound's number is retired.
- New imagery changes profiles, not codes.
- A gate moved by less than 15 m keeps its code; a larger move needs confirmation.

## 9. Data files (offline)

| File | Size | Purpose |
|---|---|---|
| `engine/data/register.json` | 5 MB | frames, every area (zone, plate name, official name, label, name key, name id, blocks, point), aliases, name ids: what decodes "Name NNNN" offline |
| `engine/data/frames.geojson` | 0.5 MB | point-in-frame lookup |
| `engine/data/border.geojson` | 0.6 MB | the national border, simplified, with its largest deviation (§2.1): where a code may be issued |
| `engine/data/quartiers.geojson` | 1 MB | the official quartier outlines, for a new home's area |
| `model/names.json` | 9 MB | the national name registry with every block's plate rule, candidates and statistics |
| `registry/*.csv.gz` | about 60 bytes per compound | every issued code with its entrance and profile |
| `model/design.json` | — | taxonomy, spoken forms, spelling words, rules |

The spot and bloc codes need only `frames.*`, a few kilobytes of code, and no network. A phone keeps the register (5 MB) and the codes of the areas it uses.

## 10. Reference script

```
python3 engine/reference/gn_codes.py test                      # vectors + check proofs
python3 engine/reference/gn_codes.py encode 9.536912 -13.682651  # CHU de Donka → 0 22FQ V835
python3 engine/reference/gn_codes.py bloc 9.536912 -13.682651    # → 0 22FQ
python3 engine/reference/gn_codes.py decode "0 22FQ V835"
python3 engine/reference/gn_codes.py home Hafia 3 · 1230         # national decode → area, plate, machine form
python3 engine/reference/gn_codes.py home Linsan 7031             # Linsan (Lélouma), not Linsan (Kindia)
```

## 11. Registry server

`server/` serves the registry as a JSON API and, on the one designated issuer, issues codes by §4 and §7 (`server/README.md`, `docs/api.md`). It uses this reference engine for every form, check and spot code, refuses to issue a code or move an entrance more than 300 m outside the national border (§2.1, `422 outside`), and `server/testdata/parity.json` holds issue requests whose numbers, forms and extension blocks it must reproduce. A code issued there is `provisional`, `issued: on-demand`; an export of its database is in the format of §8, step 6.

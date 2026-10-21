# N-Ways Addressing for Guinea: the model and the reasons for it

These notes give the reasoning behind each rule of the model, with the measurements that support it. The normative definition is [engine/SPEC.md](../engine/SPEC.md); the paper ([paper.md](paper.md), [paper.fr.md](paper.fr.md)) gives every formula with worked examples and the evaluation. All figures below are those of the published registry: 3,808,784 codes, one per compound, in 15,822 places and five frames. They are reproduced by the scripts in `tools/` from the files in `registry/` and `model/`.

## 1. What the model starts from

- **No location postcode.** La Poste guinéenne writes a three-digit radical before a post-office box number (`001 BP 457 CONAKRY`). The radical routes mail to a delivery office; it does not name a place. Its first digit is the postal region: 0 Conakry, 1 Basse-Guinée, 2 Moyenne-Guinée, 3 Haute-Guinée, 4 Guinée forestière.
- **Streets named only in Kaloum.** Conakry's streets were coded by commune in the 1990s (`KA.23` is the 23rd street of Kaloum) and Kaloum's avenues were named and plated in 2024, but no door numbers survive: only 457 objects on the whole map carry one ([existing-systems.md](existing-systems.md)).
- **Boundaries in motion.** Conakry went from 5 communes to 13 (law of January 2024, elections of 31 May 2026), and the decrees of August 2026 made 10 regions and 44 préfectures out of 8 and 33. ISO 3166-2 has not yet followed.
- **A young, fast-growing population.** RGPH-4 (2025, preliminary) counted 17,521,167 people: 38.7 % urban and 43 % under 15. Conakry has 3,407,327 (about 19 %). The censuses of 2014 and 2025 imply growth of about 4.7 % a year.
- **Many languages.** The 2025 constitution makes the national languages official beside French; Pular, Maninka and Susu are the largest. Many adults read French with difficulty, but everyone handles telephone numbers, which are read in pairs.
- **5,218,074 building footprints** inside the national border or within 300 m of it: 1,873,398 from OpenStreetMap and 3,344,676 from Google and Microsoft footprints (through Overture) that OpenStreetMap lacks. 596,703 of them are round (circularity $4\pi A/P^2 > 0.88$ and under 60 m²): the *cases rondes* of family concessions, 23.4 % of footprints in Haute-Guinée and 1.0 % in Conakry.

## 2. Official addresses first

Where the state has an address, it is the address: a second address for the same door would divide the people who use it and weaken the state's own system.

- **Kaloum (official street names, no door numbers yet).** The official street is the primary address, written as the plate writes it. The N-Ways number is added only as the door-level complement ("Avenue de la République · Almamiya 2078") until official numbers exist. 3,085 of Kaloum's 5,646 compounds stand within 30 m of a named street.
- **Communes the programme reaches next.** Each street switches to its official name when that name is published or plated; coverage is detected street by street (SPEC §8.0). When official door numbers exist, they become primary and the N-Ways code becomes a cross-reference.
- **Everywhere else**, nothing official exists, and the N-Ways code is the address.
- **P.O. boxes** are mailboxes, not addresses. The radical's first digit is reused only as the frame number.

## 3. First criterion: easy to remember, nothing to do to get it

A code that people cannot remember, or have to apply for, goes unused, and then no other property matters. Everything else gives way to this.

### 3.1 What people already remember

People remember the name of their quartier, district or village ("Hafia", "Bonfi", "Koloma", "Dalein") and telephone numbers, said in pairs. They do not remember strings of letters and digits: in French, letter names collide over a telephone (G and J, M and N, B, D, P, T and V), and letters are harder still for anyone who reads French poorly. So the code people keep is **their place name and a number read in pairs**: `Hafia 3 · 1230`, "Hafia 3, douze trente". The place name is kept short: at most 12 characters and 2 words (§6).

### 3.2 The options

| Option | Example | What a person must hold | Verdict |
|---|---|---|---|
| **A. Place name and 4 digits** | `Hafia 3 · 1230` | a word they already say and two number pairs | **chosen**: 80.0 % of compounds have four digits, the rest five (§5) |
| B. Alphanumeric grid code | `0 22JV PVQQ` | ten symbols including letters with confusable names | kept as the spot code: shown and shared, never memorised |
| C. Digits only, national | `0 0421 2471` | nine digits with no anchor | one wrong digit leads to another town |
| D. Préfecture key and digits | `KA 2471` | two letters and four digits | Siguiri préfecture alone has 384,766 buildings; the keys went stale with the 2026 reform |
| E. Bloc code and digits | `2 Q7M3 471` | a letter code and three digits | blocs are not names people use |

Four digits are the most a person keeps as one thing, two pairs, the way the end of a telephone number is kept. Five digits ("1 · 63 · 51") are still a telephone chunk and are needed only where the places sharing one name hold more than about 4,500 compounds together.

The check digit belongs to the machine form only (`GN-04261-1230-8`), for QR codes, links and systems. **It is never printed on a plate or shown to people.** The remembered form is checked by the registry instead: about half of each block stays unissued, so a wrong number usually does not exist, and when it does the application shows the place, its préfecture and the gate before anyone sets off.

### 3.3 Getting the code

| Situation | Steps | What happens |
|---|---|---|
| Existing home, N-Ways app | 1 | Open the app at the gate, or on the saved home: the card shows "Hafia 3 · 1230" with a share button (WhatsApp or SMS link) |
| New or unmapped home | 4 | Add my home (§10): gate, outline, description; the code appears at once, provisional |
| Courier or partner finding a customer | 1 | Type or paste the code, or look it up through the API |
| Plate or QR sticker on the gate | 0 for the household | Printed from the registry; scanning the QR opens navigation to the gate |

## 4. Frames: the postal regions, frozen

Spot codes need a frame: an origin and an extent on the ground. The préfecture fails as a frame in Guinea: préfectures changed in August 2026, and a code containing "KA" (Kankan) would mislead the people of the new Siguiri region as soon as signs change. The model uses **the five postal regions**, with their October 2026 outlines frozen:

| Digit | Frame | Regions (2026) | Extent | Compounds |
|---|---|---|---|---|
| 0 | Conakry | Conakry | 41 × 36 km | 258,080 |
| 1 | Basse-Guinée | Boké, Kindia | 356 × 403 km | 1,003,774 |
| 2 | Moyenne-Guinée | Labé, Mamou | 212 × 286 km | 811,367 |
| 3 | Haute-Guinée | Kankan, Faranah, Siguiri | 400 × 435 km | 1,195,252 |
| 4 | Guinée forestière | Nzérékoré, Beyla | 338 × 265 km | 540,311 |

Four reasons:

1. They are the oldest stable division in daily use, on every BP address since at least 2005 and identical to the four natural regions taught in school.
2. The 2026 decrees split regions inside them (Beyla stays in frame 4, Siguiri in frame 3), so no point changes frame.
3. The digit is already understood: `200 BP 125 LABE` and the spot code `2 …` start with the same digit.
4. Every frame fits within 480 km (400 blocs of 1.2 km), so one code length works everywhere.

Administrative names (commune, préfecture, region) are shown next to a code, looked up from its position, and never part of it.

**The border decides.** A frame's outline is a code boundary, not the country's: along the land border it may reach into a neighbouring country, and so may the 0.01° around it that SPEC §2 gives a frame. A code is therefore only issued for a building inside Guinea's national border (OpenStreetMap's admin_level 2 boundary) or within 300 m of it, the margin that covers the line's drawing error and a compound straddling it (SPEC §2.1). The registry build drops every structure and compound beyond it, and the issuer and the registry server refuse a code or an entrance there. The border ships simplified to within 5.5 m (`engine/data/border.geojson`, 0.6 MB), and that deviation is taken off the 300 m, so the check errs on Guinea's side. Spot codes are unaffected: they name squares, not homes.

## 5. Places, names and national ranges

### 5.1 Places: the names people use

A place is the name word in a home code. Guinea records its places in two ways, so the rule has two sources:

1. **Official quartiers, where their outline exists.** OpenStreetMap holds 397 quartier outlines (administrative level 10), 128 within Conakry's frame and others in Nzérékoré, Coyah, Kankan and other towns. These are the communes' own units (Hafia 1, Hafia 2, Hafia Minière, Bonfi Routière, Madina Marché), the names people write on forms.
2. **Elsewhere, the nearest named locality**: OpenStreetMap place nodes and the GeoNames populated places that OpenStreetMap lacks, 16,649 in all. They cover rural districts and secteurs, the *missidé* and *foulasso* of the Fouta, Maninka villages and forest villages. Each compound goes to the nearest locality (its Voronoi cell). A town's own node is dropped where three or more quartier nodes lie within 5 km, so that the quartiers name the town's parts.

| Frame | Kind of place | Places | Compounds | Median | 90th pct | Largest | Last number 4 / 5 digits |
|---|---|---|---|---|---|---|---|
| 0 Conakry | locality | 43 | 4,650 | 53 | 224 | 917 | 35 / 8 |
| 0 Conakry | quartier | 128 | 253,430 | 946 | 4,629 | 8,877 | 90 / 38 |
| 1 Basse-Guinée | locality | 4,608 | 770,934 | 60 | 323 | 11,848 | 4,405 / 203 |
| 1 Basse-Guinée | quartier | 112 | 232,840 | 1,397 | 5,336 | 13,285 | 81 / 31 |
| 2 Moyenne-Guinée | locality | 2,304 | 739,338 | 137 | 818 | 12,920 | 2,236 / 68 |
| 2 Moyenne-Guinée | quartier | 28 | 72,029 | 2,122 | 5,729 | 6,589 | 23 / 5 |
| 3 Haute-Guinée | locality | 5,822 | 1,054,098 | 78 | 390 | 13,423 | 5,674 / 148 |
| 3 Haute-Guinée | quartier | 83 | 141,154 | 853 | 3,555 | 12,818 | 71 / 12 |
| 4 Guinée forestière | locality | 2,651 | 476,775 | 81 | 386 | 12,127 | 2,632 / 19 |
| 4 Guinée forestière | quartier | 43 | 63,536 | 1,256 | 3,118 | 4,172 | 41 / 2 |
| **Guinea** | all | **15,822** | **3,808,784** | 81 | 509 | 13,423 | **15,288 / 534** |

Places are mostly small (median 81 compounds). The largest are towns that the map records as one locality or one quartier, such as Faranah, Mamou, Lola and Kindiadi; when their quartiers are mapped, new homes there go to the new quartiers and issued codes stay as they are.

**Freezing.** A place's outline and name are frozen at its first code. If a commune renames a quartier, the new name is added and the old one stays valid; if it redraws it, issued codes stay where they are and new homes go to whichever place holds them. This is what made the 2024 split of Ratoma into Ratoma, Lambanyi and Sonfonia harmless: quartier names survived the split and only the commune label changed.

### 5.2 One name, one national range: "Madina 12345" names one place

Guinea repeats names: Madina in 51 places, Hafia in 30, Hamdalaye in 30, Tanènè in 29. A code that needs a préfecture or commune to be understood fails whenever someone leaves it out, so **a name and a number decode to one place in all of Guinea, with nothing else said.**

1. **Name key.** Accents and case are removed, hyphens and apostrophes become spaces, a number glued to a word is split off (Soro2 = Soro 2), Cyrillic look-alike letters are read as Latin, St and Ste are expanded, doubled letters are made single, and the usual variants are merged (Hafiya = Hafia, Dankharan = Dankaran). "Hafia 3" stays a name distinct from "Hafia".
2. **One national range per key, one block per place.** Every place with the same key draws from one range: 1000–9999, or 10000–99999 if 9,000 numbers are not enough. Each block holds twice the place's compounds at first issue, rounded up to 50 (at least 50). Blocks are ordered by frame, then along a Hilbert curve over the country.
3. **Check digit.** The Damm digit covers the name's national id and the number; the block, and so the place, follows from the number.
4. **Qualifier, only if needed.** A name whose places together needed more than 90,000 numbers would take a qualifier people already use. None does: the largest range, Kindiadi's, needs 30,200.
5. **Frozen allocation.** Blocks never move. A new place with an existing name takes the next free block in that name's range; a place whose block fills takes a further block after the name's last one.

| Measure | Value |
|---|---|
| Places / places in use | 17,044 / 15,822 |
| Name keys / in use | 12,142 / 11,518 |
| Keys shared by two or more places with homes | **2,209**, covering **6,513** places |
| Shared keys spanning more than one préfecture | 1,137 |
| Names in use with 4 / 5 digits | 11,416 / 102 |
| Compounds with 4 / 5 digits | 3,048,246 (80.0 %) / 760,538 (20.0 %) |
| Most places on one name | Madina: 51 places, 13,565 compounds, 28,450 numbers, 5 digits |
| Largest range | Kindiadi: 3 places, 15,054 compounds, 30,200 numbers |
| Names needing a qualifier | 0 |

**Example: two Linsans.** Linsan in Kindia préfecture (2,707 compounds) holds block 1000–6449 of the national Linsan range; Linsan in Lélouma (591 compounds) holds 6450–7649. So "Linsan 5389" is in Kindia and "Linsan 7031" in Lélouma, with no préfecture said. Their plates read `LINSAN · 5389` and `LINSAN · 7031`.

When a name ends in a number, the house number is written after a "·": "Hafia 3 · 1230". Typed without it, every reading is tried and exactly one must be issued, or the application asks for the "·".

## 6. Plate names: short names to remember

Names taken from the map are sometimes too long to say with a number ("Missidé Bhoundou Kalouma", "Madina Kagneguiri 2", "Siguiri Koura 2"). Each place therefore has a **plate name**:

- at most **12 characters** (letters, spaces, hyphens and apostrophes; an accented letter counts once);
- at most **2 words**, linking words (de, du, des, la, le, l', d', à, and es in "Dar es Salam") not counted;
- a quartier's own number is kept ("Hafia 3", "Kagneguiri 2"): it counts as characters, not as a word.

The **official name** is kept as well: it is printed in small type on cards and plates and is never required, and typing it still works when it belongs to one plate name ("Missidé Bhoundou Kalouma 1260" and "Kalouma 1260" are the same home).

**How a plate name is made** (`tools/plates_gn.py`, with the rule in `engine/reference/plate_names.py`):

1. A short form people already say, where one is documented with a source. None is asserted for Guinea; the communes' quartier lists give full names.
2. Cleaning: text in brackets or after a slash is dropped, and so are the generic words Quartier, Cité, Lotissement, Zone, Secteur, Village, Campement, District and Base vie ("Campement Lonton" → "Lonton"). In an official quartier a trailing Cité or Village stays, because it tells sibling quartiers apart ("Coleah Cité" beside "Coleah Centre").
3. If the cleaned name fits, it is used; Saint and Sainte may be written St and Ste.
4. Otherwise, the most distinctive one or two whole words, preferring the end of the name, which in the Fouta and Haute-Guinée is usually the hamlet's own: "Missidé Bhoundou Kalouma" → "Kalouma", "Matoto Khabitaya" → "Khabitaya". Words are never cut, and titles stay with their name (Tierno, Thierno, Karamoko, Almamy), as do Belle Vue, Dar es Salam and Château d'Eau.
5. Otherwise the place is **referred to its commune** with up to three candidates: when no short form is clearly best; when every short form drops a word that tells two places apart (Maninka *koura* "new" and *kôrô* "old", the names of peoples that distinguish two halves of a village, and the landmark words Conakry uses for sibling quartiers: Centre, Marché, Mosquée, École, Gare, Port, Plateau, Cité, Minière, Routière, Carrière, Permanence); when the short form would equal a well-known town elsewhere (a préfecture or sous-préfecture seat, a region capital, one of Conakry's 13 communes) other than a town within 20 km or the place's own préfecture seat; and for long hyphenated or doubled names ("Kélou Kélou Foula"), which are never shortened automatically.

A referred place carries its first candidate as a provisional plate name and its codes are issued with it. **The commune confirms or replaces it once; the numbers never change**, and a replaced name stays valid as an alias. Some names have no short form at all, mostly single Maninka words in *-dougou* longer than 12 letters ("Noumouridougou", "Kourougbédougou"); they keep their full name provisionally.

| Measure (places in use) | Value |
|---|---|
| Official names over 12 characters / over 2 words | 1,537 / 68 |
| Plate name equal to the official name | 14,462 |
| Shortened by rule | 800: distinctive words 738, cleaned 60, Saint → St 2 |
| Referred to the commune | 746, of which 380 still over the limit; 304,656 codes carry a provisional name |
| Official names kept as aliases / dropped as ambiguous | 1,150 / 6 |

Shortening can make two names meet: "Madina Tossokere" in Fria and "Koula Tossokèrè" in Labé both become *Tossokere* and share one range, like any repeated name. An official name claimed by two plate names is not kept as an alias (`droppedAliases` in `model/names.json`).

## 7. The spot code and the bloc code

People are not asked to remember a spot code. It exists so that every square of Guinea has a code with no registry and no network: a field, a gold-panning pit near Siguiri, a stall in Madina market, a landing on Kassa.

- **Form**: `D BBBB PPPP`, for example `0 22FQ V835` at the CHU de Donka: the frame digit, the 4-character bloc and the 4-character point inside it. No check character is written; a code written with one still decodes and its check is verified.
- **Squares nested by twenty.** Characters go in pairs, a row then a column, like a draughtboard (*damier*): characters 1–2 the secteur (24 km), 1–4 the bloc (1.2 km), 5–6 the carré (60 m), 7–8 the point (3 m).
- **Metric.** Each frame computes its cells at its own reference latitude, so cells stay within 1 % of 3 m across Guinea's 7–13°N, with no projection on the phone.
- **The bloc code** (`0 22FQ`) names a 1.2 km square, about one village and its fields or one Conakry neighbourhood: the closest Guinea can come to a postcode that no reform can change. A courier knows that two homes in one bloc are within walking distance.
- **Check character**, when present, over the frame digit and the 8 characters, in the group ℤ₅ × ℤ₂ × ℤ₂: it catches every single wrong character, every swap of neighbours, every swap across one character and every twin error (SPEC §3.3).

- **At a frame's edge.** A point outside every outline but within 0.01° of one belongs to the nearest outline's frame (SPEC §2), and can lie just beyond that frame's grid. Such a point takes another frame whose outline is within 0.01° and whose grid holds it, the nearest one; else the nearest edge cell of its own frame's grid, at most 350 cells (1,050 m) away. The code decodes in the frame it names (SPEC §3.4). All 1,972 issued compounds that lie in no outline are in their own frame's grid.

**Why 3 m.** One national frame of 8 characters would give 5.25 m cells. The five postal frames give 3 m at the same length and keep the familiar first digit.

## 8. Compounds, not footprints

### 8.1 The unit

What a Guinean gives as "home" is a compound:

- **in Conakry**, a walled *concession* or *parcelle* with one gate (*portail*): the main house, annexes for relatives or tenants, a kitchen, latrines, sometimes a shop built into the street wall with its own door;
- **in Haute- and Moyenne-Guinée**, a family concession of *cases rondes* (Pular *suudu*), granaries and a kitchen, enclosed by a hedge or a fence of woven stalks or not at all, often home to several households of one family;
- **other forms**: apartment blocks in Kaloum and Ratoma, mining cités and camps (Kamsar, Sangarédi) behind one main gate, schools, health centres and mosques.

So the address names the **compound**: its main entrance (`/1`, the gate) is where navigation ends; its structures are sub-units (`.1`, `.2` …) with their own profiles; shops in the wall are entrances of kind `shopfront`; on the Îles de Loos an entrance can be a `landing`.

### 8.2 Grouping

Structures are grouped into compounds before anything is numbered (SPEC §5.1), using, in order: residents' confirmations; survey plans and Add-my-home outlines; mapped walls, fences, hedges, farmyards and small residential plots; mapped sites (schools, hospitals, markets and the like); a **concession rule** for unenclosed groups of round or small houses in scattered settlement; and an **annex rule** (a structure under 40 m² joins a neighbour at least twice its size within 8 m).

| Measure | Guinea | Conakry |
|---|---|---|
| Structures | 5,218,074 | 363,193 |
| Compounds | 3,808,784 | 258,080 |
| Structures per compound | 1.37 | 1.41 |
| Single-structure compounds | 2,898,820 | 184,498 |
| Compounds from the annex rule | 722,822 | 72,395 |
| Concessions (scattered settlement) | 174,513 | 259 |
| From mapped plots / sites | 13,029 / 2,488 | 136 / 524 |
| Family concessions (3+ round houses) | 24,050 | 3 |

Tested against the 738 enclosures that mappers drew around two or more buildings, with the enclosures hidden, the rules reproduce 12.3 % whole and 9.9 % exactly, and a further 29 % miss one building. Inside a Conakry wall the buildings stand apart while neighbours across the wall stand close, so the town rule is cautious by design, and residents are asked to confirm groupings and gates, starting with the least certain.

**Regrouping never changes an issued code.** When two codes are found to be one home, the second becomes an alias of the first. When one code turns out to cover two homes, the first keeps it and the other takes a free number from the adjacent gap.

### 8.3 Numbering

Within each place, compounds are ordered along a Hilbert curve of order 18 over the frame's 3 m grid, at their gate, or at the footprint-weighted centre of their buildings until a gate is confirmed, and spread evenly over the place's block. Neighbours get nearby numbers, and between any two neighbours a number stays free for a home built later: a house built between Hafia 3 · 1228 and 1230 receives 1229.

## 9. Building profile

Every structure and compound carries a profile (`model/design.json → profile`), each attribute with its source and the date it was last confirmed.

### 9.1 Use classes

| Class | Guinean forms | Inferred from |
|---|---|---|
| Residential | concession, case ronde (*suudu*), maison en dur, villa, immeuble | OpenStreetMap building tag; shape (round, under 60 m²); size; default |
| Annex | kitchen, latrine, store, granary | under 12 m² inside a compound; OpenStreetMap shed or toilets |
| Commerce | boutique, marché (Madina, Niger, Taouyah), magasin, entrepôt, bureau | OpenStreetMap shop and office tags; places inside the footprint; halls of 1,500 m² or more |
| Administration | préfecture, sous-préfecture, mairie, ministère, police, gendarmerie | mapped government sites |
| Education | école, école coranique, université | OpenStreetMap; places |
| Health | hôpital (Donka, Ignace Deen), centre de santé, pharmacie | OpenStreetMap; healthsites; places |
| Religion | mosquée, église | OpenStreetMap; places |
| Industry and mining | bauxite (Boké, Kamsar, Sangarédi, Fria), orpaillage (Siguiri, Mandiana), iron (Simandou) | OpenStreetMap industrial and landuse tags |
| Hospitality, transport, agriculture | hôtel, gare voiture, port, débarcadère, grenier collectif | OpenStreetMap; places |
| Under construction, ruin, unknown | | OpenStreetMap `construction` and `ruins` |

**Confidence** by source: residents 0.95, OpenStreetMap building tag 0.9, other OpenStreetMap tags 0.85, mapped compound or place 0.7, shape 0.5, default 0.3.

### 9.2 What the data says

- Houses 4,445,130, round houses 596,703, annexes 142,306, under construction 9,970; industrial 6,172, schools 4,324, shops 2,999, health 1,991, military 1,524, offices 1,375, places of worship 1,220.
- Most classes are the residential default; round houses, measured from shape, are robust and are why Guinea has a concession rule. By préfecture they reach 54.7 % of footprints in Faranah, 37.5 % in Mandiana and 34.8 % in Dinguiraye.
- Median footprint 44 m² nationally, 68.8 m² in Conakry (rectangular *maisons en dur*) and 25.0 m² in Haute-Guinée.
- The detected footprints' height is a rendering filler in Guinea (36 values spread evenly from 3.5 to 7.0 m) and is not used, so floors are known only for the 334 buildings where OpenStreetMap records them.

### 9.3 Corrections

Residents confirm their gate, grouping and use in one tap ("C'est une boutique", "Ces cases sont une seule concession"); couriers' arrivals at a gate count as evidence; business owners publish their name; partners send corrections through the API. Agreement from different people settles a change without anyone reviewing it by hand. Each correction updates the attribute's source and date. **No correction ever changes a code.**

## 10. Add my home

Guinea is building fast, and new homes cannot wait for new imagery.

1. **Stand at the gate.** The position is averaged for 10 s and one gate photo is taken.
2. **Outline the plot**: by tapping corners on imagery, by walking the boundary inside the wall, or by entering the bornes of a survey plan (WGS 84 / UTM 28N or 29N converted directly; Dabola 1981 plans marked approximate, about 25 m).
3. **Describe it**: households, structures, floors, use.
4. **Provisional code** at once: the free number nearest the middle of the gap between the home's neighbours along the curve, so it can go on the gate the same day.
5. **Confirmed** by residents: two phones, at least one at the gate, with most answers in agreement.

**A code is an address, not a land title.** Most tenure in Guinea is customary or held under a *permis d'habiter*; a code says where a gate is and nothing about who owns the land. The application says so, and an outline that overlaps another compound is flagged rather than issued.

## 11. Privacy

- Codes describe places, never people. Residential compounds carry no names, no head counts and no photos of people.
- Public: codes, gates, footprints, sizes, use classes, and the names of businesses and public buildings as their owners publish them.
- A household can ask for its gate to be hidden; the code stays.
- Loi L/2016/037/AN requires prior declaration of processing and authorisation for transfers abroad. Confirmations are stored as counts and dates, not identities, and the processing will be declared to the authority foreseen by the law once it is in place.

## 12. Choices specific to Guinea

| Choice | Guinea | Because |
|---|---|---|
| Spot-code frame | 5 postal-region frames, frozen | administrative boundaries changed in 2024 and 2026; the postal digit is already in use |
| Administrative unit in the code | none (labels only) | the same |
| Places | official quartier outlines first, then localities | 397 official quartiers are mapped |
| Spot grid | secteur, bloc, carré, point; row and column characters | explainable as a damier; the bloc is a reform-proof postcode-like unit |
| Compound rule | concession rule for round-house groups | 596,703 round houses, more than half of footprints in Faranah préfecture |
| Spoken digits | French pairs, with Pular, Maninka and Susu | the 2025 constitution; the everyday habit of telephone numbers |
| Entrances | landing kind for the islands | Îles de Loos, Kassa |
| Plate names | quartier number kept; *koura*/*kôrô*, peoples' names and Conakry landmark words treated as qualifiers | numbered and sibling quartiers (Hafia 3, Coleah Centre); village halves told apart by such words |

## 13. Open points

- Pular, Maninka and Susu numerals, and the spoken forms in those languages, are to be checked with native speakers.
- The cadastre holder, the legal datum and whether surveyors have a professional order are not confirmed.
- Grouping inside Conakry's walls is cautious: one enclosure in eight comes out whole; residents' confirmations and walls traced on imagery will improve it.
- Only 27 sous-préfecture outlines and 397 quartier outlines are mapped; rural places rely on place points.
- Most use classes are defaults; floors are almost unknown.
- The data-protection authority does not appear to be operating.
- 746 plate names await the communes' choice, 380 of them still over 12 characters.

#!/usr/bin/env python3
"""Write model/design.json: Guinea's machine-readable design.

The rules and taxonomy are written here; the numbers come from model/stats/
(the 2026 statistics) and model/frames.json, so the design and the evidence
cannot drift apart.

  tools/build-design.py
"""
import json, os

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
S = os.path.join(REPO, 'model', 'stats')


def load(name, default=None):
    p = os.path.join(S, name)
    return json.load(open(p)) if os.path.exists(p) else default


country = load('country-profile.json', {})
capital = load('capital-profile.json', {})
areas = load('areas-gn.json', {})
national = load('national-names.json', {})
frames = json.load(open(os.path.join(REPO, 'model', 'frames.json')))
vectors = json.load(open(os.path.join(REPO, 'engine', 'reference', 'test-vectors.json')))
home = {h['code']: h for h in vectors.get('home', [])}
sample = json.load(open(os.path.join(REPO, 'registry', 'sample', 'hafia-3.json')))
s1021 = next(r for r in sample['compoundsList'] if r['number'] == 1021)
pn = national.get('plateNames', {})

design = {
    'country': 'GN', 'name': 'Guinée / Guinea', 'date': '2026-10-18', 'status': 'issued 20 October 2026',
    'brand': 'N-Ways',
    'criteria': [
        {'rank': 1, 'name': 'Easy to remember, effortless to get',
         'rule': 'The code people keep is a place name they already use plus a short number said in pairs; no letters or check character to remember; the app shows the code as soon as it knows where home is.'},
        {'rank': 2, 'name': 'Stable', 'rule': 'A code never moves or changes; frames and areas are frozen; administrative reforms change labels only.'},
        {'rank': 3, 'name': 'Compound and door level', 'rule': 'The address names the compound (concession); its gate is the destination; structures, doors and flats are sub-units.'},
        {'rank': 4, 'name': 'Works offline', 'rule': 'Spot and bloc codes need only frames.json; home codes come from the area registry carried on the phone.'},
        {'rank': 5, 'name': 'Official first', 'rule': 'Where the state has an address, use its data as written (see precedence); N-Ways codes fill only the gaps; never called official until adopted.'},
        {'rank': 6, 'name': 'Open', 'rule': 'Method, engine and code data public under open licences (licence choice pending).'},
        {'rank': 7, 'name': 'Privacy', 'rule': 'Codes describe places, never people; no resident names or counts.'},
    ],
    'verdict': {
        'postcodes': 'none for locations — a 3-digit postal radical before a P.O. box number (001 BP 457 CONAKRY, UPU 2005) identifies a delivery office',
        'addressSystem': 'partial — Kaloum streets named under the presidential addressing programme (2024); no house numbers; nothing confirmed beyond Kaloum',
        'checked': '2026-10-18', 'details': 'docs/existing-systems.md',
    },
    'precedence': {
        'rule': 'Where the government already has an address, N-Ways uses its data exactly as officially written and creates nothing new; N-Ways codes fill only the gaps, because a second address for the same door would compete with the state\'s.',
        'order': [
            {'case': 'official street + official door number', 'primary': '<number> <official street>, <commune>', 'nwaysCode': 'not issued; an earlier code becomes an alias resolving to the official address'},
            {'case': 'official street, no door numbers (Kaloum, 2026)', 'primary': 'official street name as written', 'nwaysCode': 'door-level complement only: "<official street> · <area> <number>"; becomes an alias once official numbers exist'},
            {'case': 'nothing official (rest of Guinea)', 'primary': 'N-Ways home code', 'nwaysCode': 'issued'},
        ],
        'officialSources': [
            {'name': 'Programme présidentiel national d\'adressage (Ministère de l\'Urbanisme et de l\'Habitat)', 'coverage': 'Kaloum street names and plates (2024); Dixinn, Matam, rest of Conakry, Coyah, Dubréka, regional capitals announced',
             'doorNumbers': 'none found', 'dataset': 'none published; to request', 'terms': 'unknown'},
            {'name': 'Commune de Kaloum / Gouvernorat de la Ville de Conakry', 'dataset': 'to request', 'terms': 'unknown'},
            {'name': 'Announced geolocation app of the programme', 'status': 'promised Oct 2024; not found', 'terms': 'unknown'},
        ],
        'import': 'Step 0 of every registry build: load official datasets verbatim (no rewording), with source and terms; until an official list exists, street names from residents\' plate photos (2 agreeing per street) and OSM names in Kaloum, marked source: plaque (unconfirmed).',
        'coverageDetection': 'street segment officially covered when it has an official (or plaque-confirmed) name; gate officially numbered when its street has official numbers and its number is known; re-run every release, gates switch primary address automatically',
        'poBoxes': 'a BP is a mailbox, not an address; stored as free text only on request; only the radical\'s first digit is reused, as the frame number',
    },
    'interoperation': {
        'postalRadical': 'frame digit = first digit of the radical (0 Conakry, 1 Basse-, 2 Moyenne-, 3 Haute-Guinée, 4 Forestière); a BP stays a mailbox, stored as free text',
        'streetNames': 'Kaloum street plates stored on entrances (street, source: programme-national-adressage)',
        'officialHouseNumbers': 'none exist; if issued, stored and shown first',
        'plusCodes': 'every spot code converts to WGS 84 and to an Open Location Code',
    },
    'adminHierarchy': {
        'note': 'Changed twice in three years; codes do not depend on it (labels only).',
        'levels': [
            {'level': 'région', 'count2025': 8, 'count2026': 10, 'iso': 'GN-B C D F K L M N (2026 regions Beyla and Siguiri not yet in ISO)', 'osmAdminLevel': 4},
            {'level': 'préfecture', 'count2025': 33, 'count2026': 44, 'iso': 'two-letter GN-XX for the 33', 'osmAdminLevel': 6},
            {'level': 'sous-préfecture / commune urbaine', 'count': 'about 304 (unverified)', 'osmAdminLevel': 8, 'inOSM': 25},
            {'level': 'district (rural) / quartier (urban)', 'osmAdminLevel': 10, 'inOSM': 397, 'conakryInOSM': 128},
            {'level': 'secteur', 'inOSM': 0},
        ],
        'conakry': {'communes2023': 5, 'communes2026': 13,
                    'names': ['Kaloum', 'Dixinn', 'Matam', 'Ratoma', 'Lambanyi', 'Sonfonia', 'Matoto', 'Gbessia', 'Tombolia', 'Kassa', 'Manéah', 'Kagbélen', 'Sanoyah']},
    },
    'settlement': {
        'population': {'rgph4_2025': 17521167, 'urbanPct': 38.7, 'conakry': 3407327, 'conakryPct': 19.4, 'rgph3_2014': 10523261},
        'naturalRegions': ['Basse-Guinée (Guinée maritime)', 'Moyenne-Guinée (Fouta Djallon)', 'Haute-Guinée', 'Guinée forestière'],
        'facts': [
            'Conakry is a narrow peninsula (Kaloum) with the Îles de Loos offshore; island homes are reached by landing (débarcadère).',
            'Fouta Djallon: plateaus with missidé (mosque villages) and foulasso hamlets.',
            'Haute-Guinée: Maninka villages of round houses in family concessions; gold panning around Siguiri.',
            'Guinée forestière: dense villages, Nzérékoré quartiers in OSM.',
            'Bauxite towns (Kamsar, Sangarédi, Boké) and iron (Simandou).',
        ],
        'buildings2026': country.get('size', [{}])[0].get('n'),
        'roundHouses2026': (country.get('roundHouses') or [{}])[0].get('n'),
        'roundHouseShareByRegion': {r['code']: r['round_pct'] for r in country.get('byRegion', [])},
        'medianFootprintByRegionM2': {r['code']: r['a_p50'] for r in country.get('byRegion', [])},
    },
    'languages': {
        'official': ['fr', 'national languages (constitution of 26 Sep 2025)'],
        'national': ['Pular (ff)', 'Maninka (emk)', 'Susu (sus)', 'Kissi', 'Kpelle', 'Toma (Loma)'],
        'note': 'Numbers on phones and in markets are commonly said in French; the app also reads them in Pular, Maninka and Susu.',
    },
    'spoken': {
        'pairs': 'Numbers said in pairs as phone numbers are: 2471 → "24 71" (vingt-quatre soixante et onze); 5 digits → "1 24 71".',
        'digits': {
            'fr': {'0': 'zéro', '1': 'un', '2': 'deux', '3': 'trois', '4': 'quatre', '5': 'cinq', '6': 'six', '7': 'sept', '8': 'huit', '9': 'neuf'},
            'ff': {'1': "go'o", '2': 'ɗiɗi', '3': 'tati', '4': 'nayi', '5': 'jowi', '6': 'jeego', '7': 'jeeɗiɗi', '8': 'jeetati', '9': 'jeenayi'},
            'emk': {'1': 'kelen', '2': 'fila', '3': 'saba', '4': 'naani', '5': 'looli', '6': 'wooro', '7': 'wolonfila', '8': 'seegi', '9': 'kononto'},
            'sus': {'1': 'keren', '2': 'firin', '3': 'saxan', '4': 'naani', '5': 'suuli', '6': 'senni', '7': 'solofere', '8': 'solomasaxan', '9': 'solomanaani'},
        },
        'digitsStatus': 'Pular, Maninka and Susu numerals to be checked with native speakers before use (and zero, and how pairs are said).',
        'letters_fr': {'C': 'cé', 'F': 'effe', 'G': 'gé', 'H': 'ache', 'J': 'ji', 'M': 'emme', 'P': 'pé', 'Q': 'ku', 'R': 'erre', 'V': 'vé', 'W': 'double vé', 'X': 'ixe'},
        'spelling': {'C': 'Conakry', 'F': 'Faranah', 'G': 'Gaoual', 'H': 'Hamdallaye', 'J': 'Jean', 'M': 'Mamou', 'P': 'Pita', 'Q': 'quatre-quarts', 'R': 'Ratoma', 'V': 'Victor', 'W': 'Wonkifong', 'X': 'Xavier'},
        'spellingNote': 'Gé/ji (G/J) are easily confused in spoken French: always spell G and J with the word. Place words to be validated in the memorability study.',
    },
    'homeCode': {
        'form': '<area name> <number>', 'example': 'Hafia 3 1021',
        'plate': '<AREA> · <number>-<Damm digit> · <commune>, <town> (labels only)',
        'machine': 'GN-<national name id, 5 digits>-<number>-<Damm digit>',
        'unique': 'a name plus a number decodes to one place nationally; see nationalNames',
        'number': {'fourDigits': {'range': [1000, 9999], 'numbers': 9000, 'per': 'national name (shared by all areas of that name)'},
                   'fiveDigits': {'range': [10000, 99999], 'numbers': 90000, 'per': 'national name'},
                   'beyond': 'a name needing more than 90,000 numbers gets one established qualifier (préfecture or town), decided once and recorded',
                   'noLeadingZero': 'numbers never start with 0 (forms, SMS and speech drop it)'},
        'check': {'algorithm': 'Damm (order-10 totally anti-symmetric quasigroup)', 'over': 'national name id (5 digits) + home number; the number\'s block identifies the area',
                  'catches': ['every single wrong digit', 'every swap of neighbouring digits'], 'remembered': False},
        'rememberedFormCheck': 'about half of each block stays unissued, and the app shows the gate photo and place before navigation',
        'separator': 'when a name ends in a number, the house number follows a "·" (Hafia 3 · 1021); typed without it, every split is tried and the app asks only if two are issued',
        'areas': {
            'rules': ['official quartier polygon (OSM admin_level 10) where present',
                      'else nearest named locality (OSM place nodes + GeoNames P), Voronoi',
                      'town node dropped where >= 3 quartier nodes lie within 5 km',
                      'frozen at first issue; a plate name plus a number is unique nationally (see nationalNames)'],
            'stats2026': areas.get('all'), 'byFrame': areas.get('byFrame'), 'conakryQuartiers': areas.get('conakryQuartiers'),
            'structuresPerCompoundConakry': areas.get('structuresPerCompoundConakry'),
        },
        'options': [
            {'option': 'Area name + 4 digits (chosen)', 'example': 'Hafia 3 1021', 'remember': 'one word people already say + two number pairs',
             'capacity': f"9,000 numbers per national plate name, split into blocks per area; {national.get('fourDigitNames', 0):,} of {national.get('names', 0):,} names fit, {national.get('fiveDigitNames', 0)} take 5 digits, none needs a qualifier"},
            {'option': 'Alphanumeric grid code', 'example': '0 22FQ V835', 'remember': '9 symbols incl. letters with confusable French names (gé/ji)',
             'capacity': 'every 3 m square', 'use': 'kept as the spot code, shown not memorised'},
            {'option': 'Digits only, national', 'example': '0 421 2471',
             'remember': '8 digits with no anchor; one wrong digit lands in another town', 'capacity': '10^8'},
            {'option': 'Préfecture ISO key + digits', 'example': 'KA 2471',
             'remember': 'short, but the 2026 reform created 11 préfectures without ISO codes; keys would go stale', 'capacity': 'too small per préfecture (Siguiri ~386k structures)'},
            {'option': 'Bloc code + 3 digits', 'example': '2 Q7M3 471',
             'remember': 'a letter code plus digits; blocs are not names people use', 'capacity': '8,000 per 1.2 km bloc'},
        ],
    },
    'nationalNames': {
        'rule': 'A name plus a number must be unique nationally on its own — no frame, commune or préfecture needed to decode it.',
        'normalisation': ['strip accents and case', 'hyphens, apostrophes, dots → spaces; collapse spaces', 'collapse doubled letters',
                          'merge variants: iya→ia (Hafiya=Hafia), kh→k (Dankharan=Dankaran); Missidé=Misside, Tannérie=Tannerie follow from the above',
                          'underscores → spaces; a number glued to a word split off (Soro2 = Soro 2); Cyrillic look-alike letters read as Latin',
                          'St/Ste → Saint/Sainte', 'drop a leading quartier/village/secteur/district/cité', 'a trailing number is part of the name (Hafia 3 ≠ Hafia)'],
        'allocation': {
            'range': '1000–9999 if all blocks of the name fit in 9,000 numbers, else 10000–99999',
            'blocks': 'one per area; size = 2 × today\'s compounds (buildings ÷ 1.402), rounded up to 50, minimum 50',
            'order': 'frame digit, then Hilbert position of the area centre over Guinea',
            'qualifier': 'only if a name needs > 90,000 numbers: its areas regrouped once as "<name> (<préfecture or town>)"',
            'frozen': 'name ids, ranges and blocks frozen at first issue; new area with existing name → next free block; full block → extra block further in the same range; ids append-only',
        },
        'plateNames': {
            'rule': 'The remembered name is a PLATE NAME of at most 12 characters (letters, spaces, hyphens, apostrophes; an accented letter is one) and at most 2 words (linking words de/du/des/la/es... not counted; a hyphen separates words). Areas are numbered on their plate name; the official (full) name is printed small for context and never required.',
            'quartierNumber': 'a quartier\'s own number stays (Hafia 3, Dixinn Port 2): it counts in the 12 characters, not as a word',
            'derivation': ['a documented short form with its source (none asserted for Guinea yet)',
                           'clean: drop brackets, text after a slash, generic words (Quartier, Cité, Lotissement, Zone, Secteur, Village de, Campement, District, Base vie)',
                           'if it fits, it is the plate name',
                           'else the most distinctive run of one or two whole words, preferring the end of the name; never a cut word; St/Ste for Saint/Sainte',
                           'flagged needsCouncilChoice with up to 3 candidates when no candidate is clearly ahead, when the short form drops a qualifier (Koura, Kôrô, Foula, Centre, Marché, Mosquée, École, Plateau, Cité...), when it equals a well-known town elsewhere, for long hyphenated names and doubled names; the commune confirms before the first code is issued'],
            'avoid': 'préfecture and sous-préfecture seats, region capitals (with Beyla and Siguiri), the 2026 sous-préfectures, the 13 Conakry communes and big cities of the region; a town within 20 km or the area\'s own préfecture seat is its own town',
            'aliases': 'an official name that maps to one plate name decodes too; one claimed by two plate names is dropped and listed in model/names.json droppedAliases',
            'engine': 'engine/reference/gn_codes.py plate_fits() refuses a plate name over the limit unless the registry marks it as a provisional name awaiting the commune',
            'stats2026': pn,
        },
        'decode': 'split off the last 4–5 digits (or what follows "·"), normalise the name, find its range (or the plate name an official name is an alias of), find the block holding the number = the area; verify the Damm digit if given',
        'registry': 'model/names.json (frozen at first issue, 20 October 2026)',
        'stats2026': national,
        'example': {'sameNameDifferentPrefectures': [{'code': 'Linsan 3450', 'prefecture': 'Kindia', 'block': [1000, 5899], 'buildings': 3431, 'plate': home['Linsan 3450']['plate']},
                                                      {'code': 'Linsan 6450', 'prefecture': 'Lélouma', 'block': [5900, 6999], 'buildings': 740, 'plate': home['Linsan 6450']['plate']}],
                    'longOfficialName': {'official': 'Missidé Bhoundou Kalouma', 'plateName': 'Kalouma', 'codes': [h['code'] for h in vectors['home'] if 'Kalouma' in h['code']],
                                         'plate': next(h['plate'] for h in vectors['home'] if 'Kalouma' in h['code'])},
                    'sameAfterShortening': [{'official': h['name'].split(' -> ')[0], 'code': h['code'], 'plate': h['plate']} for h in vectors['home'] if 'Tosso' in h['code']],
                    'sample': {'code': 'Hafia 3 · 1021', 'nameId': sample['nameId'], 'block': sample['block'], 'plate': s1021['plate'], 'machine': s1021['machine']}},
    },
    'spotCode': {
        'frames': [{k: f[k] for k in ('digit', 'name', 'regions2026', 'west', 'south', 'refLat', 'extentKm')} for f in frames['frames']],
        'cellMetres': 3.0, 'bloc': '1.2 km (400 x 400 cells)', 'secteur': '24 km', 'carre': '60 m',
        'length': 'frame digit + 8 characters + check, everywhere', 'display': 'D BBBB PPPP-C', 'blocCode': 'D BBBB',
        'alphabet': '23456789CFGHJMPQRVWX',
        'check': 'Z5 x Z2 x Z2 with sigma = (x2, [[0,1],[1,1]]); catches single, neighbour, jump-swap and twin errors',
        'why': ['frames are the postal regions, stable since at least 2005 and matching the four natural regions',
                'no administrative unit inside the code (2024 and 2026 reforms)',
                'metric 3 m squares at each frame\'s reference latitude, no projection library',
                'nested row/column pairs explainable as a draughtboard (damier)'],
    },
    'compound': {
        'unit': 'compound (concession, parcelle, walled plot, apartment block, institutional enclosure)',
        'entranceKinds': ['gate', 'door', 'shopfront', 'landing', 'service'],
        'subUnits': {'structure': '.n', 'entrance': '/n (1 = main gate)', 'unit': '#n'},
        'grouping': [
            {'rule': 'people confirm grouping or gate', 'confidence': 0.95},
            {'rule': 'survey plan or Add-my-home outline', 'confidence': 0.9},
            {'rule': 'closed OSM wall/fence/hedge ring 40–20,000 m2 (smallest ring holding the centroid)', 'confidence': 0.8},
            {'rule': 'N-Ways gated compound = outer enclosure (estate/cité/mine camp gate → compound gate)', 'confidence': 0.75},
            {'rule': 'concession rule: round (circularity > 0.88, < 60 m2) or small (< 40 m2) structures within 10 m of each other, group span <= 60 m; >= 3 round houses = family concession', 'confidence': 0.5},
            {'rule': 'annex rule: < 40 m2 joins nearest structure >= 2x its size within 8 m', 'confidence': 0.55},
            {'rule': 'each structure alone', 'confidence': 0.3},
        ],
        'regrouping': 'never changes an issued code: merge = alias, split = new number from the adjacent gap',
        'numbering': 'Hilbert order (order 16) over the area box at the main gate (else largest structure), spread evenly over the range',
        'conakry2026': {
            'structures': (capital.get('buildings') or [{}])[0].get('n'),
            'compounds': capital.get('compounds'), 'grouping': capital.get('grouping'),
            'enclosures': capital.get('enclosures'), 'enclosedStructures': capital.get('enclosedStructures'),
            'enclosuresWithGate': capital.get('enclosureGates'), 'use': capital.get('compoundUse'),
            'note': 'Grouping used enclosures + annex rule only; family concessions are under-counted (multi-household 0.0%).',
        },
    },
    'profile': {
        'compound': {
            'code': 'string', 'use': 'one-household | multi-household | mixed | commercial | institutional | outbuildings-only',
            'useConfidence': '0-1', 'useSource': 'people | rule:<n> | inferred',
            'plotAreaM2': 'number|null', 'plotSource': 'wall-ring | survey-plan | add-my-home | none',
            'structures': 'int', 'floorAreaM2': 'number', 'households': 'int|null (only if the household says; never names)',
            'entrances': [{'n': 'int', 'kind': 'gate|door|shopfront|landing|service', 'lat': 'number', 'lon': 'number',
                           'street': 'string|null', 'confirmed': 'date|null'}],
            'name': 'string|null (businesses and public buildings only)',
            'status': 'active | under-construction | ruin | demolished | merged', 'issued': 'date', 'lastConfirmed': 'date|null',
        },
        'structure': {
            'n': 'int', 'class': 'taxonomy class', 'sub': 'taxonomy sub-class', 'confidence': '0-1',
            'classSource': 'people | osm:building | osm:tags | n-ways:compound | name-pattern | n-ways:place | shape | default',
            'footprintM2': 'number', 'perimeterM': 'number', 'circularity': '4πA/P²',
            'heightM': 'number|null', 'heightSource': 'osm:height | osm:building:levels | ml:h | people',
            'floors': 'int (OSM levels, else floor((h+0.5)/3), min 1)', 'floorAreaM2': 'footprint × floors',
            'footprintSource': 'osm | google-open-buildings | microsoft | people', 'lastConfirmed': 'per attribute: {value, source, date}',
        },
        'confidenceBySource': {'people': 0.95, 'osm:building': 0.9, 'osm:tags': 0.85, 'n-ways:compound': 0.7, 'n-ways:place': 0.7, 'shape': 0.5, 'default': 0.3},
        'public': ['codes', 'gates/entrances', 'footprint and size', 'class', 'names of businesses and public buildings', 'confirmation dates'],
        'private': ['residents\' names (never stored)', 'number of people (never stored)', 'photos of people (never kept)',
                    'gate photo of a household that asked for privacy (shown only to someone navigating there)'],
    },
    'taxonomy': [
        {'class': 'RES', 'name': 'Résidentiel', 'subs': [
            {'sub': 'concession', 'fr': 'concession familiale', 'infer': 'compound with >= 3 dwellings or the concession rule'},
            {'sub': 'case-ronde', 'fr': 'case ronde (Pular suudu)', 'infer': 'circularity > 0.88 and < 60 m2'},
            {'sub': 'maison-en-dur', 'fr': 'maison en dur', 'infer': 'rectangular dwelling 40–250 m2'},
            {'sub': 'villa', 'fr': 'villa', 'infer': '>= 250 m2 in an enclosure, or osm building=house/detached + size'},
            {'sub': 'immeuble', 'fr': 'immeuble (Kaloum, Ratoma)', 'infer': '>= 4 floors or osm building=apartments'},
            {'sub': 'petite-maison', 'fr': 'petite maison / chambre', 'infer': '12–40 m2 dwelling'}]},
        {'class': 'ANX', 'name': 'Annexe', 'subs': [
            {'sub': 'cuisine-latrine-magasin', 'infer': '< 12 m2, or osm toilets/shed/kitchen'},
            {'sub': 'grenier', 'fr': 'grenier', 'infer': 'small round structure < 12 m2 inside a concession; people'}]},
        {'class': 'COM', 'name': 'Commerce', 'subs': [
            {'sub': 'boutique', 'infer': 'shop POI / osm shop'}, {'sub': 'marche', 'fr': 'marché (Madina, Niger, Taouyah)', 'infer': 'market POI / osm amenity=marketplace'},
            {'sub': 'magasin-entrepot', 'infer': '>= 1500 m2 with 1–2 floors, osm warehouse'}, {'sub': 'bureau-banque', 'infer': 'office/bank POI'}]},
        {'class': 'GOV', 'name': 'Administration', 'subs': [
            {'sub': 'administration', 'infer': 'name pattern préfecture/sous-préfecture/mairie/gouvernorat/ministère; N-Ways government compound'},
            {'sub': 'securite', 'infer': 'police/gendarmerie/military compound'}]},
        {'class': 'EDU', 'name': 'Enseignement', 'subs': [{'sub': 'ecole'}, {'sub': 'ecole-coranique', 'fr': 'école coranique / foyer coranique'}, {'sub': 'universite'}]},
        {'class': 'HEA', 'name': 'Santé', 'subs': [{'sub': 'hopital', 'fr': 'hôpital (Donka, Ignace Deen)'}, {'sub': 'centre-de-sante'}, {'sub': 'poste-de-sante'}, {'sub': 'pharmacie'}]},
        {'class': 'REL', 'name': 'Culte', 'subs': [{'sub': 'mosquee'}, {'sub': 'missidé', 'fr': 'mosquée centrale de missidé (Fouta)'}, {'sub': 'eglise'}]},
        {'class': 'IND', 'name': 'Industrie / mines', 'subs': [{'sub': 'bauxite', 'fr': 'bauxite (Boké, Kamsar, Sangarédi, Fria)'},
            {'sub': 'orpaillage', 'fr': 'orpaillage (Siguiri, Mandiana)'}, {'sub': 'fer', 'fr': 'fer (Simandou)'}, {'sub': 'usine'}]},
        {'class': 'HOS', 'name': 'Hébergement', 'subs': [{'sub': 'hotel'}, {'sub': 'auberge'}]},
        {'class': 'TRA', 'name': 'Transport', 'subs': [{'sub': 'gare-voiture', 'fr': 'gare voiture / gare routière'}, {'sub': 'port'},
            {'sub': 'debarcadere', 'fr': 'débarcadère (Îles de Loos, Boulbinet)'}, {'sub': 'aeroport'}, {'sub': 'station-service'}]},
        {'class': 'AGR', 'name': 'Agricole', 'subs': [{'sub': 'grenier-collectif'}, {'sub': 'etable'}, {'sub': 'case-de-champ', 'fr': 'case de culture (lougan)'}]},
        {'class': 'MIX', 'name': 'Mixte', 'subs': [{'sub': 'rez-commerce-etages-logement', 'infer': 'dwelling >= 2 floors with a shop POI'}]},
        {'class': 'CON', 'name': 'Chantier', 'subs': [{'sub': 'en-construction', 'infer': 'osm building=construction; people'}]},
        {'class': 'RUI', 'name': 'Ruine', 'subs': [{'sub': 'ruine'}]},
        {'class': 'UNK', 'name': 'Inconnu', 'subs': [{'sub': 'inconnu'}]},
    ],
    'inferenceOrder': ['people', 'osm building tag (not yes)', 'osm amenity/shop/office/tourism/healthcare', 'N-Ways government/military/police compound',
                       'official-name pattern', 'N-Ways place inside footprint', 'shape (annex < 12 m2; round < 60 m2; hall >= 1500 m2)', 'default RES 0.3'],
    'buildingStats2026': {'country': country, 'conakry': {k: capital.get(k) for k in ('classMix', 'resSub', 'classSource', 'size', 'areaBands', 'floors', 'heightSource')}},
    'gettingACode': {
        'appShowsCode': ['open N-Ways at home or save home (1 tap)', 'the card "Votre code maison / Your home code" appears', 'tap Partager → WhatsApp or SMS link'],
        'steps': {'existingHome': 2, 'newHome (Add my home)': 6, 'courierLookup': 1},
        'channels': ['N-Ways app', 'plate / QR sticker on the gate', 'Add my home', 'partners look up a customer\'s code (partner API)'],
        'notOffered': 'No USSD. An SMS look-up service is a possible later option, not part of this design.',
    },
    'addMyHome': {
        'steps': ['stand at the gate: GPS averaged 10 s + one gate photo → entrance /1',
                  'outline: tap corners on imagery | walk the boundary with AR (ARKit/ARCore) anchored by averaged GPS | import survey plan beacons',
                  'describe: households (number only), structures, floors, use',
                  'provisional code: free number nearest the middle of the gap between Hilbert neighbours',
                  'confirmed: deliveries/arrivals, no dispute, or new imagery'],
        'safeguards': ['a code is an address, not a land title', 'overlaps flagged, not issued', 'gate on outline; 30–20,000 m2; closed loop; GPS vs AR within 5 m',
                       'only outline + one gate photo kept', 'offline: spot/bloc code at once, home code on next connection'],
        'cadastre': {'holder': 'Direction nationale des domaines et du cadastre (unverified)', 'law': 'Code foncier et domanial, Ordonnance O/92/019 of 30 Mar 1992 (unverified)',
                     'datum': 'Dabola 1981 / UTM 28N (EPSG:3461) legacy; WGS 84 / UTM 28N–29N (EPSG:32628/32629) presumed for new plans (unverified)',
                     'surveyors': 'sworn géomètres; professional order unconfirmed', 'openParcels': 'none known'},
    },
    'privacy': {
        'law': 'Loi L/2016/037/AN of 28 Jul 2016 (cybersecurity and personal data protection); decree of 14 Apr 2025 on civil-status/identification data',
        'authority': 'art. 47 authority not constituted (2021, DLA Piper); 2026 status unverified',
        'duties': ['prior declaration of processing once the authority exists', 'transfers abroad need authorisation — keep the registry\'s personal data (door confirmations, photos) minimal and consider hosting a copy in Guinea',
                   'no resident data in the published registry'],
        'design': 'codes describe places; residential compounds carry no occupant data; household can request residential-only display',
    },
    'governance': {
        'partners': ['Poste GN SA', 'ARPT', 'Ministère des Postes, des Télécommunications et de l\'Économie numérique',
                     'Ministère de l\'Urbanisme et de l\'Habitat (programme national d\'adressage)', 'Gouvernorat de Conakry and its 13 communes',
                     'ITCG / IGN Guinée', 'INS', 'Direction nationale des domaines et du cadastre', 'ANSSI', 'emergency services', 'couriers, banks, utilities, mining operators'],
        'contacted': 'none yet', 'details': 'GOVERNANCE.md',
    },
    'memorabilityEvaluation': {
        'design': 'randomised: 300 residents in Conakry (Hafia, Bonfi, Kipé), 150 in Labé and 150 in Kankan; each shown their home code in one of three forms (name+4 digits, bloc+digits, alphanumeric spot)',
        'measures': ['free recall after 1 day, 1 week and 4 weeks', 'error rate by type (wrong digit, swapped pair, wrong area)', 'time to say the code on the phone', 'courier success finding the gate from the code alone'],
        'languages': 'recall tested in French and in the participant\'s first language (Pular, Maninka, Susu)',
        'target': '>= 80% exact recall after one week for name+digits; adopt the form with the best one-week recall',
    },
}
json.dump(design, open(os.path.join(REPO, 'model', 'design.json'), 'w'), ensure_ascii=False, indent=1)
print('model/design.json written')

# Guinea: existing postal and address systems

Sources consulted between 17 and 21 October 2026, on the web and in the OpenStreetMap extract of 17 October 2026. **Fetched** means the page was opened and read. **Search only** means it was seen in search results but not opened. The paper ([paper.md](paper.md), section 2) cites the same sources.

## Verdict

- **Postcodes: no location postcodes.** The postal operator uses a three-digit routing prefix ("radical") in front of a post-office box number, e.g. `001 BP 457 CONAKRY` (UPU addressing sheet, 2005). The prefix identifies a delivery office, not a place. Its first digit is the postal region: 0 Conakry, 1 Basse-Guinée, 2 Moyenne-Guinée, 3 Haute-Guinée, 4 Guinée forestière. La Poste guinéenne's own website never uses the words "code postal".
- **Street addresses: partial, Kaloum only.** Conakry's streets were coded by commune and its doors numbered under a World Bank-supported programme from 1993; the street codes survive on the map (`Rue KA. 040`), the door numbers do not. Under a presidential addressing programme, the streets of Kaloum, Conakry's central commune, were named and given plates in 2024. We found no house numbering, no postcode, and no evidence that the programme went past Kaloum.
- **Consequence for N-Ways.** Guinea has no location code to interoperate with. N-Ways Guinea codes:
  - keep the postal region digit as their first character;
  - store Kaloum street names next to the code wherever they exist;
  - treat a BP number as a mailbox, never as a place.

## Postal operator (Poste GN SA, "La Poste guinéenne")

| Finding | Source | Status |
|---|---|---|
| The postcode is defined as three digits plus the BP number, to the left of the locality ("Trois chiffres et numéro de BP à gauche du nom de la localité"). The first digit is the postal region: 0 Conakry, 1 Basse-Guinée, 2 Moyenne-Guinée, 3 Haute-Guinée, 4 Guinée forestière. The radical routes the item; the box number delivers it. Examples: `001 BP 457 CONAKRY`, `100 BP 75 KINDIA`, `200 BP 125 LABE`. The head office is `001 BP 2984 CONAKRY`. The sheet is dated 03/2005. | UPU addressing sheet for Guinea, https://www.upu.int/UPU/media/upu/PostalEntitiesFiles/addressingUnit/ginFr.pdf | Fetched |
| The operator's address is given as "Almamya 8è Avenue 4è Boulevard, Commune Kaloum 001BP2984". It offers P.O. boxes, available in 24 hours (individual box 250,000 GNF/yr plus 500,000 at opening; company box 1,200,000/yr plus 1,200,000), paid by Orange Money, plus EMS and parcels. The site never uses the words "code postal". | https://www.laposte.gn/ | Fetched |
| On 16 July 2025, 15 postal relay points opened in TotalEnergies stations in Conakry. These are pickup points, not an addressing system. | guineenews.org, 17 Jul 2025 | Search only |

## Regulator (ARPT)

| Finding | Source | Status |
|---|---|---|
| Tender DAO N°002/ARPT/DTEP/2025 (posted 18 Aug 2025) recruits a consultancy to run the "États généraux du secteur des postes". The site does not mention addressing or postcodes. | https://www.arpt.gov.gn/dossier-dappel-doffre-dao-n002-arpt-dtep-2025-recrutement-dun-cabinet-pour-la-realisation-des-etats-generaux-du-secteur-des-postes-en-republique-de-guinee/ | Fetched |
| We found no outcome of these États généraux by October 2026. | searches, 18 Oct 2026 | Search only |
| ARPT and the UPU held postal regulation training in Aug 2024. | guineenews.org, 23 Aug 2024 | Search only |

## National addressing programme

| Finding | Source | Status |
|---|---|---|
| Minister of Urbanism Mory Condé describes a presidential national addressing programme. Kaloum is "effectué à 100%": avenues named and plates put up, after a pilot naming the villas of the cité ministérielle. Next in the plan: Dixinn and Matam, the rest of Conakry, Coyah and Dubréka, then regional and préfecture capitals. He promised a geolocation app "sur Google Maps", usable offline. The article does not mention house numbers or codes. | Africaguinee, 3 Oct 2024, https://www.africaguinee.com/adressage-des-rues-a-kaloum-les-explications-de-mory-conde-ministre-lurbanisme-et-de-lhabitat/ | Fetched |
| An op-ed criticises the choice of Kaloum street names. | Mosaïqueguinée, Oct 2024, https://mosaiqueguinee.com/2024/10/denomination-des-rues-de-kaloum-ne-trompons-pas-le-president-de-la-transition-par-i-j-keita/ | Search only |
| Guinea's addressing began in 1993 under the Second Urban Development Project, run by a municipal addressing unit in Conakry's technical departments. Streets were coded with the commune's initials and a number (`KA.23` is the 23rd street of Kaloum), doors were numbered metrically and alternately, and an address map and street index were published; the Third Urban Project (2003) extended signs to peri-urban areas. The address map defined the zones of a household-waste collection system run by small enterprises, after which the collection rate rose from 20 % to 80 %, and it located neighbourhoods for secondary-road works. Before addressing, fewer than 40 % of tax assessment notices were collected. | Farvacque-Vitkovic et al., *Street Addressing and the Management of Cities*, World Bank (2005), pp. 65–69, https://documents1.worldbank.org/curated/en/573071468142795481/pdf/329230Street0Addressing01not0external1.pdf (French edition: https://documents1.worldbank.org/curated/en/617021472230929414/pdf/32923Fren-ver-0stion0des0Villes0010.pdf) | Fetched |
| We found no 2025–2026 news of the programme being extended beyond Kaloum. | searches, 18 Oct 2026 | Search only |
| The MATD (territorial administration ministry) homepage shows no addressing project. | https://matd.gov.gn/ | Fetched |

**Rule: official data first.** Where the state has an address, N-Ways uses its data as written and issues no competing code, because a second address for the same door would compete with the state's and confuse people who already use it. In Kaloum the official street name is primary, and the N-Ways number is a door-level complement until official numbers exist (SPEC §8.0).

**Interoperation.** Where a Kaloum street plate exists, the registry stores `street` (and `streetNumber`, if one is ever assigned) on the compound's entrance, with `source: programme-national-adressage`. When the programme reaches other communes, the N-Ways code and the street address point to the same gate. If the state issues house numbers, N-Ways records them as the official address and shows them first.

## OpenStreetMap and open data

On 17 Oct 2026 OSM had 457 objects with `addr:housenumber`, 637 with `addr:street` and 422 with `addr:postcode` (count on the Geofabrik extract of that day). The `addr:postcode` values cannot be real postcodes, since none exist; they are probably BP numbers or imports. We found no Guinean address dataset with a reuse licence.

OSM does have **official quartier polygons**: 397 at `admin_level=10`, of which 128 lie within Conakry, plus quartiers of Nzérékoré, Coyah and others. The model uses them as places ([model.md](model.md) §5.1).

## Administrative structure (changed in 2024 and 2026)

- **Regions.** Until August 2026 there were 8 regions (ISO 3166-2 GN-B, C, D, F, K, L, M, N) and 33 préfectures with two-letter ISO codes. Presidential decrees of about 20 Aug 2026 created 10 regions (Beyla split from Nzérékoré, Siguiri from Kankan) and 44 préfectures, including Kamsar, Timbo, Kintinian and Kouankan. The implementing texts are pending, and ISO has no codes yet for the new units.
  - Focus Guinée, 25 Aug 2026, https://focusguinee.info/2026/08/25/guinee-une-nouvelle-carte-administrative-en-dix-regions/ (fetched).
  - billetdujour.com and investigatorguinee.com, Aug 2026 (search only).
- **Conakry.** The capital went from 5 communes to 13:
  - The CNT voted a law creating 17 new communes on 18 Jan 2024 (guineenews.org, search only).
  - Ratoma was split into Ratoma, Lambanyi and Sonfonia, and Matoto into Matoto, Gbessia and Tombolia (guineenews.org, 29 Apr 2024, fetched).
  - The 31 May 2026 communal elections covered Kaloum, Dixinn, Matam, Ratoma, Lambanyi, Sonfonia, Matoto, Gbessia, Tombolia, Kassa, Manéah, Kagbélen and Sanoyah (guineenews.org, 5 Jun 2026, fetched).
  - Kagbélen came from Dubréka, and Manéah and Sanoyah from Coyah (citypopulation.de citing the INS, fetched).
- **Below préfectures** come sous-préfectures, districts (rural) and quartiers (urban), with secteurs below those. OSM holds only 27 sous-préfecture polygons, so the national count of about 304 was not verified.

**Why this matters for the model.** Boundaries and names above the quartier have changed twice in three years. N-Ways Guinea codes therefore depend on no administrative boundary. They use five frozen frames (the postal regions) and areas frozen when their first code is issued. Administrative names (commune, préfecture, region) are shown next to a code as labels, looked up from its position, and they can change without changing any code.

## Population

- 2014 census (RGPH-3): 10,523,261 people (citypopulation.de citing the INS, fetched); Conakry 1,660,973, about 15.8 % (search only).
- 2025 census (RGPH-4), preliminary results of 25 Feb 2026: **17,521,167** people, 38.7% urban, 43% under 15 (guineenews.org, fetched).
  - Conakry, within the new 13-commune boundary, had **3,407,327** people, about 19.4% (citypopulation.de citing the INS, fetched).
  - The largest communes are Gbessia (520,284), Kagbélen (395,370) and Lambanyi (385,884).
- The four natural regions are Guinée maritime (Basse-Guinée), Moyenne-Guinée (Fouta Djallon), Haute-Guinée and Guinée forestière. They match postal digits 1–4.

## Languages

- The constitution of 26 Sep 2025 (referendum of 21 Sep 2025) makes the national languages official alongside French, with French as the working language (coursupreme.org.gn; guineenews.org 30 Jun 2025; IRSEM brief 84; search only).
- The national languages usually cited are Pular, Maninka, Susu, Kissi, Kpelle (Guerzé) and Toma (Loma); sources disagree on the count.
- The official Latin alphabet was reformed after 1989 (ɓ, ɗ, ɲ, ŋ). N'Ko and Adlam are reportedly promoted (Wikipedia, unverified).

## Data protection

| Finding | Source | Status |
|---|---|---|
| Loi L/2016/037/AN of 28 Jul 2016 on cybersecurity and personal data protection is the main law. Processing requires prior declaration, and sensitive data prior authorisation. Transfers abroad need the authority's authorisation. | https://anssi.gov.gn/nproject/loi-l037-2016-relative-a-la-cybersecurite-et-la-protection-des-donnees-a-caractere-personnel/ ; https://dataprotection.africa/wp-content/uploads/2022/09/Guinea_Cybersecurity-and-DPA.pdf | Search only |
| A decree of 14 Apr 2025 sets security and data-protection conditions for civil-status and identification data, with 12 months to comply. It refers only to "l'autorité en charge de la protection des données". | guineenews.org, 15 Apr 2025, https://guineenews.org/2025/04/15/guinee-les-conditions-de-securite-et-de-protection-des-donnees-personnelles-fixees-decret/ | Fetched |
| The authority foreseen in art. 47 of the 2016 law had not been set up by 2021 (DLA Piper). No named authority appears to be operating in 2026. | DLA Piper, *Data protection laws of the world: Guinea* | Unverified for 2026 |

## Land and cadastre (for importing plot outlines)

The datums below were read on the EPSG pages. The other points come from secondary sources and have not been confirmed against the legal texts.

- The Code foncier et domanial is Ordonnance O/92/019 of 30 Mar 1992. Title is registered in a livre foncier kept by a conservateur foncier. The Direction nationale des domaines et du cadastre holds cadastral plans.
- Titled land is a small share, mostly in Conakry. Most tenure is customary or held under a permis d'habiter.
- Datums (from EPSG pages, fetched): Conakry 1905 / UTM 28N (EPSG:31528) was replaced by **Dabola 1981 / UTM 28N** (EPSG:3461), on the Clarke 1880 (IGN) ellipsoid with about 25 m accuracy to WGS 84. Eastern Guinea is presumably in UTM 29N (EPSG:3462). New surveys probably use WGS 84 / UTM 28N or 29N (EPSG:32628/32629); no legal text naming the required system was found.
- Bornage (fixing boundary markers) is done by sworn géomètres. Whether an ordre des géomètres-experts exists in Guinea is unconfirmed.

## Mapping agency

The Institut de Topographie et de Cartographie de Guinée (ITCG, formerly the IGN) is named by the UK PCGN as the authority for place names. Its address is BP 4485 Conakry (UN SALB listing). We found no website. JICA carried out large-scale topographic mapping of Conakry with it (openjicareport.jica.go.jp/pdf/12263224.pdf; search only).

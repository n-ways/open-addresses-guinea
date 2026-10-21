# Governance: N-Ways Guinea codes

Status: **issued on 20 October 2026** (3,808,784 codes, provisional until residents confirm them); open under the licences in [LICENSING.md](LICENSING.md). These are "N-Ways addresses", not national addresses or postcodes, until a Guinean authority adopts them.

## Who decides what

| Decision | Who | How |
|---|---|---|
| Format, frames, alphabet, check math (`engine/SPEC.md`) | N-Ways maintainers of this repository | Change by pull request, with a written reason and a migration note. **A change may never alter an issued code.** |
| Frames (`model/frames.*`) | Frozen at the first issued code | Cannot be changed. A new frame can only be added for land not covered, and would get the next digit after 4. |
| Areas: names, polygons, digits | Registry build plus people's confirmations | An area is frozen when its first code is issued. A commune can rename it; the new name is added and the old one stays valid. |
| Grouping of buildings into compounds, profiles | Automatic, from people's agreement (the self-correcting map), with no manual review queue | Confirmations by residents, couriers and arrivals |
| Issuing new codes | The one designated issuer (below) | `POST /v1/codes` on the issuing deployment of `server/`, by the rules of `engine/SPEC.md` section 7 |
| Opening a household's privacy request | The household | Takes effect immediately, with no review |

## Institutions concerned

These are the institutions the codes are designed to sit beside. The codes compete with none of them.

- **Poste GN SA** (La Poste guinéenne): its postal radical digits are the frame digits. The aim is for codes to print on BP forms next to the box number.
- **ARPT** (Autorité de régulation des postes et télécommunications): the États généraux des postes (tender 2025) are the natural place to present the model.
- **Ministère de l'Urbanisme et de l'Habitat**: owns the presidential national addressing programme (Kaloum, 2024). Its street names are recorded on N-Ways entrances.
- **Ministère des Postes, des Télécommunications et de l'Économie numérique.**
- **Gouvernorat de la Ville de Conakry and the 13 communes** (Kaloum, Dixinn, Matam, Ratoma, Lambanyi, Sonfonia, Matoto, Gbessia, Tombolia, Kassa, Manéah, Kagbélen, Sanoyah): quartier names and boundaries.
- **ITCG / IGN Guinée** (Institut de topographie et de cartographie): geodesy and place names.
- **INS** (Institut national de la statistique): RGPH-4 enumeration areas, and quartier and district lists.
- **Direction nationale des domaines et du cadastre**: survey plans. A code is never a land title.
- **ANSSI**, and the data-protection authority once it is constituted (Loi L/2016/037/AN, art. 47).
- **Emergency services** (civil protection, SAMU, police): codes in dispatch.
- **Couriers, banks, utilities, mining operators (Boké, Siguiri)**: look-up through the N-Ways partner API.

## One issuer

Every code is a number from a name's national range, so two parties issuing independently would hand the same number to two homes. Guinea therefore has exactly one issuer at any time: N-WAYS LIMITED today, or the public body the State designates. Only the issuer's deployment of `server/` holds issuing keys; every other deployment is read-only and imports the issuer's published exports. A change of issuer is a hand-over: the new issuer imports the last export of the old one, the old one stops issuing, and only then does the new one start ([server/README.md](server/README.md#one-issuer)).

## Hand-over

The repository is self-contained: engine, data, rules and maintainers. It can transfer to a Guinean institution that adopts it without forking the engine, and N-Ways would then follow that institution's rules.

## Maintainers

The N-Ways Addressing engineering team, N-WAYS LIMITED (hello@nways.ng). A Guinean institution that adopts the registry names its own maintainers. How to propose a change is in [CONTRIBUTING.md](CONTRIBUTING.md); how to report a problem is in [SECURITY.md](SECURITY.md).

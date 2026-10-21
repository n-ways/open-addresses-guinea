# Contributing

Corrections and improvements are welcome from anyone: a commune, a ministry, a courier, a researcher or a resident.

## What can change, and how

| You want to | Do this |
|---|---|
| Report a wrong place name, a wrong area, a missing or duplicate compound | Open an issue with the machine form (`GN-…`) or the spot code, and what is wrong. Residents can also say so in the N-Ways app, where agreement from different people corrects the map. |
| Give a commune's chosen plate name for a flagged area | Open an issue or a pull request against `model/names.json` with the area's zone (`0-00412`), the name and the commune's reference. The new name is added; the old one stays valid and no number changes. |
| Propose a change to the engine or the specification | Open a pull request that changes `engine/SPEC.md`, `engine/reference/` and the vectors together, with the reason and a migration note. |
| Fix the server, the tools or the documents | Open a pull request with the change and its tests. |

## Rules every change keeps

- **An issued code never changes.** No change may renumber, move or reuse an issued code, frame, name id, block or area index. Retired numbers stay retired.
- **One issuer.** New codes are issued only by the designated issuer's deployment of `server/` (GOVERNANCE.md, "One issuer"). A pull request never adds codes to `registry/` by hand; the registry is the issuer's export.
- **People never see a check digit.** Plates and written forms carry the name and the number; the check digit is in the machine form only.
- **Places, never people.** No name, household size or photograph of a person enters the registry.
- The engine and the server use the Python standard library only.

## Checks to run

```sh
python3 engine/reference/gn_codes.py test
python3 -m unittest discover -s server/tests -t .
```

A change to the engine rebuilds `engine/reference/vectors.json` with `python3 tools/vectors.py`; every implementation must then reproduce the new vectors.

## Licences

By contributing you agree that your contribution is published under the licence of the part it changes: Apache 2.0 for code, ODbL 1.0 for data, CC BY 4.0 for documents ([LICENSING.md](LICENSING.md)).

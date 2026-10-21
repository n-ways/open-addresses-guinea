# Reporting a problem

Write to **hello@nways.ng** to report:

- a security problem in the server or the engine (for example a way to issue or change codes without a key, or to read anything beyond the published registry);
- data that should not be public (for example a code that identifies a person, or a sensitive site);
- a code that sends people to the wrong place in a way that could cause harm (an emergency route, a health facility).

Give the machine form or the spot code where it applies, what you observed and how to reproduce it. Please do not open a public issue for a security problem until it is fixed.

A deployment you run yourself is yours to secure: serve it over HTTPS, keep `ISSUE_KEYS` secret, and run it read-only unless it is the designated issuer ([server/README.md](server/README.md)).

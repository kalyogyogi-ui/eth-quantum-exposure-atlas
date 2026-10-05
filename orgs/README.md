# Organisation registry

`registry.yaml` lists 19 organisations and 96 contracts for `python -m atlas orgs`. Every
address was copied from a file the organisation publishes in its own GitHub repository
(the `source_url`), and `python -m atlas orgs-check` confirms each address still appears
there. All entries are `published: false`.

Notes on sources:

- **Aave**: the Aave address book is maintained by BGD Labs for the Aave DAO.
- **OP Mainnet**: from Optimism's superchain registry. Other OP-stack chains (Unichain, Ink,
  World Chain, Soneium) are in the same registry. They are left out because that registry is
  Optimism's, not those chains' own documentation.
- **Frax**: from the constants file in Frax's own contracts repository.
- **Liquity**: v1 deployment file. Liquity v1 has no admin keys by design, which makes it a
  useful control case for rule R0.

Skipped because their address lists are only on documentation sites this build environment
cannot reach (not GitHub): Ethena, Circle (USDC), Tether, Rocket Pool, Sky/Maker, Base,
ether.fi, Morpho. They can be added with a `source_url` to their official docs page.
Wrapped BTC was skipped because its repository does not list the deployed address.

Each run writes `out/<slug>.json` and `out/<slug>.md`. That directory is git-ignored, since
every report is a draft until the organisation has been notified.

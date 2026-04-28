# Contributing to score-core

`score-core` is the Python reference implementation of the Score specification. This repository contains the parser, validator, schema models, library validator, Context API models, Recording models, and command-line interface.

If you are looking to contribute to the Score specification itself, see [score](https://github.com/multipleworks/score). The specification is the canonical source; this repository implements it.

## What belongs in this repository

- Implementation code (parsers, validators, schema models, the CLI)
- Tests for that code
- Documentation specific to using `score-core` as a library or CLI (installation, API reference, examples of programmatic usage)
- Changelog entries describing changes to the implementation

## What does not belong in this repository

- The Score specification documents. Those live in [score](https://github.com/multipleworks/score) and are linked from the README. Do not copy specification documents into this repository, even for convenience.
- Documentation describing what Score is at the format level. The README provides a brief framing for context; deeper explanation belongs in the specification.
- Maestro-specific code or runtime adapters. Those belong in the runtime they target.
- Configuration for any specific deployment. `score-core` is a library; configuration belongs to the application that uses it.

## The single-source-of-truth rule

The Score specification has one canonical home: the [score](https://github.com/multipleworks/score) repository. `score-core` implements that specification but does not republish it.

If you find yourself wanting to add a copy of a specification document to this repository (for example, to make it available alongside the implementation), do not. Link to the canonical version instead. Duplicated documentation drifts; a developer reading the duplicate will eventually see something the canonical version no longer says.

This rule applies recursively. If `score-core` documentation needs to refer to a specific behaviour described in the specification, link to the relevant section of the specification document rather than restating it.

## Specification compatibility

`score-core` targets a specific Score specification revision. The version of the specification supported is declared in the README and in the package metadata. When the specification is updated, `score-core` is updated to match in a subsequent release.

If a specification update introduces a required field that did not exist previously, `score-core` follows the migration path described in the specification (typically: optional in the revision that introduces it, required in the next protocol version).

`score-core` does not anticipate specification changes. The implementation matches a published specification revision, not an unpublished draft.

## Making changes

For bug fixes (incorrect behaviour relative to the specification, parsing errors, validator false positives or false negatives), open a pull request with a test case demonstrating the bug.

For new features (new validation rules, new CLI commands, new convenience methods), open an issue first to discuss whether the feature belongs in `score-core` or in a separate package. The principle: `score-core` implements what the specification requires. Features that go beyond the specification belong elsewhere.

For changes that require a specification update first, do not open a pull request against `score-core` until the specification change has landed in [score](https://github.com/multipleworks/score). The specification leads; the implementation follows.

## Style

Code follows standard Python conventions (PEP 8, type hints, docstrings on public APIs). Documentation is written in British English. Prose uses hyphens (-) rather than em-dashes for any inline separator. The voice is functional and rule-stating; this is reference documentation, not editorial writing.

Tests are required for any new behaviour. Bug fixes require a regression test demonstrating the bug and verifying the fix.

## Releases

Releases follow semantic versioning. Patch releases (`0.1.x`) are bug fixes and minor improvements that do not change behaviour. Minor releases (`0.x.0`) introduce new features or support for new specification revisions. Major releases (`x.0.0`) reflect breaking changes to the implementation's public API.

Each release includes:

- An updated changelog
- An updated README version line stating which specification revision is supported
- A tagged Git release matching the published PyPI version

## Licence

By contributing, you agree that your contributions are licensed under the same MIT licence that covers the rest of this repository.

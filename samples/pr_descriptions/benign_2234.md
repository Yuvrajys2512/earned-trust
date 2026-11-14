## Fix analyzer when SuppressSourceGeneration = true (#2234)

This change makes the analyzer keep validating types that opt out of source generation,
and hardens member collection in `TypeCollector` against duplicate and mixed key kinds:
a member whose key collides or whose key kind doesn't match is skipped after its diagnostic
is reported, instead of crashing the generator.

- Analyzer diagnostics reported for suppressed types
- No more AD0001 / CS8785 crashes on duplicate or mixed keys
- 10 new tests

# Earned Trust in AI Code — Junction 2026

**Challenge:** How does AI code review keep pace with AI-written code, while humans stay accountable for every change? (Tietoevry, Junction 2026, Espoo)

**Our answer (working title):** *The AI proves what changed. The human predicts what should happen. Every mismatch is the review.*

Instead of asking a human to read 200 agent-written lines, we:

1. **Prove** each behavior change with tests that pass on the old code and fail on the new code.
2. **Ask** the named human what *should* happen before revealing what the code does.
3. **Measure** the AI reviewer on this very PR by planting known bugs it must catch.
4. **Refuse** to auto-approve anything the requirement doesn't cover.
5. **Record** a signed review record: what was proven, what was refused, what the human predicted, who signed.

Demo: agent-written fixes in the MessagePack-CSharp repo (branches `ju26-issue-2234`, `-2283`, `-2129`, `-2297`).

- Concept card: [docs/03_CONCEPT.md](docs/03_CONCEPT.md)
- How it works: [docs/04_ARCHITECTURE.md](docs/04_ARCHITECTURE.md)
- Decision log: [docs/DECISIONS.md](docs/DECISIONS.md) · Lessons: [docs/LESSONS_LOG.md](docs/LESSONS_LOG.md) · Failure modes: [docs/FAILURE_MODES.md](docs/FAILURE_MODES.md)

Team: Yuvraj Srivastava (solo).

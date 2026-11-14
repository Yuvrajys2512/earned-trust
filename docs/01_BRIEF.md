# 01 — Challenge brief (Earned Trust in AI Code)

Sponsor: Tietoevry (the agent commits are authored from a `tieto.com` address, dated 12 Nov 2026 — made for this event).
Event: Junction 2026, Hype Areena, Espoo. Final submissions **Sun 15 Nov 10:00**, review 14:00, ends 17:00 (Helsinki time).
Preliminary distribution (Fri night): 25 teams on this challenge (vs 70 on "Make Blueprints Talk").

## The challenge (as given)

**How does AI code review keep pace with AI-written code, while humans stay accountable for every change?**

### Introduction
It is Friday afternoon. A pull request lands from an agent. Two hundred lines, and your name is on the approval. Usually you would open the diff and start digging. But what if the change opened with its own explanation? What it does, why it was made, what else it touches, and how sure the AI is about each part. Suddenly you are not hunting for problems. You are checking a story, and questioning the parts that do not add up.

Pick Earned Trust in AI Code, and help define how code explains itself now and in the future.

### Background
- Agent tokens passed human tokens in February 2026 and reached 7.3 trillion by August (OpenRouter data, a16z chart).
- Reviewing every change by hand does not scale, yet engineers need a sound basis to trust AI-reviewed code.

### The challenge
Design an AI code review concept, then show it works. Define the concept, principles, reference implementation and technology considerations, across frontend, backend and security.

Challenge the traditional model: is line-by-line review still the right way to ensure quality? Balance risk, hallucination, transparency, confidence and quality in AI review. The result is a reference implementation that illustrates the concept – it is not a product.

### What we expect from each team
1. Define the concept: what your team recommends the "PR review" factory should follow.
2. State its key principles, including how it balances risk, hallucination, transparency, confidence and quality.
3. Illustrate it as a reference, on one sample agent-written change with its requirement ID.
4. Show what the AI found, what it refused to decide, and why.
5. Show how the evidence lets a named human accept the change without a full read.
6. Name the failure modes you saw, and keep a short log of decisions.

Use synthetic or cleared sample data only.

### Code input
Repo: https://github.com/te-industry-tech-office/junction26-messagepack-csharp (make your own copy before you start). Branches with AI-made changes:
- `ju26-issue-2283` — agentic implementation of bug #2283 (4 files)
- `ju26-issue-2234` — agentic implementation of bug #2234 (4 files)
- `ju26-issue-2129` — agentic implementation of issue #2129 (28 files)
- `ju26-issue-2297` — agentic implementation of issue #2297 (237 files)

"We encourage to think outside of the box and in our evaluation we put more weight on the concept than only the technical implementation. HOW CAN AI REVIEW THE CODE MADE BY AI SO THAT HUMANS CAN TRUST IT?"

### Deliverables
- **Concept card:** recommendation, principles, trade-offs, limits
- **Live walkthrough** showing where the trust comes from
- **Lessons log** and a **demo video/presentation**

Out of scope: a finished product, model training and vendor selection.
Expected outcome: a concept with explicit trade-offs that humans can trust and be accountable for.

## How we map deliverables to files

| Expectation / deliverable | Where it lives |
| --- | --- |
| 1–2 Concept + principles, concept card | `docs/03_CONCEPT.md` |
| 3 One sample change with requirement ID | Demo on `ju26-issue-2234` (#2234); record in `out/` |
| 4 Found / refused / why | Review record `findings[]`, `refusals[]` |
| 5 Named human accepts without full read | Predict-then-reveal flow + signed record |
| 6 Failure modes + decision log | `docs/FAILURE_MODES.md`, `docs/DECISIONS.md` |
| Lessons log | `docs/LESSONS_LOG.md` |
| Live walkthrough + video | Built in the last round (see `docs/05_PLAN.md`) |

## Reading between the lines
- The two hardest expectations are #4 ("what it refused to decide") and #5 ("named human accepts without a full read"). That is where to win.
- "Is line-by-line review still right?" is an invitation to say **no** and propose a different unit of review.
- "Across frontend, backend and security" — the sample is backend (C# source generator). Cover security via the untrusted-story / prompt-injection angle; mention frontend as how the human sees it (the review UI).
- The brief's own premise ("the change opened with its own explanation") is a risk: a fluent story lowers human guard and is a prompt-injection surface. Our concept treats the story as untrusted.

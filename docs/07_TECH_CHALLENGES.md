# 07 — Tech challenges (partner prizes)

Junction says tech challenges "run across every track, so any team can take them on alongside their track" — no stated cap. Prizes are usually for **best use**, so only integrate where the partner tech is load-bearing.

Partners listed on 2026.hackjunction.com: OpenAI Codex, NVIDIA, Featherless, Modal, Qualia, CRACI, Atech.dev, Scailab, IronShard, Cloudinary, Wendy, Aiven, Oxylabs.

| Partner | Fit | How it's load-bearing in our concept | Status |
| --- | --- | --- | --- |
| OpenAI Codex | Strong | Codex as the *author agent* whose PRs we review, or as test generator. Story: "how to trust coding agents" | TODO: read brief |
| NVIDIA (Nemotron) | Strong | Reviewer model; open weights → self-hostable, code never leaves the company (enterprise argument) | TODO: read brief |
| Modal | Strong | Sandboxed, parallel runs of tests on base vs PR and mutant runs | TODO: read brief |
| Featherless | Good | Second model family as independent reviewer (counters self-preference bias) | TODO: read brief |
| Aiven | Cheap add | Postgres for review records / decision log | TODO: read brief |
| Cloudinary | Better for Blueprints track | — | skip here |
| Oxylabs | Weak | GitHub API already gives issue text | skip |
| Qualia, CRACI, Atech.dev, Scailab, IronShard, Wendy | Unknown | Paste their briefs here and re-evaluate | TODO |

Rule: wire partners in Round 4 unless one is needed earlier (e.g. Modal if local .NET is too slow).

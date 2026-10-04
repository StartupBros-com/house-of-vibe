# House of Vibe

The scripts, checkers and examples from [House Notes](https://houseofvibe.ai/blog), plus the tools we ship for coding agents.

## Notes

Each folder belongs to one post and holds exactly the files that post links to. The post says what the files do, how they were tested, and what they don't show, so read it before you run anything here. The same files are served at `https://houseofvibe.ai/notes/<folder>/`, and CI fails if this copy and the site's copy ever differ.

| Folder | Post | Run |
|---|---|---|
| [`notes/claude-code-auto-memory`](notes/claude-code-auto-memory) | [Find the Claude Code memories your MEMORY.md no longer reaches](https://houseofvibe.ai/blog/claude-code-auto-memory) | `python3 memory_reach.py check --all --show 0` |
| [`notes/claude-code-project-memory`](notes/claude-code-project-memory) | [Give Claude Code project instructions you don't have to repeat](https://houseofvibe.ai/blog/claude-code-project-memory) | `node --test quote.test.mjs` beside your own `quote.mjs` |

Both are dependency-free: the checker runs on the Python standard library (3.10 or newer), and the quote test on Node's built-in test runner.

## Tools

Each tool lives in its own repo, with its own releases and issues. Install any of them from the House of Vibe marketplace inside Claude Code:

```
/plugin marketplace add https://github.com/StartupBros-com/hov-marketplace.git
/plugin install memory-dream@hov
```

| Tool | What it does |
|---|---|
| [memory-dream](https://github.com/StartupBros-com/memory-dream) | A sleep cycle for Claude Code auto-memory: an operator-gated consolidation pass plus a recall eval |
| [rent-check](https://github.com/StartupBros-com/rent-check) | Audits CLAUDE.md, AGENTS.md and the rest of the always-loaded context, so every line pays rent or gets cut |
| [skill-tuner](https://github.com/StartupBros-com/skill-tuner) | Tells you whether a change to a SKILL.md, AGENTS.md or CLAUDE.md actually worked |
| [harness-vet](https://github.com/StartupBros-com/harness-vet) | Vets skills, plugins, MCP servers and repos before you add them to your harness |
| [papercut](https://github.com/StartupBros-com/papercut) | Captures the small frictions agents route around silently and mines them into ranked fixes |
| [pro-gate](https://github.com/StartupBros-com/pro-gate) | A GPT Pro final-tier reviewer for pull requests |
| [design-rails](https://github.com/StartupBros-com/design-rails) | Keeps agents on your real design system, derived from your code and enforced in CI |
| [wsl-cdp](https://github.com/StartupBros-com/wsl-cdp) | Drives your real, logged-in Windows browser from WSL2 |
| [product-video](https://github.com/StartupBros-com/product-video) | Agent-made product walkthrough videos from a real browser session |
| [sign-it](https://github.com/StartupBros-com/sign-it) | Say "sign that" and get the signed PDF back |
| [token-eater](https://github.com/StartupBros-com/token-eater) | Spends about-to-expire AI credits on safe, verified maintenance chores |

Not in the marketplace: [synthetic-panel](https://github.com/StartupBros-com/synthetic-panel), a zero-key synthetic customer panel for testing marketing copy.

## License

MIT. See [LICENSE](LICENSE).

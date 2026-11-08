# House of Vibe

The scripts, checkers and examples from [House Notes](https://houseofvibe.ai/blog) posts, one folder per post.

## Notes

Each folder belongs to one post and holds exactly the files that post links to. The post says what the files do, how they were tested, and what they don't show, so read it before you run anything here. The same files are served at `https://houseofvibe.ai/notes/<folder>/`, and CI fails if this copy and the site's copy ever differ.

| Folder | Post | Run |
|---|---|---|
| [`notes/claude-code-auto-memory`](notes/claude-code-auto-memory) | [Find the Claude Code memories your MEMORY.md no longer reaches](https://houseofvibe.ai/blog/claude-code-auto-memory) | `python3 memory_reach.py check --all --show 0` |
| [`notes/claude-code-project-memory`](notes/claude-code-project-memory) | [Give Claude Code project instructions you don't have to repeat](https://houseofvibe.ai/blog/claude-code-project-memory) | `node --test quote.test.mjs` beside your own `quote.mjs` |

Both are dependency-free: the checker runs on the Python standard library (3.10 or newer), and the quote test on Node's built-in test runner.

## Tools

The tools we make for coding agents (memory-dream, rent-check, skill-tuner, pro-gate and the rest) live in [hov-stack](https://github.com/StartupBros-com/hov-stack), with their install steps, releases and issues. [synthetic-panel](https://github.com/StartupBros-com/synthetic-panel), a zero-key synthetic customer panel for testing marketing copy, has its own repo.

## License

MIT. See [LICENSE](LICENSE).

---

Built by [Will Mitchell](https://github.com/StartupBros) at [House of Vibe](https://houseofvibe.ai).

<!-- BEGIN:nextjs-agent-rules -->
# This is NOT the Next.js you know

This version has breaking changes — APIs, conventions, and file structure may all differ from your training data. Read the relevant guide in `node_modules/next/dist/docs/` before writing any code. Heed deprecation notices.
<!-- END:nextjs-agent-rules -->

# Lint before you push

`npm run lint` from `frontend/` before every push. CI Frontend (`.github/workflows/ci-frontend.yml`) runs the same command and blocks the merge if it fails. Vercel also lints during the build — a green local lint is the cheap signal that the Vercel deploy will succeed.

Some React-19 / Next-16 strict rules are currently demoted to warnings via `eslint.config.mjs` (TD-133 in `docs/tech-debt.md` lists which and why). When you touch a file flagged in TD-133's list, fix the underlying issue rather than copy the bad pattern, and re-promote the corresponding rule to `"error"` in eslint config once the file is clean.

Review all current changes with `git diff` and `git status`.

Write a clear, descriptive commit message following these rules:
- Imperative mood first line, under 72 characters
- Blank line, then bullet points for details if needed
- Reference any relevant issue numbers

Then:
1. Stage all relevant changes (use `git add -p` if changes span multiple concerns — split into separate commits)
2. Commit with the message
3. Push to the current branch

If tests exist, run them first. If any fail, stop and report — do not commit.

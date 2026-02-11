Prepare and create a pull request:

1. Run `git status` and `git log --oneline main..HEAD` to understand changes
2. Run tests if they exist. Stop if any fail.
3. Create a PR using `gh pr create` with:
   - A clear, descriptive title
   - A body that explains: what changed, why, and how to test
   - Any relevant labels or reviewers if configured

If there are uncommitted changes, commit them first following our commit conventions.

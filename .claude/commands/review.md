Review the current uncommitted changes (`git diff`) for:

1. **Bugs:** Logic errors, off-by-one errors, null/undefined risks
2. **Security:** Injection vulnerabilities, exposed secrets, auth issues
3. **Performance:** Unnecessary loops, missing indexes, N+1 queries
4. **Style:** Naming, consistency with existing patterns in the codebase
5. **Tests:** Are the changes adequately tested? What's missing?

Be specific — reference file names and line numbers.
For each issue, rate severity: Critical | Important | Nit

If the code looks good, say so — don't invent problems.

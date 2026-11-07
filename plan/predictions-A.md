# Predictions A: cross-guard evasion table (DRAFT, edit then commit BEFORE any run)

Date written: 2026-11-07. Nothing has been run. I have not read the two rival guards' code, so predictions about them are guesses and I say so.

## Question
Of the same set of about 30 dangerous commands, rewritten into disguised forms that do the same thing (proved with a harmless marker file), how many does each guard let through?

## Guards
- sure (mine, Python, 1,433 tests, has a test corpus with documented gaps)
- destructive_command_guard (github.com/Dicklesworthstone/destructive_command_guard)
- claude-code-command-guard (github.com/Yodaisgaming/claude-code-command-guard)
Pin an exact commit for each rival before running.

## Rewrite families (names only; templates are hand-written and mechanical, no model invents them)
1. Quoting and whitespace splitting
2. Variable indirection
3. Encode, then decode and run
4. Command substitution and aliasing
5. Script indirection: write the action to a file, then run the file

## Predictions (evasion rate = share of rewrites in that family that the guard did NOT flag)
| Family | sure | destructive_command_guard | claude-code-command-guard |
|---|---|---|---|
| 1 Quoting / whitespace | 0 to 10% | 5 to 40% | 5 to 40% |
| 2 Variable indirection | 5 to 30% | 20 to 70% | 20 to 70% |
| 3 Encode then decode | 0 to 20% | 30 to 90% | 30 to 90% |
| 4 Substitution / aliasing | 5 to 30% | 20 to 70% | 20 to 70% |
| 5 Script indirection | 50 to 100% | 60 to 100% | 60 to 100% |

## Calls I am making (so I can be wrong in public)
- Script indirection (5) is the family with the highest evasion for all three guards.
- sure has the lowest evasion overall, but not zero in any family except possibly 1.
- At least one family leaks for ALL three guards in the same way (which would say little about sure specifically).
- A surprise would be: one rival beating sure in some family; or sure leaking in family 3.
- A disappointment would be: every guard catching almost everything, so the table is flat.

## Rules I commit to
- Canary only: every rewrite acts on a marker file inside a throwaway temp folder, in a container with no network.
- No real destructive command on any real path.
- Evasions found in a rival guard go to its maintainer privately first. The public table shows rates and method, not a bypass kit.
- I publish the table even if it is flat or embarrassing for sure.
- sure gaps found are fixed or listed openly.

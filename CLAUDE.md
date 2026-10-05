# Project rules

## Python style (applies to all Python in this repo)

- Follow **PEP 8**: 4-space indents, lines of at most 79 characters
  (72 for docstrings and comments), `snake_case` functions and variables,
  `CapWords` classes, `UPPER_CASE` constants, imports at the top of the file
  grouped stdlib / third-party / local, two blank lines between top-level
  definitions.
- Follow **PEP 257** for docstrings: every module, class and function
  gets one. Use triple double quotes, a one-line summary in the imperative
  mood ending with a period, then a blank line and a longer description if
  needed. For multi-line docstrings, put the closing quotes on their own line.
- Avoid `# noqa` workarounds for style rules. Fix the code instead (for
  example, run scripts as modules, `python -m scripts.fetch_all`, rather
  than editing `sys.path`).
- Explain the "why" in comments, not the "what".

# Security Policy

## Reporting a vulnerability

If you believe you have found a security vulnerability, please report it
privately rather than opening a public issue.

- Preferred: open a private security advisory via GitHub
  ("Security" > "Report a vulnerability") on this repository, or
- Email the maintainers at barbalinardo@ucdavis.edu.

Please include enough detail to reproduce the issue. We will acknowledge your
report and work with you on a resolution and coordinated disclosure.

## Secrets and credentials

This project reads API keys and other credentials from environment variables
(for example, via a local `.env` file, which is gitignored). Never commit
secrets to the repository or paste them into issues or pull requests. If a
secret is exposed, rotate it immediately and report it through the channel
above.

# Security Policy

## Supported versions

Security fixes are applied to the latest `main` branch and the latest published release.

## Reporting a vulnerability

Do not open a public issue for a security vulnerability, credential exposure, or a way to access recordings outside the configured paths. Report it privately to the repository owner through GitHub's private reporting channel after it is enabled, or contact the maintainer directly.

## Credential handling

Recording Agent Hub does not store API keys or personal access tokens in its project config, job manifests, or logs. Supply credentials using the relevant agent's own login flow, macOS Keychain, launchd environment, or another secrets manager.

If a token is pasted into an issue, chat, terminal history, or commit, revoke it immediately and generate a replacement.

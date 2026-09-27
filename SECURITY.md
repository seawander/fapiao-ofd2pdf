# Security Policy

## Scope and expectations

This project converts untrusted **OFD** input into PDF. It is generated with
AI assistance and is provided **"as is", without warranty of any kind** (see the
disclaimer in the [README](README.md)). There is no guarantee of correctness or
security.

Because it parses complex XML and embedded resources, treat output and input as
untrusted. If you process documents from unknown sources, consider running the
converter in a sandbox or container.

## Supported versions

Only the latest `main` branch (and the most recent release tag) is supported.

## Reporting a vulnerability

- open a private advisory via GitHub:
  <https://github.com/seawander/fapiao-ofd2pdf/security/advisories/new>;
- or open an issue at
  <https://github.com/seawander/fapiao-ofd2pdf/issues> — this is fine for
  low-risk findings and for anything you are happy to discuss in public. For
  anything exploitable, please use the private advisory above and say so in
  the issue, or wait until a fix is released.

Include steps to reproduce, affected version/commit, and impact. Please give a
reasonable amount of time to respond before any public disclosure.

## Please do not send real documents

When reporting, redact or synthesise sample files. Do not attach real invoices,
official documents, or anything containing personal data.

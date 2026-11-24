# Threat model: <service>

<!-- From snicholls-tooling's templates/THREAT_MODEL.md (STANDARDS section 6): one per service. Keep it short and
     current; review it whenever an entry point, a secret or a trust boundary changes. Replace <...>. -->

- **Service:** <what it does, in one sentence>
- **Owner:** <repository or session>
- **Last reviewed:** <YYYY-MM-DD>

## 1. Assets

What an attacker wants: <customer money and balances, keys, personal data, availability, the integrity of the books>.

## 2. Entry points and trust boundaries

| Entry point | Who can reach it | Authentication | Input validated by |
|---|---|---|---|
| <HTTPS API `/v1/...`> | <the internet, behind Cloudflare> | <OAuth 2.1, ES256 tokens> | <parser and its fuzz target> |
| <webhook `/webhooks/<provider>`> | <the provider> | <signature, timestamp window> | <...> |

## 3. Secrets

| Secret | Where it lives | Who can read it | Rotation |
|---|---|---|---|
| <provider API key> | <`.credentials/<service>.env`; the key store in production> | <the service> | <how, how often> |

## 4. Threats (STRIDE) and mitigations

| Threat | Example | Mitigation | Test or check that proves it |
|---|---|---|---|
| Spoofing | <a forged webhook> | <signature verified, fail closed> | <conformance kit case> |
| Tampering | <a replayed event> | <dedup by event id, exactly-once ingest> | <property test> |
| Repudiation | <a disputed transfer> | <immutable facts, audit log> | <...> |
| Information disclosure | <a secret in a log or an error> | <`reveal()`, redacted errors by construction> | <kit's redaction check> |
| Denial of service | <an oversized request> | <limits, timeouts, rate limits> | <...> |
| Elevation of privilege | <a customer reaching admin routes> | <role checks on every route> | <...> |

## 5. Residual risks

<What is accepted, why, and until when.>

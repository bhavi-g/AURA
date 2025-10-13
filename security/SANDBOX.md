
# AURA Security & Sandbox Notes

- Run analyzers in **VM/gVisor/Firecracker** with read-only FS.
- Disable outbound network except allowlisted RPC & explorer endpoints.
- Non-root users, seccomp/apparmor profiles, resource quotas (CPU/mem/time).
- Verify supply chain: pin image digests, sign artifacts (cosign), SBOM.
- Secrets: short-lived task tokens, vault-managed; never in env or images.

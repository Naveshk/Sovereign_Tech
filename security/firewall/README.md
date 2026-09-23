# Host firewall policy

These files are deployment templates for a Linux production/air-gapped host. **Do not apply them blindly on a development machine.** Test rules in a maintenance window and keep console access available.

- Prefer nftables on the final Linux server.
- Allow only required local/internal traffic.
- Default-deny unapproved outbound internet traffic.
- Keep Ollama/ChromaDB/SQLite local to the host or controlled private network.

The Docker sandbox independently uses `--network none`, so generated code has no network namespace access.

# tcpdump evidence procedure

Run on the final Linux/air-gapped host with approved privileges.

1. Confirm `tcpdump --version`.
2. Start the Workbench backend.
3. As a Manager, use **Network Evidence → Capture 10s evidence**.
4. Inspect the generated header-only text file under `data/network_evidence/`.
5. Look for unexpected public destination addresses during the capture window.

Example manual command:

```bash
sudo tcpdump -nn -tt -l -i any -c 100
```

This captures packet headers only. It is evidence for the observation window, not proof of a permanent air gap. Host firewall enforcement must be verified separately using the approved deployment rules.

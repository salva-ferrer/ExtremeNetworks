# Simulating LLDP endpoints (APs, phones) with Alpine + lldpd in GNS3

The public GNS3 appliance registry (`GNS3/gns3-registry`) has **no** IP phone or Wi-Fi access
point template (the closest, `cisco-vWLC`, is a CAPWAP controller, useless as an LLDP
endpoint). What worked: an **Alpine container running `lldpd`** that advertises whatever LLDP
identity you need.

## Docker template (API v2)

```
POST /v2/templates
{"template_type": "docker", "compute_id": "local", "name": "Alpine-lldpd",
 "image": "alpine:latest", "adapters": 1, "console_type": "telnet", "start_command": "/bin/sh"}
```
Without `"compute_id": "local"` the creation failed on our server. The server needs Internet
access (or a local registry) to pull `alpine:latest` the first time.

## Preparing the container (through its telnet console)

```
udhcpc -i eth0              # DHCP address (link the container to a NAT node first)
apk update
apk add lldpd
lldpd                       # start the daemon
lldpcli show configuration
```

## Access point identity (copy of a real AP)

```
lldpcli configure system description "Vendor AP Software, model-x, Test Lab AP"
lldpcli configure system platform "Vendor AP"
lldpcli configure system hostname "TestAP01"
lldpcli configure system capabilities enabled bridge
lldpcli show chassis details
```
Syntax **not** accepted: `capabilities bridge enabled` and `capabilities bridge, router`.
The valid one is `capabilities enabled bridge`. To suppress the Management Address TLV:
`lldpcli configure system ip management pattern "nomatch0"`.

## Checking from Switch Engine

```
restart port <p>                                # forces re-detection (device-detect)
show lldp port <p> neighbors detailed
show upm history detail                         # with a UPM profile attached: EVENT.DEVICE received
show log                                        # UPM.Msg.LLDPDevDetected ... device type is <TYPE>(<n>)
```

## Known limitation (unresolved)

With `Enabled Capabilities: Bridge`, EXOS 32.6.3 classified the `lldpd` endpoint as
**`ROUTER`**, not `BRIDGE`, while a real AP with the same capability shows as `BRIDGE`.
Ruled out: an explicit Router capability; the container's `ip_forward`
(`sysctl -w net.ipv4.ip_forward=0`); the Management Address TLV.

**Consequence:** to test device-type filters (`$EVENT.DEVICE`), temporarily accept `ROUTER`
in the lab and flag it in the code, or use real hardware. `lldpd` is fine to test the
**mechanism** (trigger, arguments, MAC guard, configuration applied and reverted) but does not
reproduce EXOS's internal classification exactly.

## LLDP-MED phones

`lldpd` can advertise LLDP-MED (device class, network policies). **Not tested by us** (a real
phone was used). If you try it, first check which `$EVENT.DEVICE` value EXOS receives.

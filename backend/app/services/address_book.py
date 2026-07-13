def build_address_book(clients):

    entries = []

    for client in clients:
        entries.append(
            {
                "name": client.name,
                "rustdesk_id": client.rustdesk_id,
                "group": client.group_name or "Clients",
                "hostname": client.hostname or "",
                "os": client.os or "",
                "ip": client.ip or "",
                "online": bool(client.online),
                "last_seen": (
                    client.last_seen.isoformat()
                    if client.last_seen
                    else None
                )
            }
        )

    return {
        "version": "1",
        "count": len(entries),
        "entries": entries
    }

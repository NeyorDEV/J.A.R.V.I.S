"""
network_radar.py — Radar des connexions réseau actives pour JARVIS
psutil (connexions TCP) + ip-api.com batch (GeoIP, gratuit, sans clé).
"""
import psutil
import requests
import socket
import time
from typing import Set
from concurrent.futures import ThreadPoolExecutor
from core.interlocuteur import nom_virgule

# ── Config ────────────────────────────────────────────────────────────────────
_LOCAL_LAT = 46.0
_LOCAL_LON = 2.0
_CACHE_TTL = 3600
_SCAN_WINDOW_S = 60   # fenêtre glissante détection scan (secondes)
_SCAN_MIN_PORTS = 4   # ports locaux distincts pour déclarer un scan

# ── État interne ──────────────────────────────────────────────────────────────
_geo_cache: dict = {}
_first_seen: dict = {}          # ip → timestamp première apparition
_scan_local_ports: dict = {}    # remote_ip → {local_port: last_seen_ts}
_dns_cache: dict = {}           # ip → hostname ('' si non résolu)
_dns_executor = ThreadPoolExecutor(max_workers=20, thread_name_prefix='dns')

# ── Table ports → services connus ─────────────────────────────────────────────
_PORT_SERVICES: dict = {
    21: 'FTP', 22: 'SSH', 25: 'SMTP', 53: 'DNS', 80: 'HTTP',
    110: 'POP3', 143: 'IMAP', 443: 'HTTPS', 465: 'SMTPS', 587: 'SMTP',
    993: 'IMAPS', 995: 'POP3S', 1194: 'VPN', 1723: 'PPTP',
    3389: 'RDP', 3478: 'STUN', 4433: 'HTTPS', 5222: 'XMPP',
    5228: 'FCM', 5349: 'STUNS', 8080: 'HTTP', 8443: 'HTTPS',
    9001: 'TOR', 9050: 'TOR', 9150: 'TOR',
}

# ── Plages IP privées à ignorer ───────────────────────────────────────────────
_PRIVATE = (
    '127.', '10.', '192.168.', '169.254.',
    '172.16.', '172.17.', '172.18.', '172.19.',
    '172.20.', '172.21.', '172.22.', '172.23.',
    '172.24.', '172.25.', '172.26.', '172.27.',
    '172.28.', '172.29.', '172.30.', '172.31.',
    '0.0.0.0', '::',
)

# ── Niveaux de risque pays ────────────────────────────────────────────────────
_HIGH_RISK   = {'RU', 'KP', 'IR', 'BY', 'SY'}
_MEDIUM_RISK = {'CN', 'VN', 'PK', 'NG', 'CU'}

# ── Whitelist processus système Windows ──────────────────────────────────────
_SYSTEM_PROCS = {
    'svchost', 'lsass', 'wininit', 'services', 'winlogon', 'csrss',
    'msmpeng', 'msmpcorservice', 'nissrv', 'mpdefendercoreservice',
    'spoolsv', 'searchindexer', 'searchprotocolhost', 'searchfilterhost',
    'wmiprvse', 'dllhost', 'taskhostw', 'sgrmbroker', 'runtimebroker',
    'wuauclt', 'usoclient', 'tiworker', 'trustedinstaller',
    'audiodg', 'sihost', 'ctfmon',
}


def _is_private(ip: str) -> bool:
    return any(ip.startswith(p) for p in _PRIVATE) or ':' in ip


def _process_name(pid) -> str:
    if not pid:
        return "Système"
    try:
        return psutil.Process(pid).name()
    except Exception:
        return "Inconnu"


def _evict_stale() -> None:
    now = time.time()
    stale = [ip for ip, v in _geo_cache.items() if now - v.get("ts", 0) > _CACHE_TTL]
    for ip in stale:
        del _geo_cache[ip]


def _batch_geoip(ips: list) -> None:
    """Résolution GeoIP via ip-api.com (batch 100 IPs/req, 45 req/min gratuit)."""
    to_resolve = [ip for ip in ips if ip not in _geo_cache]
    if not to_resolve:
        return
    for start in range(0, len(to_resolve), 100):
        chunk = to_resolve[start:start + 100]
        try:
            resp = requests.post(
                "http://ip-api.com/batch?fields=status,country,countryCode,city,lat,lon,isp,query",
                json=[{"query": ip} for ip in chunk],
                timeout=8
            )
            if resp.ok:
                for r in resp.json():
                    ip = r.get("query", "")
                    if r.get("status") == "success":
                        _geo_cache[ip] = {
                            "country": r.get("country", "Inconnu"),
                            "cc": r.get("countryCode", "??"),
                            "city": r.get("city", ""),
                            "lat": float(r.get("lat", 0)),
                            "lon": float(r.get("lon", 0)),
                            "isp": r.get("isp", ""),
                            "ts": time.time()
                        }
                    else:
                        _geo_cache[ip] = {
                            "country": "Inconnu", "cc": "??", "city": "",
                            "lat": 0.0, "lon": 0.0, "isp": "", "ts": time.time()
                        }
        except Exception as e:
            print(f"[RADAR] GeoIP error: {e}")


def _resolve_and_cache(ip: str) -> None:
    """Résolution DNS inverse en background, résultat mis en cache."""
    try:
        _dns_cache[ip] = socket.gethostbyaddr(ip)[0]
    except Exception:
        _dns_cache[ip] = ''


def _batch_dns_async(ips: list) -> None:
    """Lance les résolutions DNS non encore cachées sans bloquer."""
    to_resolve = [ip for ip in ips if ip not in _dns_cache]
    for ip in to_resolve:
        _dns_cache[ip] = ''  # placeholder pour ne pas re-soumettre
        _dns_executor.submit(_resolve_and_cache, ip)


def _is_system_process(proc: str) -> bool:
    """Vrai si le processus est un service système Windows à masquer par défaut."""
    return proc.lower().replace('.exe', '') in _SYSTEM_PROCS


def _update_scan_tracker(all_tcp) -> Set[str]:
    """
    Détecte les scans de ports entrants : même IP distante atteignant plusieurs ports
    locaux qui sont en état LISTEN sur cette machine.
    Les ports locaux éphémères (connexions sortantes) sont ignorés pour éviter
    les faux positifs avec HTTP/2 ou les pools de connexions.
    """
    now = time.time()

    # Ports actuellement en écoute sur cette machine
    listen_ports = {c.laddr.port for c in all_tcp if c.status == 'LISTEN' and c.laddr}

    for c in all_tcp:
        if c.status != 'ESTABLISHED' or not c.raddr or not c.laddr:
            continue
        # Connexion sortante (port local éphémère) → ignorer
        if c.laddr.port not in listen_ports:
            continue
        rip = c.raddr.ip
        if _is_private(rip):
            continue
        if rip not in _scan_local_ports:
            _scan_local_ports[rip] = {}
        _scan_local_ports[rip][c.laddr.port] = now

    # Purge des entrées périmées
    for rip in list(_scan_local_ports.keys()):
        ports = {p: t for p, t in _scan_local_ports[rip].items() if now - t < _SCAN_WINDOW_S}
        if ports:
            _scan_local_ports[rip] = ports
        else:
            del _scan_local_ports[rip]

    return {ip for ip, ports in _scan_local_ports.items() if len(ports) >= _SCAN_MIN_PORTS}


def get_radar_data() -> list:
    """Retourne les connexions TCP enrichies de géolocalisation et méta-données."""
    global _first_seen
    _evict_stale()
    now = time.time()
    seen: dict = {}
    all_tcp = []

    try:
        all_tcp = psutil.net_connections(kind='tcp')
        for conn in all_tcp:
            if conn.status != 'ESTABLISHED' or not conn.raddr:
                continue
            ip = conn.raddr.ip
            if _is_private(ip) or ip in seen:
                continue
            seen[ip] = {"ip": ip, "port": conn.raddr.port, "process": _process_name(conn.pid)}
    except Exception as e:
        print(f"[RADAR] psutil error: {e}")
        return []

    if not seen:
        return []

    # Détection scan de ports (sur toutes les connexions, pas uniquement ESTABLISHED)
    scan_ips = _update_scan_tracker(all_tcp)

    # Durée de vie
    for ip in seen:
        if ip not in _first_seen:
            _first_seen[ip] = now

    # Purge des IPs disparues depuis > 10 min
    for ip in [ip for ip, ts in list(_first_seen.items()) if ip not in seen and now - ts > 600]:
        del _first_seen[ip]

    _batch_geoip(list(seen.keys()))
    _batch_dns_async(list(seen.keys()))

    result = []
    for ip, conn in seen.items():
        geo = _geo_cache.get(ip, {})
        lat, lon = geo.get("lat", 0), geo.get("lon", 0)
        if lat == 0 and lon == 0:
            continue
        cc = geo.get("cc", "??")
        proc = conn["process"]
        port = conn["port"]
        isp = geo.get("isp", "")
        risk = "high" if cc in _HIGH_RISK else ("medium" if cc in _MEDIUM_RISK else "normal")

        duration_s = round(now - _first_seen.get(ip, now))
        is_new = duration_s < 30
        port_scan = ip in scan_ips

        # Connexions système sans risque → masquées par défaut
        is_filtered = _is_system_process(proc) and risk == 'normal' and not port_scan

        # Un scan remonte le niveau de risque
        if port_scan and risk == 'normal':
            risk = 'medium'

        result.append({
            "ip": ip,
            "port": port,
            "process": proc,
            "country": geo.get("country", "Inconnu"),
            "cc": cc,
            "city": geo.get("city", ""),
            "lat": lat,
            "lon": lon,
            "isp": isp,
            "risk": risk,
            "hostname": _dns_cache.get(ip, ''),
            "service": _PORT_SERVICES.get(port, ''),
            "duration_s": duration_s,
            "is_new": is_new,
            "is_filtered": is_filtered,
            "port_scan": port_scan,
        })
    return result


def get_radar_summary(data: list) -> str:
    if not data:
        return f"Aucune connexion externe active détectée{nom_virgule()}."
    visible = [c for c in data if not c.get("is_filtered")]
    n_sys = len(data) - len(visible)
    countries = list(set(c["country"] for c in visible)) if visible else []
    high = [c for c in data if c["risk"] == "high"]
    scans = [c for c in data if c.get("port_scan")]

    n = len(visible)
    txt = (f"Radar réseau activé. {n} connexion{'s' if n != 1 else ''} active{'s' if n != 1 else ''}"
           f" vers {len(countries)} pays")
    if n_sys:
        txt += f" ({n_sys} connexion{'s' if n_sys != 1 else ''} système masquée{'s' if n_sys != 1 else ''})"
    txt += "."
    if high:
        procs = list(set(c["process"].replace(".exe", "") for c in high))
        txt += f" Attention : {len(high)} connexion{'s' if len(high) > 1 else ''} à risque via {', '.join(procs)}."
    if scans:
        txt += f" Scan de ports détecté depuis {scans[0]['ip']} !"
    return txt

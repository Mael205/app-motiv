"""Diagnostic de la signature AMO — dit lequel des trois cas bloque.

    python diag-amo.py "user:1234:567" "le-secret"

Ne parle qu'à addons.mozilla.org. N'écrit rien, ne signe rien.
"""
import sys, time, json, urllib.request, urllib.error

try:
    import jwt
except ImportError:
    sys.exit("PyJWT manque. Lance-le avec le python du venv :\n"
             r"  ..\coach-api\.venv\Scripts\python diag-amo.py <issuer> <secret>")

if len(sys.argv) != 3:
    sys.exit(__doc__)

issuer, secret = sys.argv[1].strip(), sys.argv[2].strip()
ADDON_ID = "{381939a7-d32d-47c4-aa60-4c739057d0be}"

print(f"issuer : {issuer!r}  ({len(issuer.split(':'))} parties, attendu 3)")
print(f"secret : {len(secret)} caractères\n")

def appel(chemin):
    token = jwt.encode(
        {"iss": issuer, "jti": str(time.time()), "iat": int(time.time()),
         "exp": int(time.time()) + 60},
        secret, algorithm="HS256",
    )
    req = urllib.request.Request(
        "https://addons.mozilla.org" + chemin,
        headers={"Authorization": f"JWT {token}", "User-Agent": "coach-diag/1"},
    )
    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            return r.status, json.loads(r.read() or b"{}")
    except urllib.error.HTTPError as e:
        body = e.read().decode("utf-8", "replace")
        try:
            body = json.loads(body)
        except ValueError:
            body = body[:300]
        return e.code, body

code, corps = appel("/api/v5/accounts/profile/")
print(f"[1] identité du compte           -> HTTP {code}")
if code == 200:
    print(f"    connecté en tant que : {corps.get('username')} <{corps.get('email','?')}>")
    print(f"    accord de distribution accepté : {corps.get('read_dev_agreement') or 'NON / inconnu'}")
else:
    print(f"    {corps}")
    print("\n    => Les identifiants sont refusés. La clé a été révoquée (en")
    print("       régénérer une en invalide la précédente), ou issuer/secret")
    print("       ne viennent pas de la même paire.")
    sys.exit(1)

code, corps = appel(f"/api/v5/addons/addon/{ADDON_ID}/")
print(f"\n[2] l'ID {ADDON_ID} -> HTTP {code}")
if code == 404:
    print("    libre : personne ne l'a enregistré. Normal avant la 1re signature.")
elif code == 200:
    print(f"    existe déjà. statut : {corps.get('status')}")
elif code == 403:
    print("    OCCUPÉ PAR UN AUTRE COMPTE. C'est la cause du 403 de sign.")
    print("    => change l'id dans manifest.json (ex. coach-sonde-web@mael2.dev)")
else:
    print(f"    {corps}")

if corps and isinstance(corps, dict) and code == 200 and not corps.get("status"):
    pass

print("\n[3] verdict")
print("    Si [1] = 200 et read_dev_agreement est vide/NON :")
print("      l'accord n'est pas enregistré côté API. Rouvre")
print("      https://addons.mozilla.org/developers/addon/submit/agreement")
print("      et va jusqu'au bouton de validation en bas de page.")

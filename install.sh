#!/usr/bin/env bash
set -euo pipefail
app_source="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
app_target="$HOME/.local/share/adem-optimizer"
mkdir -p "$app_target/web" "$HOME/.local/bin" "$HOME/.local/share/applications" "$HOME/.config/systemd/user"
if [[ "$app_source" != "$app_target" ]]; then
    cp "$app_source/server.py" "$app_target/server.py"
    cp "$app_source/web/index.html" "$app_source/web/style.css" "$app_source/web/app.js" "$app_source/web/icon.svg" "$app_target/web/"
fi
python3 - "$app_target" <<'PY'
from pathlib import Path
import sys
home = Path.home()
target = Path(sys.argv[1])
service = f'''[Unit]
Description=Adem lokale Linux optimizer
After=graphical-session.target

[Service]
Type=simple
ExecStart=/usr/bin/python3 "{target}/server.py" --port 8765
Restart=on-failure
RestartSec=3
NoNewPrivileges=true
UMask=0077

[Install]
WantedBy=default.target
'''
(home / '.config/systemd/user/adem-optimizer.service').write_text(service)
launcher = home / '.local/bin/adem-optimizer'
launcher.write_text('''#!/usr/bin/env bash
set -euo pipefail
systemctl --user start adem-optimizer.service
for attempt in {1..30}; do
    if python3 - <<'CHECK'
import urllib.request
try:
    with urllib.request.urlopen('http://127.0.0.1:8765/api/state', timeout=1) as response:
        assert response.status == 200
except Exception:
    raise SystemExit(1)
CHECK
    then
        exec xdg-open http://127.0.0.1:8765
    fi
    sleep 0.2
done
echo 'Adem kon niet starten. Controleer: systemctl --user status adem-optimizer.service' >&2
exit 1
''')
launcher.chmod(0o755)
desktop = f'''[Desktop Entry]
Type=Application
Name=Adem — Linux optimizer
Comment=View system usage and close selected apps
Exec="{launcher}"
Icon={target}/web/icon.svg
Terminal=false
Categories=System;Monitor;
StartupNotify=false
'''
(home / '.local/share/applications/adem-optimizer.desktop').write_text(desktop)
PY
systemctl --user daemon-reload
systemctl --user enable adem-optimizer.service
systemctl --user restart adem-optimizer.service
printf '%s\n' 'Adem installed: http://127.0.0.1:8765' 'Open from the application menu: Adem — Linux optimizer'

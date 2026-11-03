"""Captura opcional no Edge headless, em perfil isolado desta tarefa."""
from pathlib import Path
import subprocess

root=Path('outputs/2026').resolve()
browser=Path('C:/Program Files (x86)/Microsoft/Edge/Application/msedge.exe')
if not browser.exists():
    raise SystemExit('Edge não disponível para a captura opcional')
target=root/'graficos/mapa_preview.png'
subprocess.run([str(browser),'--headless','--disable-gpu','--disable-background-networking','--disable-sync',
    '--no-first-run','--hide-scrollbars','--virtual-time-budget=5000','--window-size=1440,1100',
    '--user-data-dir='+str(root.parent/'browser-mapa'), '--screenshot='+str(target),
    (root/'mapa_eleitoral.html').as_uri()],check=True,timeout=60)
print(target)

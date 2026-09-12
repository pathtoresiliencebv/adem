# Verificatie Adem

Gecontroleerd op 2026-09-12T01:14:26.327876+00:00 op de lokale Linux-computer.

- Python-backend: 11 tests geslaagd, inclusief echte SIGTERM-afsluiting van uitsluitend een eigen tijdelijk testproces, beschermde processen, PID-identiteit, eenmalige/verlopen plannen en webbeveiliging.
- Geïnstalleerde webapp via http://127.0.0.1:8765: 22 browserchecks geslaagd; 0 JavaScript-fouten.
- Axe-scan op desktop, bevestigingsvenster, 320 CSS px breedte en 200% root-tekstvergroting: geen gemelde WCAG A/AA-overtredingen binnen de gebruikte regels.
- Toetsenbord via browserautomatisering: selectie en bevestiging met Enter, Tab in het dialoogvenster, Escape, focusherstel en annuleren zonder afsluiten.
- Schermbreedte 320 CSS px en 200% root-tekstvergroting: geen horizontale pagina-overflow. Root-tekstvergroting is geen volledige handmatige browserzoomtest.
- Werkelijk testresultaat via de browser: 1 proces afgesloten of al gestopt. 0 nog actief na stopverzoek. 0 overgeslagen of mislukt.
- Gebruikersservice actief en alleen luisterend op 127.0.0.1:8765. Appmenu-launcher aangeroepen; browserproces gestart. Aanmelden na een reboot is niet getest.
- Laatste live-uitlezing: 189 gebruikersprocessen; sluitbare appgroepen: Mission Center, COSMIC Teksteditor.

Bewijs: `browser-report.json`, `desktop.png`, `mobile.png`, `confirmation.png` in deze map. Screenshots kunnen het eigen tijdelijke testproces tonen. Bestaande gebruikersapps zijn tijdens de tests niet gesloten.

Geen handmatige screenreadertest of volledige WCAG-certificering. Andere Linux-computers zijn niet geïnstalleerd of live getest; het pakket is daarvoor beschikbaar.

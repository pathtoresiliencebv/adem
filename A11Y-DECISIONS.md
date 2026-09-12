# Toegankelijkheidskeuzes

- Platform: web, English. Baseline: Standard / WCAG 2.2 AA from the global A11Y.md. No relaxed criteria.
- Confirmation: native `dialog.showModal()`, linked name and description; initial focus on cancel, Escape closes, native inert background and explicit Tab/Shift+Tab wrapping. Focus returns to the review button on cancel, or the search field when the review button is disabled after completion.
- App selection: native labelled checkbox with a 44×44 px hit area. Non-closable processes have a disabled checkbox and text status. The list uses `ul`/`li`, not an interactive ARIA grid.
- Updates: stable DOM rows preserve keyboard focus during refresh; rows are not automatically reordered. Live refresh can be paused. Explicit actions are announced through `role=status`, errors through `role=alert`. Measurements are not read every four seconds.
- Data: procenten/geheugen als tekst naast native progressbalken; decoratieve iconen verborgen voor hulptechnologie. Kleur is nooit de enige betekenisdrager.
- Responsief: bediening minimaal 44 px hoog, tekst minimaal 12 px, geen benodigde horizontale paginascroll op 320 CSS px. Zichtbare focusring van 3 px. Respecteert prefers-reduced-motion.
- Handmatige screenreadervalidatie door een gebruiker is nog nodig; automatische checks zijn geen certificering.

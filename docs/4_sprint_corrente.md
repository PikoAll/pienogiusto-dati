# Sprint corrente
- Epic attiva: 2 (go-live)
- Ticket in lavorazione: creazione repo e primo deploy (comandi a Giuseppe)
- Criteri di accettazione:
  1. `index.json` raggiungibile su Pages con `schema: 1` e ~21.700 impianti.
  2. Il run schedulato del giorno dopo pubblica da solo (cancello ±10% attivo col precedente).
- Note: orari cron 07:15/09:15 UTC approvati. Dopo il primo deploy verde: installare il timer del watchdog (README).

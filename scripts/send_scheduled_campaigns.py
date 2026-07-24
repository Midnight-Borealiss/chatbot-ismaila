"""
Envoi des campagnes programmées (Centre de Communication).

Traite les campagnes `status="scheduled"` dont `scheduled_at <= maintenant`
et les envoie (email + notification in-app), puis les marque `sent`.

À exécuter périodiquement (cron, tâche planifiée Windows, ou GitHub Action) :

  # toutes les 15 minutes (crontab)
  */15 * * * * cd /chemin/chatbot-ismaila && python scripts/send_scheduled_campaigns.py

  # GitHub Action (schedule) : voir .github/workflows/ (à créer si besoin)
"""

import sys
from pathlib import Path

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

sys.path.insert(0, str(Path(__file__).parent.parent))

from controllers.communication_controller import communication_controller


def main():
    result = communication_controller.process_scheduled()
    print(f"✅ Campagnes programmées traitées : {result.get('processed', 0)}")


if __name__ == "__main__":
    main()

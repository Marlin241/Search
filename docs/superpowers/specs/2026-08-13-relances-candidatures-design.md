# Rappels de relance et de finalisation de candidatures — Design

## Contexte

Aujourd'hui, une fois une candidature créée (`Application`), rien ne rappelle
à l'utilisateur qu'elle attend une réponse depuis longtemps, ou qu'elle n'a
jamais été effectivement envoyée (statut `a_soumettre_manuellement` resté en
l'état). L'utilisateur doit consulter la page candidatures/historique de
lui-même pour s'en rendre compte.

Ce chantier fait suite au chantier recherche proactive + notifications
(`docs/superpowers/specs/2026-08-13-recherche-proactive-notifications-design.md`),
dont il réutilise directement l'infrastructure (scheduler APScheduler,
client Resend).

C'est le premier des trois sous-chantiers du « suivi de candidatures
enrichi » (les deux autres — statistiques, pipeline visuel par statut — sont
traités séparément, dans cet ordre).

## Objectif

Envoyer un email quotidien récapitulant, pour chaque utilisateur concerné,
les candidatures nécessitant une action :
1. **À relancer** : effectivement envoyées, sans changement de statut
   depuis 7 jours (l'entreprise n'a pas répondu).
2. **À finaliser** : jamais envoyées, créées depuis 7 jours (l'utilisateur
   ne les a jamais soumises).

**Cet email part vers l'utilisateur lui-même** — c'est un rappel personnel
(« pense à relancer / finaliser »), jamais un envoi automatique vers
l'entreprise.

**Hors scope pour cette itération** (explicitement exclu) :
- Toggle activer/désactiver cette fonctionnalité, ou lien de désabonnement —
  traité comme un email transactionnel toujours actif (contrairement aux
  alertes de recherche, qui sont une notification récurrente optionnelle).
- Rappels répétés : chaque candidature ne déclenche **qu'un seul** rappel,
  jamais renvoyé même si le statut ne change toujours pas ensuite.
- Seuil personnalisable : 7 jours fixe pour les deux catégories, pas de
  réglage par utilisateur ou par candidature.
- Envoi automatique d'un message de relance à l'entreprise — hors scope,
  potentiellement un chantier futur distinct.
- Notification dans l'application, en complément de l'email.
- Statistiques et pipeline visuel — sous-chantiers suivants, spécifiés
  séparément.

## Composants

### 1. Modèle `Application` (modifié)

Ajout d'un champ :

| Champ | Type | Notes |
|---|---|---|
| `reminder_sent_at` | datetime, nullable | `NULL` tant qu'aucun rappel n'a été envoyé pour cette candidature ; renseigné une fois pour toutes après le premier envoi réussi — jamais réinitialisé, jamais réenvoyé. |

### 2. Job planifié (`app/applications/reminders.py`, nouveau)

Même schéma que `app/job_search/daily_search.py` (chantier précédent) :

- **Scheduler** : un deuxième job enregistré sur le même `BackgroundScheduler`
  déjà démarré dans le `lifespan` de `main.py` (`trigger="cron", minute=0`,
  `id="application_reminders"`) — pas de nouvelle infrastructure.
- **Sélection des utilisateurs à traiter à chaque passage horaire** :
  pour chaque utilisateur ayant au moins une `Application`, l'heure locale
  actuelle est calculée via le fuseau horaire de sa `SavedSearch` s'il en a
  une (`SavedSearch.timezone`), sinon UTC par défaut — pas de nouveau champ
  de fuseau horaire ajouté à `User` pour cette itération (voir « Prochaines
  étapes » pour la limite assumée de ce choix). Seuls les utilisateurs dont
  l'heure locale vient d'atteindre 8h sont traités à ce passage.
- **Sélection des candidatures « à relancer »** (par utilisateur) :
  `status IN (soumise_auto, soumise_manuelle_confirmee)` ET
  `submitted_at <= maintenant - 7 jours` ET `reminder_sent_at IS NULL`.
- **Sélection des candidatures « à finaliser »** (par utilisateur) :
  `status IN (a_soumettre_manuellement, en_cours)` ET
  `created_at <= maintenant - 7 jours` ET `reminder_sent_at IS NULL`.
- **Envoi** : si au moins une candidature trouvée (dans l'une ou l'autre
  catégorie), un seul email récapitulatif est envoyé listant les deux
  catégories (une section par catégorie, omise si vide). Aucun envoi si les
  deux listes sont vides.
- **Après envoi réussi** : `reminder_sent_at` est renseigné (`utcnow()`) sur
  chaque candidature incluse dans l'email, dans les deux catégories. Si
  l'envoi échoue, aucun champ n'est modifié — ces candidatures seront de
  nouveau évaluées (et donc re-proposées) au prochain passage, exactement
  comme pour `NotifiedListing` dans le chantier recherche proactive.
- **Isolation des erreurs** : chaque utilisateur est traité dans son propre
  `try/except` (même convention que `daily_search.run_daily_search`) — un
  échec pour un utilisateur n'interrompt pas le traitement des autres.

### 3. Email (`app/notifications/resend_client.py`, modifié)

- Nouvelle fonction `send_application_reminders_email(to_email: str,
  to_relance: list[Application], to_finalize: list[Application]) -> None`,
  suivant exactement les mêmes règles de sécurité que
  `send_daily_digest_email` (déjà en place, corrigées suite à la revue de
  sécurité du chantier précédent) : tout champ interpolé
  (`company_name`, `job_title`) est passé par `html.escape()`, tout lien
  par `_safe_href()` — `company_name`/`job_title` proviennent en dernier
  ressort d'APIs externes ou de saisie utilisateur, donc non fiables par
  défaut, au même titre que les champs d'une `JobListing`.
- **Sujet** : `"N candidature(s) à relancer ou finaliser"` (N = somme des
  deux listes).
- **Corps** : deux sections optionnelles (« Candidatures à relancer »,
  « Candidatures à finaliser »), chaque ligne affichant entreprise, poste,
  date pertinente (`submitted_at` pour la première catégorie, `created_at`
  pour la seconde), et un lien vers la page candidatures du frontend.
- **Nouveau setting** (`app/config.py`) : `frontend_base_url: str =
  "http://localhost:3000"` — nécessaire pour construire ce lien ; le
  chantier précédent n'avait ajouté que `backend_base_url` (utilisé pour le
  lien de désabonnement, qui pointe vers une route du backend lui-même, pas
  du frontend).

## Gestion des erreurs et cas limites

- **Utilisateur sans `SavedSearch`** : fuseau horaire par défaut UTC — voir
  composant 2. Recevra ses rappels à 8h UTC plutôt qu'à une heure locale
  pertinente ; limite assumée (voir « Prochaines étapes »).
- **Candidature éligible aux deux catégories à la fois** : impossible par
  construction — les deux ensembles de statuts (`soumise_*` vs `a_soumettre_
  manuellement`/`en_cours`) sont disjoints.
- **Candidature supprimée entretemps** : non applicable, il n'existe pas de
  route de suppression de candidature dans l'application actuelle.
- **Échec d'envoi pour un utilisateur ayant les deux catégories non vides** :
  aucune candidature n'est marquée (`reminder_sent_at` reste `NULL` pour
  toutes, pas seulement une catégorie) — l'utilisateur reçoit un email
  complet ou aucun, jamais un email partiel suivi d'un renvoi partiel.

## Tests

- **`app/applications/reminders.py`** : sélection correcte des deux
  catégories (statuts, seuil de 7 jours, exclusion des candidatures déjà
  marquées `reminder_sent_at`) ; regroupement par utilisateur ; filtre par
  heure locale (fuseau `SavedSearch.timezone` si présent, sinon UTC) ;
  aucun envoi si les deux listes sont vides ; isolation des erreurs entre
  utilisateurs (même schéma de test que `test_daily_search.py`).
- **`resend_client.send_application_reminders_email`** : contenu HTML
  correct (via `respx`) ; échappement HTML des champs `company_name`/
  `job_title` malveillants (même test que pour les offres de recherche,
  réutilisant la même logique `_safe_href`/`html.escape`) ; gestion d'un
  échec HTTP (aucune candidature marquée si `EmailSendError`).
- **Modèle `Application`** : `reminder_sent_at` par défaut `NULL` à la
  création, correctement persistable.

## Prochaines étapes (hors scope de cette spec)

- Fuseau horaire dédié sur `User` (plutôt que dépendre de l'existence d'une
  `SavedSearch`), si le fait de recevoir les rappels en UTC par défaut
  s'avère gênant en pratique pour un utilisateur sans recherche sauvegardée.
- Sous-chantiers suivants déjà identifiés : statistiques (taux de réponse,
  délai moyen), puis pipeline visuel par statut.

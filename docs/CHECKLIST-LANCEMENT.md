# Checklist de lancement — Beta yokkutelabs

À faire sur l'environnement de prod (`search.yokkutelabs.com`), navigateur réel,
dont **au moins un passage complet depuis un téléphone**. Le beta ne s'ouvre
pas tant que tout n'est pas coché.

## Landing publique
- [ ] `/` en anonyme affiche la landing (présentation produit), **pas** le formulaire de login — sur desktop **et** téléphone ; aucun scroll horizontal.
- [ ] `/` en tant qu'utilisateur connecté redirige vers `/dashboard` (sans flash de la landing).
- [ ] Formulaire « Demander un accès » → message de remerciement + **email d'accusé de réception reçu** par le demandeur ; la demande apparaît dans `/admin ▸ Demandes d'accès` ; email de notif reçu sur `ADMIN_NOTIFY_EMAIL`.
- [ ] `/admin ▸ Demandes d'accès` → **Approuver** : le demandeur reçoit un email avec un code d'invitation valide (inscription OK avec ce code) ; **Écarter** : pas d'email.
- [ ] Liens du footer (Conditions, Confidentialité, Contact, Yokkute Labs) fonctionnels.

## Infra & accès
- [ ] `search.` et `api.search.` résolvent ; TLS valide (cadenas) sur les deux.
- [ ] `curl https://api.search.yokkutelabs.com/health` → `{"status":"ok","db":"ok",...}`.
- [ ] `db` et `minio` ne sont pas joignables depuis l'extérieur.
- [ ] Requête `fetch` depuis une autre origine → bloquée par CORS.

## Auth
- [ ] Inscription **sans** code → refusée ; avec un code déjà utilisé → refusée.
- [ ] Inscription avec code + case de consentement cochée → OK ; `users.consent_version` renseigné.
- [ ] Cookie `search_app_token` : `Secure`, `HttpOnly`, `SameSite=Lax` (DevTools).
- [ ] « Mot de passe oublié » → email reçu → lien → nouveau mot de passe → login OK.
- [ ] 8 échecs de login → `429`.

## Parcours produit (téléphone)
- [ ] Inscription → onboarding → recherche → offres **sénégalaises** visibles.
- [ ] Diagnostic ATS → CV généré → lettre générée → prépa entretien.
- [ ] À la N+1ᵉ génération : encart « quota atteint » (pas une erreur rouge).
- [ ] `python -m scripts.llm_switch off` → une génération montre « en pause » (503 propre) ; `on` → rétabli.
- [ ] `/profil` montre les jauges d'utilisation.

## RGPD
- [ ] `/conditions` et `/confidentialite` accessibles sans être connecté, contenu validé (raison sociale, pays hébergeur, email de contact renseignés).
- [ ] « Exporter mes données » → JSON complet téléchargé.
- [ ] « Supprimer mon compte » (mot de passe) → login échoue ensuite ; lignes DB parties ; `mc ls local/personalization/users/<id>/` vide.

## Observabilité
- [ ] Erreur test backend → visible dans GlitchTip, **sans** contenu de CV.
- [ ] Erreur test frontend → visible dans GlitchTip.
- [ ] Uptime Kuma : `API health`, `Frontend`, `TLS` → tous verts ; une notification test reçue.

## Admin
- [ ] `ADMIN_EMAILS` renseigné dans `backend/.env` ; `python -m scripts.seed_admin` → compte créé, connexion email + mot de passe OK.
- [ ] `/admin` accessible au compte admin ; `403` / redirection pour un compte normal ; pas d'entrée de nav « Admin » pour un non-admin.
- [ ] Générer 5 codes, en révoquer 1.
- [ ] Ajuster un quota d'un testeur → visible dans `/admin/users/{id}`.
- [ ] Onglet Feedback affiche un retour test.

## Sauvegardes
- [ ] `deploy/backup/pg_backup.sh` exécuté → fichier `.age` sur R2.
- [ ] `deploy/backup/minio_mirror.sh` exécuté → objets sur R2.
- [ ] **Restauration testée** sur base jetable → `SELECT count(*) FROM users` cohérent.
- [ ] Crons installés (`crontab -l`).

## Coûts
- [ ] Plafond de dépense mensuel posé dans la console Anthropic + alertes 50/80/100 %.

## Amorçage
- [ ] Crawl manuel lancé ; offres Emploi Dakar en base ; 1ʳᵉ recherche non vide.

## Feedback humain
- [ ] Groupe WhatsApp créé ; message d'accueil + pitch 3 lignes prêts.
- [ ] 5-10 codes attribués nominativement (tableau code ↔ personne).

---
Passée le : __________  par : __________

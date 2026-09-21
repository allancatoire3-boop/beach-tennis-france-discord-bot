# Bot Discord — tournois de Beach Tennis en France

Ce bot surveille quotidiennement les nouveaux tournois de Beach Tennis programmés pendant les 12 prochains mois en France métropolitaine et en Corse.

Il est complètement indépendant du bot Montpellier.

## Configuration

### 1. Créer le webhook Discord

Dans le salon Discord national :

1. **Modifier le salon**
2. **Intégrations**
3. **Webhooks**
4. **Nouveau webhook**
5. **Copier l'URL du webhook**

### 2. Ajouter le secret GitHub

Dans ce dépôt :

1. **Settings**
2. **Secrets and variables**
3. **Actions**
4. **New repository secret**
5. Nom : `DISCORD_WEBHOOK_FRANCE_URL`
6. Secret : l'URL du webhook Discord
7. **Add secret**

### 3. Premier lancement

Dans **Actions**, ouvre **Vérifier les tournois Beach Tennis France**, puis clique sur **Run workflow**.

Le premier lancement mémorise silencieusement tous les tournois existants. Les lancements suivants annoncent uniquement les nouveaux.

## Fonctionnement

- Pratique : Beach Tennis
- Territoire : France métropolitaine et Corse
- Période glissante : aujourd'hui jusqu'à 365 jours
- Fréquence : une fois par jour
- Pagination : tous les résultats, par lots de 10
- Déduplication : `idHomologation`
- Mémoire : `seen_tournaments_france.json`

Le territoire est couvert par un maillage de recherches de 199 km. Les résultats qui apparaissent dans plusieurs zones sont fusionnés avant l'envoi sur Discord.

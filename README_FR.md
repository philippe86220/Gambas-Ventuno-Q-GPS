# Gambas-Ventuno-Q-GPS — Interface graphique Gambas3 et API JSON

Application GPS pour **Arduino VENTUNO Q** : les données GPS reçues par le MCU sont transférées au programme Python d'**Arduino App Lab**, puis affichées dans une **interface graphique native Gambas3** sous Ubuntu.

Ce projet reprend le principe du projet [UNO-Q-GPS](https://github.com/philippe86220/UNO-Q-GPS), qui utilisait une interface **WebUI HTML** sur UNO Q. Ici, l'interface utilisateur est réalisée avec **Gambas3** sur VENTUNO Q, sans Brick WebUI.

## Architecture

```text
GPS → MCU (sketch Arduino)
          │
          │ Arduino Bridge
          ▼
Arduino App Lab / conteneur main
  main.py
  ├── Bridge.provide("update_gps", ...)
  ├── dictionnaire Python _state (protégé par un Lock)
  └── serveur HTTP : 0.0.0.0:8000
                         │
                         │ GET /api/state → JSON
                         ▼
Ubuntu (hôte VENTUNO Q)
  Application Gambas3
  ├── HttpClient
  ├── JSON.Decode()
  └── affichage des coordonnées, date, heure, satellites et altitude
```

Le serveur HTTP ne donne pas directement accès aux variables Python : il **renvoie une représentation JSON** des valeurs sélectionnées lors de chaque requête. Les données restent en mémoire dans le processus Python ; aucun fichier `.json` sur disque n'est nécessaire.

> **Important :** la connexion directe depuis Ubuntu à l'adresse IP privée du conteneur a été testée sur cette VENTUNO Q. Elle dépend de la configuration réseau Docker de l'hôte et ne constitue pas une adresse stable garantie pour toutes les installations.

## Prérequis

- Arduino VENTUNO Q avec Ubuntu et Arduino App Lab.
- Une application App Lab recevant les données GPS du MCU par `Bridge`.
- Le serveur HTTP Python lancé dans le conteneur `main` sur le port **8000**.
- Gambas3 installé sur Ubuntu, avec les composants HTTP et JSON utilisés par le projet.

## Installer Gambas3

Sur l'Ubuntu de la VENTUNO Q :

```bash
sudo apt update
sudo apt install gambas3
```

Si les composants ne sont pas déjà installés par le paquet principal, installer également :

```bash
sudo apt install gambas3-gb-net-curl gambas3-gb-util-web
```

Dans les propriétés du projet Gambas, vérifier que les composants **`gb.net.curl`** (client HTTP) et **`gb.util.web`** (décodage JSON) sont activés. Les noms exacts des paquets disponibles peuvent être vérifiés avec `apt search gambas3`.

## Nom de l’application et des conteneurs Docker

Le projet Arduino App Lab s’appelle **`Gambas-Ventuno-Q-GPS`**.

Le **nom complet du conteneur Docker peut changer**. Lors de nos essais, nous avons notamment observé :

```text
gambas-ventuno-q-gps-main-1
gambas-ventuno-q-gps-main-main-1
```

L’ancien conteneur était arrêté tandis que le nouveau était actif. Interroger l’ancien conteneur avec `docker inspect` renvoyait une adresse IP vide.

L’application Gambas3 identifie donc le conteneur **en cours d’exécution** au moyen de deux filtres Docker :

- `name=gambas-ventuno-q-gps` : sélectionne les conteneurs dont le nom correspond au motif du projet.
- `label=com.docker.compose.service=main` : limite les résultats au service Docker Compose `main`, en excluant les autres services, notamment les éventuelles Bricks.

Les deux filtres sont appliqués simultanément. Cela évite de dépendre d’un nom de conteneur complet et fixe.

**Limite :** le code Gambas actuel suppose qu’un seul conteneur actif correspond aux deux filtres. Cette hypothèse était vérifiée dans la configuration testée.

## Démarrer l'application App Lab

Lancer l’application GPS dans **Arduino App Lab** et attendre le démarrage du conteneur `main`.

Pour identifier le conteneur actif :

```bash
docker ps --filter 'name=gambas-ventuno-q-gps' --filter 'label=com.docker.compose.service=main' --format '{{.Names}}'
```

Lors d’un essai, la commande a renvoyé :

```text
gambas-ventuno-q-gps-main-main-1
```

Pour examiner également les ports :

```bash
docker ps --format 'table {{.Names}}\t{{.Ports}}'
```

La colonne `PORTS` peut être vide : **aucune publication de port vers l’hôte n’est nécessaire pour le test de connexion directe à l’IP du conteneur**, dès lors que cette IP est joignable depuis Ubuntu.

## Trouver l'adresse IP du conteneur

Après avoir identifié le conteneur actif, interroger Docker (en adaptant le nom au résultat précédent) :

```bash
docker inspect -f '{{range .NetworkSettings.Networks}}{{.IPAddress}}{{end}}' gambas-ventuno-q-gps-main-main-1
```

Lors de l’un de nos derniers essais, la commande a renvoyé :

```text
172.26.0.2
```

Cette adresse est **un exemple observé**, pas une valeur permanente. Au fil des essais, nous avons notamment rencontré `172.24.0.2`, `172.25.0.2` et `172.26.0.2`.

Le programme Gambas3 découvre automatiquement **le nom du conteneur actif, puis son adresse IP actuelle**.

Tester l’API depuis Ubuntu (adapter l’adresse obtenue) :

```bash
curl http://172.26.0.2:8000/api/state
```

Une réponse JSON doit contenir les dernières données GPS connues, par exemple :

```json
{
  "lat": 46.91597,
  "long": 0.5920883333333333,
  "jour": 31,
  "mois": 10,
  "annee": 2026,
  "heure": 12,
  "minute": 43,
  "seconde": 49,
  "numsat": 6,
  "altitude": 46.9,
  "now_local": "31/10/2026 13:43:49"
}
```

Les valeurs sont illustratives. La version actuelle de `main.py` renvoie bien le champ `now_local` (et non `now_utc`).

## Serveur HTTP dans `main.py`

Le programme Python conserve les données GPS dans un dictionnaire `_state`. La fonction `update_gps(...)`, exposée via `Bridge.provide(...)`, actualise ce dictionnaire à chaque transmission du MCU. Un verrou `threading.Lock()` protège les accès concurrents.

Le serveur `ThreadingHTTPServer` écoute sur `0.0.0.0:8000` dans le conteneur et répond à :

```text
GET /api/state
```

Il sérialise l'état courant avec `json.dumps(...)`, en définissant le type de contenu `application/json`.

Le code fournit également l’heure locale française grâce à :

```python
import datetime
from zoneinfo import ZoneInfo

def now_local_fr():
    return datetime.datetime.now(ZoneInfo('Europe/Paris')).strftime('%d/%m/%Y %H:%M:%S')
```

La fonction `api_state()` appelle effectivement `now_local_fr()` et ajoute `payload["now_local"]` à la réponse. Ce point a été vérifié dans le `main.py` complet. Le code intégral reste disponible dans les fichiers source du projet.

## Interface Gambas3

Le formulaire Gambas utilise `Timer1` pour interroger périodiquement l’API, lire la réponse JSON et afficher les valeurs.

### Initialisation du Timer

**Important : dans l’éditeur de formulaire Gambas3, régler la propriété `Enabled` de `Timer1` sur `False`.**

Le Timer ne doit pas se déclencher avant que le programme ait trouvé le conteneur et construit l’adresse du serveur. Il est démarré explicitement par `Timer1.Start`, à la fin de `Form_Open()`, uniquement si l’initialisation a réussi.

Cette propriété se règle dans l’éditeur Gambas3 ; il n’est pas nécessaire de modifier manuellement `FMain.form`.

### Découverte automatique du conteneur et de son adresse IP

Gambas3 peut exécuter une commande Linux avec `Shell` et récupérer sa sortie dans une variable grâce à `To`. Deux commandes sont utilisées : `docker ps` identifie le conteneur actif, puis `docker inspect` récupère son adresse IP.

Dans `FMain.class`, déclarer une variable accessible aux différentes procédures :

```gambas
Private AdresseServeur As String
```

La procédure d’initialisation est :

```gambas
Public Sub Form_Open()

  Dim IP As String
  Dim conteneur As String

  ' Recherche du conteneur actif correspondant au service main
  Shell "docker ps --filter 'name=gambas-ventuno-q-gps' --filter 'label=com.docker.compose.service=main' --format '{{.Names}}'" To conteneur
  conteneur = Trim(conteneur)

  If conteneur = "" Then
    Message.Error("Aucun conteneur GPS principal actif.")
    Quit
  Endif

  ' Récupération de son adresse IP
  Shell "docker inspect -f '{{range .NetworkSettings.Networks}}{{.IPAddress}}{{end}}' " & Shell$(conteneur) To IP
  IP = Trim(IP)

  If IP = "" Then
    Message.Error("Impossible de récupérer l'adresse IP du conteneur.")
    Quit
  Endif

  AdresseServeur = "http://" & IP & ":8000/api/state"
  Print "Serveur GPS : "; AdresseServeur
  Timer1.Start

End
```

Les deux filtres évitent de dépendre du nom complet du conteneur et limitent la recherche au service `main`, plutôt qu’à une éventuelle Brick. `Shell$(conteneur)` permet de transmettre le nom à la commande shell en le protégeant correctement.

Si aucun conteneur actif n’est trouvé ou si son adresse IP est vide, Gambas3 affiche un message d’erreur et quitte l’application **sans démarrer le Timer**.

### Lecture périodique des données GPS

Dans `Timer1_Timer()`, l’adresse du serveur n’est plus codée en dur : elle provient de `Form_Open()`.

```gambas
Public Sub Timer1_Timer()

  Dim client As HttpClient
  Dim Reponse As String
  Dim Data As Collection

  client = New HttpClient
  client.URL = AdresseServeur
  client.Async = False
  client.Timeout = 40
  client.Get()

  If client.Status < 0 Then
    Print "Erreur"
    Quit
  Else
    If Lof(client) Then Reponse = Read #client, Lof(client)
    Print Reponse
  Endif

  Data = JSON.Decode(Reponse)

  Latitude.Text = "Latitude : " & Data["lat"]
  Longitude.Text = "Longitude : " & Data["long"]
  Date.Text = "Date UTC : " & Data["jour"] & " : " & Data["mois"] & " : " & Data["annee"]
  Heure.Text = "Heure UTC : " & Data["heure"] & " : " & Data["minute"] & " : " & Data["seconde"]
  Satellites.Text = "Satellittes : " & Data["numsat"]
  Altitude.Text = "Altitude : " & Data["altitude"]
  Date_heure_FR.Text = "Date / heure (local) : " & Data["now_local"]

End
```

Les champs de date et d’heure issus du GPS sont ici étiquetés UTC. Le champ `now_local` est fourni par le serveur Python en heure locale française.

### Conditions et limites

L’application GPS doit être démarrée dans App Lab **avant** Gambas3. L’utilisateur Ubuntu doit avoir les permissions nécessaires pour exécuter `docker ps` et `docker inspect`.

**Exemple concret :** si vous cliquez sur **Stop** dans Arduino App Lab, puis sur **Run** pour relancer l’application GPS **en laissant la fenêtre Gambas3 ouverte**, App Lab peut recréer le conteneur et lui attribuer une nouvelle adresse IP.

Gambas3 continue alors d’utiliser l’adresse mémorisée lors de son ouverture. Dans la version actuelle, si la requête HTTP échoue et que le client signale une erreur, Gambas3 se ferme. Une fois l’application GPS relancée dans App Lab, **il suffit de redémarrer Gambas3** pour découvrir le conteneur actif et sa nouvelle adresse IP.

La reconnexion automatique n’est pas encore implémentée. Ce scénario ne signifie pas qu’App Lab recrée spontanément les conteneurs pendant leur fonctionnement normal.

Le code actuel suppose également qu’un seul conteneur actif correspond aux deux filtres et qu’une adresse IP exploitable est renvoyée par `docker inspect`.

Cette technique peut servir à d’autres commandes Linux : `Shell "uname -r" To Resultat`, par exemple, récupère la version du noyau dans une variable Gambas.

### Améliorations possibles

- Vérifier le code HTTP de réponse, la présence d’un corps JSON et les erreurs de décodage.
- Gérer explicitement les erreurs de commande Docker, plusieurs conteneurs correspondants ou plusieurs interfaces réseau.
- Retrouver automatiquement le conteneur si App Lab est arrêté puis relancé alors que Gambas3 est ouvert.
- Éviter une requête synchrone dans le `Timer` si le délai de réponse peut bloquer l’interface graphique ; prévoir une requête asynchrone.
- Prévoir un message clair lorsque le GPS n’a pas encore de position (`null`).

## Pourquoi cette approche ?

Cette solution permet de **séparer les traitements et l'interface graphique** : App Lab gère le MCU, le Bridge et le serveur Python ; Gambas3 s'occupe de l'affichage natif sous Ubuntu.

Elle n'impose **aucune Brick WebUI ni Brick personnalisée pour la seule exposition du JSON**. Une Brick peut toutefois rester utile si le projet requiert des dépendances ou services spécifiques, ou pour organiser des fonctionnalités réutilisables.

La même architecture peut être réemployée pour d'autres données : capteurs, mesures analogiques, états d'entrées/sorties, tableaux de bord, etc.

## Projet d'origine

- [UNO-Q-GPS — projet GPS pour Arduino UNO Q avec interface WebUI HTML](https://github.com/philippe86220/UNO-Q-GPS)

---

*Projet expérimental développé et testé sur Arduino VENTUNO Q. Les détails réseau et les composants disponibles peuvent évoluer selon les versions d'Arduino App Lab et d'Ubuntu.*

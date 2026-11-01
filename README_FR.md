# Gambas-Ventuno-Q-GPS — Interface graphique Gambas3 et API JSON

Application GPS pour **Arduino VENTUNO Q** : les données GPS reçues par le MCU sont transférées au programme Python d'**Arduino App Lab**, puis affichées dans une **interface graphique native Gambas3** sous Ubuntu.

Ce projet reprend le principe du projet [UNO-Q-GPS](https://github.com/philippe86220/UNO-Q-GPS), qui utilisait une interface **WebUI HTML** sur UNO Q. Ici, l'interface utilisateur est réalisée avec **Gambas3** sur VENTUNO Q, sans Brick WebUI.

![Interface graphique Gambas3 – VENTUNO Q GPS](image/gambas-gps.png)

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

## Nom de l’application

Le projet Arduino App Lab s’appelle **`Gambas-Ventuno-Q-GPS`**. Le conteneur Docker associé porte le nom **`gambas-ventuno-q-gps-main-1`**.

## Démarrer l'application App Lab

Lancer l'application GPS dans **Arduino App Lab** et attendre le démarrage du conteneur `main`.

Vérifier son nom :

```bash
docker ps --format 'table {{.Names}}\t{{.Ports}}'
```

Dans la configuration testée, le conteneur s'appelle :

```text
gambas-ventuno-q-gps-main-1
```

La colonne `PORTS` peut être vide : **aucune publication de port vers l'hôte n'est nécessaire pour le test de connexion directe à l'IP du conteneur**, dès lors que cette IP est joignable depuis Ubuntu.

## Trouver l'adresse IP du conteneur

```bash
docker inspect -f '{{range .NetworkSettings.Networks}}{{.IPAddress}}{{end}}' gambas-ventuno-q-gps-main-1
```

Sur la configuration testée, cette commande renvoyait :

```text
172.25.0.2
```

Cette adresse est **un exemple observé**, pas une valeur permanente. Lors des essais, le conteneur est passé de `172.24.0.2` à `172.25.0.2` : une recherche automatique évite de modifier manuellement le code Gambas à chaque changement.

Tester l'API depuis Ubuntu (adapter l'adresse obtenue) :

```bash
curl http://172.25.0.2:8000/api/state
```

Une réponse JSON doit contenir les dernières données GPS connues, par exemple :

```json
{
  "lat": 43.91597,
  "long": 0.5820883333333333,
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

La fonction `api_state()` appelle effectivement `now_local_fr()` et ajoute `payload["now_local"]` à la réponse. Le code intégral reste disponible dans les fichiers source du projet.

## Interface Gambas3

Le formulaire Gambas utilise un `Timer` pour interroger périodiquement l'API, lire la réponse et afficher les valeurs.

Extrait représentatif du code testé :

```gambas
Public Sub Timer1_Timer()

  Dim client As HttpClient
  Dim Reponse As String
  Dim Data As Collection

  client = New HttpClient
  client.URL = "http://172.25.0.2:8000/api/state"
  client.Async = False
  client.Timeout = 40
  client.Get()

If client.Status < 0 Then
    Print "Erreur"
    Return
  Else
   ' Succès - données lues.
    If Lof(client) Then Reponse = Read #client, Lof(client)
    Print Reponse
  End If

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

Cet extrait illustre la première version avec IP fixe. La section suivante montre comment remplacer cette valeur par une adresse découverte automatiquement avec `Shell`. Les champs de date et heure provenant du GPS sont ici étiquetés UTC.

### Découverte automatique de l’adresse IP depuis Gambas3

Gambas3 peut exécuter une commande Linux avec `Shell` et récupérer sa sortie dans une variable grâce à `To`. Cela permet de trouver l'adresse IP attribuée par Docker **sans l'écrire en dur dans le code**.

Dans le formulaire Gambas, déclarer une variable accessible aux autres procédures :

```gambas
Private AdresseServeur As String

Public Sub Form_Open()

  Dim IP As String

  Shell "docker inspect -f '{{range .NetworkSettings.Networks}}{{.IPAddress}}{{end}}' gambas-ventuno-q-gps-main-1" To IP
  IP = Trim(IP)

  If IP = "" Then
    Message.Error("Conteneur introuvable ou sans adresse IP.   Démarrez d'abord l'application App Lab.")
    Return
  Endif

  AdresseServeur = "http://" & IP & ":8000/api/state"
  Print "Serveur GPS : "; AdresseServeur

End
```

Dans `Timer1_Timer()`, remplacer l'adresse fixe :

```gambas
client.URL = "http://172.25.0.2:8000/api/state"
```

par :

```gambas
If AdresseServeur = "" Then Return
client.URL = AdresseServeur
```

**Conditions et limites :** l'application App Lab doit être démarrée avant Gambas3 ; l'utilisateur Ubuntu doit pouvoir exécuter `docker inspect` sans erreur de permission. Si le conteneur est recréé **pendant** l'exécution de Gambas, il faut relancer la découverte de l'adresse. Pour un programme plus robuste, gérer également les erreurs de commande et les conteneurs possédant plusieurs interfaces réseau.

Cette technique est réutilisable pour d'autres commandes Linux : `Shell "uname -r" To Resultat`, par exemple, récupère la version du noyau dans une variable Gambas.

### Améliorations possibles
- Vérifier le code HTTP de réponse, la présence d'un corps JSON et les erreurs de décodage.
- Éviter une requête synchrone dans le `Timer` si le délai de réponse peut bloquer l'interface graphique ; prévoir une requête asynchrone.
- Prévoir un message clair lorsque le GPS n'a pas encore de position (`null`).

## Pourquoi cette approche ?

Cette solution permet de **séparer les traitements et l'interface graphique** : App Lab gère le MCU, le Bridge et le serveur Python ; Gambas3 s'occupe de l'affichage natif sous Ubuntu.

Elle n'impose **aucune Brick WebUI ni Brick personnalisée pour la seule exposition du JSON**. Une Brick peut toutefois rester utile si le projet requiert des dépendances ou services spécifiques, ou pour organiser des fonctionnalités réutilisables.

La même architecture peut être réemployée pour d'autres données : capteurs, mesures analogiques, états d'entrées/sorties, tableaux de bord, etc.

## Projet d'origine

- [UNO-Q-GPS — projet GPS pour Arduino UNO Q avec interface WebUI HTML](https://github.com/philippe86220/UNO-Q-GPS)


### Remerciements

Ce projet a été développé avec l'assistance de **ChatGPT (OpenAI)**, notamment pour la réflexion sur l'architecture de communication entre Arduino App Lab et Gambas3, la mise en œuvre du serveur HTTP Python, ainsi que l'analyse et la documentation du code.

Les différentes solutions ont été expérimentées, testées et validées sur une Arduino VENTUNO Q.

---

*Projet expérimental développé et testé sur Arduino VENTUNO Q. Les détails réseau et les composants disponibles peuvent évoluer selon les versions d'Arduino App Lab et d'Ubuntu.*

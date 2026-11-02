# Gambas-Ventuno-Q-GPS — Gambas3 Graphical Interface and JSON API

GPS application for **Arduino VENTUNO Q**: GPS data received by the MCU is transferred to the **Arduino App Lab** Python program, then displayed in a **native Gambas3 graphical interface** under Ubuntu.

This project follows the principle of the [UNO-Q-GPS](https://github.com/philippe86220/UNO-Q-GPS) project, which used an **HTML WebUI** interface on UNO Q. Here, the user interface is built with **Gambas3** on VENTUNO Q, without a WebUI Brick.

![Gambas3 graphical interface – VENTUNO Q GPS](image/gambas-gps.png)

## Architecture

```text
GPS → MCU (Arduino sketch)
          │
          │ Arduino Bridge
          ▼
Arduino App Lab / main container
  main.py
  ├── Bridge.provide("update_gps", ...)
  ├── Python _state dictionary (protected by a Lock)
  └── HTTP server: 0.0.0.0:8000
                         │
                         │ GET /api/state → JSON
                         ▼
Ubuntu (VENTUNO Q host)
  Gambas3 application
  ├── HttpClient
  ├── JSON.Decode()
  └── display of coordinates, date, time, satellites, and altitude
```

The HTTP server does not provide direct access to Python variables: it **returns a JSON representation** of the selected values with each request. The data remains in memory in the Python process; no `.json` file on disk is required.

> **Important:** Direct access from Ubuntu to the container's private IP address was tested on this VENTUNO Q. It depends on the host's Docker network configuration and does not provide an address guaranteed to remain stable across all installations.

## Prerequisites

- Arduino VENTUNO Q with Ubuntu and Arduino App Lab.
- An App Lab application receiving GPS data from the MCU through `Bridge`.
- The Python HTTP server running in the `main` container on port **8000**.
- Gambas3 installed on Ubuntu, with the HTTP and JSON components used by the project.

## Installing Gambas3

On the VENTUNO Q's Ubuntu system:

```bash
sudo apt update
sudo apt install gambas3
```

If the components are not already installed by the main package, also install:

```bash
sudo apt install gambas3-gb-net-curl gambas3-gb-util-web
```

In the Gambas project properties, check that the **`gb.net.curl`** (HTTP client) and **`gb.util.web`** (JSON decoding) components are enabled. The exact names of available packages can be checked with `apt search gambas3`.

## Application name and Docker container names

The Arduino App Lab project is named **`Gambas-Ventuno-Q-GPS`**.

**Do not assume that the full Docker container name is permanent.** During testing, App Lab created containers with different names:

```text
gambas-ventuno-q-gps-main-1
gambas-ventuno-q-gps-main-main-1
```

The old container remained present but was stopped, while the new container was running. Querying the stopped container returned an empty IP address.

The Gambas application identifies the running GPS container using two Docker filters:

- `name=gambas-ventuno-q-gps`: selects containers whose names match the application name.
- `label=com.docker.compose.service=main`: restricts the results to containers belonging to the Docker Compose `main` service, excluding other services such as additional Bricks.

Both filters are applied together.

This avoids relying on a fixed, complete container name.

**Note:** The current Gambas implementation assumes that exactly one running container matches both filters. This assumption was verified in the tested configuration.

## Starting the App Lab application

Launch the GPS application in **Arduino App Lab** and wait for its `main` container to start.

Find the active `main` container:

```bash
docker ps \
  --filter 'name=gambas-ventuno-q-gps' \
  --filter 'label=com.docker.compose.service=main' \
  --format '{{.Names}}'
```

For example, the command returned:

```text
gambas-ventuno-q-gps-main-main-1
```

The `PORTS` column may be empty: **publishing a port to the host is not necessary for testing a direct connection to the container's IP address**, provided that this IP address is reachable from Ubuntu.

## Finding the container's IP address

Once the active container has been identified, retrieve its IP address:

```bash
docker inspect -f '{{range .NetworkSettings.Networks}}{{.IPAddress}}{{end}}' gambas-ventuno-q-gps-main-main-1
```

In the latest test, this returned:

```text
172.26.0.2
```

Both the **container name** and its **IP address** may change when App Lab recreates the container. During testing, IP addresses included `172.24.0.2`, `172.25.0.2`, and `172.26.0.2`.

The Gambas program now discovers the running container and then retrieves its current IP address automatically.

Test the API from Ubuntu (replace the example address with the current one):

```bash
curl http://172.26.0.2:8000/api/state
```

A JSON response should contain the latest known GPS data, for example:

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

## HTTP server in `main.py`

The Python program stores GPS data in an `_state` dictionary. The `update_gps(...)` function, exposed through `Bridge.provide(...)`, updates this dictionary whenever the MCU sends data. A `threading.Lock()` protects concurrent access.

The `ThreadingHTTPServer` listens on `0.0.0.0:8000` inside the container and responds to:

```text
GET /api/state
```

It serializes the current state using `json.dumps(...)`, setting the content type to `application/json`.

The code also provides French local time using:

```python
import datetime
from zoneinfo import ZoneInfo

def now_local_fr():
    return datetime.datetime.now(ZoneInfo('Europe/Paris')).strftime('%d/%m/%Y %H:%M:%S')
```

The `api_state()` function calls `now_local_fr()` and adds `payload["now_local"]` to the response. The full code is available in the project's source files.

## Gambas3 interface

The Gambas form uses `Timer1` to periodically query the API, decode the JSON response and display GPS values.

**Important: set the `Enabled` property of `Timer1` to `False` in the Gambas3 form editor.** The timer must not run before the application has identified the active container and constructed a valid server URL. It is started explicitly at the end of `Form_Open()`.

### Discovering the active container and its IP address

Declare the server address as a form-level variable:

```gambas
Private AdresseServeur As String
```

The updated `Form_Open()` procedure performs two separate operations: it first identifies the running `main` container using **two filters**, then retrieves that container's IP address.

```gambas
Public Sub Form_Open()

  Dim IP As String
  Dim conteneur As String

  ' Find the running container for this application and the main service
  Shell "docker ps --filter 'name=gambas-ventuno-q-gps' --filter 'label=com.docker.compose.service=main' --format '{{.Names}}'" To conteneur
  conteneur = Trim(conteneur)

  If conteneur = "" Then
    Message.Error("Aucun conteneur GPS principal actif.")
    Quit
  Endif

  ' Retrieve the current IP address of that container
  Shell "docker inspect -f '{{range .NetworkSettings.Networks}}{{.IPAddress}}{{end}}' " & Shell$(conteneur) To IP
  IP = Trim(IP)

  If IP = "" Then
    Message.Error("Impossible de récupérer l'adresse IP du conteneur.")
    Quit
  Endif

  AdresseServeur = "http://" & IP & ":8000/api/state"
  Print "Serveur GPS : "; AdresseServeur

  ' Start the timer only after successful initialization
  Timer1.Start

End
```

The two filters prevent an additional Brick container from being selected instead of the `main` service. `Shell$(conteneur)` quotes the retrieved container name for use in the shell command.

The code assumes that exactly one running container matches both filters. If none is found, or if its IP address is empty, the application displays an error and exits **without starting the timer**. If several containers match, additional selection logic would be needed.

### Periodic HTTP requests

In `Timer1_Timer()`, use the address initialized by `Form_Open()` instead of a hard-coded IP:

```gambas
client = New HttpClient
client.URL = AdresseServeur
client.Async = False
client.Timeout = 40
client.Get()

If client.Status < 0 Then
  Print "Erreur"
  Quit
Endif

If Lof(client) Then Reponse = Read #client, Lof(client)
Data = JSON.Decode(Reponse)
```

The rest of the procedure displays `Data["lat"]`, `Data["long"]`, the UTC date and time, satellite count, altitude, and `Data["now_local"]` in the corresponding labels.

**Timer initialization and error handling:** the timer remains disabled in the form editor and is started only when `AdresseServeur` has been initialized. In the tested code, an HTTP client error also exits the application, rather than repeatedly printing errors on subsequent timer events.

**Requirements and limitations:** start the App Lab application before Gambas3. The Ubuntu user must be able to run `docker ps` and `docker inspect` without a permission error. This implementation discovers the address only when Gambas3 starts. **For example, if you stop the GPS application in Arduino App Lab and then start it again while leaving the Gambas3 window open**, App Lab may recreate the container with a different IP address. Gambas3 will still use the old address; in the current version, an HTTP connection error causes Gambas3 to exit. Once the App Lab application is running again, restart Gambas3 so that it can discover the new container and IP address. Automatic reconnection is not implemented. The IP extraction also assumes one suitable Docker network address.

This technique can be reused for other Linux commands: for example, `Shell "uname -r" To Resultat` retrieves the kernel version into a Gambas variable.

### Possible improvements

- Check the HTTP response status code, the presence of a JSON response body, and JSON decoding errors.
- Handle Docker command failures and multiple matching containers or network interfaces explicitly.
- Rediscover the active container automatically if it changes while Gambas3 is running.
- Avoid a synchronous request in the timer if response delays could freeze the graphical interface; use an asynchronous request instead.
- Provide a clear message when the GPS has not yet obtained a position (`null`).

## Why this approach?

This solution makes it possible to **separate processing from the graphical interface**: App Lab manages the MCU, the Bridge, and the Python server; Gambas3 handles the native display under Ubuntu.

It requires **neither a WebUI Brick nor a custom Brick solely to expose JSON**. A Brick may nevertheless be useful if the project requires specific dependencies or services, or to organize reusable features.

The same architecture can be reused for other data: sensors, analog measurements, input/output states, dashboards, etc.

## Original project

- [UNO-Q-GPS — GPS project for Arduino UNO Q with an HTML WebUI interface](https://github.com/philippe86220/UNO-Q-GPS)

### Acknowledgments

This project was developed with the assistance of **ChatGPT (OpenAI)**, particularly in exploring the communication architecture between Arduino App Lab and Gambas3, implementing the Python HTTP server, and analyzing and documenting the code.

The various solutions were experimented with, tested, and validated on an Arduino VENTUNO Q.

---

*Experimental project developed and tested on Arduino VENTUNO Q. Network details and available components may change depending on the versions of Arduino App Lab and Ubuntu.*

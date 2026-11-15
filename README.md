# SteelSeries Rival 3 (Gen 2) a Home Assistant RGB Bridge 🖱️🌈

Integración completa para controlar la **iluminación base RGB** de tu ratón **SteelSeries Rival 3 (Gen 2)** desde **Home Assistant** como una luz inteligente nativa.

Incluye soporte para:
- 🎨 **Rueda cromática RGB completa** (cualquier color en tiempo real).
- ☀️ **Control de brillo y blanco puro**.
- 🔌 **Apagado real**: los LEDs se apagan por completo sin restaurar el perfil blanco por defecto.
- 🔄 **Keep-Alive Inteligente**: no vuelve al perfil predeterminado tras unos segundos de inactividad.
- 🔍 **Detección USB automática**: solo corre cuando el ratón está físicamente conectado.
- 🥷 **Ejecución 100% invisible en segundo plano**: sin ventanas de terminal en tu pantalla.

---

## 📐 Arquitectura de la solución

![Diagrama de Arquitectura](images/architecture_diagram.svg)

### ¿Cómo funciona por debajo?
1. **SteelSeries GameSense API**: SteelSeries GG/Engine expone un servidor HTTP local en Windows cuyo puerto dinámico se obtiene de `%PROGRAMDATA%\SteelSeries\SteelSeries Engine 3\coreProps.json`.
2. **Handlers `context-color`**: Registramos un evento (`SET_COLOR`) que se vincula a las 3 zonas de la franja base inferior del Rival 3 (`zone: one`, `two`, `three`) y el logo.
3. **Servidor Puente en Windows**: Un script nativo de PowerShell escucha en el puerto `5055`. Cuando Home Assistant envía una petición con `{ "r": 255, "g": 0, "b": 128 }`, el puente lo traduce y se lo inyecta a SteelSeries.
4. **Heartbeat en Background**: SteelSeries requiere "latidos" periódicos para mantener un evento activo. Un hilo en segundo plano (`Runspace`) refresca el estado cada 1.5 segundos para que la luz nunca parpadee ni se revierta.

---

## 📱 Vista en Home Assistant

Una vez configurado, tendrás una entidad de luz estándar con la que puedes interactuar desde la app móvil o el navegador:

![Control en Home Assistant](images/homeassistant_light_ui.png)

---

## 🚀 Guía de Instalación Paso a Paso

### Paso 1: Configurar el ordenador con Windows (Servidor Puente)

1. Descarga o clona este repositorio en tu ordenador:
   ```bash
   git clone https://github.com/TU_USUARIO/SteelSeries-Rival3-HomeAssistant.git
   ```
2. Entra en la carpeta descargada.
3. Haz **clic derecho** sobre **`install_autostart.bat`** y selecciona **"Ejecutar como administrador"**.

Este script se encargará automáticamente de:
- Conceder el permiso de red en Windows para escuchar en el puerto `5055`.
- Crear el acceso directo en la carpeta de Inicio de Windows (`shell:startup`) para que arranque en segundo plano cada vez que inicies sesión.
- Iniciar el puente en ese mismo momento de forma silenciosa.

> **💡 Nota sobre la detección del ratón:** El puente comprueba mediante `Win32_PnPEntity` el identificador de hardware del Rival 3 (`VID_1038&PID_1870`). Si el ratón no está conectado al encender el PC, el script se cerrará solo para no consumir memoria.

---

### Paso 2: Configurar Home Assistant

Abre tu archivo `configuration.yaml` de Home Assistant (a través de SSH, Samba o tu editor habitual) y pega el contenido de [homeassistant_config.yaml](homeassistant_config.yaml):

> ⚠️ **IMPORTANTE**: Sustituye `<IP_DE_TU_PC>` por la dirección IP de tu ordenador en la red local (ejemplo `192.168.1.148`) o por la IP de **Tailscale** si tienes ambos dispositivos conectados por Tailscale (ejemplo `100.109.92.4`).

```yaml
input_boolean:
  rival3_power:
    name: "Rival 3 Estado"

input_number:
  rival3_h:
    name: "Rival 3 Hue"
    min: 0
    max: 360
    initial: 0
  rival3_s:
    name: "Rival 3 Saturation"
    min: 0
    max: 100
    initial: 0
  rival3_brightness:
    name: "Rival 3 Brillo"
    min: 0
    max: 255
    initial: 255

rest_command:
  rival3_base_color:
    url: "http://<IP_DE_TU_PC>:5055/set_color"
    method: POST
    headers:
      content-type: "application/json"
    payload: >-
      {
        "r": {{ r | default(0) }},
        "g": {{ g | default(0) }},
        "b": {{ b | default(0) }}
      }

light:
  - platform: template
    lights:
      rival3_luz_base:
        friendly_name: "Rival 3 Luz Base"
        unique_id: rival3_luz_base
        value_template: "{{ is_state('input_boolean.rival3_power', 'on') }}"
        level_template: "{{ states('input_number.rival3_brightness') | int }}"
        hs_template: >-
          ({{ states('input_number.rival3_h') | float }}, {{ states('input_number.rival3_s') | float }})
        turn_on:
          - action: input_boolean.turn_on
            target:
              entity_id: input_boolean.rival3_power
          - action: rest_command.rival3_base_color
            data:
              r: 255
              g: 255
              b: 255
        turn_off:
          - action: input_boolean.turn_off
            target:
              entity_id: input_boolean.rival3_power
          - action: rest_command.rival3_base_color
            data:
              r: 0
              g: 0
              b: 0
        set_level:
          - action: input_number.set_value
            target:
              entity_id: input_number.rival3_brightness
            data:
              value: "{{ level }}"
          - action: rest_command.rival3_base_color
            data:
              r: "{{ level }}"
              g: "{{ level }}"
              b: "{{ level }}"
        set_hs:
          - action: input_number.set_value
            target:
              entity_id: input_number.rival3_h
            data:
              value: "{{ h }}"
          - action: input_number.set_value
            target:
              entity_id: input_number.rival3_s
            data:
              value: "{{ s }}"
          - action: input_boolean.turn_on
            target:
              entity_id: input_boolean.rival3_power
          - action: rest_command.rival3_base_color
            data:
              r: >-
                {% set bri = (states('input_number.rival3_brightness') | default(255) | int) / 255.0 %}
                {% set s_norm = (s | float) / 100.0 %}
                {% if s_norm == 0 %}
                  {{ (bri * 255) | int }}
                {% else %}
                  {% set c = bri * s_norm %}
                  {% set x = c * (1 - (((h / 60.0) % 2) - 1) | abs) %}
                  {% set m = bri - c %}
                  {% if h < 60 %}{{ ((c + m) * 255) | int }}
                  {% elif h < 120 %}{{ ((x + m) * 255) | int }}
                  {% elif h < 180 %}{{ (m * 255) | int }}
                  {% elif h < 240 %}{{ (m * 255) | int }}
                  {% elif h < 300 %}{{ ((x + m) * 255) | int }}
                  {% else %}{{ ((c + m) * 255) | int }}{% endif %}
                {% endif %}
              g: >-
                {% set bri = (states('input_number.rival3_brightness') | default(255) | int) / 255.0 %}
                {% set s_norm = (s | float) / 100.0 %}
                {% if s_norm == 0 %}
                  {{ (bri * 255) | int }}
                {% else %}
                  {% set c = bri * s_norm %}
                  {% set x = c * (1 - (((h / 60.0) % 2) - 1) | abs) %}
                  {% set m = bri - c %}
                  {% if h < 60 %}{{ ((x + m) * 255) | int }}
                  {% elif h < 120 %}{{ ((c + m) * 255) | int }}
                  {% elif h < 180 %}{{ ((c + m) * 255) | int }}
                  {% elif h < 240 %}{{ ((x + m) * 255) | int }}
                  {% else %}{{ (m * 255) | int }}{% endif %}
                {% endif %}
              b: >-
                {% set bri = (states('input_number.rival3_brightness') | default(255) | int) / 255.0 %}
                {% set s_norm = (s | float) / 100.0 %}
                {% if s_norm == 0 %}
                  {{ (bri * 255) | int }}
                {% else %}
                  {% set c = bri * s_norm %}
                  {% set x = c * (1 - (((h / 60.0) % 2) - 1) | abs) %}
                  {% set m = bri - c %}
                  {% if h < 120 %}{{ (m * 255) | int }}
                  {% elif h < 180 %}{{ ((x + m) * 255) | int }}
                  {% elif h < 240 %}{{ ((c + m) * 255) | int }}
                  {% elif h < 300 %}{{ ((x + m) * 255) | int }}
                  {% else %}{{ ((x + m) * 255) | int }}{% endif %}
                {% endif %}
```

---

### Paso 3: Reiniciar Home Assistant

1. En Home Assistant ve a **Herramientas para desarrolladores** > pestaña **YAML**.
2. Pulsa en **"Comprobar configuración"**.
3. Si la configuración es válida, pulsa en **"Reiniciar"** (o reinicia el contenedor con `docker restart homeassistant`).
4. Añade la tarjeta de la entidad `light.rival3_luz_base` a tu panel de control.

¡Listo! Ya tienes control total del color de tu ratón sincronizado con tus automatizaciones, escenas y dashboards de Home Assistant.

---

## 🗑️ Desinstalación

Si alguna vez deseas eliminar el inicio automático del PC:
- Ejecuta el archivo `uninstall_autostart.bat`.
- Eliminará el acceso directo de la carpeta de inicio y cerrará el proceso activo.

---

## 📡 Alternativa recomendada si usas MQTT: Modo MQTT Discovery + `rivalcfg` (sin editar YAML ni reiniciar HA)

Si ya tienes un broker **MQTT** (por ejemplo Mosquitto) configurado en Home Assistant, esta opción te permite controlar **toda la iluminación y los ajustes internos del ratón** sin tocar `configuration.yaml`, sin reiniciar Home Assistant y sin abrir puertos en el firewall de Windows.

### Requisitos previos
- **Python 3.10+** instalado en Windows.
- **Broker MQTT** activo y conectado a tu Home Assistant.
- **SteelSeries GG / Engine** abierto (necesario únicamente para la entidad **Luz RGB** en tiempo real; los ajustes de `rivalcfg` funcionan incluso sin SteelSeries GG).

### Paso 1: Configurar las credenciales MQTT
1. Entra en la carpeta [`mqtt_bridge/`](mqtt_bridge/).
2. Copia [`config.example.json`](mqtt_bridge/config.example.json) como `config.json` y rellena los datos de tu broker:
   ```json
   {
     "mqtt_host": "192.168.1.100",
     "mqtt_port": 1883,
     "mqtt_user": "tu_usuario_mqtt",
     "mqtt_password": "tu_password_mqtt"
   }
   ```
   *(Si tu broker no usa autenticación, deja `mqtt_user` y `mqtt_password` vacíos `""`).*

### Paso 2: Instalar y activar el arranque automático
Haz doble clic en [`mqtt_bridge/install_autostart.bat`](mqtt_bridge/install_autostart.bat) (no requiere permisos de administrador). El script se encargará automáticamente de:
- Crear el entorno virtual `.venv` e instalar `paho-mqtt` y `rivalcfg`.
- Cerrar cualquier instancia previa duplicada del puente.
- Crear el acceso directo en Inicio de Windows (`shell:startup`) usando [`start_hidden.vbs`](mqtt_bridge/start_hidden.vbs).
- Iniciar el puente en segundo plano.

### Paso 3: Comprobación manual (opcional)
Si quieres ver los logs de conexión en consola antes de dejarlo en segundo plano:
```powershell
cd mqtt_bridge
.\.venv\Scripts\python.exe .\rival3_mqtt_bridge.py
```
Si muestra `[OK] Conectado al broker MQTT`, el dispositivo **SteelSeries Rival 3 Gen 2** aparecerá automáticamente en Home Assistant dentro de **Ajustes > Dispositivos y servicios > MQTT**.

### Entidades incluidas en Home Assistant
- **Controles**:
  - **Luz RGB**: control en tiempo real (rueda de color y brillo) mediante SteelSeries GameSense, sin escribir en la memoria flash del ratón.
- **Configuración (memoria interna del ratón vía `rivalcfg`)**:
  - **Zona superior / Zona central / Zona inferior**: color RGB fijo por zona (`--z1`, `--z2`, `--z3`).
  - **Luz al hacer clic**: color reactivo al pulsar botones (`-a`).
  - **Brillo LED**: deslizador de `0` a `100 %` (`-l`).
  - **Sensibilidad (DPI)**: deslizador de `200` a `8500 DPI` en pasos de `100` (`-s`).
  - **Frecuencia (Hz)**: selector `125`, `250`, `500` o `1000` (`-p`).
  - **Efecto arcoíris**: selector en español (`Todo el ratón`, `Zona inferior`, `Zona central`, `Zona superior`, etc.) e incluye **`Desactivado (color fijo)`** para volver a los colores de Z1/Z2/Z3 (`-e`).
  - **Luz al encender**: comportamiento al arrancar el ratón (`Arcoíris`, `Apagada`, `Reactiva al clic`, `Arcoíris + Reactiva`) (`-d`).
  - **Botón superior**: `Cambiar DPI (por defecto)`, `Desactivado` o `Clic central` (`-b`).
  - **Restablecer de fábrica**: botón para restaurar los valores de serie (`-r`).

> **Nota:** El cambio físico de DPI desde el botón del ratón ocurre dentro del hardware y no envía eventos al PC, por lo que no se refleja de vuelta en Home Assistant. Si quieres mantenerlos sincronizados, puedes desactivar el botón superior desde HA y ajustar el DPI desde ahí.

### Desinstalación del modo MQTT
Ejecuta [`mqtt_bridge/uninstall_autostart.bat`](mqtt_bridge/uninstall_autostart.bat) para eliminar el acceso directo de Inicio y cerrar el proceso activo.

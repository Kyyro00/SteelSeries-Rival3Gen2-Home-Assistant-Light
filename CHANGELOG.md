# Changelog

## [Unreleased]

### Added
- **Puente alternativo por MQTT Discovery + `rivalcfg` (`mqtt_bridge/`)**:
  - Descubrimiento automático en Home Assistant sin editar `configuration.yaml`, sin reiniciar Home Assistant y sin abrir puertos en el firewall de Windows.
  - Control en tiempo real de **Luz RGB** mediante la API local de SteelSeries GameSense (con heartbeat en segundo plano).
  - Exposición completa de los ajustes en memoria del **SteelSeries Rival 3 Gen 2** vía `rivalcfg`:
    - Luces RGB individuales por zona (`Zona superior`, `Zona central`, `Zona inferior`) y `Luz al hacer clic` (reactiva).
    - Deslizador de `Brillo LED` (`0–100 %`) y `Sensibilidad (DPI)` (`200–8500 DPI`).
    - Selectores amigables para `Frecuencia (Hz)` (`125` / `250` / `500` / `1000`), `Efecto arcoíris` (incluyendo `Desactivado (color fijo)`), `Luz al encender` y `Botón superior` (DPI).
    - Botón `Restablecer de fábrica` (`rivalcfg -r`).
  - Persistencia local en `state.json` de los ajustes aplicados en memoria y estado de disponibilidad (`online` / `offline` vía LWT).
  - Bloqueo de instancia única mediante mutex de Windows (`Local\Rival3HAMQTTBridgeMutex`) para evitar múltiples procesos duplicados.
  - Scripts de inicio automático (`mqtt_bridge/install_autostart.bat`, `start_hidden.vbs`, `uninstall_autostart.bat`) con creación automática de `.venv` y `config.json` desde `config.example.json`.

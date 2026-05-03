# MeterBridge

[![hacs_badge](https://img.shields.io/badge/HACS-Custom-orange.svg)](https://github.com/hacs/integration)

**MeterBridge** is a Home Assistant custom integration that connects Modbus smart meters
without any manual register configuration. Select your device and desired sensor groups
through a guided setup – no YAML or Modbus knowledge required.

## Supported Devices

| Device | Protocol | Groups |
|---|---|---|
| TQ Energy TQ300 | Modbus TCP | basic, phases, energy, quality |
| Kostal KSEM | Modbus TCP | basic, phases, energy, quality |
| Eastron SDM120 | Modbus TCP | basic, energy, quality |
| Eastron SDM230 | Modbus TCP | basic, energy, quality |
| Eastron SDM630 | Modbus TCP | basic, phases, energy, quality |

## Installation via HACS

1. Open HACS → Integrations → ⋮ → Custom repositories
2. Add `https://github.com/jedrimos/meterbridge` as **Integration**
3. Search for *MeterBridge* and install
4. Restart Home Assistant
5. Go to **Settings → Integrations → Add Integration** and search for *MeterBridge*

## Setup

The guided config flow walks you through four steps:

1. **Device selection** – pick your meter model
2. **Connection** – enter host/IP, port, Slave ID, and polling interval
3. **Sensor groups** – choose which groups to activate (Basic is pre-selected)
4. **Connection test** – a live Modbus check; errors show inline with hints

After setup you can adjust sensor groups and polling interval anytime via
**Settings → Integrations → MeterBridge → Configure**.

## Sensor Groups

| Group | Sensors |
|---|---|
| Basic | Total power, import/export power |
| Phases | L1/L2/L3 voltage, current, power |
| Energy | kWh import/export totals |
| Grid Quality | Frequency, power factor |

## Adding a New Device

Drop a JSON file into `custom_components/meterbridge/devices/` following the schema
in the existing profiles. No code changes needed.

## License

MIT

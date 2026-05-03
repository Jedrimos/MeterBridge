DOMAIN = "meterbridge"

CONF_DEVICE_ID = "device_id"
CONF_SLAVE_ID = "slave_id"
CONF_POLL_INTERVAL = "poll_interval"
CONF_GROUPS = "groups"

DEFAULT_PORT = 502
DEFAULT_SLAVE_ID = 1
DEFAULT_POLL_INTERVAL = 10

REGISTER_GROUPS: dict[str, str] = {
    "basic": "Basic Values",
    "phases": "Phase Values",
    "energy": "Energy Counters",
    "quality": "Grid Quality",
}

REGISTER_TYPE_HOLDING = "holding"
REGISTER_TYPE_INPUT = "input"

DATA_TYPE_UINT16 = "uint16"
DATA_TYPE_INT16 = "int16"
DATA_TYPE_UINT32 = "uint32"
DATA_TYPE_INT32 = "int32"
DATA_TYPE_FLOAT32 = "float32"

REGISTER_COUNT: dict[str, int] = {
    DATA_TYPE_UINT16: 1,
    DATA_TYPE_INT16: 1,
    DATA_TYPE_UINT32: 2,
    DATA_TYPE_INT32: 2,
    DATA_TYPE_FLOAT32: 2,
}

'''
O que esse script faz: conecta ao servidor OPC UA (Anonymous, Security None), lê de forma assíncrona e eficiente todas as 20 variáveis mapeadas a cada 1 segundo, organiza tudo em um JSON estruturado por grupo (command, process, status), imprime no console com timestamp UTC, registra logs de erro caso alguma leitura falhe isoladamente, e se a conexão cair por completo, entra em loop de reconexão automática a cada 5 segundos até voltar a funcionar.
'''

import asyncio
import json
import logging
from datetime import datetime, timezone

from asyncua import Client
from asyncua.ua import UaStatusCodeError

# ------------------------------------------------------------------
# Configurações
# ------------------------------------------------------------------

SERVER_URL = "opc.tcp://localhost:4840"
NAMESPACE_INDEX = 4
APP_PATH = "CODESYS Control Win V3 x64.Application"

READ_INTERVAL_SECONDS = 1.0
RECONNECT_DELAY_SECONDS = 5.0

# ------------------------------------------------------------------
# Logging
# ------------------------------------------------------------------

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)-8s | %(message)s",
)
logger = logging.getLogger("gateway_c1")

# ------------------------------------------------------------------
# Mapeamento das variáveis: nome amigável -> caminho no servidor
# ------------------------------------------------------------------

VARIABLES = {
    # GVL_C1.C1_Cmd
    "cmd_liga": "GVL_C1.C1_Cmd.bLiga",
    "cmd_desliga": "GVL_C1.C1_Cmd.bDesliga",
    "cmd_reset": "GVL_C1.C1_Cmd.bReset",
    "cmd_emergencia_ok": "GVL_C1.C1_Cmd.bEmergenciaOK",
    "cmd_hz_set": "GVL_C1.C1_Cmd.rHzSet",

    # GVL_C1.C1_Proc
    "proc_q_frig_kw": "GVL_C1.C1_Proc.rQFrigKW",
    "proc_pot_kw": "GVL_C1.C1_Proc.rPotKW",
    "proc_cop_real": "GVL_C1.C1_Proc.rCOPReal",

    # GVL_C1.C1_Sts
    "sts_estado": "GVL_C1.C1_Sts.eEstado",
    "sts_falha": "GVL_C1.C1_Sts.eFalha",
    "sts_rodando": "GVL_C1.C1_Sts.bRodando",
    "sts_em_falha": "GVL_C1.C1_Sts.bFalha",
    "sts_alarme": "GVL_C1.C1_Sts.bAlarme",
    "sts_hz": "GVL_C1.C1_Sts.rHz",
    "sts_amp": "GVL_C1.C1_Sts.rAmp",
    "sts_p_suc": "GVL_C1.C1_Sts.rPSuc",
    "sts_p_desc": "GVL_C1.C1_Sts.rPDesc",

    # GVL_Proc
    "proc_q_demanda_kw": "GVL_Proc.rQDemandaKW",
    "proc_t_camara": "GVL_Proc.rTCamara",
    "proc_t_cond": "GVL_Proc.rTCond",
    "proc_t_evap": "GVL_Proc.rTEvap",
}


def build_nodeid_string(path: str) -> str:
    """Monta a string de NodeId no formato que o asyncua espera."""
    identifier = f"|var|{APP_PATH}.{path}"
    return f"ns={NAMESPACE_INDEX};s={identifier}"


async def read_all_variables(client: Client) -> dict:
    """Lê todas as variáveis mapeadas e retorna um dicionário com os valores."""
    nodes = {name: client.get_node(build_nodeid_string(path)) for name, path in VARIABLES.items()}

    results = await asyncio.gather(
        *(node.read_value() for node in nodes.values()),
        return_exceptions=True,
    )

    data = {}
    for (name, _), value in zip(nodes.items(), results):
        if isinstance(value, Exception):
            logger.warning(f"Falha ao ler '{name}': {value}")
            data[name] = None
        else:
            data[name] = value

    return data


def build_payload(data: dict) -> dict:
    """Estrutura os dados em um payload JSON organizado e com timestamp UTC."""
    timestamp = datetime.now(timezone.utc).isoformat()

    payload = {
        "timestamp_utc": timestamp,
        "equipment": "C1",
        "command": {
            "liga": data.get("cmd_liga"),
            "desliga": data.get("cmd_desliga"),
            "reset": data.get("cmd_reset"),
            "emergencia_ok": data.get("cmd_emergencia_ok"),
            "hz_set": data.get("cmd_hz_set"),
        },
        "process": {
            "q_frig_kw": data.get("proc_q_frig_kw"),
            "pot_kw": data.get("proc_pot_kw"),
            "cop_real": data.get("proc_cop_real"),
            "q_demanda_kw": data.get("proc_q_demanda_kw"),
            "t_camara": data.get("proc_t_camara"),
            "t_cond": data.get("proc_t_cond"),
            "t_evap": data.get("proc_t_evap"),
        },
        "status": {
            "estado": data.get("sts_estado"),
            "falha": data.get("sts_falha"),
            "rodando": data.get("sts_rodando"),
            "em_falha": data.get("sts_em_falha"),
            "alarme": data.get("sts_alarme"),
            "hz": data.get("sts_hz"),
            "amp": data.get("sts_amp"),
            "p_suc": data.get("sts_p_suc"),
            "p_desc": data.get("sts_p_desc"),
        },
    }

    return payload


async def run_client():
    """Loop principal: conecta, lê ciclicamente e trata desconexões."""
    client = Client(url=SERVER_URL)

    async with client:
        logger.info(f"Conectado ao servidor OPC UA em {SERVER_URL}")

        while True:
            try:
                data = await read_all_variables(client)
                payload = build_payload(data)

                print(json.dumps(payload, indent=2, ensure_ascii=False))

                await asyncio.sleep(READ_INTERVAL_SECONDS)

            except UaStatusCodeError as e:
                logger.error(f"Erro de status OPC UA durante leitura: {e}")
                raise

            except (ConnectionError, asyncio.TimeoutError) as e:
                logger.error(f"Erro de conexão durante leitura: {e}")
                raise


async def main():
    """Loop externo de reconexão automática."""
    while True:
        try:
            await run_client()

        except Exception as e:
            logger.error(f"Conexão perdida ou erro inesperado: {e}")
            logger.info(f"Tentando reconectar em {RECONNECT_DELAY_SECONDS} segundos...")
            await asyncio.sleep(RECONNECT_DELAY_SECONDS)


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("Encerrado pelo usuário (Ctrl+C).")
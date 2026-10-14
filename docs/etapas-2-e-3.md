# Projeto SMART REFRIGERATION — Etapas 2 e 3

## Objetivo desta fase

Construir a ponte de comunicação entre o CLP (CODESYS) e o mundo externo, usando OPC UA como protocolo de leitura das variáveis do processo, Node-RED como gateway de orquestração, e MQTT (Mosquitto) como broker de publicação da telemetria, preparando o terreno para a futura ingestão em banco de dados (FastAPI + PostgreSQL/TimescaleDB).

Arquitetura alvo:
CLP (CODESYS) → OPC UA → Node-RED (gateway) → MQTT (Mosquitto) → [próxima fase: FastAPI → PostgreSQL/TimescaleDB]

---

## Etapa 2 — Node-RED como gateway OPC UA

### 2.1 Instalação e preparação

- Node-RED já estava baixado e instalado previamente pelo usuário.
- Foi instalado o pacote `node-red-contrib-opcua` via **Manage palette** (Menu → Manage palette → Install), que adiciona os nodes de cliente/servidor OPC UA ao Node-RED. O suporte a MQTT já vem nativo no Node-RED, sem necessidade de pacote adicional.

### 2.2 Configuração do node OpcUa-Client

- Endpoint apontando para o servidor OPC UA do runtime CODESYS: `opc.tcp://localhost:4840`.
- Autenticação: Anonymous (sem segurança), igual ao usado no cliente Python da Fase 3 original.
- Campos preenchidos na configuração do Endpoint: Application Name (`NodeOPCUAClient`), Application URI (`urn:mycompany:NodeOPCUAClient`), Certificate em branco, opções de transporte e keep-alive padrão.
- Mensagem `userIdentity is ANONYMOUS` observada nos logs é apenas informativa, não indica erro.
- Confirmação de conexão bem-sucedida: status do node mostrando **Session Active**.

### 2.3 Passagem do NodeId

Diferente do Python, o node OpcUa-Client do Node-RED não tem um campo fixo de NodeId na configuração — ele lê o NodeId a partir de `msg.topic` da mensagem recebida. Por isso, um node **Function** precede o OpcUa-Client, montando a mensagem assim:


javascript
Copiar

msg.topic = "ns=4;s=|var|CODESYS Control Win V3 x64.Application.GVL_C1.C1_Sts.rHz";
msg.payload = "";
return msg;




### 2.4 Testes individuais realizados

- Leitura de `GVL_C1.C1_Sts.rHz` → retornou `45` (Hz), confirmando leitura correta.
- Leitura de `GVL_Proc.rTCamara` → retornou `-8.35` (°C aproximadamente), confirmando leitura correta.
- Em ambos os testes apareceu uma mensagem inicial com `payload: undefined`, tratada como resíduo de inicialização do node, sem impacto no funcionamento.

---

## Etapa 3 — Leitura em lote e montagem do JSON completo

### 3.1 Problema a resolver

O OPC UA Client do Node-RED responde de forma **assíncrona**, uma leitura por vez. Para montar um JSON único com as 20 variáveis do processo (comandos, processo e status), foi necessário um mecanismo de disparo múltiplo e coleta progressiva das respostas.

### 3.2 Node Function "Build Requests"

Este node dispara, em sequência, uma mensagem de leitura para cada uma das 20 variáveis mapeadas (5 de comando, 7 de processo, 8 de status), usando `node.send()` várias vezes dentro de um loop. Também inicializa duas variáveis de fluxo (`flow.set`):

- `opcVariables`: lista com nome amigável e NodeId de cada variável.
- `opcResults`: objeto vazio que vai acumular as respostas conforme chegam.

Variáveis mapeadas:

**Comando (GVL_C1.C1_Cmd):** `bLiga`, `bDesliga`, `bReset`, `bEmergenciaOK`, `rHzSet`

**Processo (GVL_C1.C1_Proc):** `rQFrigKW`, `rPotKW`, `rCOPReal`

**Processo (GVL_Proc):** `rQDemandaKW`, `rTCamara`, `rTCond`, `rTEvap`

**Status (GVL_C1.C1_Sts):** `eEstado`, `eFalha`, `bRodando`, `bFalha`, `bAlarme`, `rHz`, `rAmp`, `rPSuc`, `rPDesc`

### 3.3 Node Function "Collect Results"

Conectado na saída do OpcUa-Client, este node recebe cada resposta individual, identifica a qual variável ela pertence (comparando `msg.topic` com a lista salva em `opcVariables`), e vai acumulando os valores em `opcResults` (armazenado em `flow.set`/`flow.get`).

Quando o número de respostas coletadas atinge o total de 20 variáveis, o node monta o JSON final, organizado em três blocos:

- `command`: estado dos comandos (liga, desliga, reset, emergência, setpoint de frequência).
- `process`: variáveis de processo térmico e elétrico (capacidade frigorífica, potência, COP, demanda, temperaturas).
- `status`: estado da máquina de estados, falhas, alarme, frequência real, corrente e pressões.

Após montar o JSON, o acumulador `opcResults` é zerado (`flow.set("opcResults", {})`) para preparar o próximo ciclo de leitura.

### 3.4 Fluxo completo no Node-RED
Inject → Build Requests → OpcUa-Client → Collect Results → Debug

### 3.5 Resultado validado

O debug do Node-RED retornou um único objeto JSON com os três blocos completos e coerentes com os valores vistos no UaExpert e no cliente Python, por exemplo:


json
Copiar

{
  "timestamp": "2026-10-14T18:49:30.060Z",
  "command": {
    "liga": true,
    "desliga": false,
    "reset": false,
    "emergencia_ok": true,
    "hz_set": 45
  },
  "process": {
    "q_frig_kw": 300.27,
    "pot_kw": 85.51,
    "cop_real": 3.51,
    "q_demanda_kw": 300,
    "t_camara": -8.47,
    "t_cond": 28.06,
    "t_evap": -14.57
  },
  "status": {
    "estado": 2,
    "falha": 0,
    "rodando": true,
    "falha_bit": false,
    "alarme": false,
    "hz": 45,
    "amp": 148.37,
    "p_suc": 1.39,
    "p_desc": 10.10
  }
}




Observação sobre a física da simulação: a queda do COP (de ~4.93 para ~3.51) e da pressão de sucção (de ~2.96 para ~1.39 bar) é esperada e correta, já que a câmara foi resfriando (temperatura caindo) enquanto a demanda térmica permanece fixa, reduzindo a carga real sobre o compressor.

---

## Etapa 3 (continuação) — Instalação do Mosquitto e publicação MQTT

### 3.6 Instalação do broker

- Download feito em `mosquitto.org/download`, instalador para Windows x64.
- Instalação com opções padrão, que já configura o Mosquitto como **serviço do Windows**, iniciando automaticamente na porta `1883` (sem criptografia, uso local/teste).
- Confirmação do serviço rodando via PowerShell:


powershell
Copiar

sc query mosquitto
net start mosquitto




### 3.7 Teste manual do broker (linha de comando)

Os utilitários `mosquitto_pub.exe` e `mosquitto_sub.exe` ficam em `C:\Program Files\mosquitto`. No PowerShell é necessário usar `.\` antes do nome do executável (diferente do CMD, que aceita só o nome).

Terminal 1 (escutando):

powershell
Copiar

cd "C:\Program Files\mosquitto"
.\mosquitto_sub.exe -h localhost -t sala_maquinas/c1/telemetry




Terminal 2 (publicando, feito pelo próprio Node-RED neste caso).

### 3.8 Node MQTT out no Node-RED

- Node `mqtt out` adicionado na saída do "Collect Results".
- Configuração do broker: Server `localhost`, Port `1883`, sem usuário/senha (Mosquitto sem autenticação configurada).
- Tópico de publicação definido: `sala_maquinas/c1/telemetry`.
- QoS: 0. Retain: desmarcado.

### 3.9 Teste de ponta a ponta validado

Fluxo completo testado: CLP (CODESYS) → OPC UA → Node-RED (Build Requests → OpcUa-Client → Collect Results) → MQTT out → Mosquitto.

Resultado recebido no `mosquitto_sub.exe` escutando o tópico `sala_maquinas/c1/telemetry`:


json
Copiar

{"timestamp":"2026-10-14T19:00:27.746Z","command":{"liga":true,"desliga":false,"reset":false,"emergencia_ok":true,"hz_set":45},"process":{"q_frig_kw":300.03,"pot_kw":85.48,"cop_real":3.51,"q_demanda_kw":300,"t_camara":-8.50,"t_cond":28.06,"t_evap":-14.59},"status":{"estado":2,"falha":0,"rodando":true,"falha_bit":false,"alarme":false,"hz":45,"amp":147.15,"p_suc":1.39,"p_desc":10.10}}




JSON completo, íntegro e coerente recebido via MQTT, confirmando o pipeline funcionando ponta a ponta.

---

## Status ao final das Etapas 2 e 3

- ✅ Node-RED instalado e configurado como gateway OPC UA.
- ✅ Pacote `node-red-contrib-opcua` instalado.
- ✅ Conexão OPC UA estabelecida (Session Active) com o servidor do CODESYS Control Win V3 x64.
- ✅ Leitura individual de variáveis validada (`rHz`, `rTCamara`).
- ✅ Leitura em lote das 20 variáveis via Function "Build Requests" + "Collect Results".
- ✅ JSON final estruturado em `command`, `process`, `status`, igual ao padrão usado no cliente Python.
- ✅ Mosquitto instalado e rodando como serviço do Windows na porta 1883.
- ✅ Node MQTT out configurado no Node-RED, publicando no tópico `sala_maquinas/c1/telemetry`.
- ✅ Teste de ponta a ponta validado com `mosquitto_sub.exe` recebendo o JSON completo.

## Pendências para a próxima etapa (Fase 4 em diante)

- Ajustar o node Inject para repetição automática (ex.: a cada 2 segundos), substituindo o disparo manual.
- Validar estabilidade da publicação contínua por um período prolongado.
- Iniciar a Fase 5: consumo do tópico MQTT por um serviço FastAPI, com gravação em PostgreSQL/TimescaleDB.
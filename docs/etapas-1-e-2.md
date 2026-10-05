# Smart Refrigeration: o que construímos nas Fases 0, 1 e 2

Este documento explica, na ordem em que foi feito, tudo o que já está funcionando no CODESYS antes de passarmos para a Fase 3 (OPC UA e Python).

---

## 1. Objetivo do projeto

Montar uma **sala de máquinas de refrigeração virtual**, sem equipamento real, que consiga:

- simular compressores de amônia (R-717);
- expor os dados como se fosse um CLP de verdade;
- depois transmitir (OPC UA, MQTT), armazenar, calcular consumo, COP e custo, detectar anomalias e mostrar tudo num dashboard.

Arquitetura final:

```
CLP (CODESYS) ─ OPC UA ─► Python Gateway ─ MQTT ─► Backend FastAPI
                                                      ├─► PostgreSQL / TimescaleDB
                                                      └─► Analytics / ML
                                                              │
                                                          Dashboard
```

**Onde estamos:** a primeira caixa (o CLP com o processo virtual) está pronta. Tudo daqui em diante vai ler dados que saem dela.

**Por que começar pelo CLP:** assim você entende de onde vem cada número antes de escrever o Python que lê esses números.

---

## 2. Ambiente

### O que foi instalado e configurado

| Item | Valor |
|---|---|
| IDE | CODESYS 3.5.22.x (versão nova, em português) |
| CLP virtual | CODESYS Control Win V3 x64, versão 3.5.22.40 |
| Dispositivo | `WIN-BVPJ19640TA`, conectado pelo Gateway |

### O problema que enfrentamos no início

Tentamos usar o CODESYS **3.5.11**, mas o runtime instalado no PC era o **3.5.22.40**. Os sintomas foram:

- "No device is responding to the scan request";
- aviso de segurança no Control Win;
- **Adicionar usuário online** desabilitado.

**Causa:** o runtime novo exige comunicação criptografada (TLS) e login de usuário, e o IDE antigo não sabe fazer isso.

**Solução:** instalar um IDE na mesma versão do runtime, criar um projeto novo com o dispositivo **CODESYS Control Win V3 x64** na versão 3.5.22.40 e, na primeira conexão, criar o usuário administrador do dispositivo.

**Regra prática:** o IDE e o runtime precisam ter versões compatíveis.

---

## 3. Fase 0: planejamento e decisões de projeto

Antes de escrever código, definimos o processo. Estas decisões moldam tudo o que veio depois.

### 3.1 O compressor C1

Um compressor de amônia acionado por **inversor de frequência**, com:

- faixa de frequência de **25 a 60 Hz**;
- corrente do motor de **0 a 250 A**;
- pressões medidas em **bar manométrico**.

### 3.2 Estados de operação

```
PARADO ─► PARTIDA ─► RODANDO ─► PARANDO ─► PARADO
              │          │
              └──────────┴──► FALHA ─(reset)─► PARADO
```

| Estado | Número | Significado |
|---|---|---|
| PARADO | 0 | Motor desligado, aguardando comando |
| PARTIDA | 1 | Inversor subindo até 25 Hz (frequência mínima) |
| RODANDO | 2 | Operando na frequência pedida |
| PARANDO | 3 | Descendo a rampa até zero |
| FALHA | 4 | Parou por proteção; precisa de reset |

### 3.3 Falhas e intertravamentos

| Código | Falha | Condição | Limite |
|---|---|---|---|
| 1 | Emergência | botão de emergência aberto | imediato |
| 2 | Descarga alta | pressão de descarga | ≥ 13,5 bar (alarme em 12,5) |
| 3 | Sucção baixa | pressão de sucção, só em RODANDO | ≤ 0,8 bar por 3 s |
| 4 | Sobrecorrente | corrente do motor, só em RODANDO | ≥ 230 A por 5 s (alarme em 215 A) |
| 5 | Inversor | falha do inversor | imediato |
| 6 | Timeout de partida | não chegou aos 25 Hz | 30 s |

**Regras adicionais:**

- **Anti-ciclagem:** depois de parar, o compressor só aceita nova partida após **10 s**. Protege motores reais de partidas seguidas.
- **Reset condicionado:** só rearma se a causa da falha já desapareceu.
- **Prioridade da parada:** com `bDesliga` ativo, a partida é bloqueada.

> Aviso: isto é lógica de simulação para estudo. Não é função de segurança certificada. Numa planta real, o CLP e o hardware de segurança continuam responsáveis pelos intertravamentos.

### 3.4 Decisão sobre escala

O projeto prevê C1 a C8. Por isso:

- o compressor foi desenhado como **blocos reutilizáveis** (basta criar uma lista deles depois);
- as **pressões e temperaturas ficam na planta**, não no compressor, já que numa central os compressores compartilham os coletores de sucção e descarga.

---

## 4. Fase 1: o CLP do compressor C1

### 4.1 Estrutura de objetos no projeto

Todos ficam dentro de **Application**, na árvore do dispositivo:

```
Application
├─ E_EstadoComp        Enumeração: PARADO, PARTIDA, RODANDO, PARANDO, FALHA
├─ E_CodFalha          Enumeração: os 7 códigos de falha
├─ ST_CompCmd          Estrutura: comandos
├─ ST_CompSts          Estrutura: status
├─ ST_CompInj          Estrutura: injeção de falhas
├─ ST_CompProc         Estrutura: variáveis do processo (Fase 2)
├─ GVL_Param           Constantes (limites, tempos)
├─ GVL_C1              Variáveis globais do compressor C1
├─ GVL_Proc            Variáveis globais da planta (Fase 2)
├─ FUN_PsatNH3         Função: curva de saturação da amônia (Fase 2)
├─ FB_Ruido            Gerador de ruído
├─ FB_CompControle     Máquina de estados e proteções
├─ FB_CompSim          Simulação do inversor, motor e compressor
├─ FB_Planta           Simulação da planta (Fase 2)
├─ PLC_PRG             Programa principal
└─ Configuração de Tarefas → MainTask   (ciclo de 100 ms)
```

**Por que `E_...`, `ST_...`, `FB_...`, `GVL_...`:** é uma convenção de nomes. Quem lê o projeto sabe se é enumeração, estrutura, bloco de função ou lista de variáveis só pelo prefixo.

### 4.2 O que cada bloco faz

**`FB_Ruido`**: o ST padrão não tem gerador de números aleatórios, então usamos um gerador congruencial simples. Ele adiciona pequenas oscilações aos sensores, para os dados não ficarem perfeitos demais, como numa planta real.

**`FB_CompControle`**: é o "cérebro" do compressor. A cada ciclo de 100 ms ele:

1. detecta pulsos de comando (`bLiga`, `bReset`) pela borda de subida;
2. calcula os temporizadores (anti-ciclagem, timeout de partida, sobrecorrente, sucção baixa);
3. verifica as falhas em ordem de prioridade;
4. memoriza a falha (o estado vai para FALHA e fica travado até o reset);
5. executa a máquina de estados;
6. gera as saídas: habilitação do inversor, referência de frequência e alarme.

**`PLC_PRG`**: orquestra a ordem de execução a cada ciclo:

1. o controle lê os sensores (do ciclo anterior);
2. o compressor simulado recebe o comando;
3. a planta recebe o que o compressor entregou;
4. os resultados são copiados para as variáveis globais.

### 4.3 Como se comanda o compressor

Os comandos de partida são **por pulso**: o `bLiga` só reage quando muda de `FALSE` para `TRUE`. Se ficar em `TRUE`, nada acontece de novo. Por isso o procedimento é sempre: enviar `TRUE`, depois voltar para `FALSE`.

### 4.4 Como se escreve valores no CODESYS (pegadinha que travou o teste)

1. **Online → Login** e **Online → Iniciar** (F5).
2. Abra a **GVL_C1**.
3. Na coluna **Valor preparado**, dê duplo clique (BOOL alterna, REAL aceita digitar).
4. **Ctrl+F7** (**Online → Escrever valores**) envia ao CLP.

O valor preparado **some depois do envio**. É normal. Quem confirma que funcionou é a coluna **Valor**.

---

## 5. Fase 2: o processo físico virtual

Na Fase 1, as pressões e a corrente eram fórmulas simples e independentes. Na Fase 2 elas passaram a **resultar de uma física encadeada**. Isso importa porque, na Fase 7, o COP calculado a partir dos sensores poderá ser comparado com o COP verdadeiro do simulador.

### 5.1 A cadeia física

```
Demanda térmica ─► Câmara (Tcam) ─► Evaporação (Tevap) ─► Pressão de sucção
                                          │
                  Capacidade do compressor (Hz, Tevap, Tcond)
                                          │
                  Potência elétrica ─► Corrente (A)
                                          │
Ambiente + sujeira ─► Condensação (Tcond) ─► Pressão de descarga
```

### 5.2 Equações usadas

**Pressão de saturação da amônia** (equação de Antoine, resultado em bar absoluta):

```
log10(P[mmHg]) = 7,55466 − 1002,711 / (247,885 + T[°C])
P[bar] = P[mmHg] × 0,00133322
```

A pressão manométrica é `P absoluta − 1,01325`. Conferimos a curva contra valores conhecidos (por exemplo, cerca de 4,3 bar a 0 °C e 11,7 bar a 30 °C).

**Capacidade frigorífica do compressor:**

```
Q = 440 kW × (Hz/60) × (1 + 0,035 × (Tevap + 10)) × (1 − 0,012 × (Tcond − 35))
```

- proporcional à frequência;
- sobe cerca de 3,5% por grau de aumento na evaporação;
- cai cerca de 1,2% por grau de aumento na condensação.

**COP e potência elétrica:**

```
COP ideal  = 0,60 × Tevap[K] / (Tcond − Tevap)
Pot [kW]   = Q / COP ideal + 3 kW (atrito e auxiliares)
```

O COP real é uma fração (60%) do ciclo ideal de Carnot.

**Corrente do motor:**

```
I = Pot × 1000 / (√3 × 380 V × 0,88)
```

**Câmara (balanço de energia):**

```
dTcam/dt = (Demanda − Q do compressor) / Capacidade térmica
```

Se a demanda é maior que o que o compressor entrega, a câmara esquenta, e vice-versa.

**Evaporação e condensação:**

```
Tevap = Tcam − (2 + 6 × Q / 440)
Tcond = Tbulbo_úmido + 2 + 6 × (1 + 1,5 × sujeira) × (Calor rejeitado / 560)
Calor rejeitado = Q + 0,92 × Pot
```

Ambas se aproximam do valor alvo com uma constante de tempo (ficam "lentas", como uma planta real).

### 5.3 Modelos de falha

| Cenário | Como é modelado |
|---|---|
| Condensador sujo | `rSujeiraCond` aumenta a aproximação da condensação |
| Compressor desgastado | Entrega 82% da capacidade e consome 110% da potência (COP cai ~25%) |
| Baixa demanda | A câmara esfria demais e a sucção cai (falha 3) |
| Offsets de sensor | Soma um valor à leitura de pressão, sem mudar a física |

### 5.4 Blocos novos da Fase 2

- **`FUN_PsatNH3`**: calcula a pressão de saturação a partir da temperatura.
- **`FB_Planta`**: demanda térmica (manual ou senoidal automática), câmara, evaporação, condensação e pressões.
- **`FB_CompSim`** (reescrito): rampa do inversor, capacidade, potência e corrente.
- **`GVL_Proc`**: parâmetros de cenário e estado da planta.
- **`C1_Proc`** (em `GVL_C1`): capacidade, potência e COP verdadeiro.

---

## 6. Referência de tags

### Comandos (escrita), em `GVL_C1.C1_Cmd`

| Tag | Normal | Função |
|---|---|---|
| `bLiga` | FALSE | Pulso de partida (exige 10 s parado) |
| `bDesliga` | FALSE | Para o compressor; tem prioridade |
| `bReset` | FALSE | Pulso de rearme da falha |
| `bEmergenciaOK` | TRUE | FALSE = emergência acionada |
| `rHzSet` | 45 | Frequência pedida (25 a 60 Hz) |

### Injeção de falhas (escrita), em `GVL_C1.C1_Inj`

| Tag | Normal | Função |
|---|---|---|
| `rOffsetPDesc` | 0 | Soma à leitura de descarga (bar) |
| `rOffsetPSuc` | 0 | Soma à leitura de sucção (bar) |
| `bDesgaste` | FALSE | Compressor desgastado |
| `bFalhaInversor` | FALSE | Derruba o inversor |

### Cenário da planta (escrita), em `GVL_Proc`

| Tag | Normal | Função |
|---|---|---|
| `rDemandaKW` | 300 | Carga térmica manual (kW) |
| `bDemandaAuto` | FALSE | Demanda oscilando sozinha |
| `rDemandaMin` / `rDemandaMax` | 200 / 400 | Limites da oscilação (kW) |
| `rPeriodoS` | 600 | Duração do ciclo automático (s) |
| `rSujeiraCond` | 0 | Sujeira do condensador (0 a 1) |
| `rTbuAmb` | 22 | Bulbo úmido ambiente (°C) |

### Leituras (só observar)

| Tag | Mostra |
|---|---|
| `C1_Sts.eEstado` | 0 a 4 (estado) |
| `C1_Sts.eFalha` | 0 a 6 (código da falha) |
| `C1_Sts.bRodando`, `bFalha`, `bAlarme` | Sinalizações |
| `C1_Sts.rHz`, `rAmp` | Frequência (Hz) e corrente (A) |
| `C1_Sts.rPSuc`, `rPDesc` | Pressões (bar manométrico) |
| `C1_Proc.rQFrigKW` | Capacidade frigorífica (kW) |
| `C1_Proc.rPotKW` | Potência elétrica (kW) |
| `C1_Proc.rCOPReal` | COP verdadeiro (gabarito do simulador) |
| `GVL_Proc.rTCamara`, `rTEvap`, `rTCond` | Temperaturas (°C) |
| `GVL_Proc.rQDemandaKW` | Demanda em uso |

---

## 7. Roteiro de testes

A planta tem inércia: os valores levam alguns minutos para assentar. Os números abaixo vêm de uma simulação em Python do mesmo modelo. No CODESYS podem diferir um pouco por causa do ruído.

| # | O que mudar | O que esperar |
|---|---|---|
| 1 | `bLiga` TRUE e depois FALSE | Hz sobe a 25, depois a 45. Em cerca de 1 min: ~150 A, ~10,2 bar de descarga, COP entre 3,5 e 3,8 |
| 2 | `rDemandaKW` = 400 (e `rHzSet` = 60 para compensar) | Câmara e sucção sobem |
| 2b | `bDemandaAuto` = TRUE | Demanda oscila entre 200 e 400 kW |
| 3 | `rDemandaKW` = 100 | Sucção cai abaixo de 0,8 bar em 3 a 4 min → falha 3 |
| 4 | `rSujeiraCond` = 1.0 | Descarga perto de 12,5 bar (alarme) e COP ~3,0 |
| 4b | idem + `rHzSet` = 60 | Descarga passa de 13,5 bar → falha 2 |
| 5 | `bDesgaste` = TRUE a 45 Hz | COP cai de ~3,5 para ~3,0; corrente sobe de ~148 para ~170 A |
| 6 | `rHzSet` = 60 + `bDesgaste` + `rSujeiraCond` = 0.5 | Corrente passa de 230 A → falha 4 em ~5 s |
| 7 | `bEmergenciaOK` = FALSE | Falha 1 imediata |
| 8 | `bFalhaInversor` = TRUE | Falha 5 |
| 9 | `rOffsetPDesc` = 4.0 | Leitura passa de 14 bar → falha 2 |
| 10 | `rOffsetPSuc` = -1.5 (rodando) | Leitura abaixo de 0,8 bar por 3 s → falha 3 |

### Depois de cada falha

1. Volte o tag de teste ao valor normal.
2. Pulso em `bReset` (TRUE e depois FALSE). O `eEstado` deve voltar a 0.
3. Espere 10 s e dê o pulso em `bLiga`.

---

## 8. Problemas encontrados e como resolvemos

| Problema | Causa | Solução |
|---|---|---|
| "No device is responding to the scan request" | IDE 3.5.11 incompatível com runtime 3.5.22.40 | Instalar IDE na versão do runtime |
| Adicionar usuário online desabilitado | Recurso não existe no IDE antigo | Resolvido com o IDE novo |
| "Valor preparado" sumia | Comportamento normal após Ctrl+F7 | Conferir a coluna **Valor** |
| Compressor não religava | `bLiga` ainda em TRUE, menos de 10 s parado, ou falha não rearmada | Sequência: causa → reset → 10 s → pulso de `bLiga` |
| Teste de offset de descarga não disparava | Com a física nova, `3.0` leva a ~13,2 bar (só alarme) | Usar `4.0` |
| Teste de sobrecorrente antigo não disparava | A corrente agora vem da física | Usar 60 Hz + desgaste + sujeira 0.5, com limites 215 A/230 A |

---

## 9. Limitações e premissas (para ser honesto sobre o que é simulação)

- Os parâmetros (440 kW nominais, 60% de Carnot, coeficientes de capacidade) são **plausíveis para um compressor grande de amônia, mas não de um equipamento específico**.
- A **inércia da câmara está acelerada** para o laboratório; numa planta real seria bem mais lenta.
- Ainda **não há controle de capacidade**: se a demanda cai muito, o compressor não reduz sozinho e a sucção cai até a falha 3.
- A sucção baixa só é monitorada com o compressor em RODANDO.
- O `rCOPReal` **não existe numa planta real**. Serve como gabarito para validar o COP estimado na Fase 7.
- Há um único compressor ativo. A planta já está estruturada para somar vários.

---

## 10. Próximo passo: Fase 3 (OPC UA)

O que vai acontecer:

1. Criar a **Configuração de Símbolos** no CODESYS e marcar as variáveis de `GVL_C1` e `GVL_Proc` para expor.
2. Configurar o servidor OPC UA do runtime e o acesso (no runtime 3.5.22 ele vem com segurança ativa; usaremos o usuário que você criou).
3. Escrever o cliente em Python com `asyncua`: conectar, ler as variáveis, validar os dados e gerar logs.
4. Normalizar cada leitura num JSON com timestamp, no formato do roadmap:

```json
{
  "compressor_id": "C1",
  "frequency_hz": 45.0,
  "current_a": 150.2,
  "suction_pressure_bar": 1.5,
  "discharge_pressure_bar": 10.2,
  "timestamp": "2026-10-04T10:30:00Z"
}
```

Depois disso vem a Fase 4 (publicação no MQTT com Mosquitto).

**Antes de avançar, confirme:**

- [ ] O projeto compila sem erros (Compilar → Compilar, F11).
- [ ] A partida funciona e `rHz` chega a 45.
- [ ] Pelo menos os testes 1, 3, 4 e 6 passaram.
- [ ] O Control Win está rodando e o login com o usuário criado funciona.
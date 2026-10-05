# Smart Refrigeration: todo o código do CODESYS, comentado

Este arquivo reúne **cada objeto que criamos no CODESYS**, na versão final (Fases 1 e 2 juntas), com comentários explicando o que cada linha faz. Dá para copiar e colar direto no projeto.


---

## Índice

1. [Como usar este arquivo](#1-como-usar-este-arquivo)
2. [Mapa do projeto e ordem de criação](#2-mapa-do-projeto-e-ordem-de-criação)
3. [Tipos de dados (DUTs)](#3-tipos-de-dados-duts)
4. [Variáveis globais (GVLs)](#4-variáveis-globais-gvls)
5. [Função de saturação da amônia](#5-função-de-saturação-da-amônia)
6. [Blocos de função (FBs)](#6-blocos-de-função-fbs)
7. [Programa principal (PLC_PRG)](#7-programa-principal-plc_prg)
8. [Quem chama quem](#8-quem-chama-quem)
9. [Erros comuns de compilação](#9-erros-comuns-de-compilação)

---

## 1. Como usar este arquivo

### Onde criar cada objeto

Clique com o botão direito em **Application** e use **Adicionar Objeto**:

| Tipo de objeto | Caminho no menu |
|---|---|
| Enumeração | **Adicionar Objeto → DUT...** → tipo **Enumeração** |
| Estrutura | **Adicionar Objeto → DUT...** → tipo **Estrutura** |
| Lista de variáveis globais | **Adicionar Objeto → Lista de Variáveis Globais...** |
| Função | **Adicionar Objeto → POU...** → tipo **Função**, linguagem **ST**, tipo de retorno **REAL** |
| Bloco de função | **Adicionar Objeto → POU...** → tipo **Bloco de Função**, linguagem **ST** |

Os nomes em português podem variar um pouco entre versões. Se algum não bater, use o que for mais parecido ou o atalho do menu.

### Onde colar o código

- **DUT e GVL:** têm uma área só. Apague o que o CODESYS gerou e cole o bloco inteiro.
- **POU (função, bloco de função e programa):** têm **dois painéis**.
  - **Painel de cima (declaração):** da linha `FUNCTION_BLOCK...` até o último `END_VAR`.
  - **Painel de baixo (implementação):** o código que vem depois.

Nos blocos abaixo, eu separo os dois com os títulos **"Declaração"** e **"Implementação"**.

### Convenção de nomes usada

| Prefixo | Significado | Exemplo |
|---|---|---|
| `E_` | Enumeração | `E_EstadoComp` |
| `ST_` | Estrutura (struct) | `ST_CompCmd` |
| `GVL_` | Lista de variáveis globais | `GVL_C1` |
| `FUN_` | Função | `FUN_PsatNH3` |
| `FB_` | Bloco de função | `FB_CompControle` |
| `b` | BOOL (verdadeiro/falso) | `bLiga` |
| `r` | REAL (decimal) | `rHz` |
| `e` | Enumeração | `eEstado` |
| `c` | Constante | `cHzMax` |
| `fb` | Instância de bloco de função | `fbCtrl` |
| `ton` | Temporizador TON | `tonAntiCiclo` |
| `rt` | Detector de borda de subida | `rtLiga` |

### Ciclo de execução

O programa roda a cada **100 ms**. Configure em **Configuração de Tarefas → MainTask**, campo **Intervalo**: `T#100ms`. As rampas e as constantes de tempo do simulador assumem esse valor.

---

## 2. Mapa do projeto e ordem de criação

Crie nesta ordem, porque cada objeto depende dos anteriores:

```
Application
│
├─ 1.  E_EstadoComp        Enumeração dos estados
├─ 2.  E_CodFalha          Enumeração dos códigos de falha
├─ 3.  ST_CompCmd          Estrutura de comandos
├─ 4.  ST_CompSts          Estrutura de status
├─ 5.  ST_CompInj          Estrutura de injeção de falhas
├─ 6.  ST_CompProc         Estrutura do processo
│
├─ 7.  GVL_Param           Constantes (limites e tempos)
├─ 8.  GVL_C1              Variáveis do compressor C1
├─ 9.  GVL_Proc            Variáveis da planta
│
├─ 10. FUN_PsatNH3         Curva de saturação da amônia
├─ 11. FB_Ruido            Gerador de ruído
├─ 12. FB_CompControle     Máquina de estados e proteções
├─ 13. FB_CompSim          Simulação do compressor
├─ 14. FB_Planta           Simulação da planta
│
├─ 15. PLC_PRG             Programa principal (já existe, só edite)
└─ Configuração de Tarefas → MainTask (100 ms)
```

Depois de criar tudo: **Compilar → Compilar** (F11).

---

## 3. Tipos de dados (DUTs)

### 3.1 `E_EstadoComp`: estados do compressor

**Para que serve:** dá nomes aos estados em vez de usar números soltos. Em vez de `IF estado = 2`, o código lê `IF eEstado = E_EstadoComp.RODANDO`, que é muito mais claro.

**Atributos no topo:**

- `qualified_only`: obriga a escrever `E_EstadoComp.RODANDO` (nunca só `RODANDO`). Evita conflito de nomes.
- `strict`: impede misturar a enumeração com números por engano.

```iecst
{attribute 'qualified_only'}
{attribute 'strict'}
TYPE E_EstadoComp :
(
    PARADO  := 0,    // motor desligado, esperando comando
    PARTIDA := 1,    // inversor subindo até a frequência mínima
    RODANDO := 2,    // operando na frequência pedida
    PARANDO := 3,    // descendo a rampa até zero
    FALHA   := 4     // parou por proteção, precisa de reset
) UINT;              // armazenado como inteiro de 16 bits sem sinal
END_TYPE
```

### 3.2 `E_CodFalha`: códigos de falha

**Para que serve:** diz **qual** proteção atuou. Esse número será lido pelo Python na Fase 3 para gerar o alarme certo.

```iecst
{attribute 'qualified_only'}
{attribute 'strict'}
TYPE E_CodFalha :
(
    NENHUMA         := 0,    // sem falha
    EMERGENCIA      := 1,    // botão de emergência acionado
    PDESC_ALTA      := 2,    // pressão de descarga alta
    PSUC_BAIXA      := 3,    // pressão de sucção baixa
    SOBRECORRENTE   := 4,    // corrente do motor acima do limite
    INVERSOR        := 5,    // falha do inversor de frequência
    PARTIDA_TIMEOUT := 6     // não chegou à frequência mínima a tempo
) UINT;
END_TYPE
```

### 3.3 `ST_CompCmd`: comandos para o compressor

**Para que serve:** agrupa tudo que **você escreve** para comandar o compressor. Quem controla de fora (o CODESYS, depois o Python via OPC UA) mexe só nestas variáveis.

```iecst
TYPE ST_CompCmd :
STRUCT
    bLiga          : BOOL;              // pulso de partida (age na subida FALSE -> TRUE)
    bDesliga       : BOOL;              // pede a parada; tem prioridade sobre a partida
    bReset         : BOOL;              // pulso para rearmar uma falha
    bEmergenciaOK  : BOOL := TRUE;      // TRUE = emergência liberada; FALSE = acionada
    rHzSet         : REAL := 45.0;      // frequência desejada (Hz)
END_STRUCT
END_TYPE
```

**Detalhe importante:** `bEmergenciaOK` nasce em `TRUE`. É lógica de segurança "normalmente fechada": se o fio da emergência romper, o valor vira `FALSE` e o compressor para.

### 3.4 `ST_CompSts`: status do compressor

**Para que serve:** agrupa tudo que o compressor **informa** para fora. É o que o dashboard vai mostrar.

```iecst
TYPE ST_CompSts :
STRUCT
    eEstado  : E_EstadoComp;    // estado atual (0 a 4)
    eFalha   : E_CodFalha;      // código da falha ativa (0 = nenhuma)
    bRodando : BOOL;            // TRUE quando está em RODANDO
    bFalha   : BOOL;            // TRUE quando está em FALHA
    bAlarme  : BOOL;            // TRUE perto do limite (antes do trip) ou em falha
    rHz      : REAL;            // frequência real do inversor (Hz)
    rAmp     : REAL;            // corrente do motor (A)
    rPSuc    : REAL;            // pressão de sucção (bar manométrico)
    rPDesc   : REAL;            // pressão de descarga (bar manométrico)
END_STRUCT
END_TYPE
```

### 3.5 `ST_CompInj`: injeção de falhas

**Para que serve:** são os "botões de sabotagem" para testar o sistema. Numa planta real não existem. Aqui eles deixam você provocar problemas para ver se as proteções e o dashboard reagem.

```iecst
TYPE ST_CompInj :
STRUCT
    rOffsetPDesc   : REAL;    // soma bar à LEITURA da descarga (a física não muda)
    rOffsetPSuc    : REAL;    // soma bar à LEITURA da sucção
    bDesgaste      : BOOL;    // compressor desgastado: entrega menos, consome mais
    bFalhaInversor : BOOL;    // derruba o inversor
END_STRUCT
END_TYPE
```

### 3.6 `ST_CompProc`: variáveis do processo

**Para que serve:** guarda as grandezas calculadas pela física. O `rCOPReal` é o **gabarito** do simulador: o COP verdadeiro, que não existe numa planta real. Na Fase 7 você vai estimar o COP a partir de corrente e pressões e comparar com este.

```iecst
TYPE ST_CompProc :
STRUCT
    rQFrigKW : REAL;    // capacidade frigorífica entregue (kW)
    rPotKW   : REAL;    // potência elétrica consumida (kW)
    rCOPReal : REAL;    // COP verdadeiro = rQFrigKW / rPotKW
END_STRUCT
END_TYPE
```

---

## 4. Variáveis globais (GVLs)

### 4.1 `GVL_Param`: constantes

**Para que serve:** guarda todos os limites e tempos em um lugar só. Se quiser mudar um limite de proteção, muda aqui, sem procurar no meio do código.

`VAR_GLOBAL CONSTANT` significa que o valor não pode ser alterado durante a execução.

```iecst
VAR_GLOBAL CONSTANT
    // --- Faixa de frequência do inversor ---
    cHzMin           : REAL := 25.0;     // mínimo para operar (Hz)
    cHzMax           : REAL := 60.0;     // máximo (Hz)

    // --- Pressão de descarga (bar manométrico) ---
    cPDescAlarme     : REAL := 12.5;     // acende o alarme
    cPDescTrip       : REAL := 13.5;     // desarma o compressor

    // --- Pressão de sucção ---
    cPSucTrip        : REAL := 0.8;      // abaixo disso por 3 s, desarma

    // --- Corrente do motor (A) ---
    cAmpAlarme       : REAL := 215.0;    // acende o alarme
    cAmpTrip         : REAL := 230.0;    // acima disso por 5 s, desarma

    // --- Tempos ---
    cTempoAntiCiclo  : TIME := T#10S;    // tempo mínimo parado antes de religar
    cTimeoutPartida  : TIME := T#30S;    // tempo máximo para chegar em cHzMin
END_VAR
```

### 4.2 `GVL_C1`: variáveis do compressor C1

**Para que serve:** são as variáveis "públicas" do compressor 1. Serão estas que o OPC UA vai expor na Fase 3. Cada uma é uma estrutura inteira.

```iecst
VAR_GLOBAL
    C1_Cmd  : ST_CompCmd;     // comandos (você escreve)
    C1_Sts  : ST_CompSts;     // status (você lê)
    C1_Inj  : ST_CompInj;     // injeção de falhas (você escreve)
    C1_Proc : ST_CompProc;    // processo: capacidade, potência, COP (você lê)
END_VAR
```

### 4.3 `GVL_Proc`: variáveis da planta

**Para que serve:** guarda o ambiente, a demanda e o estado da planta. É da **planta** (e não do compressor) porque, numa central, os compressores compartilham o evaporador, o condensador e as pressões. Quando tivermos C2 a C8, todos usam esta mesma GVL.

```iecst
VAR_GLOBAL
    // ---------- Cenários (você escreve) ----------
    rTbuAmb      : REAL := 22.0;     // temperatura de bulbo úmido do ar (°C)
    rDemandaKW   : REAL := 300.0;    // demanda térmica manual (kW)
    bDemandaAuto : BOOL := FALSE;    // TRUE: demanda oscila sozinha (senoide)
    rDemandaMin  : REAL := 200.0;    // mínimo da oscilação automática (kW)
    rDemandaMax  : REAL := 400.0;    // máximo da oscilação automática (kW)
    rPeriodoS    : REAL := 600.0;    // duração de um ciclo automático (s)
    rSujeiraCond : REAL := 0.0;      // sujeira do condensador: 0 = limpo, 1 = muito sujo

    // ---------- Estado da planta (você lê) ----------
    rTCamara     : REAL := -4.0;     // temperatura da câmara (°C)
    rTEvap       : REAL := -6.0;     // temperatura de evaporação (°C)
    rTCond       : REAL := 24.0;     // temperatura de condensação (°C)
    rQDemandaKW  : REAL := 300.0;    // demanda térmica em uso agora (kW)
END_VAR
```

---

## 5. Função de saturação da amônia

### `FUN_PsatNH3`

**Para que serve:** converte temperatura em pressão para a amônia (R-717) saturada. No ciclo de refrigeração, **pressão e temperatura de saturação andam juntas**. Se você sabe a temperatura de evaporação, sabe a pressão de sucção.

**Como funciona:** equação de Antoine, que é uma fórmula empírica para a pressão de vapor. Reproduz bem os valores tabelados (cerca de 4,3 bar a 0 °C, 11,7 bar a 30 °C).

**Detalhe:** o resultado é em **bar absoluta**. Quem usa a função subtrai a pressão atmosférica (1,01325) para obter o manométrico.

#### Declaração

```iecst
FUNCTION FUN_PsatNH3 : REAL
VAR_INPUT
    rTC : REAL;          // temperatura de saturação (°C)
END_VAR
VAR
    rT : REAL;           // temperatura limitada à faixa válida da fórmula
END_VAR
```

#### Implementação

```iecst
// Limita a temperatura à faixa onde a fórmula é válida (evita divisão por zero e valores absurdos)
rT := LIMIT(-60.0, rTC, 60.0);

// Antoine: log10(P[mmHg]) = A - B / (C + T)
// O CODESYS só tem EXP (base e), então: 10^x = EXP(x * ln(10)), e ln(10) = 2.302585
// Multiplicar por 0.00133322 converte mmHg para bar.
FUN_PsatNH3 := EXP(2.302585 * (7.55466 - 1002.711 / (247.885 + rT))) * 0.00133322;
```

---

## 6. Blocos de função (FBs)

### 6.1 `FB_Ruido`: gerador de ruído

**Para que serve:** adiciona pequenas oscilações aleatórias aos sensores. Dado perfeitamente liso seria irreal e esconderia problemas do tratamento de dados (filtro, validação) que vamos precisar mais adiante.

**Como funciona:** o ST padrão não tem função aleatória, então usamos um **gerador congruencial linear**: a cada ciclo, o valor `nSeed` é multiplicado e somado por constantes. O resultado parece aleatório, mas é uma sequência fixa.

#### Declaração

```iecst
FUNCTION_BLOCK FB_Ruido
VAR_INPUT
    rAmplitude : REAL := 1.0;    // o ruído varia entre -rAmplitude e +rAmplitude
END_VAR
VAR_OUTPUT
    rValor : REAL;               // valor do ruído neste ciclo
END_VAR
VAR
    nSeed : UDINT := 12345;      // estado interno do gerador (preserva entre ciclos)
END_VAR
```

#### Implementação

```iecst
// Próximo número da sequência. O estouro de 32 bits é intencional (faz parte do algoritmo).
nSeed := nSeed * 1664525 + 1013904223;

// Pega 15 bits do meio do número (os bits baixos são piores em aleatoriedade),
// transforma em REAL de 0 a ~2, subtrai 1 para ficar de -1 a +1 e escala pela amplitude.
rValor := ((UDINT_TO_REAL((nSeed / 65536) MOD 32768) / 16384.0) - 1.0) * rAmplitude;
```

---

### 6.2 `FB_CompControle`: o cérebro do compressor

**Para que serve:** decide **o que o compressor faz**. Recebe comandos e leituras de sensores e entrega: o estado, o código de falha, a frequência de referência para o inversor e o alarme.

**Estrutura em 4 etapas, a cada ciclo:**

1. **Detecção:** olha todos os sensores e descobre se há alguma falha.
2. **Memorização:** se houve falha, trava o estado em FALHA (só o reset solta).
3. **Máquina de estados:** decide a transição conforme o estado atual e os comandos.
4. **Saídas auxiliares:** habilitação do inversor e alarme.

#### Declaração

```iecst
FUNCTION_BLOCK FB_CompControle
VAR_INPUT
    stCmd       : ST_CompCmd;    // comandos do operador
    rPSuc       : REAL;          // pressão de sucção medida (bar)
    rPDesc      : REAL;          // pressão de descarga medida (bar)
    rAmp        : REAL;          // corrente medida (A)
    rHzAtual    : REAL;          // frequência atual do inversor (Hz)
    bInversorOK : BOOL;          // TRUE = inversor saudável
END_VAR
VAR_OUTPUT
    eEstado           : E_EstadoComp := E_EstadoComp.PARADO;   // estado atual
    eFalha            : E_CodFalha := E_CodFalha.NENHUMA;      // falha memorizada
    rHzRef            : REAL;      // frequência que o controle pede ao inversor
    bHabilitaInversor : BOOL;      // TRUE = inversor liberado para girar
    bAlarme           : BOOL;      // TRUE = perto do limite, ou em falha
END_VAR
VAR
    rtLiga            : R_TRIG;    // detecta a subida de bLiga (FALSE -> TRUE)
    rtReset           : R_TRIG;    // detecta a subida de bReset
    tonAntiCiclo      : TON;       // conta o tempo parado (anti-ciclagem)
    tonTimeoutPartida : TON;       // conta o tempo em PARTIDA
    tonSobrecorrente  : TON;       // conta o tempo com corrente acima do trip
    tonPSucBaixa      : TON;       // conta o tempo com sucção abaixo do trip
    eFalhaDet         : E_CodFalha;   // falha detectada neste ciclo (ainda não memorizada)
END_VAR
```

#### Implementação

```iecst
// ===== 0) Detecção de bordas dos comandos por pulso =====
// R_TRIG.Q fica TRUE por UM único ciclo, quando a entrada sobe de FALSE para TRUE.
// É por isso que bLiga e bReset precisam voltar a FALSE antes de um novo pulso.
rtLiga(CLK := stCmd.bLiga);
rtReset(CLK := stCmd.bReset);

// ===== Temporizadores =====
// TON: a saída .Q vira TRUE depois que a entrada IN ficou TRUE durante o tempo PT.
// Se IN cair antes disso, o temporizador zera.

// Anti-ciclagem: só conta enquanto está PARADO. Q = TRUE significa "já esperou o suficiente".
tonAntiCiclo(IN := (eEstado = E_EstadoComp.PARADO),
             PT := GVL_Param.cTempoAntiCiclo);

// Timeout de partida: conta enquanto está em PARTIDA. Q = TRUE significa "demorou demais".
tonTimeoutPartida(IN := (eEstado = E_EstadoComp.PARTIDA),
                  PT := GVL_Param.cTimeoutPartida);

// Sobrecorrente: só vale em RODANDO e exige 5 s seguidos acima do limite (evita disparo por pico).
tonSobrecorrente(IN := (eEstado = E_EstadoComp.RODANDO) AND (rAmp >= GVL_Param.cAmpTrip),
                 PT := T#5S);

// Sucção baixa: só vale em RODANDO (na partida a pressão é naturalmente instável) e exige 3 s seguidos.
tonPSucBaixa(IN := (eEstado = E_EstadoComp.RODANDO) AND (rPSuc <= GVL_Param.cPSucTrip),
             PT := T#3S);

// ===== 1) Detecção de falha, em ordem de prioridade =====
// A cadeia IF/ELSIF para na primeira condição verdadeira: a mais importante vence.
IF NOT stCmd.bEmergenciaOK THEN
    eFalhaDet := E_CodFalha.EMERGENCIA;
ELSIF NOT bInversorOK THEN
    eFalhaDet := E_CodFalha.INVERSOR;
ELSIF rPDesc >= GVL_Param.cPDescTrip THEN
    eFalhaDet := E_CodFalha.PDESC_ALTA;
ELSIF tonPSucBaixa.Q THEN
    eFalhaDet := E_CodFalha.PSUC_BAIXA;
ELSIF tonSobrecorrente.Q THEN
    eFalhaDet := E_CodFalha.SOBRECORRENTE;
ELSIF tonTimeoutPartida.Q THEN
    eFalhaDet := E_CodFalha.PARTIDA_TIMEOUT;
ELSE
    eFalhaDet := E_CodFalha.NENHUMA;
END_IF

// ===== 2) Memorização da falha =====
// Uma vez detectada, a falha fica TRAVADA (eFalha e estado FALHA), mesmo que a causa suma.
// Só o reset (na máquina de estados) solta. É o comportamento de "falha memorizada" de CLPs reais.
IF (eFalhaDet <> E_CodFalha.NENHUMA) AND (eEstado <> E_EstadoComp.FALHA) THEN
    eFalha  := eFalhaDet;
    eEstado := E_EstadoComp.FALHA;
END_IF

// ===== 3) Máquina de estados =====
CASE eEstado OF

    // --- PARADO: motor desligado, esperando comando ---
    E_EstadoComp.PARADO:
        rHzRef := 0.0;
        // Só parte se: houve pulso de bLiga, já passou o tempo anti-ciclagem e bDesliga não está ativo.
        // ATENÇÃO: o pulso dura 1 ciclo. Se o tempo anti-ciclagem não passou, o comando é perdido.
        IF rtLiga.Q AND tonAntiCiclo.Q AND NOT stCmd.bDesliga THEN
            eEstado := E_EstadoComp.PARTIDA;
        END_IF

    // --- PARTIDA: inversor sobe até a frequência mínima ---
    E_EstadoComp.PARTIDA:
        rHzRef := GVL_Param.cHzMin;
        IF stCmd.bDesliga THEN
            eEstado := E_EstadoComp.PARANDO;
        // Considera que chegou quando está a menos de 0,5 Hz do mínimo
        ELSIF rHzAtual >= (GVL_Param.cHzMin - 0.5) THEN
            eEstado := E_EstadoComp.RODANDO;
        END_IF

    // --- RODANDO: segue a frequência pedida pelo operador ---
    E_EstadoComp.RODANDO:
        // LIMIT(mín, valor, máx) garante que a referência fique dentro de 25 a 60 Hz
        rHzRef := LIMIT(GVL_Param.cHzMin, stCmd.rHzSet, GVL_Param.cHzMax);
        IF stCmd.bDesliga THEN
            eEstado := E_EstadoComp.PARANDO;
        END_IF

    // --- PARANDO: desce a rampa até quase zero ---
    E_EstadoComp.PARANDO:
        rHzRef := 0.0;
        IF rHzAtual < 1.0 THEN
            eEstado := E_EstadoComp.PARADO;
        END_IF

    // --- FALHA: parado e travado até o reset ---
    E_EstadoComp.FALHA:
        rHzRef := 0.0;
        // O reset só funciona se a causa já desapareceu (eFalhaDet voltou a NENHUMA)
        IF rtReset.Q AND (eFalhaDet = E_CodFalha.NENHUMA) THEN
            eFalha  := E_CodFalha.NENHUMA;
            eEstado := E_EstadoComp.PARADO;
        END_IF

END_CASE

// ===== 4) Saídas auxiliares =====
// O inversor só é liberado nos estados em que o motor deve girar (ou desacelerar)
bHabilitaInversor := (eEstado = E_EstadoComp.PARTIDA)
                  OR (eEstado = E_EstadoComp.RODANDO)
                  OR (eEstado = E_EstadoComp.PARANDO);

// Alarme: pré-aviso antes do trip, ou qualquer falha ativa
bAlarme := (rPDesc >= GVL_Param.cPDescAlarme)
        OR (rAmp   >= GVL_Param.cAmpAlarme)
        OR (eEstado = E_EstadoComp.FALHA);
```

---

### 6.3 `FB_CompSim`: o compressor simulado (inversor, motor e compressor)

**Para que serve:** faz o papel do equipamento real. Recebe o comando do controle e as condições da planta (temperaturas de evaporação e condensação) e devolve o que o equipamento produziria: frequência, corrente, capacidade frigorífica, potência e COP.

**Estrutura:**

1. **Rampa do inversor:** o Hz não salta, ele sobe e desce em rampa.
2. **Capacidade frigorífica:** depende do Hz e das temperaturas.
3. **Potência elétrica:** capacidade dividida pelo COP.
4. **Corrente:** calculada a partir da potência.

#### Declaração

```iecst
FUNCTION_BLOCK FB_CompSim
VAR_INPUT
    bHabilita : BOOL;         // TRUE = o inversor pode girar
    rHzRef    : REAL;         // frequência pedida pelo controle (Hz)
    rTEvap    : REAL;         // temperatura de evaporação, vinda da planta (°C)
    rTCond    : REAL;         // temperatura de condensação, vinda da planta (°C)
    stInj     : ST_CompInj;   // falhas injetadas (desgaste, inversor)
END_VAR
VAR_OUTPUT
    rHz         : REAL;            // frequência real do inversor (Hz)
    rAmp        : REAL;            // corrente do motor (A)
    rQFrigKW    : REAL;            // capacidade frigorífica entregue (kW)
    rPotKW      : REAL;            // potência elétrica consumida (kW)
    rCOPReal    : REAL;            // COP verdadeiro (gabarito do simulador)
    bInversorOK : BOOL := TRUE;    // TRUE = inversor saudável
END_VAR
VAR
    fbRuAmp   : FB_Ruido;    // ruído da medição de corrente
    rAlvoHz   : REAL;        // frequência para a qual a rampa está indo
    rFatEvap  : REAL;        // fator de capacidade pela temperatura de evaporação
    rFatCond  : REAL;        // fator de capacidade pela temperatura de condensação
    rCOPIdeal : REAL;        // COP do equipamento sem desgaste
    rQ        : REAL;        // capacidade calculada neste ciclo (kW)
    rP        : REAL;        // potência calculada neste ciclo (kW)
END_VAR
VAR CONSTANT
    cQNom       : REAL := 440.0;   // capacidade nominal a 60 Hz, Tevap -10 °C e Tcond 35 °C (kW)
    cEficCarnot : REAL := 0.60;    // o COP real é 60% do COP ideal de Carnot
    cPotAux     : REAL := 3.0;     // potência de atrito e auxiliares (kW)
    cTensao     : REAL := 380.0;   // tensão da rede (V)
    cCosPhi     : REAL := 0.88;    // fator de potência do motor
END_VAR
```

#### Implementação

```iecst
// O inversor está OK a menos que a falha esteja sendo injetada
bInversorOK := NOT stInj.bFalhaInversor;

// ===== 1) Rampa do inversor (ciclo de 100 ms) =====
// Se está habilitado e saudável, persegue a referência; senão, vai para zero.
IF bHabilita AND bInversorOK THEN
    rAlvoHz := rHzRef;
ELSE
    rAlvoHz := 0.0;
END_IF

// Sobe 0,5 Hz por ciclo (= 5 Hz/s) e desce 1,0 Hz por ciclo (= 10 Hz/s).
// MIN/MAX evitam passar do alvo.
IF rHz < rAlvoHz THEN
    rHz := MIN(rHz + 0.5, rAlvoHz);
ELSIF rHz > rAlvoHz THEN
    rHz := MAX(rHz - 1.0, rAlvoHz);
END_IF

// Atualiza o ruído da medição de corrente (±2 A)
fbRuAmp(rAmplitude := 2.0);

IF rHz > 1.0 THEN
    // ===== 2) Capacidade frigorífica =====
    // Sobe cerca de 3,5% por grau a mais na evaporação (sucção mais "fácil" de bombear)
    rFatEvap := MAX(0.1, 1.0 + 0.035 * (rTEvap + 10.0));
    // Cai cerca de 1,2% por grau a mais na condensação (descarga mais "difícil")
    rFatCond := MAX(0.1, 1.0 - 0.012 * (rTCond - 35.0));
    // Capacidade = nominal x (fração da frequência) x fatores de temperatura
    rQ := cQNom * (rHz / 60.0) * rFatEvap * rFatCond;

    // ===== 3) Potência elétrica =====
    // COP de Carnot = Tevap[K] / (Tcond - Tevap). O equipamento real fica em 60% disso.
    // MAX evita divisão por valores muito pequenos.
    rCOPIdeal := cEficCarnot * (rTEvap + 273.15) / MAX(rTCond - rTEvap, 5.0);
    // Potência = capacidade / COP + perdas fixas
    rP := rQ / MAX(rCOPIdeal, 0.5) + cPotAux;

    // ===== Compressor desgastado =====
    // Entrega 18% menos frio e consome 10% mais potência: o COP cai cerca de 25%.
    IF stInj.bDesgaste THEN
        rQ := rQ * 0.82;
        rP := rP * 1.10;
    END_IF

    rQFrigKW := rQ;
    rPotKW   := rP;
    rCOPReal := rQ / rP;   // rP é sempre maior que zero (tem os 3 kW de auxiliares)

    // ===== 4) Corrente do motor =====
    // Potência trifásica: P = raiz(3) x V x I x cos(phi)  ->  I = P / (raiz(3) x V x cos(phi))
    // O x1000 converte kW para W. LIMIT mantém na faixa 0 a 250 A do medidor.
    rAmp := LIMIT(0.0, rP * 1000.0 / (1.732 * cTensao * cCosPhi) + fbRuAmp.rValor, 250.0);
ELSE
    // Parado: tudo zero
    rQFrigKW := 0.0;
    rPotKW   := 0.0;
    rCOPReal := 0.0;
    rAmp     := 0.0;
END_IF
```

---

### 6.4 `FB_Planta`: a planta (câmara, evaporação, condensação e pressões)

**Para que serve:** simula tudo que é **compartilhado**: a carga térmica da câmara, a evaporação, a condensação e as pressões. Os compressores entregam frio e consomem potência, e a planta devolve as temperaturas e pressões que eles enxergam.

**Estrutura:**

1. **Demanda térmica:** manual ou automática (senoide).
2. **Câmara:** balanço de energia (demanda menos o que o compressor entrega).
3. **Evaporação:** temperatura da câmara menos uma diferença que cresce com a carga.
4. **Condensação:** ambiente mais uma aproximação que cresce com o calor rejeitado e a sujeira.
5. **Pressões:** saturação da amônia nas duas temperaturas, mais offset de sensor e ruído.

#### Declaração

```iecst
FUNCTION_BLOCK FB_Planta
VAR_INPUT
    rQCompTotKW  : REAL;    // capacidade frigorífica total entregue pelos compressores (kW)
    rPelTotKW    : REAL;    // potência elétrica total dos compressores (kW)
    rOffsetPSuc  : REAL;    // offset do sensor de sucção (falha injetada)
    rOffsetPDesc : REAL;    // offset do sensor de descarga (falha injetada)
END_VAR
VAR_OUTPUT
    rPSuc  : REAL := 2.4;   // pressão de sucção (bar manométrico)
    rPDesc : REAL := 8.8;   // pressão de descarga (bar manométrico)
END_VAR
VAR
    fbRuSuc    : FB_Ruido;  // ruído do sensor de sucção
    fbRuDesc   : FB_Ruido;  // ruído do sensor de descarga
    rFase      : REAL;      // fase da senoide da demanda automática (0 a 2*pi)
    rQRejKW    : REAL;      // calor rejeitado no condensador (kW)
    rTEvapAlvo : REAL;      // temperatura de evaporação para a qual se tende (°C)
    rTCondAlvo : REAL;      // temperatura de condensação para a qual se tende (°C)
END_VAR
VAR CONSTANT
    cDt      : REAL := 0.1;      // período do ciclo (s)
    cCapTerm : REAL := 3000.0;   // inércia térmica da câmara (kJ/K); acelerada para laboratório
    cQNom    : REAL := 440.0;    // capacidade nominal de um compressor (kW)
    cQRejNom : REAL := 560.0;    // calor rejeitado nominal (kW)
    cPatm    : REAL := 1.01325;  // pressão atmosférica (bar)
END_VAR
```

#### Implementação

```iecst
// ===== 1) Demanda térmica: manual ou ciclo senoidal automático =====
IF GVL_Proc.bDemandaAuto THEN
    // Avança a fase da senoide. 6.2832 = 2*pi (uma volta completa).
    // A cada ciclo avança (2*pi * 0.1 s / período).
    rFase := rFase + 6.2832 * cDt / MAX(GVL_Proc.rPeriodoS, 1.0);
    IF rFase >= 6.2832 THEN
        rFase := rFase - 6.2832;    // fecha a volta e recomeça
    END_IF
    // Senoide centrada na média entre mínimo e máximo, com amplitude de meia diferença
    GVL_Proc.rQDemandaKW := (GVL_Proc.rDemandaMax + GVL_Proc.rDemandaMin) / 2.0
                          + (GVL_Proc.rDemandaMax - GVL_Proc.rDemandaMin) / 2.0 * SIN(rFase);
ELSE
    GVL_Proc.rQDemandaKW := GVL_Proc.rDemandaKW;
END_IF

// ===== 2) Câmara: balanço de energia =====
// A câmara ganha calor da demanda e perde pelo que o compressor entrega.
// dT = (calor que entra - calor que sai) / capacidade térmica x tempo
// LIMIT mantém a temperatura numa faixa física (-30 a +10 °C).
GVL_Proc.rTCamara := LIMIT(-30.0,
    GVL_Proc.rTCamara + (GVL_Proc.rQDemandaKW - rQCompTotKW) / cCapTerm * cDt,
    10.0);

// ===== 3) Evaporação =====
// O refrigerante evapora mais frio que a câmara. Essa diferença cresce com a carga
// (de 2 K com o compressor parado até 8 K na carga nominal).
rTEvapAlvo := GVL_Proc.rTCamara - (2.0 + 6.0 * rQCompTotKW / cQNom);
// Aproxima 2% por ciclo do alvo: dá a "lentidão" de um sistema real
GVL_Proc.rTEvap := GVL_Proc.rTEvap + 0.02 * (rTEvapAlvo - GVL_Proc.rTEvap);

// ===== 4) Condensação =====
// Calor rejeitado = frio entregue + calor do trabalho do compressor (92% da potência elétrica)
rQRejKW := rQCompTotKW + 0.92 * rPelTotKW;
// Temperatura de condensação = ambiente + 2 K mínimos + aproximação.
// A aproximação cresce com o calor rejeitado e com a sujeira (até 2,5x com sujeira 1.0).
rTCondAlvo := GVL_Proc.rTbuAmb + 2.0
            + 6.0 * (1.0 + 1.5 * GVL_Proc.rSujeiraCond) * (rQRejKW / cQRejNom);
GVL_Proc.rTCond := GVL_Proc.rTCond + 0.02 * (rTCondAlvo - GVL_Proc.rTCond);

// ===== 5) Pressões manométricas =====
// Atualiza o ruído dos sensores
fbRuSuc(rAmplitude := 0.05);
fbRuDesc(rAmplitude := 0.08);
// Pressão = saturação (absoluta) - atmosfera + offset injetado + ruído
rPSuc  := FUN_PsatNH3(GVL_Proc.rTEvap) - cPatm + rOffsetPSuc  + fbRuSuc.rValor  * 0.1;
rPDesc := FUN_PsatNH3(GVL_Proc.rTCond) - cPatm + rOffsetPDesc + fbRuDesc.rValor * 0.1;
```

---

## 7. Programa principal (`PLC_PRG`)

**Para que serve:** é o programa que a tarefa executa a cada 100 ms. Ele só **orquestra**: chama os blocos na ordem certa e copia os resultados para as variáveis globais.

**A ordem importa:**

1. O **controle** decide com base nos sensores do ciclo anterior.
2. O **compressor simulado** executa o comando.
3. A **planta** recebe o que o compressor entregou e atualiza temperaturas e pressões.
4. Os resultados são **publicados** nas GVLs.

#### Declaração

```iecst
PROGRAM PLC_PRG
VAR
    fbCtrl   : FB_CompControle;    // controle e proteções do C1
    fbSim    : FB_CompSim;         // compressor simulado do C1
    fbPlanta : FB_Planta;          // planta compartilhada
END_VAR
```

#### Implementação

```iecst
// ===== 1) Controle: lê os sensores (valores do ciclo anterior) e decide =====
fbCtrl(stCmd       := GVL_C1.C1_Cmd,
       rPSuc       := fbPlanta.rPSuc,
       rPDesc      := fbPlanta.rPDesc,
       rAmp        := fbSim.rAmp,
       rHzAtual    := fbSim.rHz,
       bInversorOK := fbSim.bInversorOK);

// ===== 2) Compressor simulado: recebe o comando e as condições da planta =====
fbSim(bHabilita := fbCtrl.bHabilitaInversor,
      rHzRef    := fbCtrl.rHzRef,
      rTEvap    := GVL_Proc.rTEvap,
      rTCond    := GVL_Proc.rTCond,
      stInj     := GVL_C1.C1_Inj);

// ===== 3) Planta: recebe o que os compressores entregam e consomem =====
// Com mais compressores (C2 a C8), aqui entrariam as SOMAS das capacidades e potências.
fbPlanta(rQCompTotKW  := fbSim.rQFrigKW,
         rPelTotKW    := fbSim.rPotKW,
         rOffsetPSuc  := GVL_C1.C1_Inj.rOffsetPSuc,
         rOffsetPDesc := GVL_C1.C1_Inj.rOffsetPDesc);

// ===== 4) Publica o status nas variáveis globais (é isso que o OPC UA vai expor) =====
GVL_C1.C1_Sts.eEstado  := fbCtrl.eEstado;
GVL_C1.C1_Sts.eFalha   := fbCtrl.eFalha;
GVL_C1.C1_Sts.bRodando := fbCtrl.eEstado = E_EstadoComp.RODANDO;
GVL_C1.C1_Sts.bFalha   := fbCtrl.eEstado = E_EstadoComp.FALHA;
GVL_C1.C1_Sts.bAlarme  := fbCtrl.bAlarme;
GVL_C1.C1_Sts.rHz      := fbSim.rHz;
GVL_C1.C1_Sts.rAmp     := fbSim.rAmp;
GVL_C1.C1_Sts.rPSuc    := fbPlanta.rPSuc;
GVL_C1.C1_Sts.rPDesc   := fbPlanta.rPDesc;

GVL_C1.C1_Proc.rQFrigKW := fbSim.rQFrigKW;
GVL_C1.C1_Proc.rPotKW   := fbSim.rPotKW;
GVL_C1.C1_Proc.rCOPReal := fbSim.rCOPReal;
```

---

## 8. Quem chama quem

```
MainTask (a cada 100 ms)
   │
   └─ PLC_PRG
        ├─ fbCtrl   : FB_CompControle   usa  GVL_Param, E_EstadoComp, E_CodFalha, ST_CompCmd
        ├─ fbSim    : FB_CompSim        usa  FB_Ruido, ST_CompInj
        │                                    └─ recebe Tevap/Tcond de GVL_Proc
        ├─ fbPlanta : FB_Planta         usa  FB_Ruido, FUN_PsatNH3, GVL_Proc
        │
        └─ publica em  GVL_C1 (C1_Sts, C1_Proc)
```

**Fluxo dos dados em um ciclo:**

```
Sensores (ciclo anterior) ─► FB_CompControle ─► Hz de referência
                                                      │
                                                      ▼
Tevap / Tcond (planta) ────────────────────────► FB_CompSim ─► Hz, A, kW, COP, Q
                                                      │
                                                      ▼
                                                 FB_Planta ─► Tcam, Tevap, Tcond, pressões
                                                      │
                                                      └─► volta para os sensores do próximo ciclo
```

---

## 9. Erros comuns de compilação

| Mensagem ou sintoma | Causa provável | Solução |
|---|---|---|
| Identificador não definido (`E_EstadoComp` ou `ST_CompCmd`) | Objeto ainda não criado, ou nome digitado diferente | Confira o nome do objeto na árvore (maiúsculas e minúsculas contam) |
| Identificador não definido (`GVL_Param.cHzMin`) | A GVL não foi criada, ou o nome está diferente | Crie a GVL com o nome exato |
| Erro em `RODANDO` sem prefixo | Falta o `E_EstadoComp.` na frente (por causa do `qualified_only`) | Escreva `E_EstadoComp.RODANDO` |
| Tipos incompatíveis na atribuição de enumeração | Atribuiu um número a uma enumeração (por causa do `strict`) | Use sempre o nome qualificado, nunca o número |
| `R_TRIG` ou `TON` não definido | Biblioteca Standard ausente | Em **Gerenciador de Bibliotecas**, confira se a `Standard` está incluída |
| Variável declarada duas vezes | Colou a declaração do bloco **dentro** do painel de implementação (ou vice-versa) | Separe: declaração em cima, implementação embaixo |
| `FB_CompSim` com erro em `rPSuc` ou `rPDesc` | Sobrou código da versão antiga (Fase 1) | Apague **todo** o conteúdo do `FB_CompSim` e cole a versão da seção 6.3 |
| Erro de nome em `fbPlanta.rPSuc` | `FB_Planta` não existe ou o nome da saída está diferente | Confira a declaração do `FB_Planta` |

**Se continuar com erro:** copie a mensagem exata da janela de **Mensagens** (embaixo) e o nome do objeto onde aparece, que dá para achar o problema rápido.

# Smart Refrigeration Energy Management

Sala de máquinas de refrigeração **virtual**, construída do CLP até o dashboard, para estudar monitoramento de energia, eficiência (COP), custo e detecção de anomalias em sistemas industriais de amônia (R-717), **sem precisar de nenhum equipamento real**.

O processo é simulado dentro de um CLP virtual (CODESYS). A partir dele, os dados seguem por uma pipeline industrial completa: OPC UA, MQTT, banco de séries temporais, API, dashboard e, por fim, Machine Learning.

> **Status:** em desenvolvimento. As Fases 0, 1 e 2 (CLP e processo físico virtual) estão implementadas. A Fase 3 (OPC UA e Python) é a próxima.

---

## Sumário

- [Motivação](#motivação)
- [Arquitetura](#arquitetura)
- [Status do projeto](#status-do-projeto)
- [Tecnologias](#tecnologias)
- [O que já está implementado](#o-que-já-está-implementado)
- [Como executar](#como-executar)
- [Estrutura do repositório](#estrutura-do-repositório)
- [Premissas e limitações](#premissas-e-limitações)
- [Roadmap](#roadmap)
- [Autor](#autor)

---

## Motivação

Sistemas de refrigeração industrial estão entre os maiores consumidores de energia de uma fábrica. Medir a eficiência (COP), traduzir o consumo em reais e detectar cedo uma degradação (condensador sujo, compressor desgastado) tem retorno direto.

Este projeto constrói esse caminho de ponta a ponta de forma incremental e reproduzível, começando por onde o dado nasce: o CLP. Assim, cada número que os softwares seguintes consomem tem uma origem conhecida e explicável.

---

## Arquitetura

```
┌──────────────────────┐
│  PROCESSO VIRTUAL    │   Simulado dentro do CLP
│  Refrigeração (NH3)  │
└──────────┬───────────┘
           ▼
┌──────────────────────┐
│  CLP  (CODESYS)      │   Fases 0 a 2  ✔ implementado
└──────────┬───────────┘
           │ OPC UA
           ▼
┌──────────────────────┐
│  PYTHON GATEWAY      │   Fase 3  (próxima)
│  asyncua             │
└──────────┬───────────┘
           │ MQTT
           ▼
┌──────────────────────┐
│  MOSQUITTO           │   Fase 4
└──────────┬───────────┘
           ▼
┌──────────────────────┐
│  BACKEND FastAPI     │   Fases 5 a 8
└───────┬───────┬──────┘
        │       │
        ▼       ▼
┌────────────┐ ┌─────────────────┐
│ PostgreSQL │ │ Analytics / ML  │   Fases 6, 7, 10 e 11
│ TimescaleDB│ │ Python          │
└─────┬──────┘ └────────┬────────┘
      └────────┬────────┘
               ▼
        ┌─────────────┐
        │ Dashboard   │   Fase 9
        │ React/Grafana│
        └─────────────┘
```

---

## Status do projeto

| Fase | Descrição | Status |
|---|---|---|
| 0 | Planejamento: processo, variáveis, arquitetura | ✔ Feita |
| 1 | CLP: compressor C1, partida/parada, intertravamentos, falhas | ✔ Implementada |
| 2 | Processo físico virtual: temperaturas, pressões, carga, potência, COP | ✔ Implementada |
| 3 | OPC UA: servidor no CLP e cliente em Python | Próxima |
| 4 | MQTT com Mosquitto | Planejada |
| 5 | Banco: PostgreSQL, TimescaleDB, SQLAlchemy, Alembic | Planejada |
| 6 | Engenharia de dados: limpeza, validação, agregação, KPIs | Planejada |
| 7 | Eficiência energética: potência, energia, COP, custo em R$ | Planejada |
| 8 | Backend: FastAPI, Pydantic, endpoints | Planejada |
| 9 | Dashboard: React, TypeScript, gráficos, alarmes | Planejada |
| 10 | Machine Learning: detecção de anomalias | Planejada |
| 11 | MLOps: MLflow, versionamento, model registry | Planejada |
| 12 | Produção simulada: Docker, testes, health checks | Planejada |
| 13 | Escala: de C1 até C8 | Planejada |
| 14 | Documentação, vídeo e case | Planejada |

---

## Tecnologias

**Em uso**

- **CODESYS 3.5.22** (IEC 61131-3, Structured Text)
- **CODESYS Control Win V3 x64** (CLP virtual rodando no PC)

**Planejadas**

- Python, `asyncua`, FastAPI, Pydantic, SQLAlchemy, Alembic
- Mosquitto (MQTT)
- PostgreSQL e TimescaleDB
- NumPy, Pandas, SciPy, scikit-learn, XGBoost, MLflow
- React, TypeScript, Vite, Tailwind CSS, Recharts e/ou Grafana
- Docker e Docker Compose, Pytest

---

## O que já está implementado

### Compressor C1 (Fase 1)

Um compressor de amônia com inversor de frequência (25 a 60 Hz), controlado por uma máquina de estados:

```
PARADO ─► PARTIDA ─► RODANDO ─► PARANDO ─► PARADO
              │          │
              └──────────┴──► FALHA ─(reset)─► PARADO
```

**Proteções e intertravamentos**

| Código | Falha | Condição |
|---|---|---|
| 1 | Emergência | botão de emergência acionado |
| 2 | Descarga alta | ≥ 13,5 bar (alarme em 12,5 bar) |
| 3 | Sucção baixa | ≤ 0,8 bar por 3 s |
| 4 | Sobrecorrente | ≥ 230 A por 5 s (alarme em 215 A) |
| 5 | Inversor | falha do inversor |
| 6 | Timeout de partida | não chegou a 25 Hz em 30 s |

Também há **anti-ciclagem** (10 s mínimos parado antes de religar) e **falha memorizada**: só o reset rearma, e apenas se a causa já passou.

### Processo físico virtual (Fase 2)

O processo é uma cadeia física encadeada, não números soltos:

```
Demanda térmica ─► Câmara ─► Evaporação ─► Pressão de sucção
                                 │
        Capacidade do compressor (Hz, Tevap, Tcond)
                                 │
        Potência elétrica ─► Corrente (A)
                                 │
Ambiente + sujeira ─► Condensação ─► Pressão de descarga
```

- **Pressão de saturação da amônia** pela equação de Antoine (pressão manométrica, em bar).
- **Capacidade frigorífica** em função da frequência e das temperaturas de evaporação e condensação.
- **COP real** como fração do COP de Carnot, e potência elétrica a partir dele.
- **Corrente** calculada da potência (trifásico, 380 V, cos φ 0,88).
- **Câmara** com balanço de energia entre demanda e capacidade entregue.
- **Planta compartilhada:** sucção, descarga e câmara pertencem à planta, não ao compressor, o que prepara a escala para C1 a C8.

O simulador também publica o **COP verdadeiro** (`rCOPReal`). Numa planta real ele não existe, mas aqui serve como **gabarito** para validar o COP que será estimado a partir dos sensores na Fase 7.

### Cenários de falha injetáveis

| Cenário | Como provocar |
|---|---|
| Condensador sujo | `GVL_Proc.rSujeiraCond` de 0 a 1 |
| Compressor desgastado | `GVL_C1.C1_Inj.bDesgaste` |
| Baixa demanda (sucção baixa) | `GVL_Proc.rDemandaKW` baixa |
| Variação de demanda | `rDemandaKW` manual ou `bDemandaAuto` (senoidal) |
| Falha do inversor | `GVL_C1.C1_Inj.bFalhaInversor` |
| Emergência | `GVL_C1.C1_Cmd.bEmergenciaOK` em `FALSE` |
| Erro de sensor | `rOffsetPDesc` e `rOffsetPSuc` |

### Variáveis principais para integração

| Tag | Descrição |
|---|---|
| `GVL_C1.C1_Sts.eEstado` | estado (0 a 4) |
| `GVL_C1.C1_Sts.eFalha` | código da falha (0 a 6) |
| `GVL_C1.C1_Sts.rHz` | frequência (Hz) |
| `GVL_C1.C1_Sts.rAmp` | corrente (A) |
| `GVL_C1.C1_Sts.rPSuc` | pressão de sucção (bar manométrico) |
| `GVL_C1.C1_Sts.rPDesc` | pressão de descarga (bar manométrico) |
| `GVL_C1.C1_Proc.rQFrigKW` | capacidade frigorífica (kW) |
| `GVL_C1.C1_Proc.rPotKW` | potência elétrica (kW) |
| `GVL_C1.C1_Proc.rCOPReal` | COP verdadeiro (gabarito) |
| `GVL_Proc.rTCamara`, `rTEvap`, `rTCond` | temperaturas da planta (°C) |

---

## Como executar

### Requisitos

- Windows
- **CODESYS 3.5.22** (ou superior) com o pacote **CODESYS Control Win V3 x64**
- IDE e runtime em **versões compatíveis** (um IDE antigo não conecta num runtime novo)

### Passos

1. Crie um projeto no CODESYS com o dispositivo **CODESYS Control Win V3 x64**.
2. Crie os objetos na ordem indicada em [`Codigo/codigos-codesys.md`](Codigo/codigos-codesys.md) e cole o código de cada um.
3. Configure o **MainTask** com ciclo de **100 ms**.
4. **Compilar → Compilar** (F11).
5. Inicie o Control Win pela bandeja do Windows (**Start PLC**).
6. Conecte: **Configurações de Comunicação → Procurar Rede → Definir caminho ativo**. Na primeira conexão, crie o usuário administrador do dispositivo.
7. **Online → Login** e **Online → Iniciar**.

### Primeiro teste

1. Abra a `GVL_C1`.
2. Em `C1_Cmd.bLiga`, prepare `TRUE` e envie com **Ctrl+F7**. Depois volte para `FALSE`.
3. O `eEstado` passa por PARTIDA e chega a RODANDO, com `rHz` em 45.
4. Em regime, os valores esperados são aproximadamente: corrente de 150 A, descarga de 10 bar e COP entre 3,5 e 3,8.

O roteiro completo de testes e os valores esperados estão em [`Etapas/Etapas 1 e 2.md`](Etapas/Etapas%201%20e%202.md).

---

## Estrutura do repositório

```
.
├── Codigo/
│   └── codigos-codesys.md      Todo o código ST, comentado, na ordem de criação
├── Etapas/
│   └── Etapas 1 e 2.md         Explicação do que foi feito nas Fases 0, 1 e 2
├── .gitignore
└── README.md
```

Estrutura prevista ao longo do projeto:

```
smart-refrigeration/
├── plc/            CLP (CODESYS)
├── gateway/        Python: OPC UA para MQTT
├── backend/        FastAPI
├── analytics/      Cálculos e análises
├── ml/             Machine Learning
├── frontend/       Dashboard
├── database/       Modelos e migrations
├── docker/
├── tests/
├── docs/
└── docker-compose.yml
```

---

## Premissas e limitações

- Os parâmetros do modelo (capacidade nominal de 440 kW, 60% do COP de Carnot, coeficientes de capacidade) são **plausíveis para um compressor grande de amônia, mas não pertencem a um equipamento específico**. Os resultados são para estudo, não para dimensionamento.
- A **inércia térmica da câmara é acelerada** para facilitar os testes. Numa planta real seria bem mais lenta.
- Ainda **não há controle de capacidade**: com demanda muito baixa, o compressor não reduz sozinho e a sucção cai até a falha por sucção baixa.
- A proteção de sucção baixa só atua com o compressor em RODANDO.
- Há **um compressor ativo**. A planta já está estruturada para somar vários.
- O `rCOPReal` não é uma medição: é o gabarito do simulador.
- A lógica de intertravamento é **simulação para estudo**. Não é função de segurança certificada. Numa planta real, o CLP e o hardware de segurança continuam responsáveis pelo controle e pelos intertravamentos.

Quando uma grandeza for estimada (e não medida), o projeto indicará isso explicitamente.

---

## Roadmap

**Próximos passos**

1. **Fase 3:** expor as variáveis por OPC UA (Configuração de Símbolos) e criar o cliente Python com `asyncua`, com validação, normalização e logging.
2. **Fase 4:** publicar a telemetria no Mosquitto, com tópicos como `refrigeration/C1/telemetry`, `status` e `alarm`.
3. **Fase 5:** persistir os dados em PostgreSQL com TimescaleDB.

O roadmap completo, com as 14 fases, está na tabela de [status](#status-do-projeto).

---

## Autor

**Maicon Sales**

Projeto de estudo em automação industrial, engenharia de dados e IA.
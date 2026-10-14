## Puxar variaveis do CODESYS

const variables = [
    { name: "liga", nodeId: "ns=4;s=|var|CODESYS Control Win V3 x64.Application.GVL_C1.C1_Cmd.bLiga" },
    { name: "desliga", nodeId: "ns=4;s=|var|CODESYS Control Win V3 x64.Application.GVL_C1.C1_Cmd.bDesliga" },
    { name: "reset", nodeId: "ns=4;s=|var|CODESYS Control Win V3 x64.Application.GVL_C1.C1_Cmd.bReset" },
    { name: "emergencia_ok", nodeId: "ns=4;s=|var|CODESYS Control Win V3 x64.Application.GVL_C1.C1_Cmd.bEmergenciaOK" },
    { name: "hz_set", nodeId: "ns=4;s=|var|CODESYS Control Win V3 x64.Application.GVL_C1.C1_Cmd.rHzSet" },

    { name: "q_frig_kw", nodeId: "ns=4;s=|var|CODESYS Control Win V3 x64.Application.GVL_C1.C1_Proc.rQFrigKW" },
    { name: "pot_kw", nodeId: "ns=4;s=|var|CODESYS Control Win V3 x64.Application.GVL_C1.C1_Proc.rPotKW" },
    { name: "cop_real", nodeId: "ns=4;s=|var|CODESYS Control Win V3 x64.Application.GVL_C1.C1_Proc.rCOPReal" },

    { name: "estado", nodeId: "ns=4;s=|var|CODESYS Control Win V3 x64.Application.GVL_C1.C1_Sts.eEstado" },
    { name: "falha", nodeId: "ns=4;s=|var|CODESYS Control Win V3 x64.Application.GVL_C1.C1_Sts.eFalha" },
    { name: "rodando", nodeId: "ns=4;s=|var|CODESYS Control Win V3 x64.Application.GVL_C1.C1_Sts.bRodando" },
    { name: "falha_bit", nodeId: "ns=4;s=|var|CODESYS Control Win V3 x64.Application.GVL_C1.C1_Sts.bFalha" },
    { name: "alarme", nodeId: "ns=4;s=|var|CODESYS Control Win V3 x64.Application.GVL_C1.C1_Sts.bAlarme" },
    { name: "hz", nodeId: "ns=4;s=|var|CODESYS Control Win V3 x64.Application.GVL_C1.C1_Sts.rHz" },
    { name: "amp", nodeId: "ns=4;s=|var|CODESYS Control Win V3 x64.Application.GVL_C1.C1_Sts.rAmp" },
    { name: "p_suc", nodeId: "ns=4;s=|var|CODESYS Control Win V3 x64.Application.GVL_C1.C1_Sts.rPSuc" },
    { name: "p_desc", nodeId: "ns=4;s=|var|CODESYS Control Win V3 x64.Application.GVL_C1.C1_Sts.rPDesc" },

    { name: "q_demanda_kw", nodeId: "ns=4;s=|var|CODESYS Control Win V3 x64.Application.GVL_Proc.rQDemandaKW" },
    { name: "t_camara", nodeId: "ns=4;s=|var|CODESYS Control Win V3 x64.Application.GVL_Proc.rTCamara" },
    { name: "t_cond", nodeId: "ns=4;s=|var|CODESYS Control Win V3 x64.Application.GVL_Proc.rTCond" },
    { name: "t_evap", nodeId: "ns=4;s=|var|CODESYS Control Win V3 x64.Application.GVL_Proc.rTEvap" }
];

flow.set("opcVariables", variables);
flow.set("opcResults", {});

variables.forEach(v => {
    node.send({ topic: v.nodeId, payload: "" });
});

return null;

## Esse trecho de código (provavelmente usado em uma function do Node-RED) serve para estruturar e disparar a leitura dessas informações via OPC UA.
## O que ele faz na prática é preparar o terreno em três passos simples:
## 1. Mapeamento: Ele cria uma lista (variables) associando nomes amigáveis (como liga, t_camara) aos endereços reais do CLP (NodeIds do CODESYS).
## 2. Memória de Fluxo: Ele salva essa lista e cria um objeto vazio (opcResults) na memória do Node-RED (flow) para você usar depois.
## 3. Disparo da Leitura: O loop variables.forEach envia uma mensagem para a saída do bloco para cada variável da lista. O topic: v.nodeId avisa o próximo nó (que deve ser um nó de leitura do OPC UA) exatamente qual dado ele precisa buscar no CODESYS.
## Como você está tratando o retorno desses dados? Se quiser, posso te ajudar a montar o código do próximo bloco para receber essas respostas e juntar tudo no objeto opcResults que você criou.

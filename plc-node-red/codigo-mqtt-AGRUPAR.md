## Junta os dados do CODESYS

const variables = flow.get("opcVariables") || [];
const results = flow.get("opcResults") || {};

const match = variables.find(v => v.nodeId === msg.topic);
if (!match) {
    return null;
}

results[match.name] = msg.payload;
flow.set("opcResults", results);

if (Object.keys(results).length >= variables.length) {
    const output = {
        timestamp: new Date().toISOString(),
        command: {
            liga: results.liga,
            desliga: results.desliga,
            reset: results.reset,
            emergencia_ok: results.emergencia_ok,
            hz_set: results.hz_set
        },
        process: {
            q_frig_kw: results.q_frig_kw,
            pot_kw: results.pot_kw,
            cop_real: results.cop_real,
            q_demanda_kw: results.q_demanda_kw,
            t_camara: results.t_camara,
            t_cond: results.t_cond,
            t_evap: results.t_evap
        },
        status: {
            estado: results.estado,
            falha: results.falha,
            rodando: results.rodando,
            falha_bit: results.falha_bit,
            alarme: results.alarme,
            hz: results.hz,
            amp: results.amp,
            p_suc: results.p_suc,
            p_desc: results.p_desc
        }
    };

    flow.set("opcResults", {});

    msg.payload = output;
    return msg;
}

return null;


## Este código é o fechamento perfeito do fluxo. Ele funciona como um centralizador (ou agregador) de dados no Node-RED.
## Enquanto o primeiro código que você mandou disparou as perguntas para o CODESYS, este segundo código recebe as respostas uma por uma, junta tudo em um "pacote" organizado e só libera a mensagem adiante quando tiver 100% das informações coletadas.
## O passo a passo do que ele faz é:
## 1. Identifica a resposta: Ele olha para o msg.topic que acabou de chegar do OPC UA, cruza com a lista de variáveis e descobre o nome real do dado (ex: transforma o NodeId longo em "t_camara").
## 2. Guarda na memória: Ele salva o valor recebido dentro do objeto opcResults que foi criado no primeiro código.
## 3. Checa se terminou: Ele faz a verificação if (Object.keys(results).length >= variables.length). Isso significa: "Já recebi o valor de todas as 21 variáveis?"
	• Se NÃO terminou: Ele retorna null, ou seja, o Node-RED segura o fluxo e não envia nada para o próximo nó.
	• Se SIM (chegaram todas): Ele monta um objeto JSON super organizado, separado por categorias (command, process, status) com um timestamp (data e hora exata da leitura).
## 4. Limpa o balcão: Ele redefine o opcResults para {} (vazio) para que o fluxo fique pronto para a próxima rodada de leituras, e finalmente envia o pacote completo no msg.payload.

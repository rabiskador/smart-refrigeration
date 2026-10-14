## Para o Mosquitto, na maioria das vezes você não precisa fazer nada, porque ele foi instalado como serviço do Windows e já inicia sozinho com o sistema. Mas se quiser confirmar que está rodando, ou caso tenha parado por algum motivo, abra o PowerShell como administrador e use:


## sc query mosquitto
Se o STATE não aparecer como RUNNING, inicie manualmente com:

## net start mosquitto
Se precisar parar o serviço por algum motivo:


## net stop mosquitto

## Para o Node-RED, abra qualquer terminal (PowerShell ou Prompt de Comando) e digite:


## node-red

Isso vai iniciar o Node-RED e, depois de alguns segundos, o terminal vai mostrar uma mensagem do tipo Server now running at http://127.0.0.1:1880/. 
Deixe esse terminal aberto enquanto estiver trabalhando — fechá-lo encerra o Node-RED. Depois, abra o navegador e acesse:

http://localhost:1880
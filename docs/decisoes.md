# Registro de decisões

Decisões tomadas onde o pedido era ambíguo. Cada uma escolhe a opção mais simples e pode ser revista.

## Fase 1

**D1. Banco de desenvolvimento sem Docker.** Sem `DATABASE_URL`, o Django usa SQLite. Com Docker Compose, usa
PostgreSQL. Os testes rodam nos dois. Produção exige PostgreSQL.

**D2. Celery sem Redis.** Sem `REDIS_URL`, as tarefas rodam de forma síncrona (`CELERY_TASK_ALWAYS_EAGER`). Isso
permite rodar testes e o sistema local sem Redis.

**D3. Chave de criptografia.** Credenciais de API e tokens OAuth usam Fernet (`FIELD_ENCRYPTION_KEY`). Se a variável
estiver vazia, a chave é derivada da `SECRET_KEY` (só para desenvolvimento). Trocar a chave torna os valores
antigos ilegíveis: gere uma vez e guarde em cofre.

**D4. Credenciais nunca voltam para a tela.** Na edição de inversor e medidor, o campo de credenciais vem vazio;
vazio mantém o valor salvo. O admin também não mostra o campo.

**D5. Enquadramento GD automático, mas editável.** Ao salvar a usina, o enquadramento é calculado pela data do
protocolo (GD1 até 07/01/2023, inclusive; GD2 depois). Marcando "manual", o valor escolhido fica fixo, e a tela
avisa se ele divergir da data. GD3 é sempre manual. A data de corte está em `apps/cadastro/models.py` nesta fase e
passa para a tabela regulatória com vigência na fase 5. Fonte a confirmar: Lei 14.300/2022, art. 26.

**D6. UC única por integradora.** O número da UC é único por (integradora, concessionária). Duas integradoras
podem cadastrar a mesma UC (ex.: troca de integradora), e os dados ficam isolados.

**D7. Rateio.** A soma dos percentuais deve ser exatamente 100% quando houver ao menos uma beneficiária. Sem
rateio, todos os créditos ficam na UC geradora.

**D8. Custo de disponibilidade.** Nesta fase, 30/50/100 kWh por tipo de ligação (REN 1.000/2021), só para mostrar no
cadastro. A forma de aplicar em GD2 (Lei 14.300 e REN 1.059/2023) vira regra configurável na fase 5 e será
documentada aqui.

**D9. Créditos.** O saldo é guardado em lotes por mês de geração, com validade de 60 meses a partir do mês do lote.
Isso permite abater os mais antigos primeiro.

**D10. Papéis.** Administrador interno usa o Django admin. Gestor e técnico usam o painel; só o gestor edita os
dados da integradora (e, nas fases seguintes, usuários e configurações). Cliente final só verá o portal (fase 10).

**D11. Log de auditoria.** Registramos visualização dos detalhes de cliente, UC e usina, criação e alteração. A
exportação (laudos) entra quando houver exportação.

## Fase 2 (monitoramento e integrações)

**D12. Prioridade no monitoramento.** A pedido do cliente, a fase 2 entrega o monitoramento de várias usinas
por cliente, de fabricantes diferentes, numa tela só ("Usinas agora"). Faturas e auditoria vêm em seguida.

**D13. Real só com credenciais completas.** O inversor guarda o provedor (Growatt, Huawei...). Se as credenciais ou
o `id_externo` estiverem incompletos, o sistema usa o Fake e a tela mostra "dados de demonstração". Assim dá para
cadastrar a marca certa desde já e só preencher a credencial depois.

**D14. Situação da usina.** Sem comunicação: última leitura há mais de `MONITOR_HORAS_SEM_COMUNICACAO` (3 h).
Parada: inversor reporta offline, ou potência e energia zeradas entre 8 h e 16 h. Abaixo do esperado: últimos
7 dias abaixo de `MONITOR_LIMIAR_ABAIXO` (80%) da geração esperada. Sem geração esperada cadastrada, estimamos por
kWp × horas de sol de Natal × 0,78 (só para monitoramento, nunca para cálculo regulatório).

**D15. Coleta.** Status a cada 15 min e geração diária a cada 6 h (últimos 3 dias, para corrigir dias parciais),
pelo Celery beat. O botão "Atualizar agora" coleta o status na hora.

**D16. Endpoints dos fabricantes.** Seguem a documentação pública conhecida e estão marcados "CONFIRMAR" no código.
GoodWe SEMS não tem API oficial aberta para terceiros: precisa de acordo com o fabricante.

**D17. Identidade visual.** A paleta da seção 9 foi trocada a pedido do cliente: midnight black `#0A0F1C` (fundo),
electric cobalt `#1F4FFF` (faixa do topo, gráficos, seleção) e acid lime `#C8FF2E` (único destaque: botão
principal, "gerando", linha do esperado). Laranja `#FF7A45` e verde `#4ADE80` seguem só para divergência/confere.
Para links sobre o fundo escuro usamos um cobalto claro `#8EA6FF` (contraste ≥ 4,5:1). A situação da usina usa
forma e cor (círculo, quadrado, losango), nunca só cor.

## Reestruturação comercial (três perfis e três fontes)

**D18. Três níveis de acesso.**
1. *Administrador geral* (plataforma): vê tudo; cadastra integradoras e usuários de qualquer perfil; gerencia
   as credenciais de API dos inversores e os dispositivos ESP de todas as integradoras; vê os logs. Pode "entrar
   como" uma integradora para operar o painel dela (fica registrado no log, ação "atuar").
2. *Integradora* (gestor e técnico): carteira de clientes, cadastro completo, monitoramento, faturas e análise.
   Só o gestor gerencia equipe, acessos ao portal e configurações.
3. *Cliente final*: portal só de leitura, com a marca da integradora, só com as próprias usinas e contas.

**D19. Três fontes da auditoria.** A análise da conta cruza, na janela de leitura de cada fatura:
inversor (geração), medidor próprio (importação/exportação/carga) e fatura (consumo, injeção, compensação, valor).
Derivados: autoconsumo = gerado − injetado; consumo real = medido na carga, ou rede + autoconsumo. Os indícios
(kWh) apontam o que investigar; o valor a recuperar em R$ continua sendo do motor de regras com tabelas da ANEEL.

**D20. Medidor próprio na UC.** O medidor passou da usina para a unidade consumidora, porque ele mede a entrada
de energia da instalação. Pode ser ESP32 (envia para `POST /api/medidores/medicoes` com token por dispositivo,
guardado só como hash), API HTTP ou MQTT. O ESP envia contadores acumulados; a consolidação diária é máx − mín.

**D21. Lançamento manual de fatura antecipado.** Para a análise das três fontes funcionar já, o modelo de fatura e
o lançamento manual entraram agora. O leitor de PDF (pdfplumber + IA) da próxima fase preenche os mesmos campos.

**D22. Tarifa de referência só para estimativa.** "Sem solar" e "economia" nas telas usam a tarifa de referência
da concessionária (campo editável, com aviso de estimativa). Nada de regra regulatória depende dela.

**D23. Visual comercial.** A pedido do cliente (o visual anterior não vendia), o painel virou uma aplicação com
menu lateral por perfil, painéis, indicadores e gráficos Chart.js (servidos localmente, sem CDN). Isso substitui
"nada de cartões / sem menu lateral" da seção 9. Ficam: as cores pedidas, números tabulares, fichas pontilhadas,
contraste ≥ 4,5:1, foco visível, alvos ≥ 40–44 px e tabela "Ver os números" em todo gráfico. Paleta dos gráficos
validada para daltonismo sobre o fundo escuro; cor segue o papel (geração = lime, injeção = cobalto,
autoconsumo = verde-água, rede = laranja).

**D24. Migrações recriadas.** Ainda sem dados reais, as migrações foram regeneradas do zero nesta reestruturação.
A partir daqui, toda mudança de modelo vira migração incremental.

## Demonstração com clima real

**D25. Geração de demonstração segue o sol real.** Sem inversores reais conectados, o `FakeInversor` passou a
usar a irradiação solar real de cada município (Open-Meteo, sem chave), por região de 0,1°: energia do dia =
kWp × irradiação × PR; potência = kWp × irradiância horária ÷ 1000 × PR. Usamos a irradiação horizontal, que perto
do equador difere poucos por cento do plano dos módulos (~10°). O clima fica no banco e é atualizado de hora em
hora; sem rede, volta ao modelo sintético. Nos testes o clima fica desligado e a API é simulada.
Licença: o Open-Meteo gratuito é só para uso não comercial; antes de vender, contratar o plano pago ou trocar a
fonte (`CLIMA_PROVIDER`). Pesquisa em `docs/fontes-de-dados-publicas.md`.

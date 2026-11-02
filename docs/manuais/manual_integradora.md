# Manual da integradora

Este manual é para gestores e técnicos de integradoras que usam o FaturaCerta para acompanhar as usinas dos seus
clientes e conferir as contas de energia. Ele cobre o uso do dia a dia e como conectar os equipamentos.

---

## Sumário

1. [O que o FaturaCerta faz por você](#1-o-que-o-faturacerta-faz-por-você)
2. [Conceitos que você precisa conhecer](#2-conceitos-que-você-precisa-conhecer)
3. [Perfis da sua equipe](#3-perfis-da-sua-equipe)
4. [Entrar no sistema](#4-entrar-no-sistema)
5. [Visão geral da carteira](#5-visão-geral-da-carteira)
6. [Usinas agora](#6-usinas-agora)
7. [Cadastro completo de um cliente](#7-cadastro-completo-de-um-cliente)
8. [Conectar os inversores](#8-conectar-os-inversores)
9. [Conectar o medidor próprio (ESP32)](#9-conectar-o-medidor-próprio-esp32)
10. [Faturas](#10-faturas)
11. [Análise da conta: as três fontes](#11-análise-da-conta-as-três-fontes)
12. [Equipe, acessos e configurações](#12-equipe-acessos-e-configurações)
13. [O que o seu cliente vê](#13-o-que-o-seu-cliente-vê)
14. [Perguntas frequentes e solução de problemas](#14-perguntas-frequentes-e-solução-de-problemas)

---

## 1. O que o FaturaCerta faz por você

O FaturaCerta reúne, num login só, todos os seus clientes, as usinas deles (de qualquer fabricante) e as contas de
energia. Ele faz três coisas:

1. **Monitora as usinas** numa tela só: o que está gerando, o que parou, o que está abaixo do esperado.
2. **Confere a conta de energia**, cruzando o que a usina gerou, o que o medidor próprio registrou e o que a
   concessionária cobrou.
3. **Mostra ao seu cliente**, num portal com a sua marca, quanto ele gerou e quanto economizou.

O sistema detecta e avisa; quem resolve é a sua equipe.

## 2. Conceitos que você precisa conhecer

| Termo | Significado |
|---|---|
| **Cliente** | Titular das contas de energia (pessoa física ou jurídica). |
| **UC (unidade consumidora)** | Cada "relógio" da concessionária, com número próprio impresso na fatura. Um cliente pode ter várias. |
| **Usina** | O sistema fotovoltaico, ligado a uma **UC geradora**. Um cliente pode ter várias usinas, de fabricantes diferentes. |
| **Grupo A / Grupo B** | Grupo B é baixa tensão (casas e comércios; subgrupos B1, B2, B3). Grupo A é média/alta tensão (indústrias, supermercados; subgrupo A4 etc.), com demanda contratada. |
| **Tipo de ligação** | Monofásica, bifásica ou trifásica. Define o custo de disponibilidade (30, 50 ou 100 kWh) no grupo B. |
| **GD1 / GD2 / GD3** | Enquadramento da usina na Lei 14.300. GD1: pedido de acesso protocolado até 07/01/2023. GD2: depois. Muda quanto do Fio B é cobrado. |
| **Injeção** | Energia que a usina mandou para a rede porque não foi usada na hora. |
| **Compensação** | Energia injetada que a concessionária abateu do consumo. |
| **Autoconsumo** | Energia gerada e usada na hora. Não passa pelo medidor da concessionária. É calculado: geração − injeção. |
| **Medidor próprio** | Equipamento seu (normalmente um ESP32 com sensores) que mede o que entra e sai da rede, independente da concessionária. |
| **Janela de leitura** | Período entre a leitura anterior e a atual da fatura. Não coincide com o mês civil; toda comparação usa essa janela. |

## 3. Perfis da sua equipe

| Perfil | O que faz |
|---|---|
| **Gestor** | Toda a carteira: clientes, usinas, equipamentos e faturas. Cria usuários da equipe e acessos ao portal e altera as configurações da empresa. |
| **Técnico** | O mesmo que o gestor, exceto equipe, acessos e configurações. |
| **Cliente final** | Só o portal, com os dados das próprias usinas. Não altera nada. |

A sua integradora nunca vê dados de outra, e nenhuma outra vê os seus.

## 4. Entrar no sistema

1. Acesse o endereço do sistema e informe **usuário** e **senha**.
2. Você cai na **Visão geral** da sua integradora.
3. O menu lateral leva às telas: Visão geral, Usinas agora, Clientes, Faturas, Manuais e, para o gestor,
   Equipe e acessos e Configurações.
4. Para sair, use **Sair** no rodapé do menu.

No celular, o menu fica escondido: toque no ícone de menu no topo.

## 5. Visão geral da carteira

A primeira tela mostra a carteira inteira:

- **Potência agora**, **gerado hoje** e **gerado no mês**, com o percentual do esperado até hoje;
- **Usinas que precisam de atenção** e **faturas com divergência**;
- a lista **Precisa de atenção**, ordenada pela gravidade, com link para cada caso;
- gráficos: geração da carteira em 30 dias × esperado, potência de hoje a cada 15 minutos, desempenho de cada
  usina nos últimos 7 dias, geração mensal em 12 meses e potência por fabricante.

Todo gráfico tem o link **Ver os números**, que mostra a mesma informação em tabela.

## 6. Usinas agora

Todas as usinas, **agrupadas por cliente**, de qualquer fabricante. Para cada uma: situação, potência agora,
energia de hoje contra o esperado do dia e um minigráfico de 14 dias.

| Situação | Símbolo | Quando aparece |
|---|---|---|
| Gerando | círculo verde-limão | Comunicando e produzindo. |
| Sem sol agora | círculo vazado | Fora do horário de sol, sem problema. |
| Abaixo do esperado | quadrado amarelo | Últimos 7 dias abaixo de 80% do esperado. |
| Parada | losango laranja | Inversor reporta parado, ou zero de potência e energia entre 8h e 16h. |
| Sem comunicação | losango laranja | Nenhuma leitura há mais de 3 horas. |
| Sem inversor | círculo tracejado | Usina cadastrada sem inversor vinculado. |

A tela se atualiza sozinha a cada minuto. **Atualizar agora** consulta os inversores na hora. Use os filtros
(Todas, Precisam de atenção, Gerando) e a busca por cliente, usina ou fabricante.

O selo **dados de demonstração** indica um inversor sem credencial: os números são simulados até você conectar a
API do fabricante (seção 8).

## 7. Cadastro completo de um cliente

A conferência da conta só é tão boa quanto o cadastro. Siga esta ordem:

```
Cliente → Consentimento LGPD → UC(s) → Usina(s) → Arranjos de módulos → Inversor(es)
        → Medidor próprio → Faturas → Acesso ao portal
```

Na ficha de cada cliente, aba **Resumo**, o quadro **Cadastro para auditoria** mostra o percentual completo e os
oito passos:

1. Titular completo (CPF/CNPJ, segmento e contato)
2. Consentimento LGPD
3. Unidade consumidora com número, código do cliente e perfil tarifário
4. Usina com data do protocolo (define GD1/GD2)
5. Inversor com API do fabricante (fonte 1)
6. Medidor próprio (fonte 2)
7. 12 faturas no histórico (fonte 3 e linha de base da economia)
8. Acesso ao portal

### 7.1 Cliente

**Clientes → Novo cliente.** Campos em seções:

- **Titular**: tipo (PF/PJ), nome ou razão social, nome fantasia, CPF/CNPJ (validado), segmento e atividade.
- **Contato**: pessoa de contato, e-mail, telefone, WhatsApp.
- **Endereço.**
- **Perfil de uso**: horário de funcionamento (ajuda a interpretar quanto da geração é consumida na hora),
  cliente desde e observações.

Ao salvar, abre a **ficha do cliente**, com as abas Resumo, Unidades consumidoras, Usinas, Equipamentos, Faturas e
Acesso e LGPD. No topo, etiquetas resumem o perfil: segmento, subgrupo e ligação de cada UC, GD de cada usina,
potência total, fabricantes e se há medidor próprio.

### 7.2 Consentimento LGPD

Na aba **Acesso e LGPD**, informe a versão do termo e marque o aceite. O sistema registra data, hora, IP e quem
registrou. Sem consentimento, o cliente aparece como "pendente".

### 7.3 Unidade consumidora

Na ficha do cliente, botão **UC**. Tenha a fatura de energia em mãos:

- **Identificação**: concessionária, número da UC, código do cliente (como impresso na fatura), apelido e e-mail
  de recebimento da fatura (por exemplo, `faturas+uc7010453067@suaempresa.com.br`).
- **Perfil tarifário**: grupo, subgrupo, classe, tipo de ligação, tensão, modalidade tarifária, tarifa social e
  demanda contratada (grupo A; na modalidade azul, também a demanda na ponta).
- **Medidor da concessionária**: número, **constante** (fator impresso na fatura) e se é bidirecional.
- **Linha de base**: consumo médio mensal antes da usina.
- **Endereço da UC** (o município define a CIP) e coordenadas.

O sistema impede combinações inválidas, como tarifa verde em grupo B. Na página da UC, a aba **Perfil e regras**
mostra quais regras de auditoria estão ativas e o que falta para ligar as desligadas.

### 7.4 Usina

Na ficha do cliente, botão **Usina** (a lista de UCs já vem filtrada para aquele cliente):

- **Identificação**: nome, UC geradora e modalidade de GD (junto à carga, autoconsumo remoto, geração
  compartilhada, múltiplas UCs).
- **Acesso e enquadramento**: data e número do protocolo, parecer de acesso e data de conexão. O enquadramento
  **GD1/GD2 é calculado pela data do protocolo**. Para fixar outro, marque "enquadramento manual"; se ele divergir
  da data, a página da usina avisa.
- **Dados técnicos**: potência, número de módulos, tipo de instalação, inclinação, azimute e performance ratio
  esperado (padrão 0,78).
- **Geração esperada (kWh/mês)**: os 12 valores do projeto. É a régua do monitoramento.
- **UCs beneficiárias (rateio)**: para autoconsumo remoto e geração compartilhada. A soma tem de dar 100%.

### 7.5 Arranjos de módulos

Na página da usina, **Adicionar arranjo**: fabricante, modelo, potência do módulo (Wp), quantidade, inclinação,
azimute e garantia. A **potência da usina e o número de módulos são recalculados** pela soma dos arranjos.

### 7.6 Inversor

Na página da usina, botão **Inversor**: marca, modelo, número de série, tipo, potência nominal, fases, MPPTs,
instalação e garantia. A conexão com a API do fabricante está na seção 8.

### 7.7 Créditos

Na página da UC, aba **Créditos**: registre o saldo de créditos por mês de geração. A validade (60 meses) é
calculada sozinha.

### 7.8 Acesso ao portal

Na ficha do cliente, aba **Acesso e LGPD → Criar acesso**: usuário, e-mail e senha inicial (mínimo de 8
caracteres). Passe os dados ao cliente. A ficha mostra quando ele entrou pela última vez.

## 8. Conectar os inversores

O inversor é a **fonte 1** da auditoria: quanto a usina gerou. Sem credencial, o sistema mostra dados de
demonstração; com credencial, passa a ler o portal do fabricante sozinho.

1. Na página da usina, abra o inversor (ou **Inversor** para vincular um novo).
2. Em **API de monitoramento**, escolha o fabricante.
3. Em **ID no portal do fabricante**, informe o identificador da planta.
4. Em **Credenciais da API (JSON)**, cole as credenciais no formato da tabela abaixo.
5. Salve. Em até 15 minutos o selo "dados de demonstração" some e os números reais aparecem.

| Fabricante | Credenciais (JSON) | ID no portal |
|---|---|---|
| Growatt | `{"token": "..."}` | `plant_id` |
| Huawei FusionSolar | `{"usuario": "...", "senha_api": "..."}` (conta de API Northbound) | `stationCode` |
| SolarEdge | `{"api_key": "..."}` | `site_id` |
| Fronius | `{"access_key_id": "...", "access_key_value": "..."}` | `pvSystemId` |
| GoodWe (SEMS) | `{"usuario": "...", "senha": "..."}` | `powerstation_id` |
| Deye / Solarman | `{"app_id": "...", "app_secret": "...", "email": "...", "senha_sha256": "..."}` | `stationId` |

Cuidados:

- As credenciais ficam criptografadas e **nunca** aparecem de novo na tela. Para trocar, cole as novas; para
  manter, deixe o campo vazio.
- Peça ao fabricante acesso de **API** (não basta o login do aplicativo). A GoodWe exige acordo com o fabricante;
  a SolarEdge limita a 300 consultas por dia por chave.
- Se algo der errado, a página da usina mostra o último erro do inversor.

## 9. Conectar o medidor próprio (ESP32)

O medidor próprio é a **fonte 2**: prova quanto entrou e saiu da rede, sem depender da concessionária.

### 9.1 Cadastrar o medidor

Na página da UC, **Vincular medidor próprio**:

- **Dispositivo**: nome, tipo (ESP32 com sensores, medidor inteligente, gateway), **ponto de medição**, fabricante,
  modelo, série, fases, faixa dos sensores e intervalo de envio.
- **Origem dos dados**: escolha **ESP32** para o dispositivo enviar à nossa API.

| Ponto de medição | O que mede |
|---|---|
| Entrada da rede (bidirecional) | Quanto entrou da rede e quanto saiu para ela. É o caso mais comum. |
| Carga | O consumo total da instalação. |
| Rede e carga | Os dois, com dois conjuntos de sensores. |

### 9.2 Token do dispositivo

Ao salvar um medidor ESP32, o sistema mostra **uma única vez** o token do dispositivo e as instruções de envio.
Copie na hora. Se perder, abra **token e instruções** na aba Perfil e regras da UC e gere outro; o anterior para
de funcionar na hora.

### 9.3 Gravar o firmware

O sistema fornece um firmware de exemplo para ESP32 com sensor SCT-013 e transformador de tensão ZMPT101B. No topo
do arquivo, preencha a rede Wi-Fi, o endereço da API, o token e a calibração. O dispositivo envia os contadores
**acumulados** de energia a cada minuto; o sistema consolida por dia a cada 15 minutos.

> A instalação em quadro elétrico deve ser feita por profissional habilitado.

### 9.4 Conferir

Na aba **Equipamentos** da ficha do cliente, o medidor aparece como **online** quando está enviando. Na análise da
conta, o quadro "Medidor próprio" mostra a porcentagem de dias com leitura no período.

## 10. Faturas

### 10.1 Lista

Menu **Faturas**: todas as faturas da carteira, com filtro por situação (Recebida, Em revisão, Confere, Divergência)
e busca por cliente ou UC. Clique na UC para abrir a análise daquela fatura.

### 10.2 Lançar uma fatura

**Lançar fatura** (no menu Faturas ou na página da UC). Os campos seguem a ordem da conta:

- **Fatura**: UC, mês de referência, vencimento, total e situação; PDF anexo (opcional).
- **Leitura**: datas e valores das leituras anterior e atual, e a constante. **As datas são essenciais**: é por
  elas que o sistema soma a geração do inversor e as leituras do medidor próprio.
- **Energia**: consumo, consumo na ponta, injetada, compensada, saldo de créditos, modalidade GD, custo de
  disponibilidade e bandeira.
- **Valores**: Fio B, ICMS, PIS/COFINS e CIP.
- **Grupo A**: demanda contratada e medida, ultrapassagem e reativo.

Lançando a partir da UC, constante, custo de disponibilidade e demanda contratada já vêm do cadastro.

> A leitura automática do PDF e a captura das faturas pelo e-mail estão em desenvolvimento e vão preencher estes
> mesmos campos.

## 11. Análise da conta: as três fontes

Abra a UC, aba **Análise da conta**, e escolha a fatura no seletor de período.

### 11.1 Os três quadros

| Fonte | O que mostra |
|---|---|
| **1. Inversor** | Gerado na janela, esperado do projeto e desempenho (%). |
| **2. Medidor próprio** | Consumido da rede, injetado na rede, consumo da carga (se medido) e % de dias com leitura. |
| **3. Concessionária** | Consumo faturado, injetado, compensado e total cobrado, com o selo "confere" ou o número de indícios. |

### 11.2 Os números derivados

- **Autoconsumo** = gerado (inversor) − injetado (fatura).
- **Consumo real da instalação** = consumo medido na carga, ou consumido da rede + autoconsumo.
- **Atendido pelo sol** = (autoconsumo + compensado) ÷ consumo real.
- **Economia estimada** = consumo real × tarifa de referência − total pago. É uma estimativa; o valor a contestar
  em reais é calculado pelo motor de regras.

### 11.3 Indícios para auditoria

| Indício | Gravidade | O que significa e o que fazer |
|---|---|---|
| Injeção maior que a geração do inversor | alta | A fatura diz que foi injetado mais do que a usina gerou. Confira a leitura da concessionária e a API do inversor. |
| Consumo faturado X% acima do medido | alta | A concessionária cobra mais do que o seu medidor registrou. Razão quase fixa (1,25; 1,5; 2…) indica constante errada. |
| Constante na fatura difere do cadastro | alta | A fatura multiplica a leitura por um fator diferente do medidor instalado. Peça a correção. |
| Injeção não compensada | alta | Houve injeção e consumo compensável, mas a compensação ficou abaixo do possível. |
| Injeção da fatura diverge do medidor próprio | média | Diferença acima de 5% entre o injetado na fatura e o medido. |
| Leitura × constante não fecha | média | (leitura atual − anterior) × constante ≠ consumo cobrado. |
| Ultrapassagem de demanda | média | Grupo A: demanda medida acima da contratada. Avalie ajustar o contrato. |
| Geração abaixo do esperado no período | média | Menos de 80% do esperado na janela. Verifique sujeira, sombra ou falha. |
| Cobrança de energia reativa | baixa | Fator de potência abaixo de 0,92. Avalie banco de capacitores. |

### 11.4 Gráficos da análise

- **Para onde foi a energia**: consumo real (autoconsumo + rede) e a linha da geração, fatura a fatura.
- **Consumo: concessionária × medidor próprio**: fatura sempre acima por um fator fixo indica constante errada.
- **Injetado × compensado.**
- **Quanto pagou × quanto pagaria sem solar** (estimativa).

## 12. Equipe, acessos e configurações

Disponível para o **gestor**.

- **Equipe e acessos**: lista gestores, técnicos e clientes com acesso ao portal. Crie e edite usuários da sua
  integradora; desmarque **Acesso ativo** para bloquear alguém sem apagar o histórico. Na edição, deixe a senha
  em branco para manter a atual.
- **Configurações**: dados da empresa, responsável técnico (nome e CREA, usados no laudo), contato e **marca do
  portal** (logo e cor). A cor também aparece no painel da sua equipe.

## 13. O que o seu cliente vê

O portal do cliente é pensado para o celular, com o seu logo e a sua cor:

- quanto as usinas geraram hoje, a situação geral, a potência agora e a geração do mês;
- a curva de hoje e um bloco por usina com o percentual do esperado para o dia;
- **a conta do mês em formato de recibo**: quanto pagaria sem solar, quanto pagou, quanto as usinas geraram, que
  parte do consumo o sol atendeu e a economia. O selo **Conta conferida** aparece quando a análise não encontrou
  indício grave;
- a economia nos últimos 12 meses e os gráficos de geração e de custo;
- no rodapé, o seu contato.

Se uma usina dele parar, o portal mostra que a integradora já foi avisada. O cliente não vê os indícios técnicos.

## 14. Perguntas frequentes e solução de problemas

**Onde vejo se um cliente é do grupo A ou B, quantos kWp tem e qual inversor usa?**
No topo da ficha do cliente (etiquetas), na aba Unidades consumidoras e na aba Usinas. A lista de clientes mostra
perfil, usinas e kWp de relance.

**Por que aparece "dados de demonstração"?**
O inversor está sem credencial de API. Veja a seção 8.

**Cadastrei a usina, mas ela aparece como "Sem inversor".**
Vincule o inversor na página da usina.

**A análise diz "sem fatura neste período".**
Lance a fatura com as datas de leitura corretas.

**O cliente não consegue entrar.**
Em Equipe e acessos, confira se o usuário está ativo e redefina a senha.

| Sintoma | Causa provável | O que fazer |
|---|---|---|
| Inversor sempre em "dados de demonstração" | Credencial ou ID incompletos | Preencha conforme a seção 8. |
| Erro de acesso negado na página da usina | Credencial errada ou sem permissão de API | Confira no portal do fabricante se a conta tem acesso de API. |
| Usina "sem comunicação" com inversor real | Datalogger desligado, sem internet ou API fora do ar | Verifique o equipamento no local e o erro na página da usina. |
| ESP não aparece online | Sem Wi-Fi, token errado ou endereço errado | Confira o firmware; se necessário, gere outro token. |
| Valores do ESP muito pequenos | Contadores zerados a cada envio | O firmware deve enviar contadores acumulados. |
| Medidor próprio não entra na análise | Menos de 90% dos dias com leitura no período | Garanta a comunicação contínua do ESP. |

Precisa de ajuda que este manual não resolve? Fale com o suporte do FaturaCerta.

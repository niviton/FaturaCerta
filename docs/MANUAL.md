# Manual do FaturaCerta

Versão do sistema: novembro de 2026 (fases 1 e 2 concluídas, com a reestruturação em três perfis).

Este manual tem duas partes:

- **Parte I, Uso do sistema**: para quem opera no dia a dia (administrador geral, equipe da integradora e cliente final).
- **Parte II, Manual técnico**: para quem instala, configura, integra equipamentos e mantém o código.

Quando uma função ainda não existe, o manual diz isso com clareza na seção [Limitações atuais](#22-limitações-atuais).

---

## Sumário

**Parte I: Uso do sistema**

1. [O que o FaturaCerta faz](#1-o-que-o-faturacerta-faz)
2. [Conceitos que você precisa conhecer](#2-conceitos-que-você-precisa-conhecer)
3. [Perfis de acesso](#3-perfis-de-acesso)
4. [Entrar no sistema](#4-entrar-no-sistema)
5. [Administrador geral](#5-administrador-geral)
6. [Integradora: visão geral e monitoramento](#6-integradora-visão-geral-e-monitoramento)
7. [Integradora: cadastro completo de um cliente](#7-integradora-cadastro-completo-de-um-cliente)
8. [Integradora: faturas](#8-integradora-faturas)
9. [Análise da conta: as três fontes](#9-análise-da-conta-as-três-fontes)
10. [Equipe, acessos e configurações](#10-equipe-acessos-e-configurações)
11. [Portal do cliente final](#11-portal-do-cliente-final)
12. [Perguntas frequentes](#12-perguntas-frequentes)

**Parte II: Manual técnico**

13. [Arquitetura](#13-arquitetura)
14. [Instalação](#14-instalação)
15. [Configuração (variáveis de ambiente)](#15-configuração-variáveis-de-ambiente)
16. [Modelo de dados](#16-modelo-de-dados)
17. [Integrações com inversores](#17-integrações-com-inversores)
18. [Medidor próprio: ESP32 e API de medições](#18-medidor-próprio-esp32-e-api-de-medições)
19. [Tarefas agendadas](#19-tarefas-agendadas)
20. [Regras de monitoramento e de análise](#20-regras-de-monitoramento-e-de-análise)
21. [Segurança, multiempresa e LGPD](#21-segurança-multiempresa-e-lgpd)
22. [Limitações atuais](#22-limitações-atuais)
23. [Desenvolvimento: testes, lint e convenções](#23-desenvolvimento-testes-lint-e-convenções)
24. [Solução de problemas](#24-solução-de-problemas)

---

# Parte I: Uso do sistema

## 1. O que o FaturaCerta faz

O FaturaCerta é usado por **empresas integradoras de energia solar** para acompanhar as usinas dos seus clientes e
conferir se a concessionária está cobrando certo.

Ele faz três coisas:

1. **Monitora as usinas**, de qualquer fabricante, numa tela só: o que está gerando, o que parou, o que está
   abaixo do esperado.
2. **Confere a conta de energia**, cruzando o que a usina gerou, o que o medidor próprio registrou e o que a
   concessionária cobrou.
3. **Mostra ao cliente final**, num portal com a marca da integradora, quanto ele gerou e quanto economizou.

O sistema **detecta e avisa**; quem resolve é a integradora. Não fazemos serviço de campo.

## 2. Conceitos que você precisa conhecer

| Termo | Significado |
|---|---|
| **Integradora** | Empresa que instala e mantém usinas solares. É quem assina o FaturaCerta. |
| **Cliente** | Titular das contas de energia (pessoa física ou jurídica), cliente da integradora. |
| **UC (unidade consumidora)** | Cada "relógio" da concessionária, com número próprio impresso na fatura. Um cliente pode ter várias. |
| **Usina** | O sistema fotovoltaico. Fica ligado a uma **UC geradora**. Um cliente pode ter várias usinas, de fabricantes diferentes. |
| **Grupo A / Grupo B** | Grupo B é baixa tensão (casas, comércios pequenos; subgrupos B1, B2, B3). Grupo A é média/alta tensão (indústrias, supermercados; subgrupos A4 etc.), com demanda contratada. |
| **Tipo de ligação** | Monofásica, bifásica ou trifásica. Define o custo de disponibilidade (30, 50 ou 100 kWh) no grupo B. |
| **GD1 / GD2 / GD3** | Enquadramento da usina na Lei 14.300. GD1: pedido de acesso protocolado até 07/01/2023. GD2: depois dessa data. Muda quanto do Fio B é cobrado. |
| **Injeção** | Energia que a usina mandou para a rede porque não foi usada na hora. |
| **Compensação** | Energia injetada que a concessionária abateu do consumo (vira crédito). |
| **Autoconsumo** | Energia gerada e usada na hora. Não passa pelo medidor da concessionária e não aparece na fatura. É calculado: geração − injeção. |
| **Medidor próprio** | Equipamento da integradora (normalmente um ESP32 com sensores) que mede o que entra e sai da rede, independente da concessionária. |
| **Janela de leitura** | Período entre a leitura anterior e a atual da fatura. Não coincide com o mês civil; toda comparação usa essa janela. |

## 3. Perfis de acesso

O sistema tem três níveis. Cada pessoa vê só o que o seu perfil permite.

| Perfil | Quem é | O que vê e faz |
|---|---|---|
| **Administrador geral** | A equipe dona da plataforma | Tudo. Cadastra integradoras e usuários de qualquer perfil, gerencia as credenciais de API e os dispositivos de todas as integradoras, vê os logs e pode "entrar como" qualquer integradora. |
| **Integradora: gestor** | Dono ou gerente da integradora | Toda a carteira da própria integradora. Cadastra clientes, usinas e equipamentos, lança faturas, cria usuários da equipe e acessos ao portal, altera as configurações. |
| **Integradora: técnico** | Equipe operacional | O mesmo que o gestor, exceto equipe, acessos e configurações. |
| **Cliente final** | O titular das contas | Só o portal: as próprias usinas, a geração, a conta conferida e a economia. Não altera nada. |

Uma integradora nunca vê dados de outra. Isso vale para telas, buscas, links diretos e formulários.

## 4. Entrar no sistema

1. Acesse o endereço do sistema e informe **usuário** e **senha**.
2. Você é levado direto para a tela do seu perfil:
   - administrador geral → **Plataforma**;
   - gestor ou técnico → **Visão geral** da integradora;
   - cliente final → **portal do cliente**.
3. Para sair, use **Sair** no rodapé do menu lateral (ou no topo, no portal).

Em telas estreitas (celular), o menu lateral fica escondido: toque no ícone de menu no topo.

## 5. Administrador geral

O menu **Plataforma** tem cinco telas.

### 5.1 Visão geral da plataforma

Mostra, de todas as integradoras juntas:

- integradoras ativas, clientes, UCs, usinas e kWp instalados;
- quantos inversores já leem dados reais (com credencial) e quantos estão em demonstração;
- medidores próprios e quantos ESP estão enviando dados agora;
- faturas com divergência.

Abaixo, a tabela de integradoras e os gráficos: potência por integradora, fabricantes de inversor, perfil tarifário
das UCs (B1, B3, A4…), enquadramento GD1/GD2/GD3 e fontes conectadas.

Todo gráfico tem o link **Ver os números**, que abre a mesma informação em tabela.

### 5.2 Integradoras

- **Nova integradora**: preencha empresa, responsável técnico (nome e CREA, que vão no laudo), contato, marca (logo e
  cor, usados no portal do cliente) e contrato (plano, valor por usina, taxa de êxito). Ao salvar, o sistema abre o
  cadastro do **usuário gestor** dessa integradora, já com ela selecionada.
- **Editar**: altera os mesmos dados. Desmarcar "ativa" suspende a integradora.
- **Entrar como**: abre o painel da integradora como se você fosse da equipe dela. Um aviso no menu lateral mostra
  em nome de quem você está atuando; **Voltar para a plataforma** encerra. Cada entrada fica registrada no log.

### 5.3 Usuários

Lista todos os usuários, com filtro por perfil. Em **Novo usuário**:

| Perfil escolhido | O que preencher |
|---|---|
| Administrador geral | Só os dados da pessoa e o acesso. |
| Integradora (gestor ou técnico) | A integradora. |
| Cliente final | O cliente que ele vai acompanhar (a integradora é preenchida a partir do cliente). |

A senha precisa ter pelo menos 8 caracteres e não pode ser comum. Na edição, deixe a senha em branco para manter a
atual. Desmarque **Acesso ativo** para bloquear alguém sem apagar o histórico.

### 5.4 Integrações e APIs

Concentra os equipamentos de todas as integradoras:

- **Inversores**: marca, usina, cliente, integradora, API escolhida, ID no portal do fabricante, se a credencial
  está configurada, quando chegou o último dado e o último erro.
  - **Credenciais**: abre o cadastro do inversor para informar a API e as credenciais (veja a
    [seção 17](#17-integrações-com-inversores)).
  - **Testar**: consulta a API agora e mostra o resultado na própria linha (online/offline, potência e energia do
    dia, ou a mensagem de erro).
- **Medidores próprios e ESP**: tipo, UC, ponto de medição, origem dos dados, prefixo do token e último envio.

As credenciais são guardadas criptografadas e **nunca** voltam para a tela. Para trocar, digite as novas; para
manter, deixe o campo vazio.

### 5.5 Logs de auditoria

Registra quem viu, criou, alterou ou exportou dados, e quando o administrador entrou como uma integradora. Filtre
por ação. Os logs não podem ser editados.

Para manutenção avançada (catálogo de concessionárias, tarifa de referência, correções pontuais), existe o
**Django admin** em `/admin/`, acessível só ao administrador geral.

### 5.6 Manuais

Menu **Manuais**: o administrador geral abre ou baixa os dois manuais em PDF, este (completo) e o **Manual da
integradora**, para enviar às integradoras. A equipe da integradora vê só o manual dela, no mesmo menu. Cada
download fica registrado no log como "exportou".

## 6. Integradora: visão geral e monitoramento

### 6.1 Visão geral

Primeira tela da equipe. Mostra a carteira inteira:

- **Potência agora**, **gerado hoje** e **gerado no mês** (com o percentual do esperado até hoje);
- **Usinas que precisam de atenção** e **faturas com divergência**;
- lista **Precisa de atenção**, ordenada pela gravidade, com link para cada caso;
- gráficos: geração da carteira em 30 dias × esperado, potência de hoje a cada 15 minutos, desempenho de cada
  usina nos últimos 7 dias, geração mensal em 12 meses e potência por fabricante.

### 6.2 Usinas agora

Todas as usinas, **agrupadas por cliente**, de qualquer fabricante. Para cada uma: situação, potência agora, energia
de hoje contra o esperado do dia e um minigráfico de 14 dias.

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

O selo **dados de demonstração** indica equipamentos sem credencial: os números são simulados (veja a
[seção 17](#17-integrações-com-inversores)). Quando aparece **demonstração com clima real**, a simulação segue a
irradiação solar real do município: um dia nublado em Natal aparece como um dia de pouca geração.

## 7. Integradora: cadastro completo de um cliente

A análise da conta só é tão boa quanto o cadastro. A ordem recomendada:

```
Cliente → Consentimento LGPD → UC(s) → Usina(s) → Arranjos de módulos → Inversor(es)
        → Medidor próprio → Faturas → Acesso ao portal
```

A ficha de cada cliente mostra, na aba **Resumo**, o quadro **Cadastro para auditoria**, com o percentual completo
e os oito passos:

1. Titular completo (CPF/CNPJ, segmento e contato)
2. Consentimento LGPD
3. Unidade consumidora com número, código do cliente e perfil tarifário
4. Usina com data do protocolo (define GD1/GD2)
5. Inversor com API do fabricante (fonte 1)
6. Medidor próprio (fonte 2)
7. 12 faturas no histórico (fonte 3 e linha de base da economia)
8. Acesso ao portal

### 7.1 Cliente

**Clientes → Novo cliente.** Os campos estão em seções:

- **Titular**: tipo (PF/PJ), nome ou razão social, nome fantasia, CPF/CNPJ (validado), segmento e atividade.
- **Contato**: pessoa de contato, e-mail, telefone, WhatsApp.
- **Endereço.**
- **Perfil de uso**: horário de funcionamento (ajuda a interpretar quanto da geração é consumida na hora),
  cliente desde, observações.

Ao salvar, a **ficha do cliente** abre com as abas: Resumo, Unidades consumidoras, Usinas, Equipamentos, Faturas e
Acesso e LGPD. No topo, etiquetas resumem o perfil: segmento, subgrupo e ligação de cada UC, GD de cada usina,
potência total, fabricantes e se há medidor próprio.

### 7.2 Consentimento LGPD

Na aba **Acesso e LGPD**, informe a versão do termo e marque o aceite. O sistema registra data, hora, IP e quem
registrou. Sem consentimento, o cliente aparece como "pendente" na lista.

### 7.3 Unidade consumidora

Na ficha do cliente, botão **UC**. Tenha a fatura de energia em mãos:

- **Identificação**: concessionária, número da UC (instalação), código do cliente (como impresso na fatura),
  apelido e e-mail de recebimento da fatura (por exemplo, `faturas+uc7010453067@suaempresa.com.br`).
- **Perfil tarifário**: grupo, subgrupo, classe, tipo de ligação, tensão, modalidade tarifária, tarifa social e
  demanda contratada (grupo A; na modalidade azul, também a demanda na ponta).
- **Medidor da concessionária**: número, **constante** (fator impresso na fatura) e se o medidor é bidirecional.
- **Linha de base**: consumo médio mensal antes da usina.
- **Endereço da UC** (o município define a CIP) e coordenadas.

O sistema impede combinações inválidas, como tarifa verde em grupo B ou subgrupo B3 em grupo A.

A página da UC mostra, na aba **Perfil e regras**, quais regras de auditoria estão ativas e o que falta para ligar
as desligadas.

### 7.4 Usina

Na ficha do cliente, botão **Usina** (a lista de UCs já vem filtrada para aquele cliente):

- **Identificação**: nome, UC geradora e modalidade de GD (junto à carga, autoconsumo remoto, geração
  compartilhada, múltiplas UCs).
- **Acesso e enquadramento**: data e número do protocolo, parecer de acesso, data de conexão. O enquadramento
  **GD1/GD2 é calculado pela data do protocolo**. Para fixar outro valor, marque "enquadramento manual"; se ele
  divergir da data, a página da usina avisa.
- **Dados técnicos**: potência (kWp), potência de inversores, número de módulos, tipo de instalação, inclinação,
  azimute e performance ratio esperado (padrão 0,78).
- **Local e investimento.**
- **Geração esperada (kWh/mês)**: os 12 valores do projeto. É a régua do monitoramento; sem eles, o sistema estima
  pela potência e pelas horas de sol de Natal.
- **UCs beneficiárias (rateio)**: para autoconsumo remoto e geração compartilhada. A soma tem de dar 100%.

### 7.5 Arranjos de módulos

Na página da usina, **Adicionar arranjo**: fabricante, modelo, potência do módulo (Wp), quantidade, inclinação,
azimute e garantia. A **potência da usina e o número de módulos são recalculados** pela soma dos arranjos.

### 7.6 Inversor

Na página da usina, **Inversor**:

- **Equipamento**: marca, modelo, número de série, tipo (string, micro, híbrido, central), potência nominal,
  fases, MPPTs, instalação e garantia.
- **Conexão com a API do fabricante**: escolha a API (Growatt, Huawei, SolarEdge, Fronius, GoodWe, Deye), o ID da
  planta no portal do fabricante e as credenciais em JSON. Os formatos estão na [seção 17](#17-integrações-com-inversores).

Sem credencial, o inversor funciona com dados de demonstração. Isso permite cadastrar a marca certa hoje e
completar a credencial depois.

### 7.7 Medidor próprio (ESP)

Na página da UC, **Vincular medidor próprio** (ou aba **Perfil e regras → Novo medidor**):

- **Dispositivo**: nome, tipo (ESP32 com sensores de corrente, medidor inteligente, gateway), **ponto de medição**,
  fabricante, modelo, série, fases, faixa dos sensores, intervalo de envio e usina associada.
- **Origem dos dados**: ESP32 (o dispositivo envia para a nossa API), API HTTP do fabricante ou MQTT.

| Ponto de medição | O que mede |
|---|---|
| Entrada da rede (bidirecional) | Quanto entrou da rede e quanto saiu para ela. É o caso mais comum. |
| Carga | O consumo total da instalação. |
| Rede e carga | Os dois, com dois conjuntos de sensores. |

Ao salvar um medidor com origem **ESP32**, o sistema mostra **uma única vez** o token do dispositivo e as instruções
de envio. Copie na hora. Se perder, abra **token e instruções** e gere outro; o anterior para de funcionar
imediatamente.

### 7.8 Créditos

Na página da UC, aba **Créditos**: registre o saldo de créditos por mês de geração. A validade (60 meses) é calculada
sozinha.

### 7.9 Acesso ao portal

Na ficha do cliente, aba **Acesso e LGPD → Criar acesso**: usuário, e-mail e senha inicial (mínimo de 8 caracteres).
Passe os dados ao cliente. A ficha mostra quando ele entrou pela última vez.

## 8. Integradora: faturas

### 8.1 Lista de faturas

Menu **Faturas**: todas as faturas da carteira, com filtro por situação (Recebida, Em revisão, Confere,
Divergência) e busca por cliente ou UC. Cada linha mostra a janela de leitura, consumo, injetado, compensado e total.
Clique na UC para abrir a análise daquela fatura.

### 8.2 Lançar uma fatura

**Lançar fatura** (no menu Faturas ou na página da UC). Os campos seguem a ordem da conta de energia:

- **Fatura**: UC, mês de referência, vencimento, total e situação; anexo do PDF (opcional).
- **Leitura**: datas e valores das leituras anterior e atual, e a constante. **As datas são essenciais**: é por
  elas que o sistema soma a geração do inversor e as leituras do medidor próprio.
- **Energia**: consumo, consumo na ponta, injetada, compensada, saldo de créditos, modalidade GD, custo de
  disponibilidade e bandeira.
- **Valores**: Fio B, ICMS, PIS/COFINS e CIP.
- **Grupo A**: demanda contratada e medida, ultrapassagem e reativo.

Ao salvar, o sistema abre a análise daquela fatura. Ao lançar a partir da página da UC, constante, custo de
disponibilidade e demanda contratada já vêm preenchidos pelo cadastro.

> A leitura automática do PDF e a captura das faturas pelo e-mail entram nas próximas fases e vão preencher estes
> mesmos campos.

## 9. Análise da conta: as três fontes

Abra a UC e fique na aba **Análise da conta**. No seletor de período, escolha a fatura (cada opção indica quantos
indícios tem).

### 9.1 Os três quadros

| Fonte | O que mostra |
|---|---|
| **1. Inversor** | Gerado na janela, esperado do projeto e desempenho (%). |
| **2. Medidor próprio** | Consumido da rede, injetado na rede, consumo da carga (se medido) e % de dias com leitura. |
| **3. Concessionária** | Consumo faturado, injetado, compensado e total cobrado, com o selo "confere" ou o número de indícios. |

Uma fonte ausente aparece tracejada, com o atalho para cadastrá-la.

### 9.2 Os números derivados

- **Autoconsumo** = gerado (inversor) − injetado (fatura). É a energia usada na hora.
- **Consumo real da instalação** = consumo medido na carga, ou, se não houver, consumido da rede + autoconsumo.
- **Atendido pelo sol** = (autoconsumo + compensado) ÷ consumo real.
- **Economia estimada** = consumo real × tarifa de referência − total pago. É uma **estimativa**: o valor
  regulatório a recuperar é calculado pelo motor de regras (fase 5).

### 9.3 Indícios para auditoria

O sistema compara as fontes e aponta o que investigar:

| Indício | Gravidade | O que significa |
|---|---|---|
| Injeção maior que a geração do inversor | alta | A fatura diz que foi injetado mais do que a usina gerou. Erro de leitura ou de API. |
| Consumo faturado X% acima do medido | alta | A concessionária cobra mais do que o medidor próprio registrou. Se a razão é quase fixa (1,25; 1,5; 2…), suspeita de constante errada. |
| Constante na fatura difere do cadastro | alta | A fatura multiplica a leitura por um fator diferente do medidor instalado. |
| Injeção não compensada | alta | Houve injeção e consumo compensável, mas a compensação ficou abaixo do possível. |
| Injeção da fatura diverge do medidor próprio | média | Diferença acima de 5% entre o injetado na fatura e o medido. |
| Leitura × constante não fecha | média | (leitura atual − anterior) × constante ≠ consumo cobrado. |
| Ultrapassagem de demanda | média | Grupo A: demanda medida acima da contratada. |
| Geração abaixo do esperado no período | média | Gerou menos de 80% do esperado na janela. |
| Cobrança de energia reativa | baixa | Fator de potência abaixo de 0,92. Avaliar banco de capacitores. |

### 9.4 Gráficos da análise

- **Para onde foi a energia**: consumo real (autoconsumo + rede) e a linha da geração, fatura a fatura.
- **Consumo: concessionária × medidor próprio**: se a fatura fica sempre acima por um fator fixo, suspeite da
  constante.
- **Injetado × compensado.**
- **Quanto pagou × quanto pagaria sem solar** (estimativa).

## 10. Equipe, acessos e configurações

Disponível para o **gestor** (e para o administrador geral atuando como a integradora).

- **Equipe e acessos**: lista gestores, técnicos e clientes com acesso ao portal. O gestor cria e edita usuários
  da própria integradora; não pode criar administradores nem usuários de outra integradora.
- **Configurações**: dados da empresa, responsável técnico (nome e CREA, usados no laudo), contato e **marca do
  portal** (logo e cor). A cor também aparece no painel da equipe.

## 11. Portal do cliente final

Pensado para o celular, com o logo e a cor da integradora:

- **Início**: quanto as usinas geraram hoje, situação geral, potência agora e geração do mês; curva de hoje; um
  bloco por usina com o percentual do esperado para o dia.
- **Sua conta do mês**, em formato de recibo: quanto pagaria sem solar, quanto pagou, quanto as usinas geraram, que
  parte do consumo o sol atendeu e a economia. O selo **Conta conferida** aparece quando a análise não encontrou
  indício grave.
- **Economia nos últimos 12 meses** e gráficos de geração mensal e de custo.
- **Página de cada usina**: potência agora, curva de hoje, 30 dias e 12 meses.
- No rodapé, o contato da integradora.

Valores "sem solar" e "economia" são estimativas e estão identificados como tal.

## 12. Perguntas frequentes

**Onde vejo se um cliente é do grupo A ou B, quantos kWp tem e qual inversor usa?**
No topo da ficha do cliente (etiquetas), na aba Unidades consumidoras (perfil tarifário) e na aba Usinas. Na lista
de clientes, as colunas Perfil, Usinas e kWp mostram o mesmo de relance.

**Por que aparece "dados de demonstração"?**
O equipamento está sem credencial de API (ou com a API "Demonstração"). Os números são simulados. Configure a
credencial (seção 7.6) para ler os dados reais.

**Cadastrei a usina, mas ela aparece como "Sem inversor".**
Vincule o inversor na página da usina.

**A análise diz "sem fatura neste período".**
Lance a fatura da UC com as datas de leitura corretas. Sem fatura, a análise usa meses civis com inversor e medidor.

**Perdi o token do ESP.**
Na UC, aba Perfil e regras, abra "token e instruções" do medidor e gere um novo. Atualize o firmware com o novo
token.

**O cliente diz que não consegue entrar.**
Em Equipe e acessos, confira se o usuário está ativo e redefina a senha na edição.

---

# Parte II: Manual técnico

## 13. Arquitetura

| Camada | Tecnologia |
|---|---|
| Linguagem e framework | Python 3.12, Django 5.1 |
| Banco | PostgreSQL 16 (produção) ou SQLite (desenvolvimento) |
| Tarefas | Celery 5 + Redis (worker e beat) |
| Interface | Templates Django + HTMX 2.0.4 + CSS próprio; gráficos com Chart.js 4.4.1 (servidos de `static/vendor/`, sem CDN) |
| PDF | pdfplumber (leitura) e WeasyPrint (laudos), nas próximas fases |
| Criptografia de campos | `cryptography` (Fernet) |
| Testes e lint | pytest + pytest-django; ruff |
| Implantação | Docker Compose: `web`, `worker`, `beat`, `postgres`, `redis` |

### 13.1 Aplicações Django (`apps/`)

| App | Responsabilidade |
|---|---|
| `core` | Integradora (tenant), `TenantModel`, middleware de tenant, mixins de acesso, campo criptografado, log de auditoria, construtor de gráficos, `seed_demo` |
| `accounts` | Usuário com perfil (`papel`), formulário de usuário, telas de equipe |
| `cadastro` | Concessionária, cliente, consentimento, UC, usina, rateio, arranjos, inversor, medidor, lotes de crédito; catálogo de requisitos das regras |
| `integracoes` | Interfaces, implementações fictícias e conectores reais; `registro.py` escolhe a implementação |
| `monitoramento` | Coleta, séries, situação das usinas, curva do dia, API do ESP, tarefas Celery, painéis |
| `faturas` | Fatura da concessionária, lançamento manual |
| `analise` | Cruzamento das três fontes (`services.py`) e gráficos da análise |
| `plataforma` | Telas do administrador geral |
| `portal` | Telas do cliente final |

### 13.2 Rotas principais

| Rota | Perfil | Tela |
|---|---|---|
| `/entrar/`, `/sair/` | todos | Login e logout |
| `/plataforma/…` | administrador geral | Visão, integradoras, usuários, integrações, logs |
| `/painel/` | equipe | Visão geral |
| `/usinas/` | equipe | Usinas agora |
| `/cadastro/…` | equipe | Clientes, UCs, usinas, equipamentos, configurações |
| `/faturas/…` | equipe | Lista e lançamento |
| `/equipe/…` | gestor | Equipe e acessos |
| `/meu/…` | cliente final | Portal |
| `/api/medidores/medicoes` | dispositivo (token) | Recebe medições do ESP |
| `/admin/` | administrador geral | Django admin |

## 14. Instalação

### 14.1 Desenvolvimento local, sem Docker

Requisitos: Python 3.12 e Git.

```bash
git clone https://github.com/niviton/FaturaCerta.git
cd FaturaCerta
python -m venv .venv
.venv/Scripts/pip install -r requirements.txt        # Linux/macOS: .venv/bin/pip
.venv/Scripts/python manage.py migrate
.venv/Scripts/python manage.py seed_demo
.venv/Scripts/python manage.py runserver
```

Sem `DATABASE_URL`, usa `db.sqlite3`. Sem `REDIS_URL`, as tarefas rodam de forma síncrona e o beat não é necessário.
O WeasyPrint não é instalado no Windows (depende de bibliotecas do sistema); ele roda dentro da imagem Docker.

### 14.2 Docker Compose

```bash
cp .env.example .env          # edite as variáveis
docker compose up --build -d
docker compose exec web python manage.py seed_demo      # opcional: dados de demonstração
docker compose exec web python manage.py createsuperuser  # para um administrador geral real
```

O contêiner `web` aplica as migrações e coleta os arquivos estáticos ao subir, e serve com Gunicorn na porta 8000.
`worker` e `beat` usam a mesma imagem. Os volumes `pgdata` e `media` guardam banco e arquivos enviados.

### 14.3 Produção: lista de verificação

- `DJANGO_DEBUG=0`, `DJANGO_SECRET_KEY` longa e aleatória, `DJANGO_ALLOWED_HOSTS` com o domínio.
- `FIELD_ENCRYPTION_KEY` gerada uma vez e guardada em cofre. **Sem ela, as credenciais ficam ilegíveis se a
  `SECRET_KEY` mudar.**
- HTTPS no proxy reverso; com `DEBUG=0` o Django exige cookies seguros e envia HSTS.
- Backup diário do PostgreSQL e do volume `media`.
- Não rode `seed_demo` em produção. Crie o primeiro administrador com `createsuperuser` e defina o perfil
  "Administrador geral".

### 14.4 Dados de demonstração

```bash
python manage.py seed_demo [--dias 400] [--limpar]
```

Cria duas integradoras, seis clientes com cadastro completo (um caso de auditoria cada), usinas de seis
fabricantes, medidores próprios, geração diária, curva de hoje, leituras do medidor e 12 faturas por UC. Com
internet, antes de gerar busca o clima real de cada município (seção 17.2), e a geração segue o sol de verdade.
As três fontes saem da mesma simulação, por isso os indícios aparecem coerentes. `--limpar` apaga e recria. Senha de todos
os usuários: `FaturaCerta@2026`. As tarifas usadas são fictícias.

### 14.5 Manuais em PDF

Os textos dos manuais ficam em Markdown: `docs/MANUAL.md` (administrador geral, completo) e
`docs/manuais/manual_integradora.md` (integradora). Depois de editar um deles, gere os PDFs de novo:

```bash
python manage.py gerar_manuais                  # os dois
python manage.py gerar_manuais integradora      # só um
python manage.py gerar_manuais --html           # também salva o HTML intermediário para revisão
```

O comando usa o WeasyPrint (presente na imagem Docker) ou, na falta dele, o Edge/Chrome em modo headless
(Windows). Os PDFs vão para `docs/manuais/`, são versionados no Git e servidos pelo sistema em `/manuais/`, com
acesso conforme o perfil.

## 15. Configuração (variáveis de ambiente)

| Variável | Padrão | Uso |
|---|---|---|
| `DJANGO_SECRET_KEY` | valor inseguro de desenvolvimento | Chave do Django. Obrigatória em produção. |
| `DJANGO_DEBUG` | `1` | `0` em produção. |
| `DJANGO_ALLOWED_HOSTS` | `localhost,127.0.0.1,testserver` | Domínios aceitos, separados por vírgula. |
| `DJANGO_SSL_REDIRECT` | `1` | Com `DEBUG=0`, redireciona para HTTPS. |
| `DATABASE_URL` | SQLite | Ex.: `postgres://usuario:senha@host:5432/banco`. |
| `REDIS_URL` | vazio | Broker do Celery. Vazio: tarefas síncronas. |
| `FIELD_ENCRYPTION_KEY` | derivada da `SECRET_KEY` | Chave Fernet dos campos criptografados. |
| `MONITOR_HORAS_SEM_COMUNICACAO` | `3` | Horas sem leitura para "sem comunicação". |
| `MONITOR_LIMIAR_ABAIXO` | `0.8` | Fração do esperado em 7 dias para "abaixo do esperado". |
| `CLIMA_PROVIDER` | `openmeteo` | Clima real na demonstração. Vazio desliga. Open-Meteo gratuito só para uso não comercial. |
| `INVERTER_PROVIDER` | `fake` | Provedor usado quando o inversor não indica um. |
| `METER_PROVIDER` | `fake` | Idem para medidores. |
| `ANTHROPIC_API_KEY`, `ANTHROPIC_MODEL` | vazio, `claude-sonnet-5-5` | IA de leitura de fatura e assistente (próximas fases). |
| `GMAIL_CLIENT_ID`, `GMAIL_CLIENT_SECRET` | vazio | Leitura de faturas por e-mail (próxima fase). |
| `NOTIFY_EMAIL_PROVIDER` | `fake` | `smtp` envia de verdade pelo `EMAIL_BACKEND`. |
| `EMAIL_BACKEND`, `DEFAULT_FROM_EMAIL` | console | Configuração de e-mail do Django (use também `EMAIL_HOST` etc.). |
| `NOTIFY_WHATSAPP_PROVIDER` | `fake` | `cloud` usa a WhatsApp Business Cloud API. |
| `WHATSAPP_TOKEN`, `WHATSAPP_PHONE_ID`, `WHATSAPP_TEMPLATE` | vazio, vazio, `alerta_usina` | Credenciais e template aprovado na Meta. |

A **tarifa de referência** (só para estimativas de economia) não é variável de ambiente: fica em cada
concessionária, editável no Django admin.

## 16. Modelo de dados

```
Integradora (tenant)
 ├── User (papel: admin | gestor | tecnico | cliente)
 └── Cliente ── ConsentimentoLGPD
      └── UnidadeConsumidora ── Concessionaria (catálogo global)
           ├── Usina (uc_geradora) ── ArranjoModulos
           │    ├── Inversor ── GeracaoDiaria, AmostraPotencia, StatusAtual
           │    └── Rateio ── UC beneficiária
           ├── Medidor ── MedicaoBruta → LeituraMedidor
           ├── Fatura
           └── LoteCredito
LogAuditoria (global)
```

Pontos importantes:

- Todo modelo que pertence a uma integradora herda de `TenantModel` (campo `integradora` e o queryset
  `da_integradora()`). Modelos-filho (inversor, medidor, rateio, arranjo) herdam o tenant pela usina ou pela UC.
- `Usina.save()` recalcula o enquadramento pela data do protocolo, salvo se `enquadramento_manual`.
- `Usina.recalcular_potencia()` soma arranjos e inversores.
- `Medidor` guarda só o **hash** SHA-256 do token do dispositivo e um prefixo para identificação.
- `Inversor.credenciais` e `Medidor.credenciais` usam `EncryptedJSONField`.
- `Fatura` é única por (UC, mês de referência). `consumo_pela_leitura` e `leitura_confere` verificam
  (atual − anterior) × constante.

## 17. Integrações com inversores

Cada fabricante tem um conector em `apps/integracoes/inversores_reais.py`, que implementa a interface
`ProvedorInversor` (`status()`, `geracao_diaria()` e, opcionalmente, `curva_do_dia()`), devolvendo os formatos
internos `StatusInversor` e `GeracaoDia`.

**Regra de escolha** (`registro.py`): usa o conector real se o inversor indica um fabricante **e** as credenciais e
o `id_externo` estão completos; caso contrário, usa `FakeInversor` e a tela mostra "dados de demonstração".

### 17.1 Credenciais por fabricante

Informe no cadastro do inversor (campo "Credenciais da API (JSON)") e o ID no campo "ID no portal do fabricante":

| Fabricante | JSON de credenciais | ID no portal |
|---|---|---|
| Growatt | `{"token": "..."}` | `plant_id` |
| Huawei FusionSolar | `{"usuario": "...", "senha_api": "..."}` (conta de API Northbound) | `stationCode` |
| SolarEdge | `{"api_key": "..."}` | `site_id` |
| Fronius | `{"access_key_id": "...", "access_key_value": "..."}` | `pvSystemId` |
| GoodWe (SEMS) | `{"usuario": "...", "senha": "..."}` | `powerstation_id` |
| Deye / Solarman | `{"app_id": "...", "app_secret": "...", "email": "...", "senha_sha256": "..."}` | `stationId` |

Os endpoints seguem a documentação pública de cada fabricante e estão marcados `CONFIRMAR` no código: **nenhum foi
validado ainda com uma conta real**. A GoodWe não oferece API aberta a terceiros; é preciso acordo com o fabricante.
A SolarEdge limita a 300 chamadas por dia por chave.

Para validar um conector: cadastre a credencial, use **Plataforma → Integrações → Testar** e compare com o portal
do fabricante. Erros aparecem na coluna "Último dado" e na página da usina.

### 17.2 Implementação fictícia (demonstração com clima real)

`FakeInversor` gera dados determinísticos (mesma entrada, mesmo resultado). Quando há **clima real** gravado,
a geração segue o sol de verdade do município da usina:

- energia do dia = kWp × irradiação do dia (kWh/m²) × performance ratio da usina;
- potência agora = kWp × irradiância da hora (W/m²) ÷ 1000 × performance ratio, interpolada a cada 15 minutos.

O clima vem do **Open-Meteo** (sem chave), por região de 0,1° (~11 km), usando as coordenadas da usina, depois as
da UC e, na falta das duas, Natal. Fica gravado no banco (`ClimaDiario`, `ClimaHorario`) e é atualizado a cada
hora pela tarefa `atualizar_clima`. Manualmente:

```bash
python manage.py atualizar_clima --dias 400 --regerar   # busca o histórico e recalcula a demonstração
```

> O Open-Meteo gratuito é **só para uso não comercial**. Em produção comercial, contrate o plano pago ou troque a
> fonte (PVGIS, INMET). `CLIMA_PROVIDER=` (vazio) desliga e volta ao modelo sintético.

Sem clima real (sem internet ou desligado), usa o modelo sintético: geração esperada do projeto (ou kWp × horas de
sol de Natal × 0,78), clima regional sorteado e curva em sino entre 5h30 e 17h30.

Nas telas, o selo muda para **"demonstração com clima real"**. Cenários de demonstração ficam no JSON de
credenciais:

```json
{"cenario": "parada", "desde": "2026-10-20"}
{"cenario": "baixa", "fator": 0.6}
{"cenario": "offline"}
```

### 17.3 Adicionar um fabricante

1. Crie a classe em `inversores_reais.py`, herdando de `ProvedorReal`, com `codigo`, `nome`,
   `campos_obrigatorios`, `status()` e `geracao_diaria()`.
2. Registre em `PROVEDORES_REAIS`.
3. Acrescente a opção em `PROVEDORES_INVERSOR` (`apps/cadastro/models.py`).
4. Escreva um teste com a resposta da API simulada (veja `test_solaredge_mapeia_campos`).

## 18. Medidor próprio: ESP32 e API de medições

### 18.1 Fluxo

```
ESP32 ──POST a cada N s──▶ /api/medidores/medicoes ──▶ MedicaoBruta (contadores acumulados)
                                                         │  tarefa a cada 15 min
                                                         ▼
                                                  LeituraMedidor (energia por dia = máx − mín)
                                                         │
                                                         ▼
                                              Análise da conta (fonte 2)
```

### 18.2 Contrato da API

```
POST /api/medidores/medicoes
Authorization: Bearer <token do dispositivo>
Content-Type: application/json
```

Corpo: um objeto ou uma lista de até 500 objetos (para reenviar o que ficou guardado sem conexão):

```json
{
  "momento": "2026-11-01T14:30:00-03:00",
  "potencia_w": -1830.5,
  "importacao_kwh": 15234.120,
  "exportacao_kwh": 9012.450,
  "carga_kwh": 20110.300,
  "tensao_v": 221.4,
  "corrente_a": 8.3,
  "fator_potencia": 0.97
}
```

| Campo | Obrigatório | Observação |
|---|---|---|
| `momento` | não | ISO 8601. Sem ele, vale a hora do servidor. Mais de 5 minutos no futuro é rejeitado. |
| `potencia_w` | não | Positiva importando da rede, negativa injetando. |
| `importacao_kwh`, `exportacao_kwh`, `carga_kwh` | não | Contadores **acumulados**. Não zere a cada envio. |
| `tensao_v`, `corrente_a`, `fator_potencia` | não | Informativos. |

| Resposta | Quando |
|---|---|
| `201 {"recebidas": n, "intervalo_s": 60}` | Sucesso. `intervalo_s` é o intervalo cadastrado. |
| `400 {"erro": "..."}` | JSON inválido, valor inválido, lista vazia ou com mais de 500 itens, momento no futuro. |
| `401 {"erro": "token inválido"}` | Token ausente ou errado. |

Medições repetidas (mesmo dispositivo e mesmo momento) são ignoradas.

### 18.3 Firmware de exemplo

`docs/esp32/medidor_faturacerta.ino`: ESP32 com sensor SCT-013 e transformador de tensão ZMPT101B, biblioteca
EmonLib. Calcula a potência real, acumula importação e exportação, guarda os contadores na flash e envia no
intervalo configurado. Preencha Wi-Fi, URL, token e calibração no topo do arquivo.

> A instalação em quadro elétrico deve ser feita por profissional habilitado.

### 18.4 Outras origens

- **HTTP**: `MedidorHTTP` espera `GET {url_base}/medidores/{id}/diario?inicio=…&fim=…` devolvendo
  `{"itens": [{"data", "importacao_kwh", "exportacao_kwh", "carga_kwh"}]}`. Ajuste o mapeamento por fabricante.
- **MQTT**: a estrutura existe; o assinante que grava as leituras entra quando houver um medidor MQTT real.

## 19. Tarefas agendadas

Definidas em `CELERY_BEAT_SCHEDULE` (`config/settings.py`):

| Tarefa | Frequência | O que faz |
|---|---|---|
| `coletar_status_todos` | 15 min | Status instantâneo de cada inversor; grava uma amostra de potência. |
| `coletar_curvas_hoje` | 30 min | Curva de potência do dia, quando o fabricante oferece. |
| `coletar_geracao_todos` | 6 h | Geração diária dos últimos 3 dias (corrige dias parciais) e leituras dos medidores por API. |
| `consolidar_medicoes_esp` | 15 min | Converte as medições brutas do ESP em leituras diárias. |
| `atualizar_clima` | 1 h | Clima real (Open-Meteo) das regiões com usinas; refaz a curva e o status de hoje. |

Para rodar manualmente (por exemplo, depois de cadastrar credenciais):

```bash
python manage.py shell -c "from apps.monitoramento import tasks; tasks.coletar_geracao_todos(dias=35)"
```

## 20. Regras de monitoramento e de análise

### 20.1 Situação da usina (`monitoramento/services.py`, `resumir_usina`)

Avaliadas nesta ordem:

1. **Sem comunicação**: algum inversor sem leitura há mais de `MONITOR_HORAS_SEM_COMUNICACAO`.
2. **Parada**: algum inversor reporta offline, ou potência e energia zeradas entre 8h e 16h.
3. **Abaixo do esperado**: geração dos últimos 7 dias < `MONITOR_LIMIAR_ABAIXO` × esperado.
4. **Sem sol agora**: fora do horário de sol, potência zero.
5. **Gerando**: nos demais casos.

Esperado por dia: geração esperada do mês ÷ dias do mês; sem ela, kWp × horas de sol de Natal × performance
ratio. Essa estimativa serve só ao monitoramento, nunca a cálculo regulatório.

### 20.2 Balanço e indícios (`analise/services.py`)

`balanco_periodo(uc, inicio, fim, fatura)` soma, na janela de leitura (do dia seguinte à leitura anterior até a
leitura atual, inclusive):

- a geração das usinas **junto à carga** daquela UC;
- as leituras dos medidores próprios da UC (e a fração de dias cobertos).

Indícios que dependem do medidor próprio só são avaliados com pelo menos 90% dos dias cobertos. Limiares:
divergência entre fontes acima de 5%; injeção acima da geração por mais de 5 kWh; compensação abaixo do possível
por mais de 5 kWh; leitura × constante com diferença acima de 1 kWh; geração abaixo de 80% do esperado.

**Regra de ouro**: a análise trabalha em kWh e aponta indícios. Compensação, Fio B e diferença em R$ são calculados
pelo motor de regras com tabelas regulatórias com vigência (fase 5), de forma reproduzível. A IA, quando entrar,
só lê faturas e redige textos; nunca calcula valores regulatórios.

### 20.3 Requisitos das regras (`cadastro/requisitos.py`)

Para cada UC, lista quais regras estão ativas, quais não se aplicam (por exemplo, demanda no grupo B) e quais dados
faltam para ligar as desligadas. É o que alimenta a aba **Perfil e regras** e o aviso de cadastro incompleto.

## 21. Segurança, multiempresa e LGPD

- **Isolamento entre integradoras**: `TenantMiddleware` define `request.tenant` (a integradora do usuário, ou a
  escolhida pelo administrador em "entrar como"). As views da equipe herdam de `EquipeIntegradoraMixin`, que exige
  tenant; querysets filtram por `da_integradora()`; formulários restringem as escolhas de chave estrangeira ao
  tenant. Objetos de outra integradora devolvem 404. Há testes automáticos para isso.
- **Perfis**: `AdminGeralMixin`, `EquipeIntegradoraMixin` (com `apenas_gestor`) e `ClienteFinalMixin`.
- **Credenciais**: criptografadas com Fernet; nunca exibidas; vazias na edição mantêm o valor; ocultas no admin.
- **Token de dispositivo**: gerado com `secrets`, mostrado uma vez, guardado como hash SHA-256.
- **Senhas**: validadores de tamanho mínimo e de senhas comuns do Django.
- **LGPD**: consentimento do titular com data, versão do termo, IP e quem registrou; log de visualização,
  criação, alteração e atuação do administrador.
- **Senhas do portal da concessionária**: o sistema não as guarda e não faz login automático em portais.

## 22. Limitações atuais

| Item | Situação |
|---|---|
| Leitura de fatura em PDF (pdfplumber + IA) e fila de revisão | Próxima fase. Hoje o lançamento é manual. |
| Captura de faturas por Gmail/IMAP | Fase seguinte. |
| Tabelas regulatórias com vigência e motor de regras (Fio B, compensação, R$ a recuperar) | Fase 5. A análise atual é em kWh. |
| Situação da fatura (confere/divergência) | No lançamento manual, é marcada por quem lança. O cálculo automático entra com o motor de regras. |
| Laudo de contestação em PDF | Fase 7. |
| Recomendações de economia e taxa de êxito | Fase 8. |
| Alertas por e-mail/WhatsApp com carência | Fase 9 (as interfaces de notificação já existem). |
| Assistente com IA e servidor MCP | Fase 10. |
| Conectores de inversor | Prontos, mas não validados com contas reais. |
| Tema | Só escuro. |

## 23. Desenvolvimento: testes, lint e convenções

```bash
.venv/Scripts/python -m pytest          # 60 testes
.venv/Scripts/ruff check .
```

Os testes cobrem isolamento entre integradoras, os três perfis, cadastro (validações, GD1/GD2, rateio,
criptografia, arranjos, token do ESP), integrações (fictício determinístico, escolha real × fictício, mapeamento de
campos), monitoramento (situações, curva, coleta), API do ESP e os indícios da análise.

Convenções:

- Código e textos de interface em português; frases em caixa normal, sem letras maiúsculas decorativas.
- Nada regulatório fixo no código: valores vão para tabelas com vigência e fonte.
- Toda integração nova segue o padrão interface + fictício + real, escolhido em `registro.py`.
- Decisões tomadas em pontos ambíguos vão para [`docs/decisoes.md`](decisoes.md).
- Ao mudar modelos, gere a migração (`python manage.py makemigrations`) e inclua no commit.

## 24. Solução de problemas

| Sintoma | Causa provável | O que fazer |
|---|---|---|
| Inversor sempre com "dados de demonstração" | Credencial ou ID incompletos | Preencha os campos da [seção 17.1](#171-credenciais-por-fabricante) e teste em Integrações. |
| "Testar" falha com erro HTTP 401/403 | Credencial errada ou sem permissão de API | Confira no portal do fabricante se a conta tem acesso de API. |
| Usina "sem comunicação" com inversor real | Coleta parada ou API fora do ar | Verifique se `worker` e `beat` estão rodando e o erro na página da usina. |
| ESP recebe 401 | Token errado ou regenerado | Gere outro token e atualize o firmware. |
| ESP envia, mas a análise não mostra a fonte 2 | Consolidação ainda não rodou, ou menos de 90% dos dias cobertos | Aguarde 15 min (ou rode `consolidar_medicoes_esp`) e confira a cobertura. |
| Valores do ESP muito pequenos | Contadores sendo zerados a cada envio | Envie contadores acumulados. |
| "Não foi possível descriptografar o campo" | `FIELD_ENCRYPTION_KEY` ou `SECRET_KEY` trocadas | Restaure a chave original; sem ela, recadastre as credenciais. |
| Administrador vai para "Integradoras" ao abrir o painel | Não escolheu uma integradora | Use "Entrar como" na integradora desejada. |
| Gráficos não aparecem | JavaScript bloqueado ou estáticos não coletados | Em produção, rode `collectstatic`; abra "Ver os números" para ver os dados em tabela. |

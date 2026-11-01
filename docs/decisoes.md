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

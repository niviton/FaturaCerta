# Fontes de dados públicas para testar sem inversor real

Pesquisa feita em 02/11/2026: existe alguma API de inversor gratuita e aberta para conectar ao sistema?

## Resumo

Não existe API de fabricante de inversor aberta e gratuita com dados reais sem conta. Para dados reais de
geração é preciso uma usina própria ou de um cliente, com acesso de API liberado pelo fabricante. Para testes e
demonstração com o clima real, há duas fontes gratuitas e sem chave que funcionaram nos testes.

## Fabricantes de inversor

| Fonte | Situação |
|---|---|
| Fronius Solar.web Query API | Exige chave fornecida pela Fronius (voltada a instaladores; pode ser paga). Há um site de teste da API em `api.solarweb.com/swqapi/index.html`. |
| Growatt | Exige conta e token. Uma biblioteca não oficial cita um "login de demonstração", sem credencial publicada e sem garantia de funcionamento. |
| Huawei, SolarEdge, GoodWe, Deye/Solarman | Exigem conta do cliente ou do instalador. |
| Enphase | Plano gratuito "Watt": 1.000 consultas/mês, 10/min, só dados do site. O dono da usina precisa autorizar o aplicativo. Sem ambiente de testes público. |
| PVOutput.org | Conta gratuita. Ler a usina de outra pessoa parece exigir conta de doador e tem limite baixo de consultas (não confirmado na especificação oficial). |

**Não usar** chaves de API que aparecem em repositórios públicos (há exemplos da Fronius no GitHub): pertencem a
contas de terceiros, e usá-las é acesso sem autorização.

## Fontes gratuitas de dados solares (testadas)

### Open-Meteo: irradiância real, recente e previsão

- Sem chave e sem cadastro. **Gratuito só para uso não comercial**: em produção comercial, usar o plano pago ou
  outra fonte.
- Irradiância no plano dos módulos, hora a hora (`global_tilted_irradiance`, com inclinação e azimute).
- Teste para Natal (inclinação 10°, voltado ao norte):

```
https://api.open-meteo.com/v1/forecast?latitude=-5.795&longitude=-35.209&hourly=global_tilted_irradiance&tilt=10&azimuth=180&past_days=2&forecast_days=1&timezone=America/Fortaleza
```

### PVGIS (Centro Comum de Pesquisa da Comissão Europeia): geração horária simulada

- Sem chave. Gera a produção horária de uma usina de X kWp a partir de dados de satélite (SARAH3) e reanálise
  (ERA5), para anos anteriores.
- Teste para Natal (10 kWp, perdas 14%, ano de 2023):

```
https://re.jrc.ec.europa.eu/api/v5_3/seriescalc?lat=-5.795&lon=-35.209&peakpower=10&loss=14&pvcalculation=1&angle=10&aspect=180&startyear=2023&endyear=2023&outputformat=json
```

## Como usar no FaturaCerta (proposta)

1. **Demonstração com clima real** (implementado, ver D25 em `decisoes.md`): trocar o clima sorteado do `FakeInversor` pela irradiância do Open-Meteo
   (geração = kWp × irradiância × performance ratio). Um dia chuvoso em Natal aparece como dia de pouca geração.
2. **Esperado ajustado pelo clima**: comparar a geração real com o que a irradiância do dia permitia, e não só
   com a média do mês. Separa "gerou pouco porque nublou" de "gerou pouco com sol" (defeito), reduzindo alarmes
   falsos. Vale também quando os inversores reais estiverem conectados.
3. **Inversor real**: pedir a um cliente (ou usar uma usina própria) o acesso de API no aplicativo do fabricante
   e validar o conector daquela marca.

## Fontes

- Open-Meteo: https://open-meteo.com/ e https://open-meteo.com/en/docs/satellite-radiation-api
- PVGIS via pvlib: https://pvlib-python.readthedocs.io/en/stable/reference/generated/pvlib.iotools.get_pvgis_hourly.html
- Enphase: https://developer-v4.enphase.com/developer-plans e https://developer-v4.enphase.com/docs/faq
- Growatt: https://www.home-assistant.io/components/growatt_server/ e https://npmjs.com/package/growatt
- Fronius: https://manualmachine.com/fronius/solarweb/26981106-query-api-interface-documentation
- PVOutput: https://yaleman.github.io/pvoutput/api/

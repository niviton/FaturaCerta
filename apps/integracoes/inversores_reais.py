"""Conectores reais dos fabricantes de inversor.

Cada classe tem autenticação, endpoints e mapeamento de campos para o formato interno.
Só é usada quando as credenciais do inversor estão preenchidas (ver `registro.py`).
Os endpoints seguem a documentação pública de cada fabricante na data da escrita;
marque "CONFIRMAR" ao validar com uma conta real, porque essas APIs mudam com frequência.

Credenciais esperadas (JSON no cadastro do inversor, guardado criptografado):
    growatt:   {"token": "..."}                          id_externo = plant_id
    huawei:    {"usuario": "...", "senha_api": "..."}     id_externo = stationCode   (conta de API Northbound)
    solaredge: {"api_key": "..."}                         id_externo = site_id
    fronius:   {"access_key_id": "...", "access_key_value": "..."}  id_externo = pvSystemId
    goodwe:    {"usuario": "...", "senha": "..."}         id_externo = powerstation_id  (SEMS)
    deye:      {"app_id": "...", "app_secret": "...", "email": "...", "senha_sha256": "..."}  id_externo = stationId
"""

import datetime
import json
import urllib.error
import urllib.parse
import urllib.request
from decimal import Decimal

from django.core.cache import cache
from django.utils import timezone

from .base import ErroIntegracao, GeracaoDia, IntegracaoNaoConfigurada, ProvedorInversor, StatusInversor

TIMEOUT = 20


def http_json(metodo: str, url: str, *, params=None, corpo=None, headers=None) -> dict:
    if params:
        url = f"{url}?{urllib.parse.urlencode(params)}"
    dados = json.dumps(corpo).encode() if corpo is not None else None
    req = urllib.request.Request(url, data=dados, method=metodo,
                                 headers={"Content-Type": "application/json", **(headers or {})})
    try:
        with urllib.request.urlopen(req, timeout=TIMEOUT) as resp:
            texto = resp.read().decode()
            return {"_headers": dict(resp.headers), **(json.loads(texto) if texto else {})}
    except urllib.error.HTTPError as exc:
        raise ErroIntegracao(f"{url} respondeu {exc.code}") from exc
    except (urllib.error.URLError, TimeoutError, json.JSONDecodeError) as exc:
        raise ErroIntegracao(f"falha ao acessar {url}: {exc}") from exc


def d(v) -> Decimal:
    return Decimal(str(v or 0)).quantize(Decimal("0.01"))


class ProvedorReal(ProvedorInversor):
    campos_obrigatorios: tuple[str, ...] = ()

    def __init__(self, inversor):
        super().__init__(inversor)
        faltando = [c for c in self.campos_obrigatorios if not self.credenciais.get(c)]
        if faltando or not inversor.id_externo:
            raise IntegracaoNaoConfigurada(
                f"{self.nome}: faltam {', '.join(faltando + ([] if inversor.id_externo else ['id_externo']))}"
            )
        self.id = inversor.id_externo

    def _agora(self):
        return timezone.now()


class GrowattProvedor(ProvedorReal):
    """Growatt OpenAPI v1. CONFIRMAR: base varia por região (openapi.growatt.com / openapi-us...)."""

    codigo, nome = "growatt", "Growatt"
    campos_obrigatorios = ("token",)
    base = "https://openapi.growatt.com/v1"

    def _get(self, caminho, **params):
        r = http_json("GET", f"{self.base}/{caminho}", params=params, headers={"token": self.credenciais["token"]})
        if r.get("error_code") not in (0, None):
            raise ErroIntegracao(f"Growatt: {r.get('error_msg')}")
        return r.get("data", {})

    def status(self):
        data = self._get("plant/data", plant_id=self.id)
        online = data.get("status", 1) != 0  # CONFIRMAR: 0 = offline
        return StatusInversor(online, d(data.get("current_power", 0)) / 1000, d(data.get("today_energy")),
                              self._agora())

    def geracao_diaria(self, inicio, fim):
        data = self._get("plant/energy", plant_id=self.id, start_date=inicio.isoformat(),
                         end_date=fim.isoformat(), time_unit="day")
        return [GeracaoDia(datetime.date.fromisoformat(e["date"]), d(e["energy"])) for e in data.get("energies", [])]


class HuaweiProvedor(ProvedorReal):
    """FusionSolar Northbound (thirdData). Login devolve xsrf-token no cabeçalho."""

    codigo, nome = "huawei", "Huawei FusionSolar"
    campos_obrigatorios = ("usuario", "senha_api")
    base = "https://intl.fusionsolar.huawei.com/thirdData"

    def _token(self):
        chave = f"huawei-token-{self.credenciais['usuario']}"
        tok = cache.get(chave)
        if not tok:
            r = http_json("POST", f"{self.base}/login",
                          corpo={"userName": self.credenciais["usuario"], "systemCode": self.credenciais["senha_api"]})
            tok = r["_headers"].get("xsrf-token") or r["_headers"].get("XSRF-TOKEN")
            if not tok:
                raise ErroIntegracao("Huawei: login sem xsrf-token")
            cache.set(chave, tok, 25 * 60)
        return tok

    def _post(self, caminho, corpo):
        r = http_json("POST", f"{self.base}/{caminho}", corpo=corpo, headers={"XSRF-TOKEN": self._token()})
        if not r.get("success"):
            raise ErroIntegracao(f"Huawei: {r.get('failCode')} {r.get('message')}")
        return r.get("data", [])

    def status(self):
        kpi = self._post("getStationRealKpi", {"stationCodes": self.id})[0]["dataItemMap"]
        # real_health_state: 1 desconectado, 2 com falha, 3 saudável
        online = int(kpi.get("real_health_state", 3)) != 1
        # CONFIRMAR: potência instantânea vem de getDevRealKpi (inversor); aqui só a energia do dia
        return StatusInversor(online, d(0), d(kpi.get("day_power")), self._agora())

    def geracao_diaria(self, inicio, fim):
        out, mes = [], inicio.replace(day=1)
        while mes <= fim:
            ms = int(datetime.datetime.combine(mes, datetime.time(), tzinfo=datetime.UTC).timestamp() * 1000)
            for item in self._post("getKpiStationDay", {"stationCodes": self.id, "collectTime": ms}):
                dia = datetime.datetime.fromtimestamp(item["collectTime"] / 1000, tz=datetime.UTC).date()
                if inicio <= dia <= fim:
                    out.append(GeracaoDia(dia, d(item["dataItemMap"].get("inverter_power"))))
            mes = (mes + datetime.timedelta(days=32)).replace(day=1)
        return out


class SolarEdgeProvedor(ProvedorReal):
    """SolarEdge Monitoring API. Limite de 300 chamadas/dia por chave."""

    codigo, nome = "solaredge", "SolarEdge"
    campos_obrigatorios = ("api_key",)
    base = "https://monitoringapi.solaredge.com"

    def _get(self, caminho, **params):
        return http_json("GET", f"{self.base}/site/{self.id}/{caminho}",
                         params={**params, "api_key": self.credenciais["api_key"]})

    def status(self):
        ov = self._get("overview")["overview"]
        detalhes = self._get("details")["details"]
        online = detalhes.get("status") == "Active"
        return StatusInversor(online, d(ov["currentPower"]["power"]) / 1000, d(ov["lastDayData"]["energy"]) / 1000,
                              self._agora())

    def geracao_diaria(self, inicio, fim):
        r = self._get("energy", timeUnit="DAY", startDate=inicio.isoformat(), endDate=fim.isoformat())
        return [GeracaoDia(datetime.date.fromisoformat(v["date"][:10]), d(v["value"]) / 1000)
                for v in r["energy"]["values"] if v["value"] is not None]


class FroniusProvedor(ProvedorReal):
    """Fronius Solar.web Query API (SWQAPI)."""

    codigo, nome = "fronius", "Fronius"
    campos_obrigatorios = ("access_key_id", "access_key_value")
    base = "https://api.solarweb.com/swqapi"

    def _get(self, caminho, **params):
        return http_json("GET", f"{self.base}/pvsystems/{self.id}/{caminho}", params=params, headers={
            "AccessKeyId": self.credenciais["access_key_id"], "AccessKeyValue": self.credenciais["access_key_value"]})

    def status(self):
        flow = self._get("flowdata")
        canais = {c["channelName"]: c["value"] for c in flow["data"]["channels"]}
        agg = self._get("aggrdata", period="today") if flow.get("status", {}).get("isOnline") else {}
        hoje = 0
        for ch in (agg.get("data") or [{}])[0].get("channels", []):
            if ch["channelName"] == "EnergyProductionTotal":
                hoje = ch["value"]
        return StatusInversor(bool(flow.get("status", {}).get("isOnline")), d(canais.get("PowerPV", 0)) / 1000,
                              d(hoje) / 1000, self._agora())

    def geracao_diaria(self, inicio, fim):
        r = self._get("aggrdata", **{"from": inicio.isoformat(), "to": fim.isoformat(), "channel": "EnergyProductionTotal"})
        return [GeracaoDia(datetime.date.fromisoformat(item["logDateTime"][:10]), d(item["channels"][0]["value"]) / 1000)
                for item in r.get("data", [])]


class GoodWeProvedor(ProvedorReal):
    """GoodWe SEMS Portal. API não oficial para terceiros: CONFIRMAR acesso de integrador com a GoodWe."""

    codigo, nome = "goodwe", "GoodWe"
    campos_obrigatorios = ("usuario", "senha")
    base = "https://www.semsportal.com/api"

    def _token(self):
        chave = f"goodwe-token-{self.credenciais['usuario']}"
        tok = cache.get(chave)
        if not tok:
            r = http_json("POST", f"{self.base}/v2/Common/CrossLogin",
                          corpo={"account": self.credenciais["usuario"], "pwd": self.credenciais["senha"]},
                          headers={"Token": json.dumps({"version": "v2.1.0", "client": "web", "language": "en"})})
            tok = json.dumps({**r["data"], "version": "v2.1.0", "client": "web", "language": "en"})
            cache.set(chave, tok, 3600)
        return tok

    def _post(self, caminho, corpo):
        r = http_json("POST", f"{self.base}/{caminho}", corpo=corpo, headers={"Token": self._token()})
        if str(r.get("code")) != "0":
            raise ErroIntegracao(f"GoodWe: {r.get('msg')}")
        return r["data"]

    def status(self):
        data = self._post("v2/PowerStation/GetMonitorDetailByPowerstationId", {"powerStationId": self.id})
        kpi = data["kpi"]
        online = data["info"].get("status", 1) != -1  # -1 offline
        return StatusInversor(online, d(kpi.get("pac")) / 1000, d(kpi.get("power")), self._agora())

    def geracao_diaria(self, inicio, fim):
        data = self._post("v2/Charts/GetChartByPlant", {"id": self.id, "date": fim.isoformat(), "range": 2})
        out = []
        for linha in data["lines"][0]["xy"]:
            dia = datetime.date.fromisoformat(linha["x"])
            if inicio <= dia <= fim:
                out.append(GeracaoDia(dia, d(linha["y"])))
        return out


class DeyeProvedor(ProvedorReal):
    """Deye / Solarman OpenAPI (globalapi.solarmanpv.com)."""

    codigo, nome = "deye", "Deye / Solarman"
    campos_obrigatorios = ("app_id", "app_secret", "email", "senha_sha256")
    base = "https://globalapi.solarmanpv.com"

    def _token(self):
        chave = f"solarman-token-{self.credenciais['app_id']}-{self.credenciais['email']}"
        tok = cache.get(chave)
        if not tok:
            r = http_json("POST", f"{self.base}/account/v1.0/token",
                          params={"appId": self.credenciais["app_id"], "language": "en"},
                          corpo={"appSecret": self.credenciais["app_secret"], "email": self.credenciais["email"],
                                 "password": self.credenciais["senha_sha256"]})
            if not r.get("success"):
                raise ErroIntegracao(f"Solarman: {r.get('msg')}")
            tok = r["access_token"]
            cache.set(chave, tok, int(r.get("expires_in", 3600)) - 60)
        return tok

    def _post(self, caminho, corpo):
        r = http_json("POST", f"{self.base}/{caminho}", params={"language": "en"}, corpo=corpo,
                      headers={"Authorization": f"bearer {self._token()}"})
        if not r.get("success"):
            raise ErroIntegracao(f"Solarman: {r.get('msg')}")
        return r

    def status(self):
        r = self._post("station/v1.0/realTime", {"stationId": int(self.id)})
        ultimo = datetime.datetime.fromtimestamp(r.get("lastUpdateTime", 0), tz=datetime.UTC)
        online = (self._agora() - ultimo) < datetime.timedelta(hours=2)
        return StatusInversor(online, d(r.get("generationPower")) / 1000, d(r.get("generationValue")), ultimo)

    def geracao_diaria(self, inicio, fim):
        r = self._post("station/v1.0/history", {"stationId": int(self.id), "timeType": 2,
                                                "startTime": inicio.isoformat(), "endTime": fim.isoformat()})
        out = []
        for item in r.get("stationDataItems", []):
            dia = datetime.date(item["year"], item["month"], item["day"])
            out.append(GeracaoDia(dia, d(item.get("generationValue"))))
        return out


PROVEDORES_REAIS = {c.codigo: c for c in [GrowattProvedor, HuaweiProvedor, SolarEdgeProvedor, FroniusProvedor,
                                           GoodWeProvedor, DeyeProvedor]}

/*
  FaturaCerta: medidor próprio com ESP32 + sensores de corrente SCT-013 (fonte 2 da auditoria).

  Mede a entrada da rede (bidirecional) e envia os contadores ACUMULADOS para a API:
    POST {URL_API}  Authorization: Bearer {TOKEN}
    {"potencia_w": -1830.5, "importacao_kwh": 15234.120, "exportacao_kwh": 9012.450, "tensao_v": 221.4, "corrente_a": 8.3}

  Ligações (monofásico; repita por fase em instalações trifásicas):
    - SCT-013-100 (100 A / 50 mA) com resistor de carga ~22 Ω e divisor 1,65 V no GPIO 34
    - Transformador de tensão (ZMPT101B) no GPIO 35 para obter tensão e o sentido do fluxo
  Biblioteca: EmonLib (openenergymonitor). Calibre CAL_I e CAL_V com um multímetro.

  ATENÇÃO: instalação em quadro elétrico deve ser feita por profissional habilitado.
*/
#include <WiFi.h>
#include <HTTPClient.h>
#include <Preferences.h>
#include "EmonLib.h"

const char* WIFI_SSID = "SUA_REDE";
const char* WIFI_SENHA = "SUA_SENHA";
const char* URL_API = "https://SEU_DOMINIO/api/medidores/medicoes";
const char* TOKEN = "fc_COLE_O_TOKEN_AQUI";
const uint32_t INTERVALO_MS = 60000;   // igual ao "intervalo de envio" cadastrado
const float CAL_I = 60.6, CAL_V = 234.0, FASE = 1.7;

EnergyMonitor rede;
Preferences mem;
double importacaoKwh = 0, exportacaoKwh = 0;   // contadores acumulados, salvos na flash
uint32_t ultimoEnvio = 0, ultimaMedida = 0;
double somaP = 0; uint32_t nP = 0;

void setup() {
  Serial.begin(115200);
  rede.voltage(35, CAL_V, FASE);
  rede.current(34, CAL_I);
  mem.begin("fc", false);
  importacaoKwh = mem.getDouble("imp", 0);
  exportacaoKwh = mem.getDouble("exp", 0);
  WiFi.begin(WIFI_SSID, WIFI_SENHA);
  ultimaMedida = millis();
}

void loop() {
  rede.calcVI(20, 2000);                       // 20 meias-ondas
  double p = rede.realPower;                   // + importando, − injetando (depende do sentido do sensor)
  uint32_t agora = millis();
  double horas = (agora - ultimaMedida) / 3600000.0;
  ultimaMedida = agora;
  if (p >= 0) importacaoKwh += p * horas / 1000.0; else exportacaoKwh += -p * horas / 1000.0;
  somaP += p; nP++;

  if (agora - ultimoEnvio >= INTERVALO_MS) {
    ultimoEnvio = agora;
    mem.putDouble("imp", importacaoKwh);
    mem.putDouble("exp", exportacaoKwh);
    if (WiFi.status() == WL_CONNECTED) {
      HTTPClient http;
      http.begin(URL_API);
      http.addHeader("Content-Type", "application/json");
      http.addHeader("Authorization", String("Bearer ") + TOKEN);
      char corpo[256];
      snprintf(corpo, sizeof(corpo),
               "{\"potencia_w\":%.1f,\"importacao_kwh\":%.3f,\"exportacao_kwh\":%.3f,\"tensao_v\":%.1f,\"corrente_a\":%.2f}",
               somaP / max(nP, (uint32_t)1), importacaoKwh, exportacaoKwh, rede.Vrms, rede.Irms);
      int status = http.POST(corpo);
      Serial.printf("envio: %d\n", status);
      http.end();
    }
    somaP = 0; nP = 0;
  }
}

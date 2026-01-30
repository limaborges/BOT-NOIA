# Atualização Windows - Dashboard V2

**Data:** 30/01/2026

## Mudanças Principais

1. **Dashboard V2** - Novo dashboard com gráfico unificado mostrando todas as máquinas
2. **sync_client.py** - Corrigido para enviar histórico de saldo corretamente
3. **Métricas por período** - Lucro das últimas 2h, 6h, 12h, 24h
4. **Média diária** - Lucro médio por dia desde o início
5. **Top 10 Sequências de Baixos** - Mostra as 10 maiores sequências de losses consecutivos por máquina

---

## Passos para Atualizar

### 1. Parar o sync_client

Feche apenas a janela do sync_client (Ctrl+C).

**O bot NÃO precisa ser reiniciado.**

### 2. Atualizar código

```bash
cd C:\Users\SEU_USUARIO\MartingaleV2_Build
git pull
```

### 3. Reiniciar o sync_client

```bash
python sync_client.py
```

Saída esperada:
```
============================================================
  SYNC CLIENT - MartingaleV2 Dashboard
============================================================
  Maquina: CONSERVADORA  (ou ISOLADA)
  Servidor: 192.168.0.200:8080
  Intervalo: 5s
============================================================

[HH:MM:SS] OK | Saldo: R$ XXXX.XX | Lucro: +X.XX% | Uptime: Xh Xmin
```

**Pronto!** O bot pode continuar rodando normalmente.

---

## Verificar no Dashboard

Acesse: http://192.168.0.200:8080

Confirme que:
- [x] Gráfico mostra as 3 máquinas com cores diferentes
- [x] Cada máquina mostra lucro por período (2H, 6H, 12H, 24H)
- [x] Cabeçalho mostra depósito inicial e aposta base
- [x] Média diária aparece corretamente
- [x] Seção "Top Sequências de Baixos" mostra os maiores losses consecutivos

---

## Troubleshooting

### sync_client não conecta
- Verificar Tailscale conectado (ícone verde)
- Testar: `ping 192.168.0.200`

### Dados não aparecem no gráfico
- O histórico será populado conforme novas apostas acontecem
- O sync_client agora envia o histórico completo da sessão

### Git pull dá erro
```bash
git stash
git pull
git stash pop
```

---

## Arquivos Alterados

| Arquivo | Mudança |
|---------|---------|
| sync_client.py | Constrói historico_saldo a partir de historico_apostas |
| dashboard_server_v2.py | NOVO - Dashboard V2 com todas melhorias |
| UPDATE_WINDOWS.md | NOVO - Este arquivo |

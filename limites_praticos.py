#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Análise de limites práticos - o que pode dar errado
"""

print("""
{'='*70}
O QUE ESTAMOS ASSUMINDO vs REALIDADE
{'='*70}

ASSUNÇÃO 1: Máximo de 15 baixas consecutivas
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
  ✓ No dataset de 1.3M: máximo foi 15
  ✗ RISCO: Amanhã pode ter 16, 17, 18...

  O jogo não "sabe" que já teve 15 baixas.
  Cada rodada é independente.

  P(16 baixas) ≈ 0.5^16 = 0.0015% por sequência
  Com ~74 gatilhos G5/dia, em 1 ano:
  74 × 365 = 27.010 oportunidades
  P(pelo menos 1 sequência de 16) ≈ 33%


ASSUNÇÃO 2: Compound infinito
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
  Banca       Aposta C2 (1ª tent)    Aposta C2 (9ª tent)
  R$ 1.000    R$ 1,96                R$ 501
  R$ 10.000   R$ 19,57               R$ 5.011
  R$ 100.000  R$ 195,69              R$ 50.117
  R$ 1.000.000 R$ 1.956              R$ 501.173

  ✗ Plataformas têm LIMITE DE APOSTA (ex: R$ 500, R$ 1.000)
  ✗ Com banca alta, não consegue fazer martingale completo


ASSUNÇÃO 3: Execução perfeita
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
  ✗ Delay de rede
  ✗ Timeout de aposta
  ✗ Erro humano / bug do bot
  ✗ Plataforma pode negar aposta


ASSUNÇÃO 4: Plataforma permite
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
  ✗ Contas muito lucrativas são BANIDAS
  ✗ Limite de saque diário (R$ 50k?)
  ✗ KYC / verificação pode travar conta
  ✗ Plataforma pode mudar regras


{'='*70}
CENÁRIO REALISTA
{'='*70}

Com limites práticos (aposta máx R$ 500, banca máx ~R$ 50k):

  Banca C2 máxima útil: ~R$ 50.000
  Aposta máxima C2: R$ 500 (limite plataforma)
  Divisor efetivo: 50000/500 = 100 (não 511)

  Ou seja, com banca alta, você NÃO consegue usar
  todo o martingale - fica exposto a busts.


{'='*70}
RECOMENDAÇÃO CONSERVADORA
{'='*70}

  1. LIMITE DE BANCA: Não deixar passar de R$ 30-50k por conta
     - Acima disso, saca para não bater limites de aposta

  2. PROTEÇÃO REAL: Considere que pode ter 16+ baixas
     - Teste com D255 (prot 15) e reserve capital
     - Ou use D511 mas com expectativa de bust eventual

  3. DIVERSIFICAÇÃO: 4 contas em plataformas DIFERENTES
     - Plataformas diferentes = jogos diferentes
     - Baixas NÃO são sincronizadas entre plataformas

  4. SAQUE FREQUENTE: Não acumule demais
     - Tire lucro toda semana
     - Mantenha banca operacional baixa

  5. EXPECTATIVA: Ajuste para realidade
     - Com limites: ~R$ 5-10k/mês por conta é mais realista
     - Não R$ 200k/mês que a simulação "pura" mostra
""")

# Calcular limite prático
print("\n" + "="*70)
print("CÁLCULO: BANCA MÁXIMA ÚTIL")
print("="*70)

limite_aposta = 500  # Limite da plataforma
divisor_c2 = 511

# Para última tentativa (9ª): aposta = banca * 255/511
# 255/511 * banca <= 500
# banca <= 500 * 511/255 = 1002

banca_max_9a = limite_aposta * divisor_c2 / 255
print(f"\nSe limite de aposta = R$ {limite_aposta}:")
print(f"  Banca máxima para 9ª tentativa funcionar: R$ {banca_max_9a:,.0f}")

# Para ser conservador, primeira tentativa
# banca/511 <= 500
banca_max_1a = limite_aposta * divisor_c2
print(f"  Banca máxima para 1ª tentativa não chamar atenção: R$ {banca_max_1a:,.0f}")

print(f"\n  Recomendação: Manter banca entre R$ 1.000 e R$ {banca_max_9a:,.0f}")
print(f"  Sacar quando passar de R$ {banca_max_9a:,.0f}")

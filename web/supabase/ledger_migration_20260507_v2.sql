-- =============================================================
-- 2026-05-07 ledger 修正 v2
-- 1つめ口座のみで計算した「未出金取り分」を view に追加
--
-- 計算式:
--   J 未出金   = 1つめ J 累計取り分 (利益×0.20) − J 既出金累計
--   K 未出金   = 1つめ K 累計取り分 (利益×0.30) − K本人既出金 − Kの兄既出金
--   会社 未出金 = 1つめ 会社 累計取り分 (利益×0.30) − 会社配当 既出金累計
--
-- 注:
--   - 経費出金は物理的には account2/reserve から出るが、概念上は 1 つめ取り分の前払いと見なす
--   - AI 開発費は運用益外例外なので 1 つめ取り分計算には含めない
-- =============================================================
-- 適用方法: Supabase SQL Editor でこの SQL 全体を貼り付けて Run
-- =============================================================

CREATE OR REPLACE VIEW ledger_investor_summary AS
WITH a1 AS (
  SELECT investor_id,
         SUM(daily_profit) AS account1_total_profit,
         SUM(daily_profit * 0.20) AS investor_received_total,
         SUM(daily_profit * 0.20) AS j_share_total,
         SUM(daily_profit * 0.30) AS k_share_total,
         SUM(daily_profit * 0.30) AS company_share_total,
         SUM(daily_profit * 0.80) AS account1_80pct_total,
         SUM(daily_profit) AS investor_withdrawal_total
    FROM ledger_account1_daily
   GROUP BY investor_id
),
a2 AS (
  SELECT investor_id,
         SUM(daily_profit) AS account2_total_profit,
         SUM(withdrawal)   AS account2_withdrawal_total
    FROM ledger_account2_daily
   GROUP BY investor_id
),
exp AS (
  SELECT investor_id,
         SUM(total_withdrawal) AS expense_total,
         SUM(withdraw_from_reserve) AS expense_from_reserve,
         SUM(withdraw_from_account2) AS expense_from_account2,
         SUM(j_received) AS j_total,
         SUM(k_received) AS k_total,
         SUM(k_brother_received) AS k_brother_total,
         SUM(company_received) AS company_total,
         SUM(ai_dev_expense) AS ai_dev_total
    FROM ledger_expense_withdrawals
   GROUP BY investor_id
)
SELECT
  i.id AS investor_id,
  i.name AS investor_name,
  i.total_investment,
  i.account1_amount,
  i.account2_amount,
  i.initial_charge_display,
  rf.initial_amount AS reserve_initial,
  COALESCE(a1.account1_total_profit, 0) AS account1_total_profit,
  COALESCE(a1.investor_received_total, 0) AS investor_received_total,
  COALESCE(a1.account1_80pct_total, 0) AS account1_80pct_total,
  COALESCE(a2.account2_total_profit, 0) AS account2_total_profit,
  COALESCE(a2.account2_withdrawal_total, 0) AS account2_withdrawal_total,
  i.account2_amount + COALESCE(a2.account2_total_profit, 0) - COALESCE(a2.account2_withdrawal_total, 0) AS account2_balance,
  i.initial_charge_display - COALESCE(a1.account1_80pct_total, 0) AS displayed_charge_balance,
  COALESCE(a1.account1_80pct_total, 0) + COALESCE(a2.account2_total_profit, 0) AS operator_net_profit,
  COALESCE(exp.expense_total, 0) AS expense_total,
  COALESCE(exp.expense_from_reserve, 0) AS expense_from_reserve,
  COALESCE(exp.expense_from_account2, 0) AS expense_from_account2,
  (COALESCE(a1.account1_80pct_total, 0) + COALESCE(a2.account2_total_profit, 0))
    - COALESCE(exp.expense_from_account2, 0) AS operator_remaining_profit,
  COALESCE(a2.account2_total_profit, 0) - COALESCE(a2.account2_withdrawal_total, 0) AS remaining_in_account2,
  COALESCE(a1.account1_80pct_total, 0) AS remaining_charge_refund,
  COALESCE(rf.initial_amount, 0) - COALESCE(exp.expense_from_reserve, 0) AS reserve_balance,
  COALESCE(exp.j_total, 0) AS j_total,
  COALESCE(exp.k_total, 0) AS k_total,
  COALESCE(exp.k_brother_total, 0) AS k_brother_total,
  COALESCE(exp.company_total, 0) AS company_total,
  COALESCE(exp.ai_dev_total, 0) AS ai_dev_total,
  -- 1つめ口座 累計取り分 (= 利益 × 配分率)
  COALESCE(a1.j_share_total, 0) AS j_share_in_account1,
  COALESCE(a1.k_share_total, 0) AS k_share_in_account1,
  COALESCE(a1.company_share_total, 0) AS company_share_in_account1,
  -- 1つめ口座のみで計算した 未出金取り分 (= 累計取り分 − 既出金)
  COALESCE(a1.j_share_total, 0) - COALESCE(exp.j_total, 0) AS j_unpaid_in_account1,
  COALESCE(a1.k_share_total, 0) - COALESCE(exp.k_total, 0) - COALESCE(exp.k_brother_total, 0) AS k_unpaid_in_account1,
  COALESCE(a1.company_share_total, 0) - COALESCE(exp.company_total, 0) AS company_unpaid_in_account1
FROM ledger_investors i
LEFT JOIN ledger_reserve_funds rf ON rf.investor_id = i.id
LEFT JOIN a1 ON a1.investor_id = i.id
LEFT JOIN a2 ON a2.investor_id = i.id
LEFT JOIN exp ON exp.investor_id = i.id;

-- 確認用
SELECT
  investor_name,
  j_share_in_account1       AS "J累計取り分_1つめ",
  j_total                   AS "J既出金",
  j_unpaid_in_account1      AS "J未出金",
  k_share_in_account1       AS "K累計取り分_1つめ",
  k_total                   AS "K既出金本人",
  k_brother_total           AS "Kの兄既出金",
  k_unpaid_in_account1      AS "K未出金",
  company_share_in_account1 AS "会社累計取り分_1つめ",
  company_total             AS "会社既出金",
  company_unpaid_in_account1 AS "会社未出金"
FROM ledger_investor_summary
WHERE investor_name = 'H';

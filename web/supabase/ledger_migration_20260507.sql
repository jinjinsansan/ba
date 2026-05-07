-- =============================================================
-- 2026-05-07 ledger 修正
-- 1) 5/6 経費出金の値を訂正: J=$2,100 / AI開発=$1,000 (合計は変えず $8,019 のまま)
-- 2) view に 1つめ口座 J/K/会社 累計取り分を追加 (= 未出金分の見える化)
-- =============================================================
-- 適用方法: Supabase SQL Editor でこの SQL 全体を貼り付けて Run
-- =============================================================

-- (1) 5/6 経費出金の修正
-- (J 取り分が実際は $2,100、AI 開発費は $1,000 = 運用益外例外)
UPDATE ledger_expense_withdrawals
   SET j_received     = 2100.00,
       ai_dev_expense = 1000.00,
       notes          = '5/6 の経費出金。別チャージから $2,100、2 つめ口座から $5,919、計 $8,019。J 取り分 $2,100 / K $2,000 / Kの兄 $919 / 会社配当 $2,000 / AI開発費 $1,000 (運用益外例外)'
 WHERE investor_id = (SELECT id FROM ledger_investors WHERE name = 'H' LIMIT 1)
   AND withdrawal_date = '2026-05-06';

-- (2) view を再作成して 1つめ口座取り分を追加カラムで露出
CREATE OR REPLACE VIEW ledger_investor_summary AS
WITH a1 AS (
  SELECT investor_id,
         SUM(daily_profit) AS account1_total_profit,
         SUM(daily_profit * 0.20) AS investor_received_total,
         SUM(daily_profit * 0.20) AS j_share_total,           -- 1つめ口座 J 累計取り分
         SUM(daily_profit * 0.30) AS k_share_total,           -- 1つめ口座 K 累計取り分
         SUM(daily_profit * 0.30) AS company_share_total,     -- 1つめ口座 会社 累計取り分
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
  -- 1つめ口座 累計取り分 (= chargeRefund 構成内訳、現状はまだ口座から物理出金していないため全て未出金)
  COALESCE(a1.j_share_total, 0) AS j_share_in_account1,
  COALESCE(a1.k_share_total, 0) AS k_share_in_account1,
  COALESCE(a1.company_share_total, 0) AS company_share_in_account1
FROM ledger_investors i
LEFT JOIN ledger_reserve_funds rf ON rf.investor_id = i.id
LEFT JOIN a1 ON a1.investor_id = i.id
LEFT JOIN a2 ON a2.investor_id = i.id
LEFT JOIN exp ON exp.investor_id = i.id;

-- 確認用
SELECT
  investor_name,
  j_total              AS j_受取累計,
  k_total              AS k_受取累計,
  k_brother_total      AS kの兄_受取累計,
  company_total        AS 会社_受取累計,
  ai_dev_total         AS ai開発費累計,
  j_share_in_account1  AS j_1つめ未出金,
  k_share_in_account1  AS k_1つめ未出金,
  company_share_in_account1 AS 会社_1つめ未出金,
  remaining_charge_refund   AS chargeRefund_合計,
  operator_remaining_profit AS 残利益
FROM ledger_investor_summary
WHERE investor_name = 'H';

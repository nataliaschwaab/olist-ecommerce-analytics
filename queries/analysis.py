-- ============================================================
-- OLIST E-COMMERCE ANALYTICS — PostgreSQL
-- Autor: Natalia Schwaab
-- Schema: customers, orders, items, payments, products, sellers
-- ============================================================


-- ============================================================
-- BLOCO 1: VISÃO GERAL DO NEGÓCIO
-- ============================================================

-- 1.1 KPIs principais
SELECT
    COUNT(DISTINCT o.order_id)                                 AS total_pedidos,
    COUNT(DISTINCT o.customer_id)                              AS total_clientes,
    ROUND(SUM(p.payment_value)::NUMERIC, 2)                    AS receita_total,
    ROUND(AVG(p.payment_value)::NUMERIC, 2)                    AS ticket_medio
FROM orders o
JOIN payments p ON o.order_id = p.order_id
WHERE o.order_status = 'delivered';


-- 1.2 Pedidos por status (saúde do negócio)
SELECT
    order_status,
    COUNT(*)                                                   AS total,
    ROUND(100.0 * COUNT(*) / SUM(COUNT(*)) OVER (), 1)        AS pct
FROM orders
GROUP BY order_status
ORDER BY total DESC;


-- 1.3 Taxa de cancelamento por mês
SELECT
    TO_CHAR(order_purchase_timestamp::DATE, 'YYYY-MM')        AS mes,
    COUNT(*)                                                   AS total_pedidos,
    SUM(CASE WHEN order_status = 'canceled' THEN 1 ELSE 0 END) AS cancelados,
    ROUND(
        100.0 * SUM(CASE WHEN order_status = 'canceled' THEN 1 ELSE 0 END) / COUNT(*), 1
    )                                                          AS pct_cancelamento
FROM orders
GROUP BY mes
ORDER BY mes;


-- ============================================================
-- BLOCO 2: ANÁLISE DE TEMPO DE ENTREGA
-- ============================================================

-- 2.1 Tempo médio de entrega por estado do cliente
SELECT
    c.customer_state                                           AS estado,
    COUNT(o.order_id)                                         AS pedidos,
    ROUND(AVG(
        order_delivered_customer_date::DATE - order_purchase_timestamp::DATE
    ), 1)                                                      AS dias_entrega_medio,
    ROUND(AVG(
        order_estimated_delivery_date::DATE - order_purchase_timestamp::DATE
    ), 1)                                                      AS dias_estimado_medio
FROM orders o
JOIN customers c ON o.customer_id = c.customer_id
WHERE o.order_status = 'delivered'
  AND o.order_delivered_customer_date IS NOT NULL
GROUP BY c.customer_state
ORDER BY dias_entrega_medio DESC;


-- 2.2 Pedidos entregues antes vs depois do prazo estimado
SELECT
    CASE
        WHEN order_delivered_customer_date::DATE <= order_estimated_delivery_date::DATE
            THEN 'No prazo ou antes'
        ELSE 'Atrasado'
    END                                                        AS situacao,
    COUNT(*)                                                   AS pedidos,
    ROUND(100.0 * COUNT(*) / SUM(COUNT(*)) OVER (), 1)        AS pct
FROM orders
WHERE order_status = 'delivered'
  AND order_delivered_customer_date IS NOT NULL
  AND order_estimated_delivery_date IS NOT NULL
GROUP BY situacao;


-- ============================================================
-- BLOCO 3: ANÁLISE DE PRODUTOS E CATEGORIAS
-- ============================================================

-- 3.1 Top 10 categorias por receita
SELECT
    pr.product_category_name                                   AS categoria,
    COUNT(DISTINCT i.order_id)                                 AS pedidos,
    ROUND(SUM(i.price)::NUMERIC, 2)                            AS receita,
    ROUND(AVG(i.price)::NUMERIC, 2)                            AS preco_medio
FROM items i
JOIN products pr ON i.product_id = pr.product_id
JOIN orders   o  ON i.order_id   = o.order_id
WHERE o.order_status = 'delivered'
  AND pr.product_category_name IS NOT NULL
GROUP BY pr.product_category_name
ORDER BY receita DESC
LIMIT 10;


-- 3.2 Categorias com maior frete relativo ao preço
-- (sinaliza produtos pesados ou de difícil logística)
SELECT
    pr.product_category_name                                   AS categoria,
    ROUND(AVG(i.price)::NUMERIC, 2)                            AS preco_medio,
    ROUND(AVG(i.freight_value)::NUMERIC, 2)                    AS frete_medio,
    ROUND(100.0 * AVG(i.freight_value)::NUMERIC / NULLIF(AVG(i.price)::NUMERIC, 0), 1) AS pct_frete_sobre_preco
FROM items    i
JOIN products pr ON i.product_id = pr.product_id
WHERE pr.product_category_name IS NOT NULL
GROUP BY pr.product_category_name
HAVING COUNT(*) >= 50
ORDER BY pct_frete_sobre_preco DESC
LIMIT 10;


-- ============================================================
-- BLOCO 4: ANÁLISE DE SELLERS (VENDEDORES)
-- ============================================================

-- 4.1 Top 10 sellers por receita gerada
SELECT
    i.seller_id,
    COUNT(DISTINCT i.order_id)                                 AS pedidos,
    ROUND(SUM(i.price)::NUMERIC, 2)                            AS receita_total,
    ROUND(AVG(i.price)::NUMERIC, 2)                            AS ticket_medio,
    COUNT(DISTINCT i.product_id)                               AS produtos_distintos
FROM items i
JOIN orders o ON i.order_id = o.order_id
WHERE o.order_status = 'delivered'
GROUP BY i.seller_id
ORDER BY receita_total DESC
LIMIT 10;


-- 4.2 Sellers com maior taxa de cancelamento
-- (subquery para calcular totais e depois filtrar)
SELECT
    seller_id,
    total_pedidos,
    pedidos_cancelados,
    ROUND(100.0 * pedidos_cancelados / total_pedidos, 1)       AS pct_cancelamento
FROM (
    SELECT
        i.seller_id,
        COUNT(DISTINCT i.order_id)                             AS total_pedidos,
        COUNT(DISTINCT CASE WHEN o.order_status = 'canceled'
                            THEN i.order_id END)               AS pedidos_cancelados
    FROM items i
    JOIN orders o ON i.order_id = o.order_id
    GROUP BY i.seller_id
) AS sub
WHERE total_pedidos >= 20
ORDER BY pct_cancelamento DESC
LIMIT 10;


-- ============================================================
-- BLOCO 5: ANÁLISE DE CLIENTES
-- ============================================================

-- 5.1 Receita e volume por estado
SELECT
    c.customer_state                                           AS estado,
    COUNT(DISTINCT o.order_id)                                 AS pedidos,
    COUNT(DISTINCT c.customer_unique_id)                       AS clientes_unicos,
    ROUND(SUM(p.payment_value)::NUMERIC, 2)                    AS receita_total,
    ROUND(AVG(p.payment_value)::NUMERIC, 2)                    AS ticket_medio
FROM customers c
JOIN orders   o ON c.customer_id  = o.customer_id
JOIN payments p ON o.order_id     = p.order_id
WHERE o.order_status = 'delivered'
GROUP BY c.customer_state
ORDER BY receita_total DESC;


-- 5.2 Clientes recorrentes
-- (customer_unique_id identifica o mesmo cliente em múltiplos pedidos)
SELECT
    CASE
        WHEN total_pedidos = 1 THEN '1 pedido'
        WHEN total_pedidos BETWEEN 2 AND 3 THEN '2-3 pedidos'
        ELSE '4+ pedidos'
    END                                                        AS faixa,
    COUNT(*)                                                   AS clientes,
    ROUND(100.0 * COUNT(*) / SUM(COUNT(*)) OVER (), 1)        AS pct
FROM (
    SELECT c.customer_unique_id, COUNT(DISTINCT o.order_id) AS total_pedidos
    FROM customers c
    JOIN orders o ON c.customer_id = o.customer_id
    WHERE o.order_status = 'delivered'
    GROUP BY c.customer_unique_id
) AS freq
GROUP BY faixa
ORDER BY MIN(total_pedidos);


-- ============================================================
-- BLOCO 6: ANÁLISE TEMPORAL
-- ============================================================

-- 6.1 Receita mensal
SELECT
    TO_CHAR(o.order_purchase_timestamp::DATE, 'YYYY-MM')      AS mes,
    COUNT(DISTINCT o.order_id)                                 AS pedidos,
    ROUND(SUM(p.payment_value)::NUMERIC, 2)                    AS receita
FROM orders   o
JOIN payments p ON o.order_id = p.order_id
WHERE o.order_status = 'delivered'
GROUP BY mes
ORDER BY mes;


-- 6.2 Dia da semana com mais pedidos
SELECT
    TO_CHAR(order_purchase_timestamp::DATE, 'Day')            AS dia_semana,
    EXTRACT(DOW FROM order_purchase_timestamp::DATE)          AS num_dia,
    COUNT(*)                                                   AS pedidos
FROM orders
GROUP BY dia_semana, num_dia
ORDER BY num_dia;


-- 6.3 Horário de pico dos pedidos
SELECT
    EXTRACT(HOUR FROM order_purchase_timestamp::TIMESTAMP)    AS hora,
    COUNT(*)                                                   AS pedidos
FROM orders
GROUP BY hora
ORDER BY hora;

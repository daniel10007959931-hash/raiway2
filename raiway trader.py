# dydx_trader.py
# AUTOR: Ajustado por ChatGPT a partir do seu código (modo real) - 26/09/2025
# AVISO: Opera com fundos reais. Use com responsabilidade.

import os
import asyncio
import logging
import time
from logging.handlers import RotatingFileHandler
from dotenv import load_dotenv

# Tentativa de imports flexíveis (compatibilidade entre versões do SDK)
try:
    # estruturas possíveis
    from dydx_v4_client.indexer.rest.indexer_client import IndexerClient as RestIndexerClient
except Exception:
    RestIndexerClient = None

try:
    from dydx_v4_client.indexer.indexer_client import IndexerClient as IndexerClientAlt
except Exception:
    IndexerClientAlt = None

try:
    from dydx_v4_client.node.client import NodeClient
except Exception:
    NodeClient = None

# rede / factory helpers
try:
    # Alguns releases expõem make_mainnet / make_testnet
    from dydx_v4_client.network import make_mainnet, make_testnet, Network
except Exception:
    make_mainnet = None
    make_testnet = None
    Network = None

# constantes: fallback para strings se a lib não expuser
try:
    from dydx_v4_client.indexer.rest.constants import OrderType as _OrderType
    ORDER_TYPE_LIMIT = _OrderType.LIMIT if hasattr(_OrderType, "LIMIT") else "LIMIT"
except Exception:
    ORDER_TYPE_LIMIT = "LIMIT"

# Sides/time-in-force simples (a API aceita esses valores textuais na maioria dos exemplos)
ORDER_SIDE_BUY = "BUY"
ORDER_SIDE_SELL = "SELL"
TIME_IN_FORCE_IOC = "IOC"  # Immediate-Or-Cancel

# --- Logging ---
log_formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(filename)s:%(lineno)d - %(message)s')
log_file_handler = RotatingFileHandler('trading_bot.log', maxBytes=5*1024*1024, backupCount=2)
log_file_handler.setFormatter(log_formatter)
console_handler = logging.StreamHandler()
console_handler.setFormatter(log_formatter)
logger = logging.getLogger("dydx_trader")
logger.setLevel(logging.INFO)
logger.addHandler(log_file_handler)
logger.addHandler(console_handler)

logger.info("==========================================================")
logger.info("           INICIALIZANDO O ROBÔ DE TRADING DYDX           ")
logger.info("==========================================================")

# --- Carrega variáveis de ambiente ---
load_dotenv()
SIGNALS_OF_THE_DAY = os.getenv("SIGNALS_OF_THE_DAY", "BTC COMPRAR,ETH FECHAR").split(",")  # ex.: "BTC COMPRAR,ETH FECHAR"
PRIVATE_KEY = os.getenv("DYDX_PRIVATE_KEY")
DYDX_ADDRESS = os.getenv("DYDX_ADDRESS")
DYDX_NODE_URL = os.getenv("DYDX_NODE_URL")  # opcional
DYDX_INDEXER_REST = os.getenv("DYDX_INDEXER_REST", "https://indexer.dydx.trade")
DYDX_INDEXER_WS = os.getenv("DYDX_INDEXER_WS", "wss://indexer.dydx.trade")

if not PRIVATE_KEY or not DYDX_ADDRESS:
    logger.critical("FATAL: Defina DYDX_PRIVATE_KEY e DYDX_ADDRESS nas variáveis de ambiente.")
    raise SystemExit(1)

# Estratégia / configuração
LEVERAGE_CONFIG = {"BTC": 3.0, "DEFAULT": 1.0}
SUPPORTED_TICKERS = ["BTC", "ETH", "SOL", "DOGE", "LINK", "XRP"]
ISOLATED_MARGIN_SUBACCOUNT_START_ID = 1

# --- Cliente dYdX (assíncrono) ---
class DydxClient:
    """
    Wrapper assíncrono que cria indexer_client e node_client com compatibilidade
    entre variações do SDK. Use: client = await DydxClient.create(...)
    """
    def __init__(self):
        self.indexer = None
        self.node = None

    @classmethod
    async def create(cls, node_url=None, indexer_rest=None, indexer_ws=None, private_key=None):
        inst = cls()
        logger.info("Inicializando clientes dYdX (Indexador + Node)...")
        # Configura valores default se necessário
        node_url = node_url or DYDX_NODE_URL
        indexer_rest = indexer_rest or DYDX_INDEXER_REST
        indexer_ws = indexer_ws or DYDX_INDEXER_WS

        # Inicializa Indexer client (várias formas possíveis)
        try:
            if RestIndexerClient:
                logger.info("Usando RestIndexerClient (dydx_v4_client.indexer.rest.indexer_client).")
                inst.indexer = RestIndexerClient(indexer_rest)
            elif IndexerClientAlt:
                logger.info("Usando IndexerClient alternativo (dydx_v4_client.indexer.indexer_client).")
                inst.indexer = IndexerClientAlt(indexer_rest)
            else:
                # tentativa de usar factory make_mainnet e criar via config
                if make_mainnet:
                    cfg = make_mainnet(node_url=node_url, rest_indexer=indexer_rest, websocket_indexer=indexer_ws)
                    # cfg possivelmente tem .indexer ou .indexer_config
                    idx_cfg = getattr(cfg, "indexer", getattr(cfg, "indexer_config", None))
                    if idx_cfg is not None:
                        try:
                            inst.indexer = RestIndexerClient(idx_cfg)
                        except Exception:
                            # fallback constructor com URL direto
                            inst.indexer = RestIndexerClient(indexer_rest)
                else:
                    raise ImportError("Nenhum IndexerClient disponível (instale dydx-v4-client).")
            logger.info("Indexer client inicializado.")
        except Exception as e:
            logger.critical("Falha ao inicializar IndexerClient.", exc_info=True)
            raise

        # Inicializa Node client (assíncrono)
        try:
            if NodeClient is None and make_mainnet is None:
                raise ImportError("NodeClient não encontrado. Verifique instalação do SDK dydx-v4-client.")
            if make_mainnet:
                cfg = make_mainnet(node_url=node_url, rest_indexer=indexer_rest, websocket_indexer=indexer_ws)
                node_cfg = getattr(cfg, "node", None) or getattr(cfg, "node_config", None) or cfg
                # NodeClient.connect é assíncrono na maioria das versões
                if NodeClient:
                    # se NodeClient.define um método connect, usamos; senão tentamos instanciar de forma síncrona
                    if hasattr(NodeClient, "connect"):
                        logger.info("Conectando ao NodeClient (async)...")
                        inst.node = await NodeClient.connect(node_cfg)
                    else:
                        logger.info("Instanciando NodeClient (sync fallback)...")
                        inst.node = NodeClient(node_cfg)
                else:
                    raise ImportError("NodeClient não disponível na instalação atual do SDK.")
            else:
                # make_mainnet não disponível; tentar NodeClient.connect com parâmetros simples
                if NodeClient and hasattr(NodeClient, "connect"):
                    # Tentar passar um objeto/URL simples se a lib suportar
                    logger.info("Conectando ao NodeClient usando NodeClient.connect(...) (async fallback).")
                    # criar um objeto config minimal se necessário
                    node_cfg = {"node_url": node_url} if node_url else {}
                    inst.node = await NodeClient.connect(node_cfg)
                else:
                    raise ImportError("Não foi possível construir NodeClient (verifique SDK).")
            logger.info("Node client conectado com sucesso.")
        except Exception as e:
            logger.critical("Falha ao conectar NodeClient.", exc_info=True)
            raise

        return inst

    # --- métodos assíncronos de utilidade ---
    async def get_open_positions(self):
        try:
            # Endpoint do indexer para posições perp (ex.: get_perpetual_positions_v4)
            resp = await maybe_async_call(self.indexer.account.get_perpetual_positions_v4, address=DYDX_ADDRESS)
            positions = getattr(resp, "positions", []) or []
            formatted = []
            for p in positions:
                formatted.append({
                    "market": getattr(p, "market", getattr(p, "market_id", None)),
                    "side": getattr(p, "side", None),
                    "size": float(getattr(p, "size", 0)),
                    "subaccountId": getattr(p, "subaccount_id", getattr(p, "subaccountId", 0))
                })
            return formatted
        except Exception:
            logger.exception("Erro ao obter posições abertas do indexer.")
            return []

    async def get_account_balance(self):
        try:
            resp = await maybe_async_call(self.indexer.account.get_subaccount_v4, address=DYDX_ADDRESS, subaccount_number=0)
            bal = float(getattr(resp.subaccount, "quote_balance", 0.0))
            return bal
        except Exception:
            logger.exception("Erro ao obter saldo via indexer.")
            return 0.0

    async def get_market_oracle_price(self, ticker):
        market_id = f"{ticker}-USD"
        try:
            resp = await maybe_async_call(self.indexer.markets.get_perpetual_market_v4, market=market_id)
            price = float(getattr(resp.market, "oracle_price", None))
            return price
        except Exception:
            logger.exception(f"Erro ao obter preço oracle para {ticker}.")
            return None

    async def place_order(self, ticker, side, size, price, subaccount_id, reduce_only=False):
        market_id = f"{ticker}-USD"
        side_str = ORDER_SIDE_BUY if side == "BUY" else ORDER_SIDE_SELL
        size_str = str(size)
        price_str = str(price)
        client_id = int(time.time() * 1000)
        logger.info(f"Preparando ordem REAL -> {market_id} {side_str} size={size_str} price={price_str} sub={subaccount_id} reduce_only={reduce_only}")

        try:
            # Tentar várias formas de enviar a ordem para compatibilidade:
            # 1) node.post.place_order(...)
            # 2) node.place_order(...)
            node = self.node
            placed = None

            # forma 1
            post_attr = getattr(node, "post", None)
            if post_attr and hasattr(post_attr, "place_order"):
                placed = await maybe_async_call(post_attr.place_order,
                                                subaccount_id=subaccount_id,
                                                market=market_id,
                                                type=ORDER_TYPE_LIMIT,
                                                side=side_str,
                                                size=size_str,
                                                price=price_str,
                                                client_id=client_id,
                                                time_in_force=TIME_IN_FORCE_IOC,
                                                reduce_only=reduce_only)
            # forma 2
            elif hasattr(node, "place_order"):
                placed = await maybe_async_call(node.place_order,
                                                subaccount_id=subaccount_id,
                                                market=market_id,
                                                type=ORDER_TYPE_LIMIT,
                                                side=side_str,
                                                size=size_str,
                                                price=price_str,
                                                client_id=client_id,
                                                time_in_force=TIME_IN_FORCE_IOC,
                                                reduce_only=reduce_only)
            else:
                raise RuntimeError("Não foi encontrada função place_order no NodeClient da sua instalação.")

            tx_hash = getattr(placed, "tx_hash", getattr(placed, "hash", None))
            logger.info(f"Ordem enviada com sucesso. Tx Hash: {tx_hash}")
            return {"status": "success", "tx_hash": tx_hash}
        except Exception:
            logger.exception(f"Falha ao enviar ordem para {ticker}.")
            return None

# Helper: executa função que pode ser async ou sync
async def maybe_async_call(fn, *args, **kwargs):
    result = None
    try:
        if asyncio.iscoroutinefunction(fn):
            return await fn(*args, **kwargs)
        else:
            # chama síncrono em executor para não bloquear loop
            loop = asyncio.get_event_loop()
            return await loop.run_in_executor(None, lambda: fn(*args, **kwargs))
    except Exception:
        # algumas libs expõem métodos que são coroutines assincronas no objeto retornado, 
        # mas aqui tentamos chamar diretamente; se falhar, re-raise para o caller tratar.
        raise

# ----------------- Lógica de trading (mantida do seu original, adaptada para async) -----------------
def parse_signal(signal_text):
    logger.info(f"Parseando sinal bruto: '{signal_text}'")
    try:
        parts = signal_text.strip().upper().split()
        if len(parts) != 2:
            logger.warning(f"Sinal mal formatado: '{signal_text}'")
            return None
        ticker, action = parts
        action_map = {"COMPRAR": "BUY", "VENDER": "SELL", "FECHAR": "CLOSE"}
        if ticker not in SUPPORTED_TICKERS:
            logger.warning(f"Ticker {ticker} não suportado.")
            return None
        if action in action_map:
            return {"ticker": ticker, "action": action_map[action]}
        logger.warning(f"Ação desconhecida: {action}")
        return None
    except Exception:
        logger.exception("Erro ao parsear sinal.")
        return None

async def process_signals_async(signals):
    logger.info("Iniciando ciclo de processamento (async).")
    client = await DydxClient.create(node_url=DYDX_NODE_URL, indexer_rest=DYDX_INDEXER_REST, indexer_ws=DYDX_INDEXER_WS, private_key=PRIVATE_KEY)

    parsed = [parse_signal(s) for s in signals if s]
    parsed = [p for p in parsed if p is not None]
    logger.info(f"{len(parsed)} sinais válidos.")

    if not parsed:
        logger.warning("Nenhum sinal válido. Saindo.")
        return

    # Etapa 1: fechar posições não listadas nos sinais
    try:
        open_positions = await client.get_open_positions()
        tickers_in_signals = {p["ticker"] for p in parsed}
        for position in open_positions:
            pos_ticker = position["market"].replace("-USD", "")
            if pos_ticker not in tickers_in_signals:
                logger.warning(f"Fechando posição não listada hoje: {pos_ticker}")
                price = await client.get_market_oracle_price(pos_ticker)
                if not price:
                    logger.error(f"Não foi possível obter preço p/ {pos_ticker}, pulando.")
                    continue
                side_to_close = "BUY" if position["side"] == "SELL" else "SELL"
                await client.place_order(ticker=pos_ticker, side=side_to_close, size=position["size"], price=price, subaccount_id=int(position["subaccountId"]), reduce_only=True)
            else:
                logger.info(f"Manter posição existente em {pos_ticker}.")
    except Exception:
        logger.exception("Erro no protocolo de reset de segurança.")

    # Etapa 2: abrir novas posições para sinais BUY/SELL
    try:
        new_signals = [s for s in parsed if s["action"] in ("BUY", "SELL")]
        if not new_signals:
            logger.info("Nenhum sinal de abertura.")
            return

        account_balance = await client.get_account_balance()
        total = len(new_signals)
        margin_per_trade = account_balance / total if total > 0 else 0.0

        existing_markets = [p["market"] for p in await client.get_open_positions()]
        used_subaccounts = {int(p.get("subaccountId", 0)) for p in await client.get_open_positions()}
        next_sub = ISOLATED_MARGIN_SUBACCOUNT_START_ID

        for s in new_signals:
            ticker = s["ticker"]
            market_id = f"{ticker}-USD"
            if market_id in existing_markets:
                logger.info(f"Posição já existe para {ticker}, pulando.")
                continue

            while next_sub in used_subaccounts:
                next_sub += 1
            subaccount_id = next_sub
            used_subaccounts.add(subaccount_id)

            lev = LEVERAGE_CONFIG.get(ticker, LEVERAGE_CONFIG["DEFAULT"])
            price = await client.get_market_oracle_price(ticker)
            if not price:
                logger.error(f"Preço não disponível p/ {ticker}.")
                continue

            position_value = margin_per_trade * lev
            order_size = position_value / price
            logger.info(f"Abrindo {s['action']} {ticker}: size={order_size:.6f} @ {price:.2f} (valor nocional ${position_value:.2f})")
            await client.place_order(ticker=ticker, side=s["action"], size=order_size, price=price, subaccount_id=subaccount_id, reduce_only=False)

    except Exception:
        logger.exception("Erro na etapa de abertura de posições.")

# Entrypoint
def main():
    signals = [s.strip() for s in SIGNALS_OF_THE_DAY if s and s.strip()]
    # garante que rodamos o loop event-driven
    try:
        asyncio.run(process_signals_async(signals))
    except Exception:
        logger.exception("Erro crítico no loop principal.")
    finally:
        logging.shutdown()
        print("Execução finalizada. Verifique trading_bot.log para detalhes.")

if __name__ == "__main__":
    main()

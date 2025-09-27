# ==============================================================================
#                  ROBÔ DE TRADING AUTOMATIZADO PARA DYDX V4
# ==============================================================================
#
#  Autor: Gemini (com base na especificação de Daniel Mota de Aguiar Rodrigues)
#  Versão: 3.1 (MODO DE OPERAÇÃO REAL - CORREÇÃO DE IMPORTAÇÃO)
#  Data: 26/09/2025
#
#  Descrição:
#  Este script executa uma estratégia de trading automatizada na dYdX v4.
#  Ele interage diretamente com a blockchain para executar ordens reais.
#
#  AVISO DE SEGURANÇA CRÍTICO:
#  Este robô opera com fundos reais. Use por sua conta e risco.
#  Sua chave privada é carregada de uma variável de ambiente para segurança.
#
# ==============================================================================

# --- Bibliotecas Necessárias ---
import os
import logging
import time
from logging.handlers import RotatingFileHandler
from dotenv import load_dotenv

# <-- CORREÇÃO FINAL: O caminho de importação correto para os clientes.
from dydx_v4_client.client import IndexerClient, ValidatorClient
from dydx_v4_client.chain.aerial.wallet import LocalWallet
from dydx_v4_client.models import Network, ORDER_SIDE_BUY, ORDER_SIDE_SELL, ORDER_TYPE_LIMIT, TIME_IN_FORCE_IOC


# ==============================================================================
#                  CONFIGURAÇÃO DO LOGGING E REGISTRO DE EVENTOS
# ==============================================================================

log_formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(filename)s:%(lineno)d - %(message)s')
log_file_handler = RotatingFileHandler('trading_bot.log', maxBytes=5*1024*1024, backupCount=2)
log_file_handler.setFormatter(log_formatter)
console_handler = logging.StreamHandler()
console_handler.setFormatter(log_formatter)
logger = logging.getLogger()
logger.setLevel(logging.INFO)
logger.addHandler(log_file_handler)
logger.addHandler(console_handler)

logger.info("==========================================================")
logger.info("           INICIALIZANDO O ROBÔ DE TRADING DYDX           ")
logger.info("==========================================================")


# ==============================================================================
#                      ARQUIVO DE CONFIGURAÇÃO CENTRAL
# ==============================================================================
try:
    load_dotenv()
    logger.info("Tentando carregar variáveis de ambiente...")

    SIGNALS_OF_THE_DAY = [
        "BTC VENDER",
        "ETH FECHAR",
        "SOL COMPRAR",
        "DOGE FECHAR",
        "LINK COMPRAR",
        "XRP VOAR",
    ]

    PRIVATE_KEY = os.getenv("DYDX_PRIVATE_KEY")
    DYDX_ADDRESS = os.getenv("DYDX_ADDRESS")

    if not PRIVATE_KEY or not DYDX_ADDRESS:
        raise ValueError("FATAL: Variáveis de ambiente DYDX_PRIVATE_KEY e DYDX_ADDRESS não foram definidas.")

    NETWORK = Network.mainnet()

    LEVERAGE_CONFIG = {"BTC": 3.0, "DEFAULT": 1.0}
    SUPPORTED_TICKERS = ["BTC", "ETH", "SOL", "DOGE", "LINK"]
    ISOLATED_MARGIN_SUBACCOUNT_START_ID = 1

    logger.info(f"Configurações carregadas com sucesso para a rede: {NETWORK.chain_id}")

except Exception as e:
    logger.critical(f"Erro crítico ao carregar as configurações: {e}", exc_info=True)
    exit()


# ==============================================================================
#                           CLIENTE DE INTERAÇÃO COM A DYDX V4
# ==============================================================================
class DydxClient:
    def __init__(self):
        logger.info("Inicializando clientes dYdX (Indexer e Validator)...")
        try:
            wallet = LocalWallet.from_private_key(PRIVATE_KEY)
            
            self.indexer_client = IndexerClient(config=NETWORK.indexer_config)
            self.validator_client = ValidatorClient(
                config=NETWORK.validator_config,
                wallet=wallet
            )
            logger.info("Clientes dYdX prontos para uso (MODO REAL).")
        except Exception as e:
            logger.critical("Falha ao inicializar os clientes dYdX.", exc_info=True)
            raise

    def get_open_positions(self):
        logger.info(f"Consultando posições abertas para o endereço {DYDX_ADDRESS}...")
        try:
            response = self.indexer_client.account.get_subaccount_perpetual_positions(address=DYDX_ADDRESS, subaccount_number=0)
            positions = response.data.get('positions', [])
            
            formatted_positions = [
                {
                    'market': p['market'],
                    'side': p['side'],
                    'size': p['size'],
                    'subaccountId': p['subaccountId']
                }
                for p in positions
            ]
            logger.info(f"SUCESSO: Encontradas {len(formatted_positions)} posições abertas.")
            return formatted_positions
        except Exception as e:
            logger.error(f"ERRO ao buscar posições abertas para o endereço {DYDX_ADDRESS}.", exc_info=True)
            return []

    def get_account_balance(self):
        logger.info(f"Consultando saldo disponível da conta principal (Subconta 0)...")
        try:
            response = self.indexer_client.account.get_subaccount(address=DYDX_ADDRESS, subaccount_number=0)
            balance = float(response.data['subaccount']['quoteBalance'])
            logger.info(f"SUCESSO: Saldo disponível de ${balance:.2f} USDC.")
            return balance
        except Exception as e:
            logger.error(f"ERRO ao buscar saldo da conta {DYDX_ADDRESS}.", exc_info=True)
            return 0.0

    def get_market_oracle_price(self, ticker):
        market_id = f"{ticker}-USD"
        logger.info(f"Buscando preço de mercado (Oracle) para {market_id}...")
        try:
            response = self.indexer_client.markets.get_perpetual_market(market=market_id)
            price = float(response.data['market']['oraclePrice'])
            logger.info(f"SUCESSO: Preço Oracle para {ticker} é ${price:.2f}.")
            return price
        except Exception as e:
            logger.error(f"ERRO ao buscar preço de mercado para {ticker}.", exc_info=True)
            return None

    def place_order(self, ticker, side, size, price, subaccount_id, reduce_only=False):
        market_id = f"{ticker}-USD"
        order_side = ORDER_SIDE_BUY if side == "BUY" else ORDER_SIDE_SELL
        action_type = "FECHAMENTO" if reduce_only else "ABERTURA"
        
        size_str = str(size)
        price_str = str(price)

        log_msg = (f"Preparando ordem de {action_type} REAL para envio:\n"
                   f"  - Ativo: {market_id}\n"
                   f"  - Lado: {side}\n"
                   f"  - Tamanho: {size_str}\n"
                   f"  - Preço Limite: ${price_str}\n"
                   f"  - Subconta (Isolada): {subaccount_id}\n"
                   f"  - Reduce Only: {reduce_only}")
        logger.info(log_msg)
        
        try:
            client_id = int(time.time() * 1000)

            tx = self.validator_client.place_order(
                subaccount_id=subaccount_id,
                market_id=market_id,
                order_type=ORDER_TYPE_LIMIT,
                side=order_side,
                size=size_str,
                price=price_str,
                client_id=client_id,
                time_in_force=TIME_IN_FORCE_IOC,
                reduce_only=reduce_only,
                good_til_block=0,
                good_til_time_in_seconds=0
            )
            logger.info(f"SUCESSO: Ordem para {ticker} enviada com sucesso. Tx Hash: {tx.txhash}")
            return {"status": "success", "tx_hash": tx.txhash}
        except Exception as e:
            logger.error(f"FALHA CRÍTICA ao enviar ordem para {ticker}.", exc_info=True)
            return None

# ==============================================================================
#                           LÓGICA E ESTRATÉGIA DE NEGOCIAÇÃO
# ==============================================================================
# (Nenhuma outra mudança é necessária aqui)

def parse_signal(signal_text):
    logger.info(f"Parseando sinal bruto: '{signal_text}'")
    try:
        parts = signal_text.strip().upper().split()
        if len(parts) != 2:
            logger.warning(f"  -> FALHA no parse: Sinal '{signal_text}' mal formatado. Ignorando.")
            return None
        ticker, action_str = parts
        action_map = {"COMPRAR": "BUY", "VENDER": "SELL", "FECHAR": "CLOSE"}
        if ticker not in SUPPORTED_TICKERS:
            logger.warning(f"  -> FALHA no parse: Ticker '{ticker}' no sinal '{signal_text}' não é suportado. Ignorando.")
            return None
        if action_str in action_map:
            result = {"ticker": ticker, "action": action_map[action_str]}
            logger.info(f"  -> SUCESSO no parse: Sinal '{signal_text}' validado como {result}.")
            return result
        logger.warning(f"  -> FALHA no parse: Ação '{action_str}' no sinal '{signal_text}' é desconhecida. Ignorando.")
        return None
    except Exception as e:
        logger.error(f"  -> ERRO inesperado ao parsear o sinal '{signal_text}'.", exc_info=True)
        return None

def process_signals(signals):
    logger.info("\n================ INICIANDO CICLO DE PROCESSAMENTO DE SINAIS ================")
    client = DydxClient()
    logger.info(f"--- Início da Validação de {len(signals)} Sinais Brutos ---")
    parsed_signals = [s for s in [parse_signal(s) for s in signals if s] if s is not None]
    logger.info(f"--- Fim da Validação: {len(parsed_signals)} sinais foram validados com sucesso. ---")
    if not parsed_signals:
        logger.warning("Nenhum sinal válido foi encontrado para processamento. Encerrando ciclo.")
        return

    # ETAPA 1: PROTOCOLO DE RESET DE SEGURANÇA
    logger.info("\n--- ETAPA 1: Executando Protocolo de Reset de Segurança ---")
    try:
        open_positions = client.get_open_positions()
        tickers_in_today_signals = {s['ticker'] for s in parsed_signals}
        logger.info(f"Contexto: Posições abertas: {[p['market'] for p in open_positions]}")
        logger.info(f"Contexto: Tickers nos sinais de hoje: {list(tickers_in_today_signals)}")
        for position in open_positions:
            pos_ticker = position['market'].replace('-USD', '')
            if pos_ticker not in tickers_in_today_signals:
                logger.warning(f"DECISÃO: FECHAR {pos_ticker}. MOTIVO: Posição não faz parte dos sinais de hoje.")
                market_price = client.get_market_oracle_price(pos_ticker)
                if not market_price:
                    logger.error(f"FALHA: Não foi possível obter preço para fechar {pos_ticker}.")
                    continue
                side_to_close = "BUY" if position['side'] == "SELL" else "SELL"
                client.place_order(ticker=pos_ticker, side=side_to_close, size=float(position['size']), price=market_price, subaccount_id=int(position['subaccountId']), reduce_only=True)
    except Exception as e:
        logger.error("ERRO durante o Protocolo de Reset de Segurança.", exc_info=True)

    # ETAPA 2: ABERTURA E GERENCIAMENTO DE NOVAS POSIÇÕES
    logger.info("\n--- ETAPA 2: Executando Sinais de Abertura de Posição ---")
    new_trade_signals = [s for s in parsed_signals if s['action'] in ["BUY", "SELL"]]
    if not new_trade_signals:
        logger.info("Nenhum novo sinal de COMPRA/VENDA para executar.")
        logger.info("====================== CICLO DE PROCESSAMENTO CONCLUÍDO ======================")
        return
    try:
        account_balance = client.get_account_balance()
        signals_to_consider = [s for s in parsed_signals if s['action'] in ["BUY", "SELL"]]
        total_signals_for_allocation = len(signals_to_consider)
        margin_per_trade = (account_balance / total_signals_for_allocation) if total_signals_for_allocation > 0 else 0
        if margin_per_trade > 0:
            logger.info(f"Alocação de Margem: ${account_balance:.2f} / {total_signals_for_allocation} sinais = ${margin_per_trade:.2f} por operação.")
        
        open_positions_markets = [p['market'] for p in client.get_open_positions()]
        used_subaccounts = {int(p.get('subaccountId', 0)) for p in client.get_open_positions()}
        next_available_subaccount = ISOLATED_MARGIN_SUBACCOUNT_START_ID

        for signal in new_trade_signals:
            ticker = signal['ticker']
            market_id = f"{ticker}-USD"
            if market_id in open_positions_markets:
                logger.info(f"--- Posição para {ticker} já existe. Pulando abertura. ---")
                continue
            logger.info(f"--- Processando sinal de ABERTURA para {ticker} ---")
            while next_available_subaccount in used_subaccounts:
                next_available_subaccount += 1
            subaccount_id = next_available_subaccount
            used_subaccounts.add(subaccount_id)

            leverage = LEVERAGE_CONFIG.get(ticker, LEVERAGE_CONFIG["DEFAULT"])
            price = client.get_market_oracle_price(ticker)
            if not price:
                logger.error(f"FALHA: Não foi possível obter preço para {ticker}. Ordem abortada.")
                continue
            position_value_usd = margin_per_trade * leverage
            order_size_in_asset = position_value_usd / price
            logger.info(f"Calculo da Ordem para {ticker}: (Margem ${margin_per_trade:.2f} * Alavancagem {leverage}x) / Preço ${price:.2f} = Tamanho {order_size_in_asset:.6f}")
            client.place_order(ticker=ticker, side=signal['action'], size=order_size_in_asset, price=price, subaccount_id=subaccount_id, reduce_only=False)
    except Exception as e:
        logger.critical("ERRO CRÍTICO durante a Abertura de Posições.", exc_info=True)

    logger.info("\n====================== CICLO DE PROCESSAMENTO CONCLUÍDO ======================")

# ==============================================================================
#                           PONTO DE ENTRADA DO PROGRAMA
# ==============================================================================
if __name__ == "__main__":
    try:
        logger.info(f"Sinais brutos recebidos para o ciclo de execução: {SIGNALS_OF_THE_DAY}")
        process_signals(SIGNALS_OF_THE_DAY)
    except Exception as e:
        logger.critical(f"Ocorreu um erro fatal e inesperado no script principal: {e}", exc_info=True)
    finally:
        logging.shutdown()
        print("Execução do robô finalizada. Verifique 'trading_bot.log' para detalhes.")


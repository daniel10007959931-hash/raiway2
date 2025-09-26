# 
========================================================================
====== 
#                  ROBÔ DE TRADING AUTOMATIZADO PARA DYDX V4 
# 
========================================================================
====== 
# 
#  Autor: Gemini (com base na especificação de Daniel Mota de Aguiar Rodrigues) 
#  Versão: 1.2 (Logging Excepcionalmente Detalhado) 
#  Data: 26/09/2025 
# 
#  Descrição: 
#  Este script executa uma estratégia de trading automatizada na dYdX v4. 
#  Ele foi projetado para ser implantado na plataforma Railway e utiliza 
#  práticas de segurança para o gerenciamento de chaves e logging robusto 
#  para facilitar a depuração e auditoria. 
# 
#  AVISO DE SEGURANÇA CRÍTICO: 
#  NUNCA exponha sua chave privada (PRIVATE_KEY) diretamente no código. 
#  Este script foi projetado para carregar a chave de uma variável de 
#  ambiente, que é a forma segura de gerenciá-la em plataformas como a Railway. 
# 
# 
========================================================================
====== 
 
# --- Bibliotecas Necessárias --- 
import os 
import logging 
from logging.handlers import RotatingFileHandler 
from dotenv import load_dotenv 
 
# Descomente as linhas abaixo quando a biblioteca dydx-v4-client estiver instalada 
# from dydx_v4_client import IndexerClient, ValidatorClient 
# from dydx_v4_client.constants import Network 
 
# 
========================================================================
====== 
#                  CONFIGURAÇÃO DO LOGGING E REGISTRO DE EVENTOS 
# 
========================================================================
====== 

# CÓDIGO CORRIGIDO (TUDO EM UMA LINHA)
log_formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(filename)s:%(lineno)d - %(message)s')

log_file_handler = RotatingFileHandler('trading_bot.log', maxBytes=5*1024*1024, 
backupCount=2) 
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
 
 
# 
========================================================================
====== 
#                      ARQUIVO DE CONFIGURAÇÃO CENTRAL 
# 
========================================================================
====== 
try: 
    load_dotenv() 
    logger.info("Tentando carregar variáveis de ambiente...") 
 
    SIGNALS_OF_THE_DAY = [ 
        "BTC VENDER", 
        "ETH FECHAR", 
        "SOL COMPRAR", 
        "DOGE FECHAR", 
        "LINK COMPRAR", # Ticker não suportado para teste de log 
        "XRP VOAR",     # Ação inválida para teste de log 
    ] 
 
    PRIVATE_KEY = os.getenv("DYDX_PRIVATE_KEY") 
    DYDX_ADDRESS = os.getenv("DYDX_ADDRESS") 
 
    if not PRIVATE_KEY or not DYDX_ADDRESS: 
        raise ValueError("FATAL: Variáveis de ambiente DYDX_PRIVATE_KEY e DYDX_ADDRESS não foram definidas.") 
 



    RPC_ENDPOINT = "https://dydx-mainnet-full-rpc.public.blastapi.io" 
    INDEXER_ENDPOINT = "https://indexer.dydx.trade/v4" 
 
    LEVERAGE_CONFIG = {"BTC": 3.0, "DEFAULT": 1.0} 
    SUPPORTED_TICKERS = ["BTC", "ETH", "SOL", "DOGE"] 
    ISOLATED_MARGIN_SUBACCOUNT_START_ID = 128 
 
    logger.info("Configurações carregadas com sucesso.") 
 
except Exception as e: 
    logger.critical(f"Erro crítico ao carregar as configurações: {e}", exc_info=True) 
    exit() 
 
 
# 
========================================================================
====== 
#                           CLIENTE DE INTERAÇÃO COM A DYDX V4 
# 
========================================================================
====== 
class DydxClient: 
    def __init__(self): 
        logger.info("Inicializando clientes dYdX (Indexer e Validator)...") 
        try: 
            self.indexer_client = None 
            self.validator_client = None 
            logger.info("Clientes dYdX prontos para uso (MODO SIMULADO).") 
        except Exception as e: 
            logger.critical("Falha ao inicializar os clientes dYdX.", exc_info=True) 
            raise 
 
    def get_open_positions(self): 
        logger.info(f"Consultando posições abertas para o endereço {DYDX_ADDRESS}...") 
        try: 
            simulated_positions = [ 
                {'market': 'SOL-USD', 'side': 'BUY', 'size': '10.5', 'subaccountId': 128}, 
                {'market': 'LINK-USD', 'side': 'SELL', 'size': '50.0', 'subaccountId': 129} 
            ] 
            logger.info(f"SUCESSO (Simulação): Encontradas {len(simulated_positions)} posições abertas: {simulated_positions}") 
            return simulated_positions 
        except Exception as e: 



            logger.error(f"ERRO ao buscar posições abertas no Indexer para o endereço {DYDX_ADDRESS}.", exc_info=True) 
            return [] 
 
    def get_account_balance(self): 
        logger.info(f"Consultando saldo disponível da conta {DYDX_ADDRESS}...") 
        try: 
            simulated_balance = 1000.0 
            logger.info(f"SUCESSO (Simulação): Saldo disponível de ${simulated_balance:.2f} USDC.") 
            return simulated_balance 
        except Exception as e: 
            logger.error(f"ERRO ao buscar saldo da conta {DYDX_ADDRESS}.", exc_info=True) 
            return 0.0 
 
    def get_market_bbo_price(self, ticker): 
        logger.info(f"Buscando preço de mercado (BBO) para {ticker}-USD...") 
        try: 
            prices = {"BTC": 68500.0, "ETH": 3550.0, "SOL": 152.50, "DOGE": 0.16, "LINK": 18.0} 
            price = prices.get(ticker) 
            if price: 
                logger.info(f"SUCESSO (Simulação): Preço BBO para {ticker} é ${price:.2f}.") 
                return price 
            else: 
                raise ValueError(f"Preço para ticker '{ticker}' não encontrado na simulação.") 
        except Exception as e: 
            logger.error(f"ERRO ao buscar preço de mercado para {ticker}.", exc_info=True) 
            return None 
 
    def place_order(self, ticker, side, size, price, subaccount_id, reduce_only=False): 
        action_type = "FECHAMENTO" if reduce_only else "ABERTURA" 
        log_msg = (f"Preparando ordem de {action_type} para envio:\n" 
                   f"  - Ativo: {ticker}-USD\n" 
                   f"  - Lado: {side}\n" 
                   f"  - Tamanho: {size:.6f}\n" 
                   f"  - Preço Limite (BBO): ${price:.4f}\n" 
                   f"  - Subconta (Isolada): {subaccount_id}\n" 
                   f"  - Reduce Only: {reduce_only}") 
        logger.info(log_msg) 
        try: 
            logger.warning(f"--- MODO DE SIMULAÇÃO: A ordem para {ticker} NÃO será realmente enviada. ---") 
            tx_hash = f"simulated_tx_{ticker}_{subaccount_id}" 



            logger.info(f"SUCESSO (Simulação): Ordem para {ticker} processada com sucesso. Tx Hash: {tx_hash}") 
            return {"status": "success", "tx_hash": tx_hash} 
        except Exception as e: 
            logger.error(f"FALHA CRÍTICA ao enviar ordem para {ticker}.", exc_info=True) 
            return None 
 
# 
========================================================================
====== 
#                           LÓGICA E ESTRATÉGIA DE NEGOCIAÇÃO 
# 
========================================================================
====== 
def parse_signal(signal_text): 
    """Converte um sinal de texto em um dicionário estruturado e validado.""" 
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
    parsed_signals = [parse_signal(s) for s in signals if s] 
    parsed_signals = [s for s in parsed_signals if s is not None] # Remove os nulos 
    logger.info(f"--- Fim da Validação: {len(parsed_signals)} sinais foram validados com sucesso. {len(signals) - len(parsed_signals)} foram ignorados. ---") 
 
    if not parsed_signals: 
        logger.warning("Nenhum sinal válido foi encontrado para processamento. Encerrando ciclo.") 
        return 
 
    # --- ETAPA 1: PROTOCOLO DE RESET DE SEGURANÇA --- 
    logger.info("\n--- ETAPA 1: Executando Protocolo de Reset de Segurança ---") 
    try: 
        open_positions = client.get_open_positions() 
        tickers_in_today_signals = {s['ticker'] for s in parsed_signals} 
        logger.info(f"Contexto para o Reset: Posições abertas encontradas: {[p['market'] for p in open_positions]}") 
        logger.info(f"Contexto para o Reset: Tickers nos sinais de hoje: {list(tickers_in_today_signals)}") 
         
        positions_to_close_count = 0 
        for position in open_positions: 
            pos_ticker = position['market'].replace('-USD', '') 
            logger.info(f"Analisando posição aberta em {pos_ticker}...") 
             
            if pos_ticker not in tickers_in_today_signals: 
                positions_to_close_count += 1 
                logger.warning(f"  -> DECISÃO: FECHAR {pos_ticker}. MOTIVO: Posição não faz parte dos sinais de hoje.") 
                 
                market_price = client.get_market_bbo_price(pos_ticker) 
                if not market_price: 
                    logger.error(f"  -> FALHA: Não foi possível obter preço para fechar {pos_ticker}. Fechamento abortado para este ativo.") 
                    continue 
 
                side_to_close = "BUY" if position['side'] == "SELL" else "SELL" 
                client.place_order( 
                    ticker=pos_ticker, side=side_to_close, size=float(position['size']), 



                    price=market_price, subaccount_id=int(position['subaccountId']), reduce_only=True 
                ) 
            else: 
                logger.info(f"  -> DECISÃO: MANTER {pos_ticker}. MOTIVO: Ativo está presente nos sinais de hoje.") 
         
        if positions_to_close_count == 0: 
            logger.info("Nenhuma posição aberta necessitou de fechamento obrigatório.") 
 
    except Exception as e: 
        logger.error("ERRO durante o Protocolo de Reset de Segurança.", exc_info=True) 
 
    # --- ETAPA 2: ABERTURA E GERENCIAMENTO DE NOVAS POSIÇÕES --- 
    logger.info("\n--- ETAPA 2: Executando Sinais de Abertura de Posição ---") 
     
    new_trade_signals = [s for s in parsed_signals if s['action'] in ["BUY", "SELL"]] 
     
    if not new_trade_signals: 
        logger.info("Nenhum novo sinal de COMPRA/VENDA para executar. Apenas sinais de FECHAR ou de manutenção foram processados.") 
        logger.info("====================== CICLO DE PROCESSAMENTO CONCLUÍDO ======================") 
        return 
 
    try: 
        account_balance = client.get_account_balance() 
        total_signals_for_allocation = len(parsed_signals) 
        margin_per_trade = 0 
 
        if total_signals_for_allocation > 0: 
            margin_per_trade = account_balance / total_signals_for_allocation 
            logger.info("--- Início do Cálculo de Alocação de Margem ---") 
            logger.info(f"  - Saldo Total Disponível: ${account_balance:.2f}") 
            logger.info(f"  - Número Total de Sinais Válidos: {total_signals_for_allocation}") 
            logger.info(f"  - Cálculo: ${account_balance:.2f} / {total_signals_for_allocation} = ${margin_per_trade:.2f}") 
            logger.info(f"  - Margem Base por Nova Operação: ${margin_per_trade:.2f}") 
            logger.info("--- Fim do Cálculo de Alocação de Margem ---") 
        else: 
            logger.warning("Nenhum sinal válido para basear a alocação de margem. Novas posições não serão abertas.") 
 
        open_positions = client.get_open_positions() 
        used_subaccounts = {int(p.get('subaccountId', 0)) for p in open_positions} 



        next_available_subaccount = ISOLATED_MARGIN_SUBACCOUNT_START_ID 
         
        logger.info(f"\nIniciando processamento de {len(new_trade_signals)} novas operações de COMPRA/VENDA...") 
        for signal in new_trade_signals: 
            ticker = signal['ticker'] 
            logger.info(f"--- Processando sinal de ABERTURA para {ticker} ---") 
             
            logger.info(f"  - Procurando subconta livre a partir de ID {next_available_subaccount} (usadas: {used_subaccounts})...") 
            while next_available_subaccount in used_subaccounts: 
                next_available_subaccount += 1 
            subaccount_id = next_available_subaccount 
            logger.info(f"  - Subconta {subaccount_id} alocada para a nova posição em {ticker}.") 
            used_subaccounts.add(subaccount_id) 
             
            leverage = LEVERAGE_CONFIG.get(ticker, LEVERAGE_CONFIG["DEFAULT"]) 
            price = client.get_market_bbo_price(ticker) 
             
            if not price: 
                logger.error(f"  - FALHA: Não foi possível obter preço para {ticker}. Ordem abortada.") 
                continue 
             
            logger.info(f"  - Calculando tamanho da ordem para {ticker}:") 
            position_value_usd = margin_per_trade * leverage 
            order_size_in_asset = position_value_usd / price 
            logger.info(f"    - Margem: ${margin_per_trade:.2f} * Alavancagem: {leverage}x = Valor Nocional de ${position_value_usd:.2f}") 
            logger.info(f"    - Valor Nocional: ${position_value_usd:.2f} / Preço do Ativo: ${price:.2f} = Tamanho de {order_size_in_asset:.6f} {ticker}") 
             
            client.place_order( 
                ticker=ticker, side=signal['action'], size=order_size_in_asset, 
                price=price, subaccount_id=subaccount_id, reduce_only=False 
            ) 
 
    except Exception as e: 
        logger.critical("ERRO CRÍTICO durante a Abertura e Gerenciamento de Posições.", exc_info=True) 
 
    logger.info("\n====================== CICLO DE PROCESSAMENTO CONCLUÍDO ======================") 
 
 



# 
========================================================================
====== 
#                           PONTO DE ENTRADA DO PROGRAMA 
# 
========================================================================
====== 
if __name__ == "__main__": 
    try: 
        logger.info(f"Sinais brutos recebidos para o ciclo de execução: 
{SIGNALS_OF_THE_DAY}") 
        process_signals(SIGNALS_OF_THE_DAY) 
    except Exception as e: 
        logger.critical(f"Ocorreu um erro fatal e inesperado no script principal: {e}", exc_info=True) 
    finally: 
        logging.shutdown() # Garante que todos os logs sejam escritos antes de fechar 
        print("Execução do robô finalizada. Verifique 'trading_bot.log' para detalhes.")

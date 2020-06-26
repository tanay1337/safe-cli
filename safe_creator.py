import argparse
import sys
from binascii import Error
from typing import List, Set

import pyfiglet
from eth_account import Account
from eth_account.signers.local import LocalAccount
from prompt_toolkit import HTML, print_formatted_text

from gnosis.eth import EthereumClient
from gnosis.safe import ProxyFactory, Safe

from safe_cli.prompt_parser import PromptParser, check_ethereum_address


def positive_integer(number: str) -> int:
    number = int(number)
    if number <= 0:
        raise argparse.ArgumentTypeError(f'{number} is not a valid threshold. Must be > 0')
    return number


def check_private_key(private_key: str) -> str:
    """
    Ethereum private key validator for ArgParse
    :param private_key: Ethereum Private key
    :return: Ethereum Private key
    """
    try:
        Account.from_key(private_key)
    except (ValueError, Error):  # TODO Report `Error` exception as a bug of eth_account
        raise argparse.ArgumentTypeError(f'{private_key} is not a valid private key')
    return private_key


parser = argparse.ArgumentParser()
parser.add_argument('node_url', help='Ethereum node url')
parser.add_argument('private_key', help='Deployer private_key', type=check_private_key)
parser.add_argument('--threshold', help='Threshold', type=positive_integer, default=1)
parser.add_argument('--owners', help='Owners. By default it will be just the deployer', nargs='+',
                    type=check_ethereum_address)

if __name__ == '__main__':
    args = parser.parse_args()
    node_url: str = args.node_url
    account: LocalAccount = Account.from_key(args.private_key)
    owners: List[str] = list(set(args.owners)) if args.owners else [account.address]
    threshold: int = args.threshold
    if len(owners) < threshold:
        print_formatted_text('Threshold cannot be bigger than the number of unique owners')
        sys.exit(1)

    ethereum_client = EthereumClient(node_url)

    print_formatted_text(pyfiglet.figlet_format('Gnosis Safe Creator'))  # Print fancy text
    print_formatted_text(f'Creating new Safe with owners={owners} and threshold={threshold}')
    # Support only Mainnet, Rinkeby, Goerli and Kovan
    safe_contract_address = '0x34CfAC646f301356fAa8B21e94227e3583Fe3F5F'
    proxy_factory_address = '0x76E2cFc1F5Fa8F6a5b3fC4c8F4788F0116861F9B'
    callback_handler_address = '0xd5D82B6aDDc9027B22dCA772Aa68D5d74cdBdF44'
    if not ethereum_client.w3.eth.getCode(proxy_factory_address):
        print_formatted_text('Network not supported')
        sys.exit(1)

    salt_nonce = 5  # Must be random. TODO Add support for CPK
    gas_price = 0
    safe_creation_tx = Safe.build_safe_create2_tx(ethereum_client, safe_contract_address,
                                                  proxy_factory_address, salt_nonce, owners, threshold, gas_price,
                                                  fallback_handler=callback_handler_address,
                                                  payment_token=None)
    proxy_factory = ProxyFactory(proxy_factory_address, ethereum_client)
    ethereum_tx_sent = proxy_factory.deploy_proxy_contract_with_nonce(account,
                                                                      safe_contract_address,
                                                                      safe_creation_tx.safe_setup_data,
                                                                      safe_creation_tx.salt_nonce)
    print_formatted_text(f'Tx with tx-hash={ethereum_tx_sent.tx_hash.hex()} '
                         f'will create safe={ethereum_tx_sent.contract_address}')

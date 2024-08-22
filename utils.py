from solders.pubkey import Pubkey # type: ignore
from solders.instruction import Instruction # type: ignore
from solana.transaction import AccountMeta
from solana.rpc.types import TokenAccountOpts
from solders.compute_budget import set_compute_unit_limit, set_compute_unit_price # type: ignore

from solana.rpc.commitment import Commitment
from solana.rpc.types import TxOpts
from solana.transaction import Transaction
import solders.system_program as sp
from solders.keypair import Keypair # type: ignore
import json, requests

import spl.token.instructions as spl_token
from spl.token.client import Token
from spl.token._layouts import ACCOUNT_LAYOUT
from spl.token.constants import WRAPPED_SOL_MINT

from layouts import SWAP_LAYOUT, LIQ_LAYOUT
from typing import Tuple

LAMPORTS_PER_SOL = 1000000000
AMM_PROGRAM_ID = Pubkey.from_string('675kPX9MHTjS2zt1qfr1NYHuzeLXfQM9H24wFSUt1Mp8')
SERUM_PROGRAM_ID = Pubkey.from_string('srmqPvymJeFKQ4zGQed1GFppgkRHL9kaELCbyksJtPX')
AMM_POOL_ID = Pubkey.from_string('CDSr3ssLcRB6XYPJwAfFt18MZvEZp4LjHcvzBVZ45duo')
withdrawQueue = Pubkey.from_string("11111111111111111111111111111111")
lpVault = Pubkey.from_string("11111111111111111111111111111111")

def getBalance(solana_client, mint, payer):
    try:
      tokenPk = mint
      amount_in = 0
      accountProgramId = solana_client.get_account_info_json_parsed(tokenPk)
      programid_of_token = accountProgramId.value.owner

      accounts = (
        solana_client.get_token_accounts_by_owner_json_parsed(
          payer.pubkey(), TokenAccountOpts(program_id=programid_of_token)
        )
      ).value
      
      for account in accounts:
        mint_in_acc = account.account.data.parsed["info"]["mint"]
        if str(mint_in_acc) == str(mint):
          amount_in = account.account.data.parsed["info"]["tokenAmount"]["uiAmount"]
          break
      return amount_in
    except Exception as e:
      print('error_occured', e)
      pass

def extract_pool_info(pools_list: list, mint: str) -> dict:
  for pool in pools_list:
    if pool['baseMint'] == mint and pool['quoteMint'] == 'So11111111111111111111111111111111111111112':
      return pool
    elif pool['quoteMint'] == mint and pool['baseMint'] == 'So11111111111111111111111111111111111111112':
      return pool
  raise Exception(f'{mint} pool not found!')
  
def fetch_pool_keys(mint: str):
  amm_info = {}
  all_pools = {}
  try:
    # Using this so it will be faster else no option, we go the slower way.
    with open('all_pools.json', 'r') as file:
      all_pools = json.load(file)
    amm_info = extract_pool_info(all_pools, mint)
  except:
    print('no local pool keys found, downloading from server, might take some time, please wait ...')
    resp = requests.get('https://api.raydium.io/v2/sdk/liquidity/mainnet.json', stream=True)
    pools = resp.json()
    official = pools['official']
    unofficial = pools['unOfficial']
    all_pools = official + unofficial

    # Store all_pools in a JSON file
    with open('all_pools.json', 'w') as file:
      json.dump(all_pools, file)
    try:
      amm_info = extract_pool_info(all_pools, mint)
    except:
      return "failed"

  return {
    'amm_id': Pubkey.from_string(amm_info['id']),
    'authority': Pubkey.from_string(amm_info['authority']),
    'base_mint': Pubkey.from_string(amm_info['baseMint']),
    'base_decimals': amm_info['baseDecimals'],
    'quote_mint': Pubkey.from_string(amm_info['quoteMint']),
    'quote_decimals': amm_info['quoteDecimals'],
    'lp_mint': Pubkey.from_string(amm_info['lpMint']),
    'open_orders': Pubkey.from_string(amm_info['openOrders']),
    'target_orders': Pubkey.from_string(amm_info['targetOrders']),
    'base_vault': Pubkey.from_string(amm_info['baseVault']),
    'quote_vault': Pubkey.from_string(amm_info['quoteVault']),
    'market_id': Pubkey.from_string(amm_info['marketId']),
    'market_base_vault': Pubkey.from_string(amm_info['marketBaseVault']),
    'market_quote_vault': Pubkey.from_string(amm_info['marketQuoteVault']),
    'market_authority': Pubkey.from_string(amm_info['marketAuthority']),
    'bids': Pubkey.from_string(amm_info['marketBids']),
    'asks': Pubkey.from_string(amm_info['marketAsks']),
    'event_queue': Pubkey.from_string(amm_info['marketEventQueue'])
  }

def make_swap_instruction(amount_in: int, token_account_in: Pubkey.from_string, token_account_out: Pubkey.from_string, accounts: dict, mint, ctx, owner) -> Instruction:
  tokenPk = mint
  accountProgramId = ctx.get_account_info_json_parsed(tokenPk)
  TOKEN_PROGRAM_ID = accountProgramId.value.owner

  keys = [
    AccountMeta(pubkey=TOKEN_PROGRAM_ID, is_signer=False, is_writable=False),
    AccountMeta(pubkey=accounts["amm_id"], is_signer=False, is_writable=True),
    AccountMeta(pubkey=accounts["authority"], is_signer=False, is_writable=False),
    AccountMeta(pubkey=accounts["open_orders"], is_signer=False, is_writable=True),
    AccountMeta(pubkey=accounts["target_orders"], is_signer=False, is_writable=True),
    AccountMeta(pubkey=accounts["base_vault"], is_signer=False, is_writable=True),
    AccountMeta(pubkey=accounts["quote_vault"], is_signer=False, is_writable=True),
    AccountMeta(pubkey=SERUM_PROGRAM_ID, is_signer=False, is_writable=False),
    AccountMeta(pubkey=accounts["market_id"], is_signer=False, is_writable=True),
    AccountMeta(pubkey=accounts["bids"], is_signer=False, is_writable=True),
    AccountMeta(pubkey=accounts["asks"], is_signer=False, is_writable=True),
    AccountMeta(pubkey=accounts["event_queue"], is_signer=False, is_writable=True),
    AccountMeta(pubkey=accounts["market_base_vault"], is_signer=False, is_writable=True),
    AccountMeta(pubkey=accounts["market_quote_vault"], is_signer=False, is_writable=True),
    AccountMeta(pubkey=accounts["market_authority"], is_signer=False, is_writable=False),
    AccountMeta(pubkey=token_account_in, is_signer=False, is_writable=True),  # UserSourceTokenAccount
    AccountMeta(pubkey=token_account_out, is_signer=False, is_writable=True),  # UserDestTokenAccount
    AccountMeta(pubkey=owner.pubkey(), is_signer=True, is_writable=False)  # UserOwner
  ]

  data = SWAP_LAYOUT.build(
    dict(
      instruction=9,
      amount_in=int(amount_in),
      min_amount_out=0
    )
  )
  
  return Instruction(AMM_PROGRAM_ID, data, keys)

def sell_get_token_account(ctx, owner: Pubkey.from_string, mint: Pubkey.from_string):
  try:
    account_data = ctx.get_token_accounts_by_owner(owner, TokenAccountOpts(mint))
    return account_data.value[0].pubkey
  except:
    print("Mint Token Not found")
    return None

async def make_liquidity_remover_instruction(
  payer_pk, Lp_account, quoteAccount, BaseAccount, accounts, TOKEN_PROGRAM_ID, amount
):
  keys = [
    #     // system
    AccountMeta(pubkey=TOKEN_PROGRAM_ID, is_signer=False, is_writable=False),
    #     // amm
    AccountMeta(pubkey=accounts["amm_id"], is_signer=False, is_writable=True),
    AccountMeta(pubkey=accounts["authority"], is_signer=False, is_writable=False),
    AccountMeta(pubkey=accounts["open_orders"], is_signer=False, is_writable=True),
    AccountMeta(
        pubkey=accounts["target_orders"], is_signer=False, is_writable=True
    ),
    AccountMeta(pubkey=accounts["lp_mint"], is_signer=False, is_writable=True),
    AccountMeta(pubkey=accounts["base_vault"], is_signer=False, is_writable=True),
    AccountMeta(pubkey=accounts["quote_vault"], is_signer=False, is_writable=True),
    AccountMeta(pubkey=withdrawQueue, is_signer=False, is_writable=True),
    AccountMeta(pubkey=lpVault, is_signer=False, is_writable=True),
    #     // market
    AccountMeta(pubkey=SERUM_PROGRAM_ID, is_signer=False, is_writable=False),
    AccountMeta(pubkey=accounts["market_id"], is_signer=False, is_writable=True),
    AccountMeta(
        pubkey=accounts["market_base_vault"], is_signer=False, is_writable=True
    ),
    AccountMeta(
        pubkey=accounts["market_quote_vault"], is_signer=False, is_writable=True
    ),
    AccountMeta(
        pubkey=accounts["market_authority"], is_signer=False, is_writable=False
    ),
    #     // user
    AccountMeta(pubkey=Lp_account, is_signer=False, is_writable=True),
    AccountMeta(pubkey=BaseAccount, is_signer=False, is_writable=True),
    AccountMeta(pubkey=quoteAccount, is_signer=False, is_writable=True),
    AccountMeta(pubkey=payer_pk, is_signer=True, is_writable=False),
    #     // market
    AccountMeta(pubkey=accounts["event_queue"], is_signer=False, is_writable=True),
    AccountMeta(pubkey=accounts["bids"], is_signer=False, is_writable=True),
    AccountMeta(pubkey=accounts["asks"], is_signer=False, is_writable=True),
  ]
  data = LIQ_LAYOUT.build(dict(instruction=4, amount_in=amount))
  return Instruction(AMM_PROGRAM_ID, data, keys)

def create_account_with_seed_args(
    ctx,
    program_id: Pubkey,
    owner: Pubkey,
    payer: Keypair,
    amount: int,
    skip_confirmation: bool,
    commitment: Commitment,
) -> Tuple[Pubkey, Transaction, Keypair, Keypair, TxOpts]:

    GAS_PRICE = 5000000
    GAS_LIMIT = 10000000

    new_keypair = Keypair()
    seed_str = str(new_keypair.pubkey())[0:32]

    seed_pk = Pubkey.create_with_seed(payer.pubkey(), seed_str, program_id)
    amount = Token.get_min_balance_rent_for_exempt_for_account(ctx)

    txn = Transaction(fee_payer=payer.pubkey())

    """
    Gas and shit
    """
    txn.add(set_compute_unit_price(GAS_PRICE))
    txn.add(set_compute_unit_limit(GAS_LIMIT))

    txn.add(
      sp.create_account_with_seed(
        sp.CreateAccountWithSeedParams(
          from_pubkey=payer.pubkey(),
          to_pubkey=seed_pk,
          base=payer.pubkey(),
          seed=seed_str,
          lamports=amount,
          space=ACCOUNT_LAYOUT.sizeof(),
          owner=program_id,
        )
      )
    )

    txn.add(
      spl_token.initialize_account(
        spl_token.InitializeAccountParams(
            account=seed_pk,
            mint=WRAPPED_SOL_MINT,
            owner=owner,
            program_id=program_id,
        )
      )
    )

    return (
      seed_pk,
      txn,
      payer,
      new_keypair,
      TxOpts(skip_confirmation=skip_confirmation, preflight_commitment=commitment),
    )

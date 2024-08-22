import asyncio, os, time, csv, pytz, json
from datetime import datetime
from dotenv import load_dotenv

from solana.rpc.api import Client
from solana.rpc.api import RPCException
from solana.rpc.async_api import AsyncClient
from solana.rpc.types import TokenAccountOpts, TxOpts
from solana.rpc.commitment import Commitment, Confirmed
from solana.transaction import AccountMeta, Transaction

from solders.pubkey import Pubkey # type: ignore
from solders.keypair import Keypair # type: ignore
from solders.instruction import Instruction # type: ignore
from solders.compute_budget import set_compute_unit_price, set_compute_unit_limit # type: ignore
from solders.system_program import create_account, CreateAccountParams

from spl.token.constants import WRAPPED_SOL_MINT, TOKEN_PROGRAM_ID, MINT_LEN
from spl.token.client import Token
from spl.token.core import _TokenCore
from spl.token.instructions import create_associated_token_account, \
  get_associated_token_address, \
  close_account, CloseAccountParams, \
  initialize_mint, InitializeMintParams, \
  mint_to, MintToParams
from layouts import METADAT_STRUCTURE
from utils import fetch_pool_keys, \
  make_swap_instruction, \
  sell_get_token_account, \
  getBalance, \
  create_account_with_seed_args, \
  make_liquidity_remover_instruction
from nft import upload_token_metadata_to_IPFS

load_dotenv()
solana_client = Client(os.getenv("RPC_HTTPS_URL"))
async_client = AsyncClient(os.getenv("RPC_HTTPS_URL"))

SYSTEM_PROGRAM = Pubkey.from_string('11111111111111111111111111111111')
SYSTEM_RENT = Pubkey.from_string('SysvarRent111111111111111111111111111111111')
TOKEN_METADATA_PROGRAM = Pubkey.from_string("metaqbxxUerdq28cj1RbAWkYQm3ybzjb6a8bt518x1s")

async def get_transaction_with_timeout(client, txid, commitment=Confirmed, timeout=10):
  loop = asyncio.get_event_loop()
  return await loop.run_in_executor(None, client.get_transaction, txid, "json")

async def get_token_account(ctx, owner: Pubkey.from_string, mint: Pubkey.from_string):
  try:
    account_data = await ctx.get_token_accounts_by_owner(owner, TokenAccountOpts(mint))
    return account_data.value[0].pubkey, None
  except:
    swap_associated_token_address = get_associated_token_address(owner, mint)
    swap_token_account_Instructions = create_associated_token_account(owner, owner, mint)
    return swap_associated_token_address, swap_token_account_Instructions

async def buy(token_to_swap, payer, amount):
  retry_count = 0
  while retry_count < int(os.getenv('MAX_RETRIES')):
    try:
      mint = Pubkey.from_string(token_to_swap)
      pool_keys = fetch_pool_keys(str(mint))
      accountProgramId = solana_client.get_account_info_json_parsed(mint)
      amount_in = int(amount * 10 ** pool_keys['quote_decimals'])
      TOKEN_PROGRAM_ID = accountProgramId.value.owner
      
      balance_needed = Token.get_min_balance_rent_for_exempt_for_account(solana_client)
      swap_associated_token_address, swap_token_account_Instructions = await get_token_account(async_client, payer.pubkey(), mint)
      WSOL_token_account, swap_tx, payer, Wsol_account_keyPair, opts, = _TokenCore._create_wrapped_native_account_args(
                TOKEN_PROGRAM_ID, payer.pubkey(), payer, amount_in,
                False, balance_needed, Commitment("confirmed"))
      
      instructions_swap = make_swap_instruction(amount_in,
                                                WSOL_token_account,
                                                swap_associated_token_address,
                                                pool_keys,
                                                mint,
                                                solana_client,
                                                payer)
      
      params = CloseAccountParams(account=WSOL_token_account, dest=payer.pubkey(), owner=payer.pubkey(), program_id=TOKEN_PROGRAM_ID)
      closeAcc = (close_account(params))
      
      if swap_token_account_Instructions != None:
          swap_tx.add(swap_token_account_Instructions)

      #compute unit price and comute unit limit gauge your gas fees more explanations on how to calculate in a future article
      swap_tx.add(instructions_swap, set_compute_unit_price(25_232), set_compute_unit_limit(200_337), closeAcc)
      
      # Execute Transaction
      txn = solana_client.send_transaction(swap_tx, payer,Wsol_account_keyPair)
      txid_string_sig = txn.value
      
      if txid_string_sig:
          print("Waiting For Transaction Confirmation .......")
          print(f"Transaction Signature: https://solscan.io/tx/{txid_string_sig}")
          # Await transaction confirmation with a timeout
          await asyncio.wait_for(
              get_transaction_with_timeout(solana_client, txid_string_sig, commitment="confirmed", timeout=10),
              timeout=15
          )
          
          data = [
            datetime.now(pytz.utc).strftime('%Y-%m-%d %H:%M:%S'),
            'swap_bome',
            txid_string_sig,
            amount_in,
            'complete'
          ]
          update_log('transaction', data)
          print("Transaction Confirmed")
          return True
      return True
    except asyncio.TimeoutError:
      print("Transaction confirmation timed out. Retrying...")
      retry_count += 1
      time.sleep(int(os.getenv('RETRY_DELAY')))
    except RPCException as e:
      print(f"RPC Error: [{e.args[0].message}]... Retrying...")
      retry_count += 1
      time.sleep(int(os.getenv('RETRY_DELAY')))
    except Exception as e:
      print(f"Unhandled exception on buy: {e}. Retrying...")
      retry_count = os.getenv('MAX_RETRIES')
      data = [
        datetime.now(pytz.utc).strftime('%Y-%m-%dT%H:%M:%S.%fZ'),
        'swap_bome',
        '-',
        amount_in,
        'failed'
      ]
      update_log('transaction', data)
      return False
    print("Failed to confirm transaction after maximum retries.")
    return False

async def sell(token_to_swap, payer, amount):
  retry_count = 0
  while retry_count < int(os.getenv('MAX_RETRIES')):
    try:
      mint = Pubkey.from_string(token_to_swap)
      pool_keys = fetch_pool_keys(str(mint))
      sol= WRAPPED_SOL_MINT
      accountProgramId = solana_client.get_account_info_json_parsed(mint)
      amount_in = int(amount * 10 ** pool_keys['base_decimals'])
      TOKEN_PROGRAM_ID = accountProgramId.value.owner
      
      account_balance = 0
      accounts = solana_client.get_token_accounts_by_owner_json_parsed(payer.pubkey(), TokenAccountOpts(program_id=TOKEN_PROGRAM_ID)).value
      for account in accounts:
        mint_in_acc = account.account.data.parsed['info']['mint']
        if mint_in_acc == str(mint):
          account_balance = int(account.account.data.parsed['info']['tokenAmount']['amount'])
          break

      swap_token_account = sell_get_token_account(solana_client, payer.pubkey(), mint)
      WSOL_token_account, WSOL_token_account_Instructions = await get_token_account(solana_client, payer.pubkey(), sol)
      
      if account_balance < amount_in:
        print('Your account is low balance to swap.')
        return False

      instructions_swap = make_swap_instruction(amount_in,
                                                swap_token_account,
                                                WSOL_token_account,
                                                pool_keys,
                                                mint,
                                                solana_client,
                                                payer)
      
      params = CloseAccountParams(account=WSOL_token_account, dest=payer.pubkey(), owner=payer.pubkey(), program_id=TOKEN_PROGRAM_ID)
      closeAcc = (close_account(params))
      
      swap_tx = Transaction()
      if WSOL_token_account_Instructions != None:
        recent_blockhash = solana_client.get_latest_blockhash(commitment="confirmed")
        swap_tx.recent_blockhash = recent_blockhash.value.blockhash
        swap_tx.add(WSOL_token_account_Instructions)

      #Modify Compute Unit Limit and Price Accordingly  to your Gas Preferences
      swap_tx.add(instructions_swap, set_compute_unit_price(25_232), set_compute_unit_limit(200_337))
      swap_tx.add(closeAcc)
      
      # Execute Transaction
      txn = solana_client.send_transaction(swap_tx, payer)
      txid_string_sig = txn.value
      
      if txid_string_sig:
        print("Waiting For Transaction Confirmation .......")
        print(f"Transaction Signature: https://solscan.io/tx/{txid_string_sig}")
        # Await transaction confirmation with a timeout
        await asyncio.wait_for(
          get_transaction_with_timeout(solana_client, txid_string_sig, commitment="confirmed", timeout=10),
          timeout=15
        )
        
        data = [
          datetime.now(pytz.utc).strftime('%Y-%m-%d %H:%M:%S'),
          'swap_sol',
          txid_string_sig,
          amount_in,
          'complete'
        ]
        update_log('transaction', data)
        print("Transaction Confirmed")
        return True
    except asyncio.TimeoutError:
      print("Transaction confirmation timed out. Retrying...")
      retry_count += 1
      time.sleep(int(os.getenv('RETRY_DELAY')))
    except RPCException as e:
      print(f"RPC Error: [{e.args[0].message}]... Retrying...")
      retry_count += 1
      time.sleep(int(os.getenv('RETRY_DELAY')))
    except Exception as e:
      print(f"Unhandled exception on sell: {e}. Retrying...")
      retry_count = os.getenv('MAX_RETRIES')
      data = [
        datetime.now(pytz.utc).strftime('%Y-%m-%d %H:%M:%S'),
        'swap_sol',
        '-',
        amount_in,
        'failed'
      ]
      update_log('transaction', data)
      return False
    print("Failed to confirm transaction after maximum retries.")
    return False

async def liquidity_remove(solana_client, amm_id, payer,take_profit):
    pool_keys = fetch_pool_keys(amm_id)

    if pool_keys == "failed":
        print("Failed to retrieve pool keys...")
        return "failed"

    txnBool = True
    while txnBool:
        try:
            # Get lp balance
            amount_in = await getBalance(pool_keys["lp_mint"], solana_client, payer)

            # get token program id for mint
            TOKEN_PROGRAM_ID_MINT = None
            if (
              str(pool_keys["base_mint"])
              == "So11111111111111111111111111111111111111112"
            ):
              accountProgramId = await solana_client.get_account_info_json_parsed(
                pool_keys["quote_mint"]
              )
              TOKEN_PROGRAM_ID_MINT = accountProgramId.value.owner
            else:
              accountProgramId = await solana_client.get_account_info_json_parsed(
                pool_keys["base_mint"]
              )
              TOKEN_PROGRAM_ID_MINT = accountProgramId.value.owner

            # get lp mint account
            lp_account_pk = await sell_get_token_account(
              solana_client, payer.pubkey(), pool_keys["lp_mint"]
            )

            if (
              str(pool_keys["base_mint"])
              == "So11111111111111111111111111111111111111112"
            ):
              # get quote mint account
              quoteAccount_pk = await sell_get_token_account(
                solana_client, payer.pubkey(), pool_keys["quote_mint"]
              )

              # get base mint account
              base_token_account_pk, swap_tx, payer, base_account_keyPair, opts = (
                create_account_with_seed_args(
                  solana_client,
                  TOKEN_PROGRAM_ID,
                  payer.pubkey(),
                  payer,
                  amount_in,
                  False,
                  "confirmed",
                )
              )

              # create seed account close instructions
              closeAcc = close_account(
                CloseAccountParams(
                  account=base_token_account_pk,
                  dest=payer.pubkey(),
                  owner=payer.pubkey(),
                  program_id=TOKEN_PROGRAM_ID,
                )
              )

            else:
              base_token_account_pk = await sell_get_token_account(
                solana_client, payer.pubkey(), pool_keys["base_mint"]
              )  # account of liquidity

              quoteAccount_pk, swap_tx, payer, base_account_keyPair, opts = (
                create_account_with_seed_args(
                  solana_client,
                  TOKEN_PROGRAM_ID,
                  payer.pubkey(),
                  payer,
                  amount_in,
                  False,
                  "confirmed",
                )
              )

              closeAcc = close_account(
                CloseAccountParams(
                  account=quoteAccount_pk,
                  dest=payer.pubkey(),
                  owner=payer.pubkey(),
                  program_id=TOKEN_PROGRAM_ID,
                )
              )

        
            print("Create Liquidity Instructions...")
            instructions_swap = await make_liquidity_remover_instruction(
              payer.pubkey(),
              lp_account_pk,
              quoteAccount_pk,
              base_token_account_pk,
              pool_keys,
              TOKEN_PROGRAM_ID_MINT,
              amount_in,
            )

            # add instructions to txn
            swap_tx.add(instructions_swap)
            swap_tx.add(closeAcc)
            signers = [payer]

            while True:
              worth = await solana_client.get_account_info_json_parsed(pool_keys['quote_vault'])
              
              worth = worth.value.lamports / 1000000000
              print("Current Worth: ",worth)
              if worth >= take_profit:
                  print("Profit Reached: ",worth)
                  break
              time.sleep(1)           
            
            try:
              print("Execute Transaction...")
              start_time = time.time()

              txn = await solana_client.send_transaction(swap_tx, *signers)
              txid_string_sig = txn.value
              print(f"Transaction Sent: https://solscan.io/tx/{txn.value}")
              end_time = time.time()
              execution_time = end_time - start_time
              print(f"Execution time of send: {execution_time} seconds\n--------------------------------")
              # once txn has been sent, it has already been successful and u can access it on solscan.
              # remaining code is only to confirm if there were any errors in the txn or not.

              print("Getting status of transaction now...")
              checkTxn = True
              while checkTxn:
                try:
                  status = await solana_client.get_transaction(
                    txid_string_sig, "json"
                  )
                  if status.value.transaction.meta.err == None:
                    print("Transaction Success", txn.value)

                    end_time = time.time()
                    execution_time = end_time - start_time
                    print(f"Total Execution time: {execution_time} seconds")

                    txnBool = False
                    checkTxn = False
                    return txid_string_sig

                  else:
                    print("Transaction Failed")
                    end_time = time.time()
                    execution_time = end_time - start_time
                    print(f"Execution time: {execution_time} seconds")
                    checkTxn = False

                except Exception as e:
                  time.sleep(0.1)

            except RPCException as e:
              print(f"[Important] Error: [{e.args[0].data.logs}]...\nRetrying...")
              time.sleep(0.1)

            except Exception as e:
              print(f"[Important] Error: [{e}]...\nEnd...")
              txnBool = False
              return "failed"
        except Exception as e:
          if "NoneType" in str(e):
            print(e)
            return "failed"
          print("[Important] Main LP Remove error Raydium... retrying...\n", e)

def create_spl_token(name, symbol, uri, payer: Keypair):
  try:
    newToken = Keypair()
    lamports = solana_client.get_minimum_balance_for_rent_exemption(MINT_LEN).value
    ata = get_associated_token_address(payer.pubkey(), newToken.pubkey())
    
    # instruction sets
    tx = Transaction()
    # create new account
    create_ix = create_account(CreateAccountParams(
      from_pubkey=payer.pubkey(),
      to_pubkey=newToken.pubkey(),
      space=MINT_LEN,
      lamports=lamports,
      owner=TOKEN_PROGRAM_ID
    ))
    tx.add(create_ix)
    
    # create mint
    mint_ix = initialize_mint(InitializeMintParams(
      mint=newToken.pubkey(),
      decimals=9,
      mint_authority=payer.pubkey(),
      freeze_authority=payer.pubkey(),
      program_id=TOKEN_PROGRAM_ID
    ))
    tx.add(mint_ix)
    
    # create associate account
    associate_ix = create_associated_token_account(
      payer=payer.pubkey(), 
      owner=payer.pubkey(), 
      mint=newToken.pubkey()
    )
    tx.add(associate_ix)
    
    # create mint
    assoicate_mint_ix = mint_to(MintToParams(
      amount=10000000000, # 100 spl token to ata
      dest=ata,
      mint=newToken.pubkey(),
      mint_authority=payer.pubkey(),
      program_id=TOKEN_PROGRAM_ID,
    ))
    tx.add(assoicate_mint_ix)
    
    # create metadata
    meta_data = {
      "instructionDiscriminator": 33,
      "createMetadataAccountArgsV3": {
        "data": {
          "name": name,
          "symbol": symbol,
          "uri": uri,
          "sellerFeeBasisPoints": 500,
          "creators": [
            {
              "address": bytes(payer.pubkey()),
              "verified": 1,
              "share": 100
            }
          ],
          "collection": None,
          "uses": None
        },
        "isMutable": 1,
        "collectionDetails": None
      }
    }
    meta_ix_data = METADAT_STRUCTURE.build(meta_data)
    metadata_pda = Pubkey.find_program_address([b"metadata", bytes(TOKEN_METADATA_PROGRAM), bytes(newToken.pubkey())], TOKEN_METADATA_PROGRAM)[0]

    # account list for instruction
    accounts = [
      AccountMeta(pubkey=metadata_pda, is_signer=False, is_writable=True), # metadata
      AccountMeta(pubkey=newToken.pubkey(), is_signer=False, is_writable=False), # mint
      AccountMeta(pubkey=payer.pubkey(), is_signer=True, is_writable=False), # mint authority
      AccountMeta(pubkey=payer.pubkey(), is_signer=True, is_writable=True), # payer
      AccountMeta(pubkey=payer.pubkey(), is_signer=False, is_writable=False), # update authority
      AccountMeta(pubkey=SYSTEM_PROGRAM, is_signer=False, is_writable=False), # system program
      AccountMeta(pubkey=SYSTEM_RENT, is_signer=False, is_writable=False) # rent
    ]
    
    meta_ix = Instruction(TOKEN_METADATA_PROGRAM, meta_ix_data, accounts)
    tx.add(meta_ix)
    
    tx_id = solana_client.send_transaction(tx, payer, newToken, opts=TxOpts(skip_preflight=True, skip_confirmation=False))
    print('Waiting transaction complete ....')
    
    print('=' * 60)
    print(f'=  spl       token:   {str(newToken.pubkey())} =')
    print(f'=  associate token:   {str(ata)} =')
    print(f'=  token meta data:   {uri} =')
    print(f'=  transaction id:    {tx_id} =')
    print('=' * 60)
    
  except Exception as e:
    print('Exeption was occured: ', e)

async def swap_bome(amount):
  token_to_buy = os.getenv('TOKEN_TARGET')
  payer = Keypair.from_base58_string(os.getenv('PRIVATE_KEY'))
  await buy(token_to_buy, payer, amount)

async def swap_sol(amount):
  token_to_sell = os.getenv('TOKEN_TARGET')
  payer = Keypair.from_base58_string(os.getenv('PRIVATE_KEY'))
  await sell(token_to_sell, payer, amount)
  
async def spl_token(file, avatar):
  # open token infomation json file
  with open(file, 'r') as file:
    data = json.load(file)
  
  # check token meta is not empty
  if not 'name' in data or not 'symbol' in data:
    print('Json data does not contains minimum information for token meta')
    return
  # upload data to ipfs
  meta_uri = upload_token_metadata_to_IPFS(data, avatar)
  
  # create new spl token with data
  if not meta_uri:
    print('Sorry could not upload meta data, please try again later.')
  else:
    payer = Keypair.from_base58_string(os.getenv('PRIVATE_KEY'))
    create_spl_token(data['name'], data['symbol'], meta_uri, payer)

def liquidity_info():
  token_bome = Pubkey.from_string(os.getenv('TOKEN_LP'))
  payer = Keypair.from_base58_string(os.getenv('PRIVATE_KEY'))
  
  amount = getBalance(solana_client, token_bome, payer)
  print('Your liquidity valance is: ', amount)

def update_log(filename, row):
  header = ['date', 'type', 'transaction_id', 'value', 'status']

  try:
    if not os.path.isfile(filename + '.csv'):
      # If the file doesn't exist, write the header
      with open(filename + '.csv', mode='w', newline='') as file:
        writer = csv.writer(file)
        writer.writerow(header)
        
    with open(filename + '.csv', mode='a', newline='') as file:
      writer = csv.writer(file)
      writer.writerow(row)

    print('log saved to csv flie.')
  except Exception as e:
    print('fail to save to csv file')
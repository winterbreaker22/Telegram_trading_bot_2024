import cmd, argparse, asyncio, platform
from solana_api import swap_bome, \
  swap_sol, \
  liquidity_info, \
  spl_token

class CLI_Solana(cmd.Cmd):
  intro='''
  =================================================================
  =                                                               =
  =              WELCOME TO SOLANA BOME EXCHANGE CLI              =
  =                                                               =
  =       1.   swap_sol_to_bome <amount:float>                    =
  =       2.   swap_bome_to_sol <amount:float>                    =
  =       3.   get_liquidity                                      =
  =       4.   create_token <file_path:str> <avatar_path:str>     =
  =       5.   quit                                               =
  =                                                               =
  =       6.   help  <command_name>                               =
  =                                                               =
  =================================================================
  '''
  prompt='(solana_bot) '
  
  def do_help(self, arg: str) -> bool | None:
    return super().do_help(arg)
  
  def do_get_liquidity(self, arg: str) -> bool | None:
    """
    get wallet info. 
    get_liquidity
    """
    try:
      liquidity_info()
    except Exception as e:
      print('error: ', e)
  
  def do_swap_sol_to_bome(self, arg: str) -> bool | None:
    """
    Swap SOL to BOME token. 
    swap_bome <amount>
    """
    try:
      parser = argparse.ArgumentParser(description="Swap BOME to SOL")
      parser.add_argument("amount", type=float, help="Amount of BOME tokens to swap")
      
      args = parser.parse_args(arg.split())
      asyncio.run(swap_bome(args.amount))
      
    except Exception as e:
      print("Error parsing arguments:", e)
  
  def do_swap_bome_to_sol(self, arg: str) -> bool | None:
    """
    Swap BOME token to SOL. 
    swap_bome_to_sol <amount>
    """
    try:
      parser = argparse.ArgumentParser(description="Swap BOME to SOL")
      parser.add_argument("amount", type=float, help="Amount of BOME tokens to swap")
      
      args = parser.parse_args(arg.split())
      asyncio.run(swap_sol(args.amount))
      
    except argparse.ArgumentError as e:
      print("Error parsing arguments:", e)
     
  def do_create_token(self, arg: str) -> bool | None:
    """
    Create new SPL token with Meta data. 
    create_token <file_path> <avatar_path>
    """
    try:
      parser = argparse.ArgumentParser(description="Create new SPL token")
      parser.add_argument("file_path", default='token_detail.json', type=str, help="json file path that contains the metadata")
      parser.add_argument("avatar_path", default='avatar.png', type=str, help="image file path for new token")
      
      args = parser.parse_args(arg.split())
      asyncio.run(spl_token(args.file_path, args.avatar_path))
    except argparse.ArgumentError as e:
      print("Error parsing arguments:", e)

  def do_quit(self, arg: str) -> bool | None:
    print('Thanks for your attention.')
    return True
  
if __name__ == "__main__":
    if platform.system() == 'Windows':
      asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
      
    CLI_Solana().cmdloop()
import requests, json, os
from requests_toolbelt.multipart.encoder import MultipartEncoder
from dotenv import load_dotenv

load_dotenv()
JWT = os.getenv('JWT')

def upload_token_metadata_to_IPFS(token_info, src="./avatar.png", jwt=JWT):
  # Ensure the file exists
  if not os.path.exists(src):
    print(f"The file {src} does not exist.")
    return
  
  # store image
  print('start uploading image...')
  with open(src, 'rb') as file:
    m = MultipartEncoder(
      fields={
        'file': ('file.png', file, 'image/png'),
        'pinataMetadata': '{"name": "avatar.png"}',
        'pinataOptions': '{"cidVersion": 0}'
      }
    )

    headers = {
      'Content-Type': m.content_type,
      'Authorization': f'Bearer {jwt}'
    }

    try:
      response = requests.post("https://api.pinata.cloud/pinning/pinFileToIPFS", data=m, headers=headers)
      data = response.json()
      token_info['image'] = f'https://ipfs.io/ipfs/{data["IpfsHash"]}'
      print('image upload: ', data)
    except requests.exceptions.RequestException as e:
      print(e)
      return None
    
  print('start uploading meta json...')
  # store metadata as json
  try:
    json_string = json.dumps(token_info, indent=2)
    json_meta = MultipartEncoder(
      fields={
        'file': ('metadata.json', json_string, 'application/json'),
        'pinataMetadata': '{"name": "metadata.json"}',
        'pinataOptions': '{"cidVersion": 0}'
      }
    )

    headers = {
      'Content-Type': json_meta.content_type,
      'Authorization': f'Bearer {JWT}'
    }
    response = requests.post("https://api.pinata.cloud/pinning/pinFileToIPFS", data=json_meta, headers=headers)
    data = response.json()
    print('metadata json upload: ', data)
    return f'https://ipfs.io/ipfs/{data["IpfsHash"]}'
  except Exception as e:
    print('exception: ', e)
    return None

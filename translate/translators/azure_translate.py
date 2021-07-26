import json
import uuid
from typing import Dict

import aiohttp

from translate.common.errors import NoAPIKeyException, BadTranslation
from translate.translators.translator import Translator


class AzureTranslate(Translator):
    def __init__(self, api_key):
        super().__init__()
        self.api_key = api_key

    @classmethod
    async def build(cls, keys: Dict[str, str]) -> "AzureTranslate":
        try:
            return AzureTranslate(keys['api_key'])
        except KeyError:
            raise NoAPIKeyException("set api azure api_key <API_KEY>")

    async def translate(self, source: str, target: str, text: str) -> str:
        endpoint = "https://api.cognitive.microsofttranslator.com"

        path = '/translate'
        constructed_url = endpoint + path

        params = {
            'api-version': '3.0',
            'from': source,
            'to': target,
        }
        headers = {
            'Ocp-Apim-Subscription-Key': self.api_key,
            'Content-type': 'application/json',
            'X-ClientTraceId': str(uuid.uuid4())
        }
        body = [{'text': text}]

        async with aiohttp.ClientSession() as session:
            async with session.post(constructed_url, params=params, headers=headers, json=body) as resp:
                content = json.loads(await resp.read())
                status = resp.status

        if status == 400:
            raise BadTranslation(content['error']['message'])
        elif status != 200:
            raise IOError(f'{status}: request aborted\n\n{content}')
        return content[0]['translations'][0]['text']

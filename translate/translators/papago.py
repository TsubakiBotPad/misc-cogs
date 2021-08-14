from typing import Dict

import aiohttp

from translate.common.errors import NoAPIKeyException, UserTranslationError, TranslationError
from translate.translators.translator import Translator


class Papago(Translator):
    def __init__(self, client_id, client_secret):
        self.client_id = client_id
        self.client_secret = client_secret

    @classmethod
    async def build(cls, keys: Dict[str, str]) -> "Papago":
        try:
            return Papago(keys['client_id'], keys['client_secret'])
        except KeyError:
            raise NoAPIKeyException("set api papago client_id <CLIENT_ID> client_secret <CLIENT_SECRET>")

    async def translate(self, source: str, target: str, text: str) -> str:
        url = 'https://openapi.naver.com/v1/papago/n2mt'
        headers = {
            "X-Naver-Client-Id": self.client_id,
            "X-Naver-Client-Secret": self.client_secret
        }
        data = {'source': source, 'target': target, 'text': text}

        async with aiohttp.ClientSession() as session:
            async with session.post(url, headers=headers, data=data) as resp:
                content = await resp.json()
                status = resp.status

        if status == 400:
            raise UserTranslationError(content['errorMessage'])
        if status != 200:
            raise TranslationError(f'{status}: request aborted\n\n{content}')
        return content['message']['result']['translatedText']

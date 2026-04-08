import requests
from systemsettings.models import SystemSettings


class ChapaService:

    @staticmethod
    def initialize_payment(payload):
        sys_settings = SystemSettings.get_solo()
        url = f"{sys_settings.chapa_base_url}/transaction/initialize"

        headers = {
            "Authorization": f"Bearer {sys_settings.chapa_secret_key}"
        }

        response = requests.post(url, json=payload, headers=headers)

        return response.json()


    @staticmethod
    def verify_payment(tx_ref):
        sys_settings = SystemSettings.get_solo()
        url = f"{sys_settings.chapa_base_url}/transaction/verify/{tx_ref}"

        headers = {
            "Authorization": f"Bearer {sys_settings.chapa_secret_key}"
        }

        response = requests.get(url, headers=headers)

        return response.json()

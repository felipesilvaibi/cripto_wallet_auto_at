import base64
import datetime as dt
import hmac
import os

import gspread
import pandas as pd
import requests
from dotenv import load_dotenv
from oauth2client.service_account import ServiceAccountCredentials

load_dotenv()


class UpdateGoogleWalletSheet:
    def execute(self):
        sheet_instance = self.__get_sheet_instance()
        wallet_cripto_value_map = self.__get_wallet_cripto_value_map(sheet_instance)
        okx_account_balance = self.__get_okx_client(
            "GET", "/api/v5/account/balance", payload={}
        )
        self.__update_google_wallet_sheet(
            wallet_cripto_value_map, okx_account_balance, sheet_instance
        )

    def __get_google_client(self):
        scope = [
            "https://spreadsheets.google.com/feeds",
            "https://www.googleapis.com/auth/drive",
        ]
        creds = ServiceAccountCredentials.from_json_keyfile_name(
            "data/google_client_secret.json", scope
        )

        return gspread.authorize(creds)

    def __get_sheet_instance(self):
        client = self.__get_google_client()
        sheet = client.open("Carteira")

        return sheet.get_worksheet(0)

    def __get_wallet_cripto_value_map(self, sheet_instance):
        wallet_cripto_value_map = []

        cell_value = "CRIPTO"
        cell_range = sheet_instance.range("A5:AD5")
        for cell in cell_range:
            if cell.value == cell_value:
                col_num = cell.col
                col_values = sheet_instance.col_values(col_num)
                break

        for i in range(len(col_values)):
            if col_values[i] not in ["ATIVO", "CRIPTO"] and col_values[i] != "":
                wallet_cripto_value_map.append(
                    {
                        "nome": col_values[i],
                        "col": col_num + 1,
                        "row": i + 1,
                    }
                )

        df_wallet_cripto_value_map = pd.DataFrame(wallet_cripto_value_map)
        return df_wallet_cripto_value_map.set_index("nome")

    def __get_okx_client(self, http_method, url_path, payload={}):
        def get_time():
            return dt.datetime.utcnow().isoformat()[:-3] + "Z"

        def signature(timestamp, method, request_path, body, secret_key):
            if str(body) == "{}" or str(body) == "None":
                body = ""
            message = str(timestamp) + str.upper(method) + request_path + str(body)
            mac = hmac.new(
                bytes(secret_key, encoding="utf8"),
                bytes(message, encoding="utf-8"),
                digestmod="sha256",
            )
            d = mac.digest()
            return base64.b64encode(d)

        def get_header(request="GET", endpoint="", body: dict = dict()):
            cur_time = get_time()
            header = dict()

            header["CONTENT-TYPE"] = "application/json"
            header["OK-ACCESS-KEY"] = os.getenv("OKX_API_KEY")
            header["OK-ACCESS-SIGN"] = signature(
                cur_time, request, endpoint, body, os.getenv("OKX_API_SECRET")
            )
            header["OK-ACCESS-TIMESTAMP"] = str(cur_time)
            header["OK-ACCESS-PASSPHRASE"] = os.getenv("OKX_PASS_PHRASE")

            return header

        url = "https://www.okx.com" + url_path
        header = get_header(http_method, url_path, payload)
        print(header)
        response = requests.get(url, headers=header)
        return response.json()

    def __update_google_wallet_sheet(
        self, df_wallet_cripto_value_map, okx_account_balance, sheet_instance
    ):
        for coin_details in okx_account_balance["data"][0]["details"]:
            try:
                item = df_wallet_cripto_value_map.loc[coin_details["ccy"]]
            except KeyError:
                item = None
            if item is not None:
                sheet_instance.update_cell(
                    item["row"], item["col"], round(float(coin_details["eqUsd"]), 2)
                )


if __name__ == "__main__":
    main_class = UpdateGoogleWalletSheet()
    main_class.execute()

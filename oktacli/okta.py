import json

import requests


class Okta:

    def __init__(self, url, token):
        self.token = token
        self.url = url + "/api/v1/"

        self.session = requests.Session()
        self.session.headers.update({
            'Content-Type':  'application/json',
            'Accept':        'application/json',
            'Authorization': 'SSWS ' + token,
        })

    def list_users(self):
        rsp = self.session.get(self.url + "users/")
        if rsp.status_code >= 400:
            raise requests.HTTPError(json.dumps(rsp.json()))
        return rsp.json()

    def update_user(self, user_id, **fields):
        body = json.dumps({'profile': fields}).encode("utf-8")
        rsp = self.session.post(self.url + "users/" + user_id,
                                data=body)
        if rsp.status_code >= 400:
            raise requests.HTTPError(json.dumps(rsp.json()))
        return rsp.json()

    def search_user(self, query_str):
        rsp = self.session.get(self.url + "users",
                               params={'search': query_str})
        if rsp.status_code >= 400:
            raise requests.HTTPError(json.dumps(rsp.json()))
        return rsp.json()

    def reset_password(self, user_id, *, send_email=True):
        url = self.url + f"users/{user_id}/lifecycle/reset_password"
        rsp = self.session.post(
                url,
                params={'sendEmail': f"{str(send_email).lower()}"}
        )
        if rsp.status_code >= 400:
            raise requests.HTTPError(json.dumps(rsp.json()))
        return rsp.json()


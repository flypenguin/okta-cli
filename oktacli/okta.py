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

    def list_users(self, filter_query="", search_query=""):
        rv = []
        url = self.url + "users/"
        params = {}
        if filter_query:
            params["filter"] = filter_query
        if search_query:
            params["search"] = search_query
        rsp = self.session.get(url, params=params)
        while True:
            if rsp.status_code >= 400:
                raise requests.HTTPError(json.dumps(rsp.json()))
            rv += rsp.json()
            url = rsp.links.get("next", {"url": ""})["url"]
            if not url:
                break
            rsp = self.session.get(url)
        return rv

    def add_user(self, query_params, **fields):
        body = json.dumps(fields).encode("utf-8")
        rsp = self.session.post(self.url + "users/",
                                params=query_params,
                                data=body)
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

    def reset_password(self, user_id, *, send_email=True):
        url = self.url + f"users/{user_id}/lifecycle/reset_password"
        rsp = self.session.post(
                url,
                params={'sendEmail': f"{str(send_email).lower()}"}
        )
        if rsp.status_code >= 400:
            raise requests.HTTPError(json.dumps(rsp.json()))
        return rsp.json()


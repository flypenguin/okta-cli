import enum
import json
import time

import requests


class REST(enum.Enum):
    get = "get"
    put = "put"
    post = "post"
    delete = "delete"


class Okta:

    def __init__(self, url, token):
        self.token = token
        self.path_base = "/api/v1"

        # TODO: use urljoin or something for this
        self.url = url + self.path_base

        self.session = requests.Session()
        self.session.headers.update({
            'Content-Type':  'application/json',
            'Accept':        'application/json',
            'Authorization': 'SSWS ' + token,
        })

    def call_okta_raw(self, path, method, *, params=None, body_obj=None,
                      implicit_url=True):
        call_method = getattr(self.session, method.value)
        call_params = {"params": params if params is not None else {}}
        call_path = self.url + path if implicit_url else path
        if method == REST.post and body_obj:
            call_params["data"] = json.dumps(body_obj)

        while True:
            rsp = call_method(call_path, **call_params)

            if rsp.status_code != 429:
                # not throttled? break the loop.
                break

            # get header with "we're good again" date (epoch time)
            until = int(rsp.headers.get("X-Rate-Limit-Reset"))
            delay = max(1, int(until - time.time()))
            time.sleep(delay)
            # now try again

        if rsp.status_code >= 400:
            raise requests.HTTPError(json.dumps(rsp.json()))
        return rsp

    def call_okta(self, path, method, *, params=None, body_obj=None):
        rsp = self.call_okta_raw(path, method, params=params, body_obj=body_obj)
        rv = rsp.json()
        # NOW, we either have a SINGLE DICT in the rv variable,
        #     *OR*
        # a list.
        while True:
            # now, let's get all the "next" links. if we do NOT have a list,
            # we do not have "next" links :) . handy!
            url = rsp.links.get("next", {"url": ""})["url"]
            if not url:
                break
            rsp = self.call_okta_raw(url, REST.get, implicit_url=False)
            # now the += operation is safe, cause we have a list.
            # this is a liiiitle bit implicit, but should work smoothly.
            rv += rsp.json()
        # filter out _links items from the final result list
        if isinstance(rv, list):
            rv = list(filter(lambda x: x.pop("_links", None), rv))
        elif isinstance(rv, dict):
            rv.pop("_links", None)
        return rv

    def list_groups(self, query_ex="", filter_ex=""):
        params = {}
        if query_ex:
            params["query"] = query_ex
        if filter_ex:
            params["filter"] = filter_ex
        return self.call_okta("/groups", REST.get, params=params)

    def list_users(self, filter_query="", search_query=""):
        if filter_query:
            params = {"filter": filter_query}
        elif search_query:
            params = {"search": search_query}
        else:
            params = {}
        return self.call_okta("/users", REST.get, params=params)

    def list_apps(self):
        return self.call_okta("/apps", REST.get)

    def add_user(self, query_params, body_object):
        body = json.dumps(body_object).encode("utf-8")
        rsp = self.session.post(self.url + "/users/",
                                params=query_params,
                                data=body)
        if rsp.status_code >= 400:
            raise requests.HTTPError(json.dumps(rsp.json()))
        return rsp.json()

    def update_user(self, user_id, body_object):
        path = "/users/" + user_id
        return self.call_okta(path, REST.post, body_obj=body_object)

    def get_profile_schema(self):
        path = "/meta/schemas/user/default/"
        return self.call_okta(path, REST.get)

    def deactivate_user(self, user_id, send_email=True):
        """
        Deactivates a user.
        :param user_id: The user ID
        :param send_email: On True admins will be notified
        :return: None
        """
        path = "/users/" + user_id + "/lifecycle/deactivate"
        params = {"sendEmail": "true"} if send_email else {}
        return self.call_okta_raw(path, REST.post, params=params)

    def delete_user(self, user_id, send_email=True):
        """
        Deletes a user.
        :param user_id: The user ID
        :param send_email: On True admins will be notified
        :return: None
        """
        path = "/users/" + user_id
        params = {"sendEmail": "true"} if send_email else {}
        return self.call_okta_raw(path, REST.delete, params=params)

    def reset_password(self, user_id, *, send_email=True):
        url = self.url + f"/users/{user_id}/lifecycle/reset_password"
        rsp = self.session.post(
                url,
                params={'sendEmail': f"{str(send_email).lower()}"}
        )
        if rsp.status_code >= 400:
            raise requests.HTTPError(json.dumps(rsp.json()))
        return rsp.json()

    def expire_password(self, user_id, *, temp_password=False):
        url = self.url + f"/users/{user_id}/lifecycle/expire_password"
        rsp = self.session.post(
                url,
                params={'tempPassword': f"{str(temp_password).lower()}"}
        )
        if rsp.status_code >= 400:
            raise requests.HTTPError(json.dumps(rsp.json()))
        return rsp.json()

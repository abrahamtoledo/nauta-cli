import json
import re

import bs4
import requests

from nautacli.exceptions import NautaLoginException, NautaLogoutException, NautaException

_re_login_fail_reason = re.compile('alert\("(?P<reason>[^"]*?)"\)')


class NautaProtocol(object):
    @classmethod
    def _get_inputs(cls, form_soup):
        return {
            _["name"]: _.get("value", default=None)
            for _ in form_soup.select("input[name]")
        }

    @classmethod
    def create_session(cls):
        session = requests.Session()

        r = session.get("http://www.etecsa.cu")
        if b'secure.etecsa.net' not in r.content:
            raise NautaLoginException("Ya estas conectado. Usa 'nauta down' para cerrar la sesion.")

        soup = bs4.BeautifulSoup(r.text, 'html.parser')
        action = soup.form["action"]
        data = cls._get_inputs(soup)

        # Now go to the login page
        r = session.post(action, data)
        soup = bs4.BeautifulSoup(r.text, 'html.parser')
        form_soup = soup.find("form", id="formulario")

        login_action = form_soup["action"]
        data = cls._get_inputs(form_soup)

        return session, login_action, data

    @classmethod
    def login(cls, session, login_action, data, username, password):

        r = session.post(
            login_action,
            {
                **data,
                "username": username,
                "password": password
            }
        )

        if not r.ok:
            raise NautaLoginException(
                "Fallo el inicio de sesion: {} - {}".format(
                    r.status_code,
                    r.reason
                )
            )

        if not "online.do" in r.url:
            soup = bs4.BeautifulSoup(r.text, "html.parser")
            script_text = soup.find_all("script")[-1].get_text()

            match = _re_login_fail_reason.match(script_text)
            raise NautaLoginException(
                "Fallo el inicio de sesion: {}".format(
                    match and match.groupdict().get("reason")
                )
            )

        # If we reached here. We are logged in
        # Get attribute_uuid
        m = re.search(r'ATTRIBUTE_UUID=(\w+)&CSRFHW=', r.text)
        attribute_uuid = m and m.group(1)

        return attribute_uuid

    @classmethod
    def logout(cls, csrfhw, username=None, wlanuserip=None, attribute_uuid=None, session=None):
        logout_url = \
            (
                "https://secure.etecsa.net:8443/LogoutServlet?" +
                "CSRFHW={}&" +
                "username={}&" +
                "ATTRIBUTE_UUID={}&" +
                "wlanuserip={}"
            ).format(
                csrfhw,
                username,
                attribute_uuid,
                wlanuserip
            )

        session = session or requests.session()
        response = session.get(logout_url)
        if not response.ok:
            raise NautaLogoutException(
                "Fallo al cerrar la sesion: {} - {}".format(
                    response.status_code,
                    response.reason
                )
            )

        if "SUCCESS" not in response.text.upper():
            raise NautaLogoutException(
                "Fallo al cerrar la sesion: {}".format(
                    response.text[:100]
                )
            )

    @classmethod
    def get_user_time(cls, username, password=None, csrfhw=None, session=None):
        session = session or requests.Session()
        r = session.get(
            "https://secure.etecsa.net:8443/EtecsaQueryServlet?"
            "CSRFHW={}&"
            "op=getLeftTime&"
            "op1={}".format(csrfhw, username))

        return r.text

    @classmethod
    def get_user_credit(cls, session, data, username, password):

        r = session.post(
            "https://secure.etecsa.net:8443/EtecsaQueryServlet",
            {
                **data,
                "username": username,
                "password": password
            }
        )

        if not r.ok:
            raise NautaException(
                "Fallo al obtener la informacion del usuario: {} - {}".format(
                    r.status_code,
                    r.reason
                )
            )

        soup = bs4.BeautifulSoup(r.text)
        credit_tag = soup.select_one("#sessioninfo > tbody:nth-child(1) > tr:nth-child(2) > td:nth-child(2)")

        if not credit_tag:
            raise NautaException(
                "Fallo al obtener el credito del usuario: no se encontro la informacion"
            )

        return credit_tag.get_text()


class NautaSession(object):
    def __init__(self, username, csrfhw, wlanuserip=None, attribute_uuid=None, requests_session=None):
        self.username = username
        self.csrfhw = csrfhw
        self.wlanuserip = wlanuserip
        self.attribute_uuid = attribute_uuid
        self.requests_session = requests_session

    def __enter__(self):
        pass

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.logout()

    def logout(self):
        NautaProtocol.logout(
            csrfhw=self.requests_session,
            username=self.username,
            wlanuserip=self.wlanuserip,
            attribute_uuid=self.attribute_uuid,
            session=self.requests_session
        )

    def get_remaining_time(self):
        return NautaProtocol.get_user_time(
            username=self.username,
            csrfhw=self.csrfhw,
            session=self.requests_session
        )

    def save(self, fp):
        json.dump(
            self.__dict__,
            fp
        )

    @classmethod
    def load(cls, fp):
        inst = object.__new__(cls)
        inst.__dict__ = json.load(fp)
        return inst


class NautaClient(object):
    def __init__(self, user, password):
        self.username = user
        self.password = password
        self.csrfhw = None
        self.wlanuserip = None

    def start_session(self):
        session, login_action, data = NautaProtocol.create_session()

        self.csrfhw = data['CSRFHW']
        self.wlanuserip = data['wlanuserip']

        attribute_uuid = NautaProtocol.login(
            session,
            login_action,
            data,
            self.username,
            self.password
        )

        return NautaSession(
            username=self.username,
            csrfhw=self.csrfhw,
            wlanuserip=self.wlanuserip,
            attribute_uuid=attribute_uuid,
            requests_session=session
        )

    def get_user_credit(self):
        session, _, data = NautaProtocol.create_session()

        return NautaProtocol.get_user_credit(
            session=session,
            data=data,
            username=self.username,
            password=self.password
        )

    def logout(self):
        NautaProtocol.logout(
            csrfhw=self.csrfhw,
            username=self.username,
            wlanuserip=self.wlanuserip
        )

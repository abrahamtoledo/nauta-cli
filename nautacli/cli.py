from datetime import datetime

import requests
import json
import time
import bs4
import sys
import dbm
import os
import re
import getpass


class Cli(object):
    def __init__(self, CONFIG_DIR):
        self.CONFIG_DIR = CONFIG_DIR

        try:
            os.makedirs(self.CONFIG_DIR)
        except FileExistsError:
            pass
        
        self.CARDS_DB = os.path.join(self.CONFIG_DIR, "cards")
        self.ATTR_UUID_FILE = os.path.join(self.CONFIG_DIR, "attribute_uuid")
        self.LOGOUT_URL_FILE = os.path.join(self.CONFIG_DIR, "logout_url")
        self.logfile = open(os.path.join(self.CONFIG_DIR, "connections.log"), "a")

    @staticmethod
    def get_inputs(form_soup):
        form = {}
        for i in form_soup.find_all("input"):
            try:
                form[i["name"]] = i["value"]
            except KeyError:
                continue
        return form

    def log(self, *args, **kwargs):
        kwargs.update(dict(file=self.logfile))
        print(
            "{} ".format(datetime.now()),
            *args,
            **kwargs,
        )
        self.logfile.flush()

    def expand_username(self, username):
        """If user enters just username (without domain) then expand it"""
        with dbm.open(self.CARDS_DB) as cards_db:
            for user in cards_db.keys():
                user = user.decode()
                user_part = user[:user.index('@')]
                if username == user_part:
                    return user
        return username  # not found

    def get_password(self, username):
        with dbm.open(self.CARDS_DB) as cards_db:
            if not username in cards_db:
                return None
            info = json.loads(cards_db[username].decode())
            return info['password']

    def select_card(self):
        cards = []
        with dbm.open(self.CARDS_DB) as cards_db:
            for card in cards_db.keys():
                info = json.loads(cards_db[card].decode())
                tl = self.parse_time(info.get('time_left', '00:00:00'))
                if tl <= 0:
                    continue
                info['username'] = card
                cards.append(info)
        cards.sort(key=lambda c: c['time_left'])
        if len(cards) == 0:
            return None, None
        return cards[0]['username'], cards[0]['password']

    def up(self, args):
        """
        :param args:
        :return:
        """

        if args.username:
            username = args.username
            password = self.get_password(username)
            if password is None:
                print("Invalid card: {}".format(args.username))
                return
        else:
            username, password = self.select_card()
            if username is None:
                print("No card available, add one with 'nauta cards add'")
                return
            username = username.decode()

        session = requests.Session()

        tl = self.time_left(username)
        print("Using card {}. Time left: {}".format(username, tl))
        self.log("Connecting with card {}. Time left on card: {}".format(username, tl))

        r = session.get("http://www.etecsa.cu")
        if b'secure.etecsa.net' not in r.content:
            print("Looks like you're already connected. Use 'nauta down' to log out.")
            return

        soup = bs4.BeautifulSoup(r.text, 'html.parser')
        action = soup.form["action"]
        form = self.get_inputs(soup)
        r = session.post(action, form)

        soup = bs4.BeautifulSoup(r.text, 'html.parser')

        form_soup = soup.find("form", id="formulario")
        action = form_soup["action"]
        form = self.get_inputs(form_soup)

        csrfhw = form['CSRFHW']
        wlanuserip = form['wlanuserip']

        form['username'] = username
        form['password'] = password


        last_attribute_uuid = ""
        try:
            last_attribute_uuid = open(self.ATTR_UUID_FILE, "r").read().strip()
        except FileNotFoundError:
            pass

        guessed_logout_url = (
            "https://secure.etecsa.net:8443/LogoutServlet?" +
            "CSRFHW={}&" +
            "username={}&" +
            "ATTRIBUTE_UUID={}&" +
            "wlanuserip={}"
        ).format(
            csrfhw,
            username,
            last_attribute_uuid,
            wlanuserip
        )
        with open(self.LOGOUT_URL_FILE, "w") as f:
            f.write(guessed_logout_url + "\n")

        self.log("Attempting connection. Guessed logout url:", guessed_logout_url)
        try:
            r = session.post(action, form)
            m = re.search(r'ATTRIBUTE_UUID=(\w+)&CSRFHW=', r.text)
            attribute_uuid = None
            if m:
                attribute_uuid = m.group(1)
        except:
            attribute_uuid = None

        if attribute_uuid is None:
            print("Log in failed :(")
        else:
            with open(self.ATTR_UUID_FILE, "w") as f:
                f.write(attribute_uuid + "\n")

            login_time = int(time.time())
            logout_url = (
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
            with open(self.LOGOUT_URL_FILE, "w") as f:
                f.write(logout_url + "\n")

            print("Logged in successfully. To logout, run 'nauta down'")
            print("or just hit Ctrl+C here, I'll stick around...")
            self.log("Connected. Actual logout URL is: '{}'".format(logout_url))
            if logout_url == guessed_logout_url:
                self.log("Guessed it right ;)")
            else:
                self.log("Bad guess :(")
            try:
                while True:
                    elapsed = int(time.time()) - login_time

                    print("\rConnection time: {} ".format(
                        self.human_secs(elapsed)
                    ), end="")

                    if args.time is not None:
                        print(". Automatically Disconnect in {}".format(
                            self.human_secs(args.time - elapsed)
                        ), end="")

                        if elapsed > args.time:
                            raise KeyboardInterrupt()

                    if not os.path.exists(self.LOGOUT_URL_FILE):
                        break

                    time.sleep(1)

            except KeyboardInterrupt:
                print("Got a Ctrl+C, logging out...")
                self.log("Got Ctrl+C. Attempting disconnect...")
                self.down([])

                elapsed = int(time.time()) - login_time
                self.log("Connection time:", self.human_secs(elapsed))

                tl = self.time_left(username)
                print("Reported time left:", tl)
                self.log("Reported time left:", tl)

    def down(self, args):
        try:
            logout_url = open(self.LOGOUT_URL_FILE).read().strip()
        except FileNotFoundError:
            print("Connection seems to be down already. To connect, use 'nauta up'")
            return
        session = requests.Session()
        print("Logging out...")
        r = None
        for error_count in range(10):
            try:
                r = session.get(logout_url)
                break
            except requests.RequestException:
                print("There was a problem logging out, retrying %d..." % error_count)
        if r:
            self.log("Logout message: %s" % r.text)
            if 'SUCCESS' in r.text:
                print('Connection closed successfully')
                os.remove(self.LOGOUT_URL_FILE)

    def fetch_expire_date(self, username, password):
        session = requests.Session()
        r = session.get("https://secure.etecsa.net:8443/")
        soup = bs4.BeautifulSoup(r.text, 'html.parser')

        form = self.get_inputs(soup)
        action = "https://secure.etecsa.net:8443/EtecsaQueryServlet"
        form['username'] = username
        form['password'] = password
        r = session.post(action, form)
        soup = bs4.BeautifulSoup(r.text, 'html.parser')
        exp_node = soup.find(string=re.compile("expiración"))
        if not exp_node:
            return "**invalid credentials**"
        exp_text = exp_node.parent.find_next_sibling('td').text.strip()
        exp_text = exp_text.replace('\\', '')
        return exp_text

    def fetch_usertime(self, username):
        session = requests.Session()
        r = session.get("https://secure.etecsa.net:8443/EtecsaQueryServlet?op=getLeftTime&op1={}".format(username))
        return r.text

    def time_left(self, username, fresh=False, cached=False):
        now = time.time()
        with dbm.open(self.CARDS_DB, "c") as cards_db:
            card_info = json.loads(cards_db[username].decode())
            last_update = card_info.get('last_update', 0)
            password = card_info['password']
            if not cached and (fresh or now - last_update > 60):
                time_left = self.fetch_usertime(username)
                last_update = time.time()
                if re.match(r'[0-9:]+', time_left):
                    card_info['time_left'] = time_left
                    card_info['last_update'] = last_update
                    cards_db[username] = json.dumps(card_info)
            time_left = card_info.get('time_left', 'N/A')
            return time_left

    def expire_date(self, username, fresh=False, cached=False):
        # expire date computation won't depend on last_update
        # because the expire date will change very infrequently
        # in the case of rechargeable accounts and it will
        # never change in the case of non-rechargeable cards
        with dbm.open(self.CARDS_DB, "c") as cards_db:
            card_info = json.loads(cards_db[username].decode())
            if not cached and (fresh or not 'expire_date' in card_info):
                password = card_info['password']
                exp_date = self.fetch_expire_date(username, password)
                card_info['expire_date'] = exp_date
                cards_db[username] = json.dumps(card_info)
            exp_date = card_info['expire_date']
            return exp_date

    def delete_cards(self, cards):
        with dbm.open(self.CARDS_DB, "c") as cards_db:
            if len(cards) > 0:
                print("Will delete these cards:")
                for card in cards:
                    print("  ", str(card))
                sys.stdout.flush()
                while True:
                    reply = input("Proceed (y/n)? ")
                    if reply.lower().startswith("y"):
                        for card in cards:
                            del cards_db[card]
                        break
                    if reply.lower().startswith("n"):
                        break

    def cards(self, args):
        entries = []
        with dbm.open(self.CARDS_DB, "c") as cards_db:
            for card in cards_db.keys():
                card = card.decode()
                card_info = json.loads(cards_db[card].decode())
                password = card_info['password']
                if not args.v:
                    password = "*" * len(password)
                entries.append((card, password))

        con_error = False
        for card, password in entries:
            if not con_error:
                try:
                    time = self.time_left(card, args.fresh, args.cached)
                    expiry = self.expire_date(card, args.fresh, args.cached)
                except requests.exceptions.ConnectionError:
                    con_error = True
                    print('WARNING: It seems that you have no network access. Showing data from cache.')

            if con_error:
                time = self.time_left(card, args.fresh, True)
                expiry = self.expire_date(card, args.fresh, True)

            print("{}\t{}\t(expires {})".format(
                card,
                time,
                expiry
            ))

    def verify(self, username, password):
        session = requests.Session()
        r = session.get("https://secure.etecsa.net:8443/")
        soup = bs4.BeautifulSoup(r.text, 'html.parser')

        form = self.get_inputs(soup)
        action = "https://secure.etecsa.net:8443/EtecsaQueryServlet"
        form['username'] = username
        form['password'] = password
        r = session.post(action, form)
        soup = bs4.BeautifulSoup(r.text, 'html.parser')
        exp_node = soup.find(string=re.compile("expiración"))
        if not exp_node:
            return False
        return True

    def cards_add(self, args):
        username = args.username or input("Username: ")
        password = getpass.getpass("Password: ")
        if not self.verify(username, password):
            print("Credentials seem incorrect")
            return
        with dbm.open(self.CARDS_DB, "c") as cards_db:
            cards_db[username.lower()] = json.dumps({
                'password': password,
            })

    def cards_clean(self, args):
        cards_to_purge = []
        with dbm.open(self.CARDS_DB, "c") as cards_db:
            for card in cards_db.keys():
                info = json.loads(cards_db[card].decode())
                tl = self.parse_time(info.get('time_left'))
                if tl == 0:
                    cards_to_purge.append(card)
        self.delete_cards(cards_to_purge)

    def cards_rm(self, args):
        self.delete_cards(args.usernames)

    def cards_info(self, args):
        username = args.username
        with dbm.open(self.CARDS_DB, "c") as cards_db:
            card_info = json.loads(cards_db[username].decode())
            password = card_info['password']
    
        session = requests.Session()
        r = session.get("https://secure.etecsa.net:8443/")
        soup = bs4.BeautifulSoup(r.text, 'html.parser')
    
        form = self.get_inputs(soup)
        action = "https://secure.etecsa.net:8443/EtecsaQueryServlet"
        form['username'] = username
        form['password'] = password
        r = session.post(action, form)
        soup = bs4.BeautifulSoup(r.text, 'html.parser')
    
        print("Información")
        print("-----------")
        table = soup.find('table', id='sessioninfo')
        for tr in table.find_all('tr'):
            key, val = tr.find_all('td')
            key = key.text.strip()
            val = val.text.strip().replace('\\', '')
            print(key, val)
    
        print()
        print("Sesiones")
        print("--------")
        table = soup.find('table', id='sesiontraza')

        for tr in table.find_all('tr'):
            tds = tr.find_all('td')
            if len(tds) > 0: # avoid the empty line on the ths row
                for cell in tds:
                    print(cell.text.strip(), end="\t")
                print()

import copy
import datetime
import json
from itertools import zip_longest
from pathlib import Path
from threading import Thread

import requests
import urllib3

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
requests.packages.urllib3.disable_warnings()


class MagnumCache:
    def __init__(self, **kwargs):

        self.insite = "127.0.0.1"
        self.nature = "mag-1"
        self.cluster_ip = None
        self.port_remap = None
        self.ipg_matches = []
        self.router_db = {}
        self.ipg_db = []
        self.no_port_list = None
        self.routers_match = ["EXE", "IPX"]

        for key, value in kwargs.items():

            if ("ipg_matches" in key) and value:
                self.ipg_matches.extend(value)

            else:
                setattr(self, key, value)

        self.cache_url = "http://{}/proxy/insite/{}/api/-/model/magnum/{}".format(self.insite, self.nature, self.cluster_ip)

        self.catalog_cache()

    def config_fetch(self):

        try:

            # Get OT Bearer Token
            login = {"username": "admin", "password": "admin"}

            response = requests.post(
                "https://%s/api/v1/login" % self.insite,
                headers={"Content-Type": "application/json"},
                data=json.dumps(login),
                verify=False,
                timeout=30.0,
            ).json()

            otbt = {"otbt-is": response["otbt-is"]}

            # Get magnum config
            response = requests.get(self.cache_url, params=otbt, verify=False, timeout=30.0)

            return json.loads(response.text)

        except Exception as e:

            with open("edge_ports", "a+") as f:
                f.write(str(datetime.datetime.now()) + " --- " + "magnum_cache_builder" + "\t" + str(e) + "\r\n")

            return None

    def catalog_cache(self):

        config = self.config_fetch()

        if config:

            for device in config["magnum-controlled-devices"]:

                # inventory routers that are either IPX or EXE
                if device["device"] in self.routers_match:

                    router = {
                        device["device-name"]: {
                            "device_name": device["device-name"],
                            "device": device["device"],
                            "device_size": device["device-size"],
                            "device_type": device["device-type"],
                            "control_1_address": device["control-1-address"]["host"],
                            "control_2_address": device["control-2-address"]["host"]
                            if "control-2-address" in device.keys()
                            else None,
                            "ports_db": {},
                            "params": [],
                        }
                    }

                    self.router_db.update(router)

                if device["device"] in self.ipg_matches and "future" not in device.keys():

                    edge_template = {
                        "s_device_name": device["device-name"],
                        "s_device": device["device"],
                        "s_device_size": device["device-size"],
                        "s_device_type": device["device-type"],
                        "s_control_address": device["control-1-address"]["host"],
                        "connections": {},
                    }

                    edge_template.update({"s_main": None, "s_backup": None} if self.dual_hot else {"as_router": []})

                    try:

                        if device["device"] == "3067VIP10G-3G" and self.dual_hot:

                            sfp_tree = {}

                            for sfp in device["sfps"]:
                                if "link" in sfp.keys():

                                    port = int(sfp["number"][:-1])

                                    if port not in sfp_tree:
                                        sfp_tree.update({port: [sfp]})

                                    else:
                                        sfp_tree[port].append(sfp)

                            groups = [parts for _, parts in sorted(sfp_tree.items())]

                        else:

                            # create group of sets() of links either in pairs or in singles - depending if this is a dual hot system
                            # there has to be a link object or it won't be grouped. *big assumption that if dual hot connections are consecutive*
                            # example: ({sfp},{sfp}),({sfp},{sfp}) OR ({sfp}),({sfp})
                            groups = zip_longest(
                                *[iter([sfp for sfp in device["sfps"] if "link" in sfp.keys()])] * (2 if self.dual_hot else 1)
                            )

                        # create a link number by iteration through each set (either pair of sfps or singles)
                        for link_num, link_parts in enumerate(groups, 1):

                            link_def = {link_num: []}

                            # iterate a pair of objects with a pair of labels if dual hot is enabled
                            # otherwise use the router label with a single object per set
                            for link, label in zip(link_parts, (["main", "backup"] if self.dual_hot else ["router"])):

                                link_def[link_num].append(
                                    {
                                        "port": link["link"]["port"],
                                        "device": link["link"]["device"],
                                        "capacity": link["link"]["capacity"] * 1000000,
                                        "sfp": link["number"],
                                        "type": label,
                                    }
                                )

                                if self.dual_hot:
                                    edge_template["s_" + label] = link["link"]["device"]

                                else:

                                    edge_template["as_" + label].append(link["link"]["device"])
                                    edge_template["as_" + label] = list(set(edge_template["as_" + label]))

                            edge_template["connections"].update(link_def)

                    except Exception as e:
                        print(e)

                    self.ipg_db.append(edge_template)

            def create_parameters(port):

                num = port["port"]
                label = port["type"]
                router = port["device"]

                try:

                    for _, params in self.router_parameters.items():

                        x = copy.deepcopy(params)

                        x["id"] = x["id"].replace("<replace>", str(num - 1))
                        x["name"] = x["name"] + ("_" + label if label is not "router" else "")

                        self.router_db[router]["params"].append(x)

                except Exception as e:
                    print(e)

            # iterate through each edge device collected from the magnumm config
            for ipg in self.ipg_db:

                # iterate through each link definition in the connections tree of the ipg
                for _, group in ipg["connections"].items():

                    # map the create_parameters the groups from each link list() to activate map()
                    list(map(create_parameters, group))


class EdgeCollector(MagnumCache):
    def __init__(self, **kwargs):

        self.dual_hot = None
        self.annotate = None

        self.fetch = self.fetch_api

        self.router_parameters = {
            "rx_allocated": {
                "id": "241.<replace>@i",
                "type": "integer",
                "name": "l_rx_rate_allocated",
            },
            "rx_measured": {
                "id": "932.<replace>@i",
                "type": "integer",
                "name": "l_rx_rate_measured",
            },
            "tx_allocated": {
                "id": "242.<replace>@i",
                "type": "integer",
                "name": "l_tx_rate_allocated",
            },
            "tx_measured": {
                "id": "933.<replace>@i",
                "type": "integer",
                "name": "l_tx_rate_measured",
            },
            "port_status": {
                "id": "921.<replace>@i",
                "type": "integer",
                "name": "s_operation_status",
            },
            "port_speed": {"id": "920.<replace>@i", "type": "integer", "name": "l_speed"},
        }

        self.router_parameter_control = {
            "rate_allocated": {"multiplier": 1000},
            "rate_measured": {"multiplier": 1000},
            "operation_status": {"convert": {0: "UP", 1: "DOWN"}},
            "speed": {"multiplier": 1000000},
        }

        if "dual_hot" in kwargs.keys():
            self.dual_hot = kwargs["dual_hot"]

        for key, value in kwargs.items():

            if "magnum_cache" in key:
                MagnumCache.__init__(self, **value)

            elif "override" in key and value:

                try:

                    with open(str(Path(value)), "r") as reader:
                        self.override_dict = json.loads(reader.read())

                    self.fetch = self.fetch_override

                except Exception as e:
                    print(e)
                    quit()

            elif key == "annotate":

                exec("from {} import {}".format(value["module"], value["dict"]), globals())

                self.annotate = eval(value["dict"] + "()")

            elif key == "annotate_db":
                self.annotate = value

            else:
                setattr(self, key, value)

    def fetch_api(self, router):

        try:

            with requests.Session() as session:

                ## get the session ID from accessing the login.php site
                resp = session.get(
                    "http://%s/login.php" % router["control_1_address"],
                    verify=False,
                    timeout=30.0,
                )

                session_id = resp.headers["Set-Cookie"].split(";")[0]

                payload = {
                    "jsonrpc": "2.0",
                    "method": "get",
                    "params": {"parameters": router["params"]},
                    "id": 1,
                }

                url = "http://%s/cgi-bin/cfgjsonrpc" % (router["control_1_address"])

                headers = {
                    "content_type": "application/json",
                    "Cookie": session_id + "; webeasy-loggedin=true",
                }

                response = session.post(
                    url,
                    headers=headers,
                    data=json.dumps(payload),
                    verify=False,
                    timeout=30.0,
                )

                return json.loads(response.text)

        except Exception as e:

            with open("edge_ports", "a+") as f:
                f.write(str(datetime.datetime.now()) + " --- " + "router_api_fetch" + "\t" + str(e) + "\r\n")

            return None

    def fetch_override(self, router):

        try:
            return self.override_dict[router["device_name"]]

        except Exception:
            return None

    def snapshot_routers(self, router, store):

        response = self.fetch_api(router)

        store.update({router["device_name"]: response})

    def create_snapshot(self):

        store = {}

        threads = [
            Thread(
                target=self.snapshot_routers,
                args=(
                    router,
                    store,
                ),
            )
            for _, router in self.router_db.items()
            if len(router["params"]) > 0
        ]

        for x in threads:
            x.start()

        for y in threads:
            y.join()

        with open(self.cluster_ip, "w") as writer:
            writer.write(json.dumps(store, indent=1))

    def router_process(self, router):

        # reset to the port db tree to nothing
        router["ports_db"] = {}

        response = self.fetch(router)

        try:

            for param in response["result"]["parameters"]:

                try:

                    # skip over if a parameter is flagged with error
                    if "error" not in param.keys():

                        # port instance of string: 241.269@i = 269(+1)
                        base_port = int(param["id"].split("@")[0].split(".")[1]) + 1

                        name = param["name"]
                        value = param["value"]

                        # convert values based on how conversions are defined in the parameter control
                        for k, v in self.router_parameter_control.items():

                            if k in name and "multiplier" in v.keys():
                                value = value * v["multiplier"]

                            elif k in name and "convert" in v.keys():
                                value = v["convert"][value]

                        # add parameter to a nested port object to the router definition.
                        if base_port in router["ports_db"].keys():
                            router["ports_db"][base_port].update({name: value})

                        else:
                            router["ports_db"].update({base_port: {name: value, "as_issues": []}})

                except Exception as e:
                    print(e)
                    continue

            # perform the status and over subscription calculation here to make it easy
            for _, parts in router["ports_db"].items():

                rx_rate_allocated = 0
                rx_rate_measured = 0
                tx_rate_allocated = 0
                tx_rate_measured = 0

                for k, v in parts.items():

                    if "operation_status" in k and v == "DOWN":
                        parts["as_issues"].append("port_status")

                    elif "rx_rate_allocated" in k:
                        rx_rate_allocated = v
                    elif "rx_rate_measured" in k:
                        rx_rate_measured = v
                    elif "tx_rate_allocated" in k:
                        tx_rate_allocated = v
                    elif "tx_rate_measured" in k:
                        tx_rate_measured = v

                if rx_rate_allocated < rx_rate_measured:
                    parts["as_issues"].append("rx_over")

                if tx_rate_allocated < tx_rate_measured:
                    parts["as_issues"].append("tx_over")

        except Exception as e:
            print(e)

    @property
    def collect(self):

        threads = [
            Thread(
                target=self.router_process,
                args=(router,),
            )
            for _, router in self.router_db.items()
            if len(router["params"]) > 0
        ]

        for x in threads:
            x.start()

        for y in threads:
            y.join()

        documents = []

        overall_counters = {
            "i_port_status": 0,
            "i_over_subscriptions": 0,
            "i_port_configuration": 0,
            "s_type": "summary",
        }

        for ipg in self.ipg_db:

            for link, ports in ipg["connections"].items():

                # copy in the ipg dictionary template and remove the connections
                ipg_def = copy.deepcopy(ipg)
                ipg_def.pop("connections")

                # place holder to merge issues together
                issues = []

                for port in ports:

                    try:

                        router_port_parts = copy.deepcopy(self.router_db[port["device"]]["ports_db"][port["port"]])

                        # extend the issue list and pop out the issue list from the definition.
                        issues.extend(router_port_parts.pop("as_issues"))

                        # merge the port metrics into the ipg definition.
                        ipg_def.update(router_port_parts)

                        # add port number, capacity and sfp setting from the link to the definitons
                        for x, y in zip(["port", "capacity", "sfp"], ["i", "l", "s"]):

                            key = "{}_{}{}".format(y, x, "_" + port["type"] if port["type"] is not "router" else "")
                            ipg_def.update({key: port[x]})

                        # do port speed and capacity compare here. create an alert if they don't match
                        for k, v in router_port_parts.items():
                            if "speed" in k:
                                if v != port["capacity"]:
                                    issues.append("portspeed_missmatch")

                    except Exception as e:
                        print(e)
                        continue

                # finish off the ipg definition with issues data and type
                ipg_def.update(
                    {
                        "i_link": link,
                        "b_fault": True if issues else False,
                        "i_num_issues": len(issues),
                        "as_issues": list(set(issues)),
                        "s_type": "port",
                    }
                )

                # annotate the ipg def is room annotations is enabled
                if self.annotate:

                    if ipg_def["s_device_name"] in self.annotate.keys():
                        ipg_def.update(self.annotate[ipg_def["s_device_name"]])

                # merge the ipg def to the final document structure
                document = {
                    "fields": ipg_def,
                    "host": ipg_def["s_control_address"],
                    "name": "linkmon",
                }

                documents.append(document)

                overall_counters["i_over_subscriptions"] += issues.count("rx_over")
                overall_counters["i_over_subscriptions"] += issues.count("tx_over")
                overall_counters["i_port_status"] += issues.count("port_status")
                overall_counters["i_port_configuration"] += issues.count("portspeed_missmatch")

        # finish the overall counters document
        document = {
            "fields": overall_counters,
            "host": self.cluster_ip,
            "name": "linkmon",
        }

        documents.append(document)

        return documents


def main():

    params = {
        # "override": "_files/100.103.224.21",
        # "dual_hot": True,
        # "annotate": {"module": "ThirtyRock_PROD_edge_def", "dict": "return_reverselookup"},
        # "annotate_db": return_reverselookup(),
        "magnum_cache": {
            "insite": "127.0.0.1",
            "nature": "mag-1",
            "cluster_ip": "100.103.224.21",
            "ipg_matches": ["570IPG-X19-25G", "SCORPION", "3067VIP10G-3G"],
        },
    }

    collector = EdgeCollector(**params)

    # collector.create_snapshot()

    print(json.dumps(collector.collect, indent=1))


if __name__ == "__main__":
    main()

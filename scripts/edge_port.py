import copy
import datetime
import json
from threading import Thread

import requests
import urllib3


urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
requests.packages.urllib3.disable_warnings()


class magnum_cache:
    def catalog_cache(self):

        cache = self.cache_fetch()

        if cache:

            # main database initilized as empty dictionary and no port list initilized
            self.router_db = {}
            self.no_port_list = []

            # temp dict to organize the catalog
            port_list_db = {}

            for device in cache["magnum"]["magnum-controlled-devices"]:

                if device["device"] == "EXE":

                    router = {
                        device["device-name"]: {
                            "device_name": device["device-name"],
                            "device": device["device"],
                            "device_size": device["device-size"],
                            "device_type": device["device-type"],
                            "control_1_address": device["control-1-address"]["host"],
                            "control_2_address": device["control-2-address"]["host"],
                            "ports_db": {},
                            "params": [],
                        }
                    }

                    self.router_db.update(router)

                # future use if edges are connected to IPX cards
                if device["device"] == "IPX":
                    pass

                # future key dicates if the device is virtually modeled in the config as a placeholder
                if device["device"] in self.ipg_matches and "future" not in device.keys():

                    edge_template = {
                        "device_name": device["device-name"],
                        "device": device["device"],
                        "device_size": device["device-size"],
                        "device_type": device["device-type"],
                        "control_address": device["control-1-address"]["host"],
                        "sfps": {},
                    }

                    # test if a link was found
                    linked = None

                    # collect the sfp linkage (if exists) and create the parameter string now
                    # with the port information.
                    if "sfps" in device.keys():
                        for sfp_db in device["sfps"]:

                            sfp = copy.deepcopy(sfp_db)

                            # not every IPG SFP is linked to the router
                            if "link" in sfp.keys():

                                # add params list to the sfp dictionary
                                sfp["params"] = []

                                # iterate through each of the parames in the inherited parameter db update the fake [port] string
                                # to the sfp port number (-minus 1 (0 based ports))
                                for _, value in self.exe_parameters.items():

                                    param = copy.deepcopy(value)

                                    # zero base it and then replace the template marker '[port]'
                                    port_num = sfp["link"]["port"] - 1
                                    param["id"] = param["id"].replace("[port]", str(port_num))

                                    sfp["params"].append(param)

                                # convert Mb to bits
                                sfp["link"]["capacity"] = sfp["link"]["capacity"] * 1000000

                                # make copy of edge dictionary and add the sfp to the dict.
                                edge = copy.deepcopy(edge_template)
                                edge["sfps"].update(sfp)

                                # update the port_list_db with the port number as the object. create the
                                # router object if it doesn't already exist
                                if sfp["link"]["device"] in port_list_db.keys():
                                    port_list_db[sfp["link"]["device"]].update(
                                        {sfp["link"]["port"]: edge}
                                    )

                                else:
                                    port_list_db.update({sfp["link"]["device"]: {}})
                                    port_list_db[sfp["link"]["device"]].update(
                                        {sfp["link"]["port"]: edge}
                                    )

                                linked = True

                    if not linked:
                        # add to not linked list
                        self.no_port_list.append(edge_template)

            # merge the port_list_db with the router db. then merge all the port api parameters
            # into a single list in the router db.
            for router, ports in port_list_db.items():
                if router in self.router_db.keys():

                    self.router_db[router]["ports_db"].update(ports)

                    for _, port in ports.items():
                        self.router_db[router]["params"].extend(port["sfps"]["params"])

    def cache_fetch(self):

        try:

            response = requests.get(self.cache_url, verify=False, timeout=30.0)

            return json.loads(response.text)

        except Exception as e:

            with open("edge_ports", "a+") as f:
                f.write(
                    str(datetime.datetime.now())
                    + " --- "
                    + "magnum_cache_builder"
                    + "\t"
                    + str(e)
                    + "\r\n"
                )

            return None

    def __init__(self, **kwargs):

        self.insite = None
        self.nature = "mag-1"
        self.cluster_ip = None
        self.port_remap = None
        self.ipg_matches = []
        self.router_db = None
        self.no_port_list = None

        for key, value in kwargs.items():

            if ("insite" in key) and value:
                self.insite = value

            if ("host" in key) and value:
                self.host = value

            if ("nature" in key) and value:
                self.nature = value

            if ("cluster_ip" in key) and value:
                self.cluster_ip = value

            if ("ipg_matches" in key) and value:
                self.ipg_matches.extend(value)

        self.cache_url = "http://{}/proxy/insite/{}/api/-/model/magnum/{}".format(
            self.insite, self.nature, self.cluster_ip
        )

        self.catalog_cache()


class edge_collector(magnum_cache):
    def fetch_api(self, router, parameters):

        try:

            with requests.Session() as session:

                ## get the session ID from accessing the login.php site
                resp = session.get("http://%s/login.php" % router, verify=False, timeout=30.0,)

                sessionID = resp.headers["Set-Cookie"].split(";")[0]

                payload = {
                    "jsonrpc": "2.0",
                    "method": "get",
                    "params": {"parameters": parameters},
                    "id": 1,
                }

                url = "http://%s/cgi-bin/cfgjsonrpc" % (router)

                headers = {
                    "content_type": "application/json",
                    "Cookie": sessionID + "; webeasy-loggedin=true",
                }

                response = session.post(
                    url, headers=headers, data=json.dumps(payload), verify=False, timeout=30.0,
                )

                return json.loads(response.text)

        except Exception as e:

            with open("edge_ports", "a+") as f:
                f.write(
                    str(datetime.datetime.now())
                    + " --- "
                    + "router_api_fetch"
                    + "\t"
                    + str(e)
                    + "\r\n"
                )

            return None

    def thread_process(self, router, parts, catalog):

        # need error handling....
        response = self.fetch_api(parts["control_1_address"], parts["params"])

        if isinstance(response, dict):

            try:

                router_result = {router: response["result"]["parameters"]}

            except Exception:
                router_result = {}

            # scan through every result in each router object and build a new dictionary
            # with the ipg as each object and update the object if it already exists
            for router, results in router_result.items():

                for param in results:

                    # skip over if a parameter is flagged with error
                    if "error" not in param.keys():

                        # port instance of string: 241.269@i = 269(+1)
                        base_port = int(param["id"].split("@")[0].split(".")[1]) + 1

                        # check if the cache lookup has the port
                        if base_port in self.router_db[router]["ports_db"].keys():

                            # creates a prefix which is a subset of the router name string
                            # which is then concatinated into field names.
                            prefix_key = eval(self.router_prefix) + "_"

                            # reference in the ipg dictionary by the port
                            ipg = self.router_db[router]["ports_db"][base_port]

                            name = ipg["device_name"]
                            sfp = int(ipg["sfps"]["number"])

                            sfp_key = "i_" + prefix_key + "IPG_SFP"
                            exe_key = "i_" + prefix_key + "EXE_PORT"

                            capacity = ipg["sfps"]["link"]["capacity"]
                            capacity_key = "l_" + prefix_key + "CAPACITY"

                            # check if the ipg name is in the result dictionary
                            # if not, then create the object
                            if name not in catalog.keys():

                                catalog.update({name: {"links": {}}})

                            # base_port is used to seperate multiple links an ipg has to one router.
                            if base_port not in catalog[name]["links"].keys():

                                catalog[name]["links"].update({base_port: {}})

                                # create base information.
                                # this may get updated twice for multiple links, but no biggie
                                fields = {
                                    "s_device_name": ipg["device_name"],
                                    "s_device": ipg["device"],
                                    "s_device_size": ipg["device_size"],
                                    "s_device_type": ipg["device_type"],
                                    "s_control_address": ipg["control_address"],
                                }

                                catalog[name].update(fields)

                            # add the sfp number and the exe port numbers for links found in base_port object
                            if sfp_key not in catalog[name]["links"][base_port].keys():
                                catalog[name]["links"][base_port].update({sfp_key: sfp})

                            if exe_key not in catalog[name]["links"][base_port].keys():
                                catalog[name]["links"][base_port].update({exe_key: base_port})

                            # add capacity information to link
                            if capacity_key not in catalog[name]["links"][base_port].keys():
                                catalog[name]["links"][base_port].update({capacity_key: capacity})

                            # iterate through each of the control paramters
                            for key, item in self.exe_parameter_control.items():

                                # check if the key in control parameters is in the name of the parameter
                                if key in param["name"]:

                                    # perform change depending what the change is for parameter
                                    if "multiplier" in item.keys():
                                        param["value"] = param["value"] * item["multiplier"]

                                    elif "convert" in item.keys():
                                        param["value"] = item["convert"][param["value"]]

                                    # convert name from say RX Rate Allocated --> l_X_RX_Rate_Allocated
                                    param["name"] = (
                                        item["type"] + prefix_key + param["name"].replace(" ", "_")
                                    )

                            # add parameter to link object
                            catalog[name]["links"][base_port].update(
                                {param["name"]: param["value"]}
                            )

    @property
    def collect(self):

        # test prints
        override = {
            "7N.EXE.002.PROD.X": "172.17.151.13",
            "7N.EXE.026.PROD.Y": "172.17.151.15",
        }

        for router, parts in self.router_db.items():

            if self.override:
                parts["control_1_address"] = override[router]

            if self.verbose:
                print(
                    router,
                    len(parts["ports_db"].keys()),
                    len(parts["params"]),
                    parts["control_1_address"],
                )

        if self.verbose:
            print("Not connected", len(self.no_port_list))

        # documents list returned to poller program
        documents = []

        # shared dictionary for processing thread
        self.catalog_results = {}

        threads = [
            Thread(target=self.thread_process, args=(router, parts, self.catalog_results,))
            for router, parts in self.router_db.items()
        ]

        for x in threads:
            x.start()

        for y in threads:
            y.join()

        counters = {
            "i_portfailures": 0,
            "i_oversubscriptions": 0,
            "i_speedstatus": 0,
            "s_type": "summary",
        }

        # create analysis and comparison on everything
        # then build the document list through the iterations.
        for _, data in self.catalog_results.items():

            links = data["links"]

            ## add a link number to each ipg link for aggregations##
            # dict_keys - > list - > sorted
            for index, key in enumerate(sorted(list(links.keys())), 1):
                links[key]["i_LINK"] = index

            # begin checking each link and do the comparison/analysis
            for key, link in links.items():

                # init placeholders
                compare_rates, compare_speed, link_faults = {}, {}, []

                for label, value in link.items():

                    # perform link operation status verification
                    if "Status" in label and value == "DOWN":
                        link_faults.append("{}".format(label[2:]))
                        counters["i_portfailures"] += 1

                    # store the measure and allocated parameters into an organized dictionary nested by the router
                    if "TX" in label or "RX" in label:

                        parts = label.split("_")
                        if parts[1] not in compare_rates.keys():
                            compare_rates.update(
                                {
                                    parts[1]: {
                                        "TX": {"Measured": None, "Allocated": None},
                                        "RX": {"Measured": None, "Allocated": None},
                                    }
                                }
                            )

                        compare_rates[parts[1]][parts[2]][parts[4]] = value

                    # store the capacity and speed into a organized dictionary nested by the router
                    if "Speed" in label or "CAPACITY" in label:

                        parts = label.split("_")
                        if parts[1] not in compare_speed.keys():
                            compare_speed.update({parts[1]: {"Speed": None, "CAPACITY": None}})

                        compare_speed[parts[1]][parts[2]] = value

                # iterate through rates dictionary and perform compare in each nested [router][tx/rx] object
                for router, collections in compare_rates.items():
                    for direction, params in collections.items():

                        if params["Measured"] > params["Allocated"]:

                            link_faults.append("{}_{}_Over".format(router, direction))
                            counters["i_oversubscriptions"] += 1

                # iterate through speed and capacity and compare if they are not the same
                for router, params in compare_speed.items():
                    if params["Speed"] != params["CAPACITY"]:

                        link_faults.append("{}_portSpeed_missmatch".format(router))
                        counters["i_speedstatus"] += 1

                # complete the fault flag creation
                if len(link_faults) > 0:

                    link["b_FAULT"] = True
                    link["s_FAULT_LIST"] = ", ".join(link_faults)
                    link["as_FAULT_LIST"] = link_faults

                else:
                    link["b_FAULT"] = False

                ##### building the insite poller document list #####
                ####################################################

                fields = {}

                # load in the link items
                for label, value in link.items():
                    fields.update({label: value})

                # load in top level items
                for label, value in data.items():
                    if label != "links":
                        fields.update({label: value})

                # annotate the document if annotation is active
                if self.annotate:

                    if fields["s_device_name"] in self.annotate.keys():
                        fields.update(self.annotate[fields["s_device_name"]])

                fields.update({"s_type": "port"})

                document = {
                    "fields": fields,
                    "host": fields["s_control_address"],
                    "name": "linkmon",
                }

                documents.append(document)

        ### create summary ##
        document = {"fields": counters, "host": self.cluster_ip, "name": "linkmon"}

        documents.append(document)

        if self.verbose:
            # print(json.dumps(self.catalog_results))
            print("ipgs:", len(self.catalog_results.keys()))
            links = 0
            for _, parts in self.catalog_results.items():
                links = links + len(parts["links"])
            print("links:", links)
            print("document_list:", len(documents))
            print(counters)

        return documents

    def __init__(self, **kwargs):

        self.exe_parameters = {
            "rx_allocated": {"id": "241.[port]@i", "type": "integer", "name": "RX Rate Allocated",},
            "rx_measured": {"id": "932.[port]@i", "type": "integer", "name": "RX Rate Measured",},
            "tx_allocated": {"id": "242.[port]@i", "type": "integer", "name": "TX Rate Allocated",},
            "tx_measured": {"id": "933.[port]@i", "type": "integer", "name": "TX Rate Measured",},
            "port_status": {"id": "921.[port]@i", "type": "integer", "name": "Operation Status",},
            "port_speed": {"id": "920.[port]@i", "type": "integer", "name": "Speed"},
        }

        self.exe_parameter_control = {
            "Allocated": {"type": "l_", "multiplier": 1000},
            "Measured": {"type": "l_", "multiplier": 1000},
            "Status": {"type": "s_", "convert": {0: "UP", 1: "DOWN"}},
            "Speed": {"type": "l_", "multiplier": 1000000},
        }

        if "magnum_cache" in kwargs.keys():
            magnum_cache.__init__(self, **kwargs["magnum_cache"])

        self.verbose = None
        self.override = None
        self.disconnected = None
        self.catalog_results = {}
        self.annotate = None

        for key, value in kwargs.items():

            if "verbose" in key and value:
                self.verbose = True

            if "override" in key and value:
                self.override = True

            if "disconnected" in key and value:
                self.disconnected = True

            if "router_prefix" in key and value:
                self.router_prefix = value

            if key == "annotate":

                exec("from {} import {}".format(value["module"], value["dict"]), globals())

                self.annotate = eval(value["dict"] + "()")

            if "annotate_db" in key:
                self.annotate = value


def main():

    params = {
        "override": True,
        "verbose": True,
        "disconnected": True,
        "router_prefix": "router[-1:]",
        "annotate": {"module": "ThirtyRock_PROD_edge_def", "dict": "return_reverselookup"},
        # "annotate_db": return_reverselookup(),
        "magnum_cache": {
            "insite": "172.16.205.201",
            "nature": "mag-1",
            "cluster_ip": "100.103.224.21",
            "ipg_matches": ["570IPG-X19-25G"],
        },
    }

    collector = edge_collector(**params)

    print(json.dumps(collector.collect, indent=2))
    # print(len(return_reverselookup().keys()))
    # inputQuit = False

    # while inputQuit is not "q":

    #     print(json.dumps(collector.collect, indent=2))

    #     inputQuit = input("\nType q to quit or just hit enter: ")


if __name__ == "__main__":
    main()

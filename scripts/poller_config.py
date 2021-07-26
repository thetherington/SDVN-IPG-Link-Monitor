import json
from edge_port import EdgeCollector
from insite_plugin import InsitePlugin


class Plugin(InsitePlugin):
    def can_group(self):
        return False

    def fetch(self, hosts):

        try:

            self.collector

        except Exception:

            # from ThirtyRock_PROD_edge_def import return_reverselookup

            params = {
                # "dual_hot": True,
                # "annotate_db": return_reverselookup(),
                "magnum_cache": {
                    "insite": "127.0.0.1",
                    "nature": "mag-1",
                    "cluster_ip": hosts[-1],
                    "ipg_matches": ["570IPG-X19-25G", "SCORPION", "3067VIP10G-3G"],
                },
            }

            self.collector = EdgeCollector(**params)

        return json.dumps(self.collector.collect)

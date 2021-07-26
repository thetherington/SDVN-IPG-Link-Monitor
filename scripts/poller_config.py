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

            from ThirtyRock_PROD_edge_def import return_reverselookup

            params = {
                "dual_hot": True,
                "annotate_db": return_reverselookup(),
                "magnum_cache": {
                    "insite": "100.103.224.9",
                    "nature": "mag-1",
                    "cluster_ip": "100.103.224.21",
                    "ipg_matches": ["570IPG-X19-25G"],
                },
            }

            self.collector = EdgeCollector(**params)

        return json.dumps(self.collector.collect)

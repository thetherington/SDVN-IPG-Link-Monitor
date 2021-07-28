# Edge Link Connectivity Collector

The purpose of this script module is to discover edge device links from a Magnum SDVN system and collect the port health, configuration, and measured/allocated bandwidth parameters from a core SDVN router device (EXE or IPX).  This module uses the Magnum SDVN configuration to discover all devices of a particular type(s), and fetches the webeasy parameters of the ports connected from a core router.  This script module compares and analyzes the measured bandwidth vs. the allocated bandwidth of a port.  If issues are detected with the link of a device, then they are recorderd and summarized.  

Below are the module distinct abilities and features that it provides:

1. Supports device type(s) group lookup in Magnum SDVN.
2. Comparitive analysis of measured bandwidth vs. allocated bandwidth.
3. Analyze port status and port speed configuration.
4. Support a dual hot router mode (main / backup) grouping of links.
5. Overall summary status of all links in a SDVN system.
6. Supports custom control room annotations definition (_if one exists_)

## Minimum Requirements:

- inSITE Version 11.0 or inSITE 10.3 Service Pack 13+
- Python3.7 (_already installed on inSITE machine_)
- Python3 Requests library (_already installed on inSITE machine_)

## Installation:

Installation of the status monitoring module requires copying two scripts into the poller modules folder:

1. Copy __edge_port.py__ script to the poller python modules folder:
   ```
    cp scripts/edge_port.py /opt/evertz/insite/parasite/applications/pll-1/data/python/modules/
   ```

2. Restart the poller application

## Configuration:

To configure a poller to use the module start a new python poller configuration outlined below

1. Click the create a custom poller from the poller application settings page
2. Enter a Name, Summary and Description information
3. Enter the Magnum Cluster IP in the _Hosts_ tab
4. From the _Input_ tab change the _Type_ to __Python__
5. From the _Input_ tab change the _Metric Set Name_ field to __ipg__
6. From the _Input_ tab change the _Freqency_ value to __30000__ (_30 seconds_)
7. From the _Python_ tab select the _Advanced_ tab and enable the __CPython Bindings__ option
8. Select the _Script_ tab, then paste the contents of __scripts/poller_config.py__ into the script panel.

9. Update the below argument _ipg_matches_ list with the device type labels to be collected.

```
                    "ipg_matches": ["570IPG-X19-25G", "SCORPION", "3067VIP10G-3G"],
```
10.  Save changes, then restart the poller program.

__Optional Parameters / Configuration__

11. To enable the dual hot router mode of grouping links with main/backup annotations, uncomment the below line: 

   ```
               "dual_hot": True,
   ```

12. (Optional) Locate the sections that import a custom control room definition file (_if available_) and uncomment the lines.

   ```
            # control room annotation file
            from ThirtyRock_PROD_edge_def import return_roomlist
   ```

   ```
                "annotate_db": return_reverselookup(),
   ```

## Testing:

The edge_port script can be ran manually from the shell using the following command

```
python edge_port.py
```

You can configure the script with custom settings via the below dictionary definition:

```
    params = {
        "override": "_files/100.103.224.21",
        "dual_hot": True,
        "annotate": {"module": "ThirtyRock_PROD_edge_def", "dict": "return_reverselookup"},
        # "annotate_db": return_reverselookup(),
        "magnum_cache": {
            "insite": "172.16.205.77",
            "nature": "mag-1",
            "cluster_ip": "100.103.224.21",
            "ipg_matches": ["570IPG-X19-25G", "SCORPION", "3067VIP10G-3G"],
        },
    }
```

Below is a sample output:

```
[
 {
  "fields": {
   "s_device_name": "3N.IPG.042.A.05",
   "s_device": "570IPG-X19-25G",
   "s_device_size": "16x0",
   "s_device_type": "edge",
   "s_control_address": "100.103.228.225",
   "s_main": "7N.EXE.002.PROD.X",
   "s_backup": "7N.EXE.026.PROD.Y",
   "l_rx_rate_allocated_main": 15000000,
   "l_rx_rate_measured_main": 15008449000,
   "l_tx_rate_measured_main": 1670000,
   "l_speed_main": 25000000000,
   "l_tx_rate_allocated_main": 20000000,
   "s_operation_status_main": "UP",
   "i_port_main": 794,
   "l_capacity_main": 25000000000,
   "l_rx_rate_allocated_backup": 15000000,
   "l_rx_rate_measured_backup": 15007331000,
   "l_tx_rate_measured_backup": 312000,
   "l_speed_backup": 25000000000,
   "l_tx_rate_allocated_backup": 20000000,
   "s_operation_status_backup": "UP",
   "i_port_backup": 794,
   "l_capacity_backup": 25000000000,
   "i_link": 1,
   "b_fault": true,
   "i_num_issues": 2,
   "as_issues": [
    "rx_over"
   ],
   "s_type": "port"
  },
  "host": "100.103.228.225",
  "name": "linkmon"
 },
 {
  "fields": {
   "s_device_name": "7N.IPG.058.B.08",
   "s_device": "570IPG-X19-25G",
   "s_device_size": "8x8",
   "s_device_type": "edge",
   "s_control_address": "100.103.226.84",
   "s_main": "7N.EXE.002.PROD.X",
   "s_backup": "7N.EXE.026.PROD.Y",
   "l_rx_rate_allocated_main": 12135000000,
   "l_rx_rate_measured_main": 10639659000,
   "l_tx_rate_measured_main": 9580815000,
   "l_speed_main": 25000000000,
   "l_tx_rate_allocated_main": 10860000000,
   "s_operation_status_main": "UP",
   "i_port_main": 595,
   "l_capacity_main": 25000000000,
   "l_rx_rate_allocated_backup": 12135000000,
   "l_rx_rate_measured_backup": 10639937000,
   "l_tx_rate_measured_backup": 9580008000,
   "l_speed_backup": 25000000000,
   "l_tx_rate_allocated_backup": 10860000000,
   "s_operation_status_backup": "UP",
   "i_port_backup": 595,
   "l_capacity_backup": 25000000000,
   "i_link": 1,
   "b_fault": false,
   "i_num_issues": 0,
   "as_issues": [],
   "s_type": "port",
   "PCR": "CR8H",
   "SWITCHER": "XVS_7058"
  },
  "host": "100.103.226.84",
  "name": "linkmon"
 },
 {
  "fields": {
   "i_port_status": 81,
   "i_over_subscriptions": 536,
   "i_port_configuration": 43,
   "s_type": "summary"
  },
  "host": "100.103.224.21",
  "name": "linkmon"
 }
]
```
import requests
import time

ZABBIX_URL = "http://10.0.147.10:8080/api_jsonrpc.php"
TOKEN = "126a5fb4a1705f6b35fe502671b4939bb153a99c99eac78024607e9c770ff4ae"

START_TIME = int(time.time()) - 3600
END_TIME = int(time.time())

header = {
    "Content-Type": "application/json-rpc",
    "Authorization": f"Bearer {TOKEN}",
}


def get_zabbix_hosts(host: str):
    payload = {
        "jsonrpc": "2.0",
        "method": "host.get",
        "params": {
            "filter": {
                "host": [host]
            },
            "output": ["hostid", "name"]
        },
        "id": 1
    }

    r = requests.post(
        ZABBIX_URL,
        headers=header,
        json=payload,
        timeout=10
    )
    r.raise_for_status()
    return r.json()["result"]


def get_zabbix_host_items(hostid: str):
    payload = {
        "jsonrpc": "2.0",
        "method": "item.get",
        "params": {
            "output": ["itemid", "name", "key_"],
            "hostids": hostid,
            "sortfield": "name"
        },
        "id": 2
    }

    r = requests.post(
        ZABBIX_URL,
        headers=header,
        json=payload,
        timeout=10
    )
    r.raise_for_status()
    return r.json()["result"]


def filter_items_by_key(items, name_list):
    result = []
    for item in items:
        if item["name"] in name_list:
            result.append(item["itemid"])
    return result


interface_list = []


def filter_to_list(keyname: str = "", i: str = "1"):
    interface_list.clear()

    if not keyname:
        interface_list.append(f"Interface GigabitEthernet0/0/{i}(): Bits received")
        interface_list.append(f"Interface GigabitEthernet0/0/{i}(): Bits sent")
        interface_list.append(f"Interface GigabitEthernet0/0/{i}(): Operational status")
        return interface_list

    interface_list.append(keyname)
    return interface_list


def get_interface_traffic(itemids):
    result = []

    for itemid in itemids:
        payload = {
            "jsonrpc": "2.0",
            "method": "history.get",
            "params": {
                "output": "extend",
                "history": 3,
                "itemids": [itemid],
                "sortfield": "clock",
                "sortorder": "DESC",
                "limit": 1
            },
            "id": 3
        }

        r = requests.post(
            ZABBIX_URL,
            headers=header,
            json=payload,
            timeout=10
        )
        r.raise_for_status()
        result.append(r.json()["result"])

    return result


def main(hostname: str = "10.0.147.254", interface_number: str = "3"):
    hosts = get_zabbix_hosts(hostname)
    if not hosts:
        return {}

    items = get_zabbix_host_items(hosts[0]["hostid"])

    interface_names = filter_to_list(i=interface_number)
    item_ids = filter_items_by_key(items, interface_names)

    traffic = get_interface_traffic(item_ids)

    result = {}

    for i, t in enumerate(traffic):
        # 最后一项是接口状态
        if i == len(traffic) - 1:
            result[interface_list[i]] = (
                "active" if t and t[0]["value"] == "1" else "inactive"
            )
            break

        if t:
            value = f"{float(t[0]['value']) / 1000:.2f}Kbps"
            result[interface_list[i]] = value

    return result


if __name__ == "__main__":
    print(main())

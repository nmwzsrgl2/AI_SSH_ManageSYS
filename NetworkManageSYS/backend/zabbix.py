import requests
import time
import json
import os
ZABBIX_URL = os.getenv("ZABBIX_URL")
ZABBIX_USER = os.getenv("ZABBIX_USER")
ZABBIX_PASS = os.getenv("ZABBIX_PASS")
TOKEN = os.getenv("TOKEN")


START_TIME = int(time.time()) - 3600  # 一小时前
END_TIME = int(time.time())  # 当前时间
header= {
        'Content-Type': 'application/json-rpc',
        "Authorization": f"Bearer {TOKEN}"
}
class zabbix_api:
    def __init__(self):
        self.url = ZABBIX_URL
        self.header = header
        self.interface_list = []
    def get_zabbix_hosts(self):
        payload = {
        "jsonrpc": "2.0",
        "method": "host.get",
        "params": {
            "history": 5,
            "output": [
        "hostid",
        "host",
        "name",
        'active_available'
    ],
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


    def get_zabbix_host_items(self,hostid):
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
    #通过主机获得的监控项items的数据按名字过滤
    def filter_items_by_key(self,items, name_prefix):
        interface_list = []
        for item in items:
            if item["name"] in name_prefix:
                interface_list.append(item['itemid'])
        return interface_list
    #主要筛选监控项的名称
    def filter_to_list(self,keyname:str = '', i:str = '1'):
        if len(keyname) == 0:
            self.interface_list.clear()
            self.interface_list.append(f"Interface GigabitEthernet0/0/{i}(): Bits received")
            self.interface_list.append(f"Interface GigabitEthernet0/0/{i}(): Bits sent")
            return self.interface_list
        return [keyname]
    #得到历史数据
    def get_interface_traffic(self,itemid):
        result = []
        for i in itemid: #itemid = ['50898', '51000']
            payload = {
                "jsonrpc": "2.0",
                "method": "history.get",
                "params": {
                    "output": "extend",
                    "history": 3,               #可能值:0 - 数值型float;1 - 字符型;2 - 日志型;3 - (默认) 无符号数值型;4 - 文本型;5 - 二进制型.
                    "itemids": [i],
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


# def main(hostname:str = '10.0.147.254',interface_number:str = '3'):
#     hosts = get_zabbix_hosts(hostname)
#     items = get_zabbix_host_items(hosts[0]['hostid'])
#     interface = filter_to_list(i=interface_number)
#     keys = filter_items_by_key(items, interface)
#     traffic = get_interface_traffic(keys)
#     result = {}
#     for i,t in enumerate(traffic):
#         #转换为 Kbps
#         if t:
#             value = str(float(t[0]['value']) / 1000) +"Kbps"
#             result[interface_list[i]] = value
#     return result

    #主函数
    def main(self,name_prefix):
        result_list = []
        result = {}
        r = self.get_zabbix_hosts()
        key = ["zabbix[host,agent,available]",'system.uptime']
        for host in r:
            items = self.get_zabbix_host_items(host['hostid'])
            result['name'] = host['host']
            if host['host'] in name_prefix:
                continue
            for item in items:
                if item['key_'] == key[0]:
                    active = self.get_interface_traffic([item['itemid']])
                    result['status'] = 'normal' if active[0][0]['value'] == '1' else 'problem'
                if item['key_'] == key[1]:
                    version = self.get_interface_traffic([item['itemid']])
                    result['runing'] = (int(version[0][0]['value']) / 3600 /24).__floor__()  #单位天
            result_list.append(result)
            result = {}
        return json.dumps(result_list)

if __name__ == "__main__":
    zabbix = zabbix_api()
    #排除列表，zabbix_hostname
    name_prefix = ['SW1']
    a = zabbix.main(name_prefix=name_prefix)
    print(a)
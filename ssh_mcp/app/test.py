from ssh_mcp import SSHManager
import httpx
import json
headers = {
    "content-type":"application/json"
}
payload = {"username":"admin","password":"admin123"}
r = httpx.post("http://10.0.147.50:5555/api/login",json=payload,headers=headers)
headers['Cookie'] = r.cookies.get('session')
devices_id = []
respones = httpx.get("http://10.0.147.50:5555/api/devices",headers=headers)
if respones.text:
    respones = json.loads(respones.text)
    for i in respones:
        devices_id.append(i['id'])

payload = {'device_ids': devices_id}
r = httpx.post("http://10.0.147.50:5555/api/devices/batch-inspect",json=payload,headers=headers,timeout=45,)
a = json.loads(r.content.decode("utf-8"))
print(a)

    
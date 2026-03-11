import json
import httpx
import re
import time

class Dify_agent:
    def __init__(self, user_query: str, model: str = "",conversation_id:str='',user:str='admin',task_id:str=''):  # 将 user_query 类型改为 str
        self.model = model
        self.user_query = user_query
        self.conversation_id = conversation_id
        self.url = "http://10.0.147.60/v1/chat-messages"
        self.user = user
        self.task_id = task_id
        self.headers = {
            'Authorization': 'Bearer app-UXPqFYVlNGLYEdRk3zPkn93e',
            'Content-Type': 'application/json' 
        }

    async def request_dify(self):
        timestamp = time.time()
        payload = {
            "inputs": {},
            "query": self.user_query,
            "response_mode": "streaming",
            "conversation_id": self.conversation_id,
            "user": "admin",
            "files": []
        }
        isthinking = False
        async with httpx.AsyncClient(timeout=120) as client:
            async with client.stream(
                "POST",
                self.url,
                headers=self.headers,
                json=payload
            ) as response:
                async for line in response.aiter_lines():
                    if not line:
                        continue
                    if not line.startswith("data:"):
                        continue

                    data = line.replace("data:", "", 1).strip()

                    chunk = json.loads(data)
                    # if chunk.get("event") == "workflow_started":
                    #     yield json.dumps(
                    #         {
                    #             "conversation_id": chunk.get("conversation_id"),
                    #         },
                    #         ensure_ascii=False
                    #     )
                    task_id =  str(chunk.get("task_id"))
                    if chunk.get("event") == "message_end":
                        yield json.dumps(
                            {"content": True,
                             "conversation_id":str(chunk.get("conversation_id"))
                             },
                            ensure_ascii=False
                        )
                        return
                    if chunk.get("event") == "message":
                        answer = chunk.get("answer", "")
                        pattern = r'<think>'
                        pattern2 = r'</think>'
                        think_match = re.search(pattern, answer, re.DOTALL)
                        think_match2 = re.search(pattern2,answer,re.DOTALL)
                        if think_match or isthinking:
                            isthinking = True
                            thinking = str(answer).replace("<think>\n",'')
                            content = ""
                        if think_match2 or isthinking ==False :
                            isthinking = False
                            thinking = ''
                            content = str(answer).replace("\n</think>",'')

                        yield json.dumps(
                            {
                                "content": content,
                                "thinking": thinking,
                                "conversation_id":"",
                                "task_id": task_id
                            },
                            ensure_ascii=False
                        )
    def stop_chat(self):
        payload = {
            "user": self.user
        }
        res = httpx.post(f'http://10.0.147.60/v1/chat-messages/:{self.task_id}/stop',headers=self.headers,json=payload)
        return json.loads(res.text)





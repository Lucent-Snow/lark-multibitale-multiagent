import requests
import os
from dotenv import load_dotenv

class FeishuClient:
    def __init__(self, app_id=None, app_secret=None):
        load_dotenv()
        self.app_id = app_id or os.getenv('FEISHU_APP_ID')
        self.app_secret = app_secret or os.getenv('FEISHU_APP_SECRET')
        self.base_url = "https://open.feishu.cn"
        self.access_token = None
        self.token_expire_time = 0
        
        if not self.app_id or not self.app_secret:
            raise ValueError("请提供飞书 App ID 和 App Secret")
    
    def _get_access_token(self):
        """获取访问令牌"""
        import time
        if self.access_token and time.time() < self.token_expire_time:
            return self.access_token
        
        url = f"{self.base_url}/open-apis/auth/v3/tenant_access_token/internal"
        headers = {"Content-Type": "application/json"}
        data = {
            "app_id": self.app_id,
            "app_secret": self.app_secret
        }
        
        try:
            resp = requests.post(url, json=data, headers=headers)
            resp.raise_for_status()
            result = resp.json()
            
            if result.get("code") == 0:
                self.access_token = result["tenant_access_token"]
                self.token_expire_time = time.time() + result["expire"] - 60
                return self.access_token
            else:
                print("获取访问令牌失败: %s" % result.get("msg"))
                return None
        except Exception as e:
            print("获取访问令牌异常: %s" % str(e))
            return None
    
    def list_tables(self):
        """列出所有多维表格"""
        token = self._get_access_token()
        if not token:
            return []
        
        url = f"{self.base_url}/open-apis/bitable/v1/apps"
        headers = {"Authorization": f"Bearer {token}"}
        
        try:
            resp = requests.get(url, headers=headers, params={"page_size": 50})
            resp.raise_for_status()
            result = resp.json()
            
            if result.get("code") == 0:
                tables = []
                for item in result.get("data", {}).get("items", []):
                    tables.append({
                        'table_id': item.get("table_id", ""),
                        'name': item.get("name", ""),
                        'app_token': item.get("app_token", ""),
                        'fields': []
                    })
                return tables
            else:
                print("API 调用失败: %s" % result.get("msg"))
                return []
        except Exception as e:
            print("获取表格列表失败: %s" % str(e))
            return []
    
    def get_table_detail(self, app_token, table_id):
        """获取表格详情和字段信息"""
        token = self._get_access_token()
        if not token:
            return None
        
        url = f"{self.base_url}/open-apis/bitable/v1/apps/{app_token}/tables/{table_id}"
        headers = {"Authorization": f"Bearer {token}"}
        
        try:
            resp = requests.get(url, headers=headers)
            resp.raise_for_status()
            result = resp.json()
            
            if result.get("code") == 0:
                return result.get("data", {})
            else:
                print("获取表格详情失败: %s" % result.get("msg"))
                return None
        except Exception as e:
            print("获取表格详情异常: %s" % str(e))
            return None
    
    def create_work_order(self, app_token, table_id, order_data):
        """在工单台账中创建新工单"""
        token = self._get_access_token()
        if not token:
            return None
        
        url = f"{self.base_url}/open-apis/bitable/v1/apps/{app_token}/tables/{table_id}/records"
        headers = {
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json"
        }
        data = {
            "fields": order_data
        }
        
        try:
            resp = requests.post(url, json=data, headers=headers)
            resp.raise_for_status()
            result = resp.json()
            
            if result.get("code") == 0:
                return result.get("data", {}).get("record")
            else:
                print("创建工单失败: %s" % result.get("msg"))
                return None
        except Exception as e:
            print("创建工单异常: %s" % str(e))
            return None
    
    def query_work_orders(self, app_token, table_id, filter_condition=None):
        """查询工单，支持筛选条件"""
        token = self._get_access_token()
        if not token:
            return []
        
        url = f"{self.base_url}/open-apis/bitable/v1/apps/{app_token}/tables/{table_id}/records"
        headers = {"Authorization": f"Bearer {token}"}
        params = {"page_size": 100}
        
        if filter_condition:
            params["filter"] = str(filter_condition)
        
        try:
            resp = requests.get(url, headers=headers, params=params)
            resp.raise_for_status()
            result = resp.json()
            
            if result.get("code") == 0:
                return result.get("data", {}).get("items", [])
            else:
                print("查询工单失败: %s" % result.get("msg"))
                return []
        except Exception as e:
            print("查询工单异常: %s" % str(e))
            return []
    
    def query_pending_orders(self, app_token, table_id):
        """查询所有待分派的工单"""
        return self.query_work_orders(app_token, table_id)
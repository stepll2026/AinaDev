import unittest
from types import SimpleNamespace
from unittest.mock import AsyncMock

from fastapi import FastAPI
from fastapi.testclient import TestClient
from app.api.admin_system import router
from app.core.db import get_db
from app.core.deps import get_current_user


class LoginBrandingTests(unittest.TestCase):
    def setUp(self):
        self.rows = {}
        self.db = SimpleNamespace(
            scalars=AsyncMock(side_effect=lambda *args: list(self.rows.values())),
            get=AsyncMock(side_effect=lambda model, key: self.rows.get(key)),
            add=lambda row: self.rows.update({row.key: row}),
            commit=AsyncMock(),
        )
        self.app = FastAPI()
        self.app.include_router(router)
        self.app.dependency_overrides[get_db] = lambda: self.db
        self.client = TestClient(self.app)

    def test_save_public_read_and_clear(self):
        self.app.dependency_overrides[get_current_user] = lambda: SimpleNamespace(role='super_admin')
        body = {'login_title': '示例社区', 'login_subtitle': '开发者学习交流社区'}
        self.assertEqual(self.client.put('/api/admin/site-config', json=body).status_code, 200)
        public = self.client.get('/api/admin/site-config-public').json()
        self.assertEqual(public['login_title'], body['login_title'])
        self.assertEqual(public['login_subtitle'], body['login_subtitle'])
        self.rows['mcp_api_key'] = SimpleNamespace(key='mcp_api_key', value='secret')
        self.assertNotIn('mcp_api_key', self.client.get('/api/admin/site-config-public').json())
        self.client.put('/api/admin/site-config', json={'login_title': '', 'login_subtitle': ''})
        self.assertEqual(self.client.get('/api/admin/site-config-public').json()['login_subtitle'], '')

    def test_permissions_and_limits(self):
        self.assertIn(self.client.put('/api/admin/site-config', json={'login_title': 'x'}).status_code, (401, 403))
        self.app.dependency_overrides[get_current_user] = lambda: SimpleNamespace(role='user')
        self.assertEqual(self.client.put('/api/admin/site-config', json={'login_title': 'x'}).status_code, 403)
        self.app.dependency_overrides[get_current_user] = lambda: SimpleNamespace(role='super_admin')
        self.assertEqual(self.client.put('/api/admin/site-config', json={'login_title': 'x' * 121}).status_code, 422)

    def test_unconfigured_keeps_original_copy(self):
        public = self.client.get('/api/admin/site-config-public').json()
        self.assertEqual(public['login_title'], 'AI 开发者社区')
        self.assertEqual(public['login_subtitle'], '企业 AI 原生开发者社区 · 内部私有部署')

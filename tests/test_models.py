# Unit Tests for Proxy Collector

import unittest
from src.models import ProxyLink, CheckResult, AppSettings
from src.utils import parse_proxy_url, format_rtt, format_dc


class TestProxyLink(unittest.TestCase):
    def test_create_proxy_link(self):
        proxy = ProxyLink(
            server='example.com',
            port=443,
            secret='ee1234567890abcdef'
        )
        self.assertEqual(proxy.server, 'example.com')
        self.assertEqual(proxy.port, 443)
        self.assertEqual(proxy.secret, 'ee1234567890abcdef')
    
    def test_proxy_key(self):
        proxy1 = ProxyLink('example.com', 443, 'secret')
        proxy2 = ProxyLink('EXAMPLE.COM', 443, 'SECRET')
        self.assertEqual(proxy1.key, proxy2.key)
    
    def test_tg_link(self):
        proxy = ProxyLink('example.com', 443, 'secret')
        link = proxy.tg_link()
        self.assertIn('tg://proxy', link)
        self.assertIn('server=example.com', link)
        self.assertIn('port=443', link)
        self.assertIn('secret=secret', link)
    
    def test_to_dict(self):
        proxy = ProxyLink('example.com', 443, 'secret')
        data = proxy.to_dict()
        self.assertEqual(data['server'], 'example.com')
        self.assertEqual(data['port'], 443)
        self.assertEqual(data['secret'], 'secret')
    
    def test_from_dict(self):
        data = {'server': 'example.com', 'port': 443, 'secret': 'secret'}
        proxy = ProxyLink.from_dict(data)
        self.assertEqual(proxy.server, 'example.com')


class TestCheckResult(unittest.TestCase):
    def test_create_check_result(self):
        proxy = ProxyLink('example.com', 443, 'secret')
        result = CheckResult(proxy=proxy, ok=True, rtt_ms=50.5, dc=2)
        
        self.assertTrue(result.ok)
        self.assertEqual(result.rtt_ms, 50.5)
        self.assertEqual(result.dc, 2)
    
    def test_to_dict(self):
        proxy = ProxyLink('example.com', 443, 'secret')
        result = CheckResult(proxy=proxy, ok=True, rtt_ms=50.5)
        data = result.to_dict()
        
        self.assertTrue(data['ok'])
        self.assertEqual(data['rtt_ms'], 50.5)


class TestAppSettings(unittest.TestCase):
    def test_default_settings(self):
        settings = AppSettings()
        self.assertEqual(settings.concurrency, 40)
        self.assertEqual(settings.connect_timeout, 3.0)
        self.assertEqual(settings.language, 'ru')
    
    def test_to_dict(self):
        settings = AppSettings(concurrency=50)
        data = settings.to_dict()
        self.assertEqual(data['concurrency'], 50)
    
    def test_from_dict(self):
        data = {'concurrency': 60, 'connect_timeout': 5.0}
        settings = AppSettings.from_dict(data)
        self.assertEqual(settings.concurrency, 60)
        self.assertEqual(settings.connect_timeout, 5.0)


class TestUtils(unittest.TestCase):
    def test_parse_proxy_url_tg(self):
        url = 'tg://proxy?server=example.com&port=443&secret=abc123'
        result = parse_proxy_url(url)
        
        self.assertIsNotNone(result)
        self.assertEqual(result['server'], 'example.com')
        self.assertEqual(result['port'], 443)
        self.assertEqual(result['secret'], 'abc123')
    
    def test_parse_proxy_url_https(self):
        url = 'https://t.me/proxy?server=example.com&port=443&secret=abc123'
        result = parse_proxy_url(url)
        
        self.assertIsNotNone(result)
        self.assertEqual(result['server'], 'example.com')
    
    def test_parse_invalid_url(self):
        result = parse_proxy_url('invalid_url')
        self.assertIsNone(result)
    
    def test_format_rtt(self):
        self.assertEqual(format_rtt(50.5), '50ms')
        self.assertEqual(format_rtt(150.7), '150.7ms')
        self.assertEqual(format_rtt(1500.0), '1.50s')
        self.assertEqual(format_rtt(None), 'N/A')
    
    def test_format_dc(self):
        self.assertEqual(format_dc(2), 'DC 2')
        self.assertEqual(format_dc(None), 'N/A')


if __name__ == '__main__':
    unittest.main()

from django.test import TestCase, Client
from django.urls import reverse

class SmokeTest(TestCase):
    def test_server_starts(self):
        """
        Basic smoke test to ensure Django test client works.
        Prevents silent config issues.
        """
        client = Client()
        response = client.get("/")
        # We check for 200 or 404 to ensure the app is routing requests 
        # even if a home page isn't defined yet.
        self.assertIn(response.status_code, [200, 302, 404])

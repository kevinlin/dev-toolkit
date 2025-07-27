#!/usr/bin/env python3
"""
Outlook OAuth2 Authentication Module

Handles OAuth2 authentication and Microsoft Graph API access for Outlook accounts.
This replaces the Basic Authentication/IMAP approach which Microsoft has deprecated.
"""

import http.server
import socketserver
import urllib.parse
import webbrowser
from dataclasses import dataclass
from typing import Dict, List, Optional

import msal
import requests


@dataclass
class OutlookMessage:
    """Represents an email message from Microsoft Graph API"""
    id: str
    subject: str
    body_content: str
    sender_email: str
    received_datetime: str
    is_read: bool
    word_count: int = 0

class OutlookOAuth2Client:
    """Handles OAuth2 authentication and Microsoft Graph API access for Outlook"""

    # Microsoft Graph API endpoints
    AUTHORITY = "https://login.microsoftonline.com/common"
    GRAPH_ENDPOINT = "https://graph.microsoft.com/v1.0"

    # Required scopes for email access
    SCOPES = [
        "https://graph.microsoft.com/Mail.Read",
        "https://graph.microsoft.com/Mail.ReadWrite",
        "https://graph.microsoft.com/User.Read"
    ]

    def __init__(self, client_id: str, client_secret: str = None, redirect_uri: str = "http://localhost:8080"):
        """
        Initialize OAuth2 client for Outlook

        Args:
            client_id: Azure app registration client ID
            client_secret: Optional client secret for confidential client
            redirect_uri: Redirect URI for OAuth2 flow
        """
        self.client_id = client_id
        self.client_secret = client_secret
        self.redirect_uri = redirect_uri
        self.access_token = None
        self.refresh_token = None
        self.token_cache_file = "outlook_token_cache.json"

        # Initialize MSAL client
        if client_secret:
            # Confidential client (with secret)
            self.app = msal.ConfidentialClientApplication(
                client_id=client_id,
                client_credential=client_secret,
                authority=self.AUTHORITY
            )
        else:
            # Public client (no secret)
            self.app = msal.PublicClientApplication(
                client_id=client_id,
                authority=self.AUTHORITY
            )

    def get_auth_url(self) -> str:
        """Get the authorization URL for OAuth2 flow"""
        auth_url = self.app.get_authorization_request_url(
            scopes=self.SCOPES,
            redirect_uri=self.redirect_uri
        )
        return auth_url

    def acquire_token_interactive(self) -> bool:
        """
        Acquire token using interactive OAuth2 flow

        Returns:
            bool: True if authentication successful, False otherwise
        """
        try:
            # First try to get token silently from cache
            accounts = self.app.get_accounts()
            if accounts:
                result = self.app.acquire_token_silent(self.SCOPES, account=accounts[0])
                if result and "access_token" in result:
                    self.access_token = result["access_token"]
                    self.refresh_token = result.get("refresh_token")
                    print("✅ Token acquired from cache")
                    return True

            # If no cached token, do interactive auth
            print("🔑 Starting interactive OAuth2 authentication...")
            print("📱 A browser window will open for authentication")

            if self.client_secret:
                # Use authorization code flow for confidential client
                return self._auth_code_flow()
            else:
                # Use device code flow for public client
                return self._device_code_flow()

        except Exception as e:
            print(f"❌ Authentication error: {e}")
            return False

    def _device_code_flow(self) -> bool:
        """Use device code flow for authentication (recommended for CLI apps)"""
        try:
            flow = self.app.initiate_device_flow(scopes=self.SCOPES)

            if "user_code" not in flow:
                raise ValueError("Failed to create device flow")

            print("\n📋 Device Code Authentication:")
            print(f"   Go to: {flow['verification_uri']}")
            print(f"   Enter code: {flow['user_code']}")
            print("   Waiting for authentication...")

            # Automatically open browser
            webbrowser.open(flow['verification_uri'])

            # Wait for user to complete authentication
            result = self.app.acquire_token_by_device_flow(flow)

            if "access_token" in result:
                self.access_token = result["access_token"]
                self.refresh_token = result.get("refresh_token")
                print("✅ Authentication successful!")
                return True
            else:
                print(f"❌ Authentication failed: {result.get('error_description', 'Unknown error')}")
                return False

        except Exception as e:
            print(f"❌ Device code flow error: {e}")
            return False

    def _auth_code_flow(self) -> bool:
        """Use authorization code flow for authentication"""
        try:
            auth_url = self.get_auth_url()
            print(f"Opening browser to: {auth_url}")
            webbrowser.open(auth_url)

            # Start local server to receive callback
            auth_code = self._start_callback_server()

            if not auth_code:
                print("❌ Failed to receive authorization code")
                return False

            # Exchange code for token
            result = self.app.acquire_token_by_authorization_code(
                auth_code,
                scopes=self.SCOPES,
                redirect_uri=self.redirect_uri
            )

            if "access_token" in result:
                self.access_token = result["access_token"]
                self.refresh_token = result.get("refresh_token")
                print("✅ Authentication successful!")
                return True
            else:
                print(f"❌ Token exchange failed: {result.get('error_description', 'Unknown error')}")
                return False

        except Exception as e:
            print(f"❌ Authorization code flow error: {e}")
            return False

    def _start_callback_server(self) -> Optional[str]:
        """Start temporary server to receive OAuth2 callback"""
        auth_code = None

        class CallbackHandler(http.server.BaseHTTPRequestHandler):
            def do_GET(self):
                nonlocal auth_code
                parsed_url = urllib.parse.urlparse(self.path)
                query_params = urllib.parse.parse_qs(parsed_url.query)

                if 'code' in query_params:
                    auth_code = query_params['code'][0]
                    self.send_response(200)
                    self.send_header('Content-type', 'text/html')
                    self.end_headers()
                    self.wfile.write(b'<html><body><h1>Authentication successful!</h1><p>You can close this window.</p></body></html>')
                else:
                    self.send_response(400)
                    self.send_header('Content-type', 'text/html')
                    self.end_headers()
                    self.wfile.write(b'<html><body><h1>Authentication failed!</h1></body></html>')

            def log_message(self, format, *args):
                pass  # Suppress server logs

        try:
            port = int(self.redirect_uri.split(':')[-1])
            with socketserver.TCPServer(("", port), CallbackHandler) as httpd:
                print(f"📡 Waiting for callback on {self.redirect_uri}")
                httpd.timeout = 60  # 60 second timeout
                httpd.handle_request()
                return auth_code
        except Exception as e:
            print(f"❌ Callback server error: {e}")
            return None

    def refresh_access_token(self) -> bool:
        """Refresh the access token using refresh token"""
        if not self.refresh_token:
            return False

        try:
            result = self.app.acquire_token_by_refresh_token(
                self.refresh_token,
                scopes=self.SCOPES
            )

            if "access_token" in result:
                self.access_token = result["access_token"]
                self.refresh_token = result.get("refresh_token", self.refresh_token)
                return True
            else:
                print(f"❌ Token refresh failed: {result.get('error_description', 'Unknown error')}")
                return False

        except Exception as e:
            print(f"❌ Token refresh error: {e}")
            return False

    def _make_graph_request(self, endpoint: str, method: str = "GET", data: Dict = None) -> Optional[Dict]:
        """Make authenticated request to Microsoft Graph API"""
        if not self.access_token:
            print("❌ No access token available")
            return None

        headers = {
            "Authorization": f"Bearer {self.access_token}",
            "Content-Type": "application/json"
        }

        url = f"{self.GRAPH_ENDPOINT}{endpoint}"

        try:
            if method == "GET":
                response = requests.get(url, headers=headers)
            elif method == "POST":
                response = requests.post(url, headers=headers, json=data)
            else:
                raise ValueError(f"Unsupported HTTP method: {method}")

            if response.status_code == 401:
                # Token might be expired, try to refresh
                if self.refresh_access_token():
                    headers["Authorization"] = f"Bearer {self.access_token}"
                    if method == "GET":
                        response = requests.get(url, headers=headers)
                    elif method == "POST":
                        response = requests.post(url, headers=headers, json=data)
                else:
                    print("❌ Token refresh failed, re-authentication required")
                    return None

            if response.status_code == 200:
                return response.json()
            else:
                print(f"❌ Graph API error: {response.status_code} - {response.text}")
                return None

        except Exception as e:
            print(f"❌ Graph API request error: {e}")
            return None

    def get_sent_messages(self, limit: int = 500) -> List[OutlookMessage]:
        """
        Get sent messages from Outlook using Microsoft Graph API

        Args:
            limit: Maximum number of messages to retrieve

        Returns:
            List[OutlookMessage]: List of sent messages
        """
        messages = []

        # Query sent items folder
        endpoint = f"/me/mailFolders/SentItems/messages?$top={min(limit, 1000)}&$select=id,subject,body,sender,receivedDateTime,isRead"

        while endpoint and len(messages) < limit:
            result = self._make_graph_request(endpoint)

            if not result or "value" not in result:
                break

            for msg_data in result["value"]:
                try:
                    # Extract message content
                    body_content = ""
                    if "body" in msg_data and msg_data["body"]:
                        body_content = msg_data["body"].get("content", "")
                        # If HTML, convert to text using html2text
                        if msg_data["body"].get("contentType") == "html":
                            try:
                                import html2text
                                h = html2text.HTML2Text()
                                h.ignore_links = True
                                h.ignore_images = True
                                h.ignore_emphasis = True
                                h.body_width = 0  # No line wrapping
                                h.unicode_snob = True  # Better Unicode handling
                                h.bypass_tables = False
                                h.ignore_tables = False
                                h.single_line_break = False  # Allow double line breaks for paragraphs
                                body_content = h.handle(body_content)

                                # Clean up excessive line breaks that html2text might add
                                body_content = re.sub(r'\n\s*\n\s*\n+', '\n\n', body_content)
                                # Remove leading/trailing whitespace
                                body_content = body_content.strip()

                            except ImportError:
                                # Fallback to basic HTML stripping with line break preservation
                                import re
                                # Convert common HTML elements to line breaks first
                                body_content = re.sub(r'<br\s*/?>', '\n', body_content, flags=re.IGNORECASE)
                                body_content = re.sub(r'</p>', '\n\n', body_content, flags=re.IGNORECASE)
                                body_content = re.sub(r'</div>', '\n', body_content, flags=re.IGNORECASE)
                                body_content = re.sub(r'</h[1-6]>', '\n\n', body_content, flags=re.IGNORECASE)
                                # Remove all remaining HTML tags
                                body_content = re.sub(r'<[^>]+>', '', body_content)
                                # Clean up excessive whitespace
                                body_content = re.sub(r'\n\s*\n\s*\n+', '\n\n', body_content)

                    sender_email = ""
                    if "sender" in msg_data and msg_data["sender"]:
                        email_addr = msg_data["sender"].get("emailAddress", {})
                        sender_email = email_addr.get("address", "")

                    message = OutlookMessage(
                        id=msg_data.get("id", ""),
                        subject=msg_data.get("subject", ""),
                        body_content=body_content,
                        sender_email=sender_email,
                        received_datetime=msg_data.get("receivedDateTime", ""),
                        is_read=msg_data.get("isRead", False),
                        word_count=len(body_content.split()) if body_content else 0
                    )

                    messages.append(message)

                except Exception as e:
                    print(f"⚠️ Error parsing message: {e}")
                    continue

            # Check for pagination
            endpoint = result.get("@odata.nextLink", "").replace(self.GRAPH_ENDPOINT, "") if "@odata.nextLink" in result else None

        return messages[:limit]

    def test_connection(self) -> bool:
        """Test the connection to Microsoft Graph API"""
        result = self._make_graph_request("/me")
        if result:
            email = result.get("mail", result.get("userPrincipalName", "Unknown"))
            print(f"✅ Connected to Microsoft Graph as: {email}")
            return True
        else:
            print("❌ Failed to connect to Microsoft Graph")
            return False


def create_outlook_oauth_client(email_address: str) -> OutlookOAuth2Client:
    """
    Create Outlook OAuth2 client with default Microsoft client ID

    For production use, you should register your own Azure app and use your client ID.
    This uses a public client registration that works for demo purposes.

    Args:
        email_address: Email address (for reference only)

    Returns:
        OutlookOAuth2Client: Configured OAuth2 client
    """

    # This is a public client ID for Microsoft Graph Explorer (for demo purposes)
    # For production, register your own app at: https://portal.azure.com
    DEFAULT_CLIENT_ID = "14d82eec-204b-4c2f-b7e8-296a70dab67e"  # Microsoft Graph Explorer

    print(f"📧 Creating OAuth2 client for: {email_address}")
    print("🔑 Using default client ID (register your own for production)")

    return OutlookOAuth2Client(
        client_id=DEFAULT_CLIENT_ID,
        redirect_uri="http://localhost:8080"
    )

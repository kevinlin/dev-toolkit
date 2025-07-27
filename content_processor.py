#!/usr/bin/env python3
"""
Content Processor Module

Handles email content extraction, cleaning, and filtering for the Email Exporter Script.
Processes HTML/text content, strips quoted replies, greetings, signatures, and validates content quality.
"""

import email.message
import hashlib
import re
from typing import Set

# Import HTML processing libraries
try:
    import html2text
    from bs4 import BeautifulSoup

    HTML_PROCESSING_AVAILABLE = True
except ImportError:
    HTML_PROCESSING_AVAILABLE = False
    print(
        "Warning: HTML processing libraries not available. Install with: pip install beautifulsoup4 html2text"
    )


class ContentProcessor:
    """Handles email content extraction, cleaning, and filtering"""

    def __init__(self):
        # Configure html2text converter
        if HTML_PROCESSING_AVAILABLE:
            self.html_converter = html2text.HTML2Text()
            self.html_converter.ignore_links = True
            self.html_converter.ignore_images = True
            self.html_converter.ignore_emphasis = False
            self.html_converter.body_width = 0  # Don't wrap lines
            self.html_converter.unicode_snob = True
        else:
            self.html_converter = None

    def extract_body_content(self, message: email.message.Message) -> str:
        """
        Extract body content from email message, handling multipart messages.

        Args:
            message: Email message to extract content from

        Returns:
            str: Extracted and cleaned body content
        """
        try:
            body_content = ""

            if message.is_multipart():
                # Handle multipart messages - prioritize text/plain, fallback to text/html
                text_parts = []
                html_parts = []

                for part in message.walk():
                    content_type = part.get_content_type()
                    content_disposition = str(part.get("Content-Disposition", ""))

                    # Skip attachments
                    if "attachment" in content_disposition:
                        continue

                    try:
                        payload = part.get_payload(decode=True)
                        if payload is None:
                            continue

                        # Decode bytes to string
                        if isinstance(payload, bytes):
                            # Try to get charset from content type
                            charset = part.get_content_charset() or "utf-8"
                            try:
                                text_content = payload.decode(charset)
                            except (UnicodeDecodeError, LookupError):
                                # Fallback to utf-8 with error handling
                                text_content = payload.decode("utf-8", errors="ignore")
                        else:
                            text_content = str(payload)

                        # Collect text and HTML parts
                        if content_type == "text/plain":
                            text_parts.append(text_content)
                        elif content_type == "text/html":
                            html_parts.append(text_content)

                    except Exception as e:
                        print(f"Warning: Error processing message part: {str(e)}")
                        continue

                # Prefer plain text over HTML
                if text_parts:
                    body_content = "\n\n".join(text_parts)
                elif html_parts:
                    # Convert HTML to text
                    html_content = "\n\n".join(html_parts)
                    body_content = self.convert_html_to_text(html_content)

            else:
                # Handle single-part messages
                payload = message.get_payload(decode=True)
                if payload is not None:
                    # Decode bytes to string
                    if isinstance(payload, bytes):
                        charset = message.get_content_charset() or "utf-8"
                        try:
                            body_content = payload.decode(charset)
                        except (UnicodeDecodeError, LookupError):
                            body_content = payload.decode("utf-8", errors="ignore")
                    else:
                        body_content = str(payload)

                    # If it's HTML content, convert to text
                    content_type = message.get_content_type()
                    if content_type == "text/html":
                        body_content = self.convert_html_to_text(body_content)

            # Clean and normalize the extracted content
            if body_content:
                body_content = self.strip_quoted_replies(body_content)
                body_content = self.strip_opening_greetings(body_content)
                body_content = self.strip_signatures(body_content)
                body_content = self.normalize_whitespace(body_content)

            return body_content

        except Exception as e:
            print(f"Error extracting body content: {str(e)}")
            return ""

    def convert_html_to_text(self, html_content: str) -> str:
        """
        Convert HTML content to plain text using html2text and BeautifulSoup.

        Args:
            html_content: HTML content to convert

        Returns:
            str: Plain text content
        """
        if not html_content or not html_content.strip():
            return ""

        try:
            # First, use BeautifulSoup for robust HTML parsing and cleanup
            if HTML_PROCESSING_AVAILABLE:
                soup = BeautifulSoup(html_content, "html.parser")

                # Remove script and style elements
                for script in soup(["script", "style"]):
                    script.decompose()

                # Get cleaned HTML
                cleaned_html = str(soup)

                # Convert to text using html2text
                if self.html_converter:
                    text_content = self.html_converter.handle(cleaned_html)
                else:
                    # Fallback: use BeautifulSoup's get_text method
                    text_content = soup.get_text()
            else:
                # Fallback: basic HTML tag removal using regex
                text_content = re.sub(r"<[^>]+>", "", html_content)

            return text_content

        except Exception as e:
            print(f"Warning: Error converting HTML to text: {str(e)}")
            # Fallback: basic HTML tag removal
            try:
                return re.sub(r"<[^>]+>", "", html_content)
            except Exception:
                return html_content

    def strip_quoted_replies(self, content: str) -> str:
        """
        Strip quoted replies and forwarded text from email content using comprehensive regex patterns.

        Args:
            content: Email content to clean

        Returns:
            str: Content with quoted replies removed
        """
        if not content:
            return ""

        try:
            lines = content.split("\n")
            cleaned_lines = []

            # Comprehensive patterns for quoted replies and forwards
            quote_patterns = [
                # Basic quote patterns
                r"^>.*",  # Lines starting with >
                r"^\s*>.*",  # Lines starting with whitespace and >
                r"^\s*>\s*>.*",  # Multiple levels of quoting
                # "On ... wrote:" patterns (various formats)
                r"^On .* wrote:.*",  # "On [date] [person] wrote:"
                r"^On .* at .* wrote:.*",  # "On [date] at [time] [person] wrote:"
                r"^On .*, .* wrote:.*",  # "On [day], [date] [person] wrote:"
                r"^\d{1,2}/\d{1,2}/\d{2,4}.*wrote:.*",  # Date formats with "wrote:"
                r"^\w+,\s+\w+\s+\d+,\s+\d{4}.*wrote:.*",  # "Monday, January 15, 2024 ... wrote:"
                # Email header patterns (forwards and replies)
                r"^From:.*",  # Email headers in forwards
                r"^To:.*",
                r"^Cc:.*",
                r"^Bcc:.*",
                r"^Subject:.*",
                r"^Date:.*",
                r"^Sent:.*",
                r"^Reply-To:.*",
                # Outlook-style patterns
                r"^\s*-----Original Message-----.*",  # Outlook original message
                r"^\s*________________________________.*",  # Outlook separator line
                r"^\s*From: .*",  # Forward headers with spacing
                r"^\s*Sent: .*",
                r"^\s*To: .*",
                r"^\s*Subject: .*",
                r"^\s*Date: .*",
                # Gmail-style patterns
                r"^\s*On .* <.*@.*> wrote:.*",  # Gmail "On [date] <email> wrote:"
                r"^\d{4}-\d{2}-\d{2} \d{2}:\d{2} GMT.*wrote:.*",  # Gmail timestamp format
                # Apple Mail patterns
                r"^Begin forwarded message:.*",  # Apple Mail forward
                r"^Forwarded message:.*",
                r"^Message forwarded.*",
                # Other common patterns
                r"^\s*\[.*\] wrote:.*",  # [Name] wrote:
                r"^\s*<.*@.*> wrote:.*",  # <email@domain.com> wrote:
                r'^\s*".*" <.*@.*> wrote:.*',  # "Name" <email> wrote:
                # Signature separators
                r"^\s*--\s*$",  # Standard signature separator
                r"^\s*---+\s*$",  # Dash separators
                # Mobile email patterns
                r"^Sent from my .*",  # "Sent from my iPhone/Android"
                r"^Get Outlook for .*",  # Outlook mobile signature
                # International patterns
                r".*\s+schrieb:.*",  # German "wrote"
                r".*\s+escribió:.*",  # Spanish "wrote"
                r".*\s+écrit:.*",  # French "wrote"
                r".*\s+scrisse:.*",  # Italian "wrote"
            ]

            # Compile patterns for efficiency
            compiled_patterns = [re.compile(pattern, re.IGNORECASE) for pattern in quote_patterns]

            # Additional patterns to detect start of quoted sections
            quote_start_patterns = [
                re.compile(r"^\s*[-=_]{3,}\s*$"),  # Lines with multiple dashes/equals/underscores
                re.compile(r"^\s*\*{3,}\s*$"),  # Lines with multiple asterisks
                re.compile(r"^\s*#{3,}\s*$"),  # Lines with multiple hash symbols
            ]

            in_quoted_section = False
            consecutive_empty_lines = 0

            for i, line in enumerate(lines):
                # Check if this line starts a quoted section
                is_quote_line = any(pattern.match(line) for pattern in compiled_patterns)
                is_separator_line = any(pattern.match(line) for pattern in quote_start_patterns)

                # Track consecutive empty lines
                if not line.strip():
                    consecutive_empty_lines += 1
                else:
                    consecutive_empty_lines = 0

                # Start quoted section if we hit a quote pattern or separator
                if is_quote_line or is_separator_line:
                    in_quoted_section = True
                    continue

                # Handle quoted section logic
                if in_quoted_section:
                    # If we hit multiple empty lines, we might be out of the quoted section
                    if consecutive_empty_lines >= 1:  # Reduced from 2 to 1 for better detection
                        # Look ahead to see if the next non-empty line looks like original content
                        next_content_line = None
                        for j in range(i + 1, len(lines)):
                            if lines[j].strip():
                                next_content_line = lines[j]
                                break

                        if next_content_line:
                            # Check if the next line looks like original content
                            is_next_quote = any(
                                pattern.match(next_content_line) for pattern in compiled_patterns
                            )
                            if (
                                not is_next_quote and len(next_content_line.strip()) > 5
                            ):  # Reduced threshold
                                # Looks like we're back to original content
                                in_quoted_section = False

                    # If we're still in quoted section, check if this line should be kept
                    if in_quoted_section:
                        # Check if this line looks like original content
                        if (
                            line.strip()
                            and len(line.strip()) > 10
                            and not any(pattern.match(line) for pattern in compiled_patterns)
                            and not re.match(
                                r"^\s*(From|To|Subject|Date|Sent|Cc|Bcc):", line, re.IGNORECASE
                            )
                            and not line.strip().startswith(">")
                        ):  # Don't keep lines that start with >
                            # This might be original content mixed in, keep it
                            in_quoted_section = False
                        else:
                            continue

                # If we're not in a quoted section, keep the line
                if not in_quoted_section:
                    cleaned_lines.append(line)

            # Join lines and do a final cleanup pass
            result = "\n".join(cleaned_lines)

            # Remove any remaining quoted blocks that might have been missed
            # Look for patterns like "On ... wrote:" followed by indented content
            result = re.sub(
                r"\n\s*On\s+.*wrote:\s*\n(.*\n)*?(?=\n\S|\n*$)",
                "\n",
                result,
                flags=re.IGNORECASE | re.MULTILINE,
            )

            # Remove forwarded message blocks
            result = re.sub(
                r"\n\s*-+\s*Forwarded message\s*-+.*?\n(.*\n)*?(?=\n\S|\n*$)",
                "\n",
                result,
                flags=re.IGNORECASE | re.MULTILINE,
            )

            return result

        except Exception as e:
            print(f"Warning: Error stripping quoted replies: {str(e)}")
            return content

    def strip_opening_greetings(self, content: str) -> str:
        """
        Strip opening greetings from email content.

        Args:
            content: Email content to clean

        Returns:
            str: Content with opening greetings removed
        """
        if not content:
            return ""

        try:
            lines = content.split("\n")
            cleaned_lines = []
            greeting_found = False

            # Patterns for opening greetings - more precise patterns
            greeting_patterns = [
                # Standard greetings with names (ensure they end the line after name/punctuation)
                r"^(Hi|Hello|Hey|Dear)\s+[A-Za-z][A-Za-z\s\'.-]*[,:]?\s*$",  # Hi Krishna, Hello Ben, Dear Raina
                # Formal greetings
                r"^Dear\s+(Sir|Madam|Sir\s+or\s+Madam)[,:]?\s*$",  # Dear Sir or Madam
                r"^To\s+whom\s+it\s+may\s+concern[,:]?\s*$",  # To whom it may concern
                # Group greetings
                r"^(Hi|Hello|Hey)\s+(all|everyone|team|folks|guys)[,:]?\s*$",  # Hi all, Hello everyone
                r"^(Hi|Hello|Hey)\s+there[,:!.]?\s*$",  # Hi there
                # Time-based greetings
                r"^(Good\s+morning|Good\s+afternoon|Good\s+evening)[,:]?\s*$",
                r"^(Good\s+morning|Good\s+afternoon|Good\s+evening)\s+[A-Za-z][A-Za-z\s\'.-]*[,:]?\s*$",
                # Simple greetings
                r"^(Hi|Hello|Hey)[,:]?\s*$",  # Just "Hi," or "Hello"
                # Multiple name greetings
                r"^(Hi|Hello|Hey|Dear)\s+[A-Za-z][A-Za-z\s\'.-]*(\s+and\s+[A-Za-z][A-Za-z\s\'.-]*)+[,:]?\s*$",  # Hi John and Jane
            ]

            # Compile patterns for efficiency
            compiled_greeting_patterns = [
                re.compile(pattern, re.IGNORECASE) for pattern in greeting_patterns
            ]

            # Process lines and remove greeting lines at the very beginning only
            for i, line in enumerate(lines):
                line_stripped = line.strip()

                # Only check for greetings in the first few non-empty lines
                if i < 3 and line_stripped:  # Only check first 3 non-empty lines for greetings
                    is_greeting = any(
                        pattern.match(line_stripped) for pattern in compiled_greeting_patterns
                    )
                    if is_greeting:
                        greeting_found = True
                        continue  # Skip greeting lines
                    elif greeting_found:
                        # If we already found a greeting and this line is not a greeting,
                        # we're done with greeting removal
                        pass

                # Keep all other lines
                cleaned_lines.append(line)

            return "\n".join(cleaned_lines)

        except Exception as e:
            print(f"Warning: Error stripping opening greetings: {str(e)}")
            return content

    def strip_signatures(self, content: str) -> str:
        """
        Strip signatures from email content, including Kevin Lin's specific signature.

        Args:
            content: Email content to clean

        Returns:
            str: Content with signatures removed
        """
        if not content:
            return ""

        try:
            lines = content.split("\n")
            cleaned_lines = []

            # Patterns for signature detection
            signature_patterns = [
                # Kevin Lin's specific signature patterns
                r"^(Best\s+regards|Sincerely\s+yours|Regards|Sincerely)[,:]?\s*$",
                r"^Kevin\s+Lin\s*$",
                r"^Lin\s+Yun\s*$",
                # Common signature closings
                r"^(Best|Regards|Thanks|Thank\s+you|Cheers|Yours\s+truly|Yours\s+sincerely)[,:]?\s*$",
                r"^(Kind\s+regards|Warm\s+regards|With\s+regards)[,:]?\s*$",
                r"^(Best\s+wishes|Many\s+thanks|Thank\s+you\s+very\s+much)[,:]?\s*$",
                # Signature separators
                r"^\s*--\s*$",  # Standard signature separator
                r"^\s*---+\s*$",  # Multiple dashes
                r"^\s*_{3,}\s*$",  # Multiple underscores
                # Mobile signatures
                r"^Sent\s+from\s+my\s+.*$",  # Sent from my iPhone/Android
                r"^Get\s+Outlook\s+for\s+.*$",  # Get Outlook for iOS/Android
                # Name-like patterns (common names that might be signatures)
                r"^[A-Z][a-z]+\s+[A-Z][a-z]+\s*$",  # First Last
                r"^[A-Z][a-z]+\s+[A-Z]\.\s+[A-Z][a-z]+\s*$",  # First M. Last
                r"^[A-Z]\.\s+[A-Z][a-z]+\s*$",  # F. Last
            ]

            # Compile patterns for efficiency
            compiled_signature_patterns = [
                re.compile(pattern, re.IGNORECASE) for pattern in signature_patterns
            ]

            # Work backwards from the end to detect signature blocks
            signature_start_index = len(lines)

            # Look for signature patterns starting from the end
            for i in range(len(lines) - 1, -1, -1):
                line = lines[i].strip()

                # Skip empty lines
                if not line:
                    continue

                # Check if this line matches a signature pattern
                is_signature_line = any(
                    pattern.match(line) for pattern in compiled_signature_patterns
                )

                if is_signature_line:
                    # Found a signature line, mark this as potential signature start
                    signature_start_index = i

                    # Look for preceding signature lines (like "Best regards" followed by "Kevin Lin")
                    # Continue checking previous lines for related signature content
                    for j in range(i - 1, max(0, i - 5), -1):  # Check up to 5 lines before
                        prev_line = lines[j].strip()
                        if not prev_line:
                            continue  # Skip empty lines

                        # Check if previous line is also part of signature
                        is_prev_signature = any(
                            pattern.match(prev_line) for pattern in compiled_signature_patterns
                        )
                        if is_prev_signature:
                            signature_start_index = j
                        else:
                            break  # Stop if we hit non-signature content

                    break  # Found signature block, stop searching
                else:
                    # If we hit substantial content (more than 10 words), stop looking for signatures
                    words = line.split()
                    if len(words) > 10:
                        break

            # Keep only lines before the signature
            cleaned_lines = lines[:signature_start_index]

            # Remove trailing empty lines
            while cleaned_lines and not cleaned_lines[-1].strip():
                cleaned_lines.pop()

            return "\n".join(cleaned_lines)

        except Exception as e:
            print(f"Warning: Error stripping signatures: {str(e)}")
            return content

    def normalize_whitespace(self, content: str) -> str:
        """
        Normalize whitespace and standardize line breaks, removing blank lines.

        Args:
            content: Content to normalize

        Returns:
            str: Content with normalized whitespace and blank lines removed
        """
        if not content:
            return ""

        try:
            # Replace different types of line breaks with standard \n
            content = re.sub(r"\r\n|\r", "\n", content)

            # Remove excessive whitespace while preserving paragraph structure
            # Replace multiple spaces with single space
            content = re.sub(r"[ \t]+", " ", content)

            # Remove leading/trailing whitespace from each line
            lines = content.split("\n")
            cleaned_lines = [line.strip() for line in lines]

            # Remove all blank lines as requested
            cleaned_lines = [line for line in cleaned_lines if line]

            # Join lines back together with single newlines
            content = "\n".join(cleaned_lines)

            return content

        except Exception as e:
            print(f"Warning: Error normalizing whitespace: {str(e)}")
            return content.strip() if content else ""

    def is_valid_content(self, content: str) -> bool:
        """
        Validate that content meets minimum quality requirements for meaningful email detection.

        Args:
            content: Content to validate

        Returns:
            bool: True if content is valid, False otherwise
        """
        if not content or not content.strip():
            return False

        try:
            # Clean content for analysis
            cleaned_content = content.strip()

            # Count words (split by whitespace and filter out empty strings)
            words = [word for word in cleaned_content.split() if word.strip()]
            word_count = len(words)

            # Requirement 3.1: minimum 20 words
            if word_count < 20:
                return False

            # Additional quality checks for meaningful content detection

            # Check if content is mostly non-alphabetic (might be encoded/corrupted)
            alpha_chars = sum(1 for c in cleaned_content if c.isalpha())
            total_chars = len(cleaned_content.replace(" ", "").replace("\n", "").replace("\t", ""))

            if total_chars > 0:
                alpha_ratio = alpha_chars / total_chars
                # Require at least 40% alphabetic characters (lowered from 50% to be less strict)
                if alpha_ratio < 0.4:
                    return False

            # Check for minimum sentence structure
            # Look for basic punctuation that indicates proper sentences
            sentence_endings = sum(1 for c in cleaned_content if c in ".!?")
            if sentence_endings == 0 and word_count > 50:
                # Long content without any sentence endings might be corrupted
                return False

            # Check for excessive repetition (might indicate spam or corrupted content)
            if word_count >= 10:
                # Count unique words vs total words
                unique_words = {
                    word.lower() for word in words if len(word) > 2
                }  # Ignore short words
                if len(unique_words) > 0:
                    uniqueness_ratio = len(unique_words) / len([w for w in words if len(w) > 2])
                    # If less than 30% of words are unique, might be spam or repetitive content
                    if uniqueness_ratio < 0.3:
                        return False

            # Check for common spam/system patterns in content
            spam_patterns = [
                r"click here",
                r"unsubscribe",
                r"viagra",
                r"casino",
                r"lottery",
                r"winner",
                r"congratulations.*won",
                r"urgent.*action.*required",
                r"verify.*account.*immediately",
            ]

            content_lower = cleaned_content.lower()
            spam_matches = sum(1 for pattern in spam_patterns if re.search(pattern, content_lower))

            # If multiple spam patterns match, likely not meaningful personal content
            if spam_matches >= 2:
                return False

            # Check for minimum content diversity
            # Content should have a mix of different word lengths
            if word_count >= 20:
                word_lengths = [len(word) for word in words]
                avg_word_length = sum(word_lengths) / len(word_lengths)

                # Very short average word length might indicate corrupted content
                if avg_word_length < 2.5:
                    return False

                # Very long average word length might indicate encoded content
                if avg_word_length > 15:
                    return False

            return True

        except Exception as e:
            print(f"Warning: Error validating content: {str(e)}")
            return False

    def is_system_generated(self, message: email.message.Message) -> bool:
        """
        Check if message appears to be system-generated (auto-replies, receipts, etc.).

        Args:
            message: Email message to check

        Returns:
            bool: True if message appears to be system-generated
        """
        try:
            # Check common system-generated message indicators
            subject = message.get("Subject", "").lower()

            # Enhanced system message patterns for comprehensive detection
            system_patterns = [
                # Auto-replies and out of office
                r"auto.?reply",
                r"automatic.*reply",
                r"out of office",
                r"vacation.*message",
                r"away.*message",
                r"absence.*notification",
                r"currently.*unavailable",
                # Delivery notifications and bounces
                r"delivery.*notification",
                r"delivery.*status.*notification",
                r"undelivered.*mail",
                r"mail.*delivery.*failed",
                r"message.*undeliverable",
                r"bounce.*message",
                r"returned.*mail",
                r"mail.*system.*error",
                # Read receipts and confirmations
                r"read.*receipt",
                r"delivery.*receipt",
                r"message.*receipt",
                r"confirmation.*receipt",
                # System daemons and postmaster
                r"mailer.?daemon",
                r"postmaster",
                r"mail.*administrator",
                # No-reply patterns
                r"no.?reply",
                r"do.?not.?reply",
                r"donot.*reply",
                # Calendar and meeting notifications
                r"meeting.*invitation",
                r"calendar.*notification",
                r"appointment.*reminder",
                r"event.*notification",
                # Security and system alerts
                r"security.*alert",
                r"password.*reset",
                r"account.*notification",
                r"system.*notification",
                r"service.*notification",
                # Subscription and newsletter patterns (only if combined with other indicators)
                # r'unsubscribe',  # Commented out as it's too broad
                # r'newsletter',   # Commented out as it's too broad
                # r'mailing.*list', # Commented out as it's too broad
                # Error messages
                r"error.*report",
                r"failure.*notification",
                r"warning.*message",
            ]

            # Check subject line against all patterns
            for pattern in system_patterns:
                if re.search(pattern, subject, re.IGNORECASE):
                    return True

            # Check sender/from field for system addresses
            from_field = message.get("From", "").lower()
            system_senders = [
                "mailer-daemon",
                "postmaster",
                "noreply",
                "no-reply",
                "donotreply",
                "do-not-reply",
                "bounce",
                "auto-reply",
                "autoreply",
                "system",
                "admin",
                "administrator",
                "notification",
                "alerts",
                "security",
                "support",
            ]

            for sender in system_senders:
                if sender in from_field:
                    return True

            # Check for auto-reply and system headers
            auto_reply_headers = [
                "X-Autoreply",
                "X-Autorespond",
                "Auto-Submitted",
                "X-Auto-Response-Suppress",
                "X-Mailer-Daemon",
                "X-Failed-Recipients",
                "X-Delivery-Status",
            ]

            for header in auto_reply_headers:
                header_value = message.get(header)
                # Special handling for Auto-Submitted header
                if header_value and (
                    (header == "Auto-Submitted" and header_value.lower() != "no")
                    or (header != "Auto-Submitted")
                ):
                    return True

            # Check message body for system-generated patterns
            try:
                # Get a sample of the message body to check for system patterns
                body_sample = ""
                if message.is_multipart():
                    for part in message.walk():
                        if part.get_content_type() == "text/plain":
                            payload = part.get_payload(decode=True)
                            if payload:
                                if isinstance(payload, bytes):
                                    charset = part.get_content_charset() or "utf-8"
                                    try:
                                        body_sample = payload.decode(charset)[
                                            :500
                                        ]  # First 500 chars
                                    except (UnicodeDecodeError, LookupError):
                                        body_sample = payload.decode("utf-8", errors="ignore")[:500]
                                break
                else:
                    payload = message.get_payload(decode=True)
                    if payload and isinstance(payload, bytes):
                        charset = message.get_content_charset() or "utf-8"
                        try:
                            body_sample = payload.decode(charset)[:500]
                        except (UnicodeDecodeError, LookupError):
                            body_sample = payload.decode("utf-8", errors="ignore")[:500]

                # Check body for system-generated content patterns
                if body_sample:
                    body_patterns = [
                        r"this.*is.*an.*automatic.*message",
                        r"do.*not.*reply.*to.*this.*message",
                        r"this.*message.*was.*automatically.*generated",
                        r"undelivered.*mail.*returned.*to.*sender",
                        r"delivery.*status.*notification",
                        r"out.*of.*office.*auto.*reply",
                    ]

                    for pattern in body_patterns:
                        if re.search(pattern, body_sample.lower(), re.IGNORECASE):
                            return True

            except Exception:
                # If body checking fails, continue with other checks
                pass

            return False

        except Exception as e:
            print(f"Warning: Error checking if message is system-generated: {str(e)}")
            return False

    def hash_content(self, content: str) -> str:
        """
        Generate a SHA-256 hash of normalized content for duplicate detection.

        Args:
            content: Content to hash

        Returns:
            str: SHA-256 hash of the content
        """
        if not content:
            return ""

        try:
            # Normalize content before hashing to ensure consistent comparison
            normalized_content = self.normalize_whitespace(content)

            # Convert to lowercase and remove extra whitespace for better duplicate detection
            # This helps catch duplicates that might have minor formatting differences
            content_for_hashing = re.sub(r"\s+", " ", normalized_content.lower().strip())

            # Check if content is empty after normalization
            if not content_for_hashing:
                return ""

            # Generate SHA-256 hash
            content_bytes = content_for_hashing.encode("utf-8")
            hash_object = hashlib.sha256(content_bytes)
            content_hash = hash_object.hexdigest()

            return content_hash

        except Exception as e:
            print(f"Warning: Error hashing content: {str(e)}")
            return ""

    def is_content_duplicate(self, content: str, existing_hashes: Set[str]) -> bool:
        """
        Check if content is a duplicate based on content hash comparison.

        Args:
            content: Content to check for duplication
            existing_hashes: Set of existing content hashes

        Returns:
            bool: True if content is a duplicate, False otherwise
        """
        if not content or not content.strip():
            return False

        try:
            content_hash = self.hash_content(content)

            if not content_hash:
                return False

            return content_hash in existing_hashes

        except Exception as e:
            print(f"Warning: Error checking content duplicate: {str(e)}")
            return False

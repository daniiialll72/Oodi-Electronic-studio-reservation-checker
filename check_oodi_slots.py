#!/usr/bin/env python3
"""
Oodi Electronic Studio Reservation Checker
Checks available reservation slots for electronic studios at Oodi library in Helsinki.
Uses GraphQL API to fetch reservation data from Varaamo.
"""

import requests
from datetime import datetime, timedelta, timezone
from typing import List, Dict, Optional
import json
import sys
import time
import subprocess
import platform
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
import os


class OodiReservationChecker:
    """Check available reservation slots at Oodi library using GraphQL API."""
    
    # Known electronic studio resource IDs at Oodi
    ELECTRONIC_STUDIO_IDS = [193]  # Add more IDs as discovered
    
    # GraphQL endpoint
    GRAPHQL_ENDPOINT = 'https://varaamo.hel.fi/graphql/'
    
    def __init__(self, telegram_bot_token: Optional[str] = None, telegram_chat_id: Optional[str] = None,
                 telegram_chat_ids: Optional[List[str]] = None,
                 email_smtp_server: Optional[str] = None, email_smtp_port: Optional[int] = None,
                 email_username: Optional[str] = None, email_password: Optional[str] = None,
                 email_to: Optional[str] = None, email_to_list: Optional[List[str]] = None):
        """
        Initialize the checker with a requests session and notification settings.
        
        Args:
            telegram_bot_token: Telegram bot token (get from @BotFather)
            telegram_chat_id: Single Telegram chat ID (for backward compatibility)
            telegram_chat_ids: List of Telegram chat IDs to send notifications to
            email_smtp_server: SMTP server for email (e.g., 'smtp.gmail.com')
            email_smtp_port: SMTP port (e.g., 587 for TLS)
            email_username: Email username for SMTP authentication
            email_password: Email password or app password
            email_to: Single email address (for backward compatibility)
            email_to_list: List of email addresses to send notifications to
        """
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
        })
        
        # Notification settings
        self.telegram_bot_token = telegram_bot_token or os.getenv('TELEGRAM_BOT_TOKEN')
        
        # Support both single chat_id and list of chat_ids
        if telegram_chat_ids:
            self.telegram_chat_ids = telegram_chat_ids
        elif telegram_chat_id:
            self.telegram_chat_ids = [telegram_chat_id]
        else:
            # Try to parse from env var (can be comma-separated)
            chat_id_env = os.getenv('TELEGRAM_CHAT_ID', '')
            if chat_id_env:
                self.telegram_chat_ids = [cid.strip() for cid in chat_id_env.split(',') if cid.strip()]
            else:
                self.telegram_chat_ids = []
        
        self.email_smtp_server = email_smtp_server or os.getenv('EMAIL_SMTP_SERVER')
        self.email_smtp_port = email_smtp_port or int(os.getenv('EMAIL_SMTP_PORT', '0') or '0')
        self.email_username = email_username or os.getenv('EMAIL_USERNAME')
        self.email_password = email_password or os.getenv('EMAIL_PASSWORD')
        
        # Support both single email and list of emails
        if email_to_list:
            self.email_to_list = email_to_list
        elif email_to:
            self.email_to_list = [email_to]
        else:
            # Try to parse from env var (can be comma-separated)
            email_to_env = os.getenv('EMAIL_TO', '')
            if email_to_env:
                self.email_to_list = [email.strip() for email in email_to_env.split(',') if email.strip()]
            else:
                self.email_to_list = []
    
    def _get_csrf_token(self) -> Optional[str]:
        """
        Get CSRF token from the Varaamo website (required for GraphQL requests).
        
        Returns:
            CSRF token string or None if not found
        """
        try:
            url = 'https://varaamo.hel.fi/en/reservation-unit/193'
            response = self.session.get(url, timeout=10)
            response.raise_for_status()
            
            # Look for CSRF token in cookies
            csrf_token = self.session.cookies.get('csrftoken') or self.session.cookies.get('csrf_token')
            if csrf_token:
                return csrf_token
        except Exception:
            pass
        
        return None
    
    def get_reservations_via_graphql(self, resource_id: str, date: Optional[datetime] = None) -> List[Dict]:
        """
        Get reservations for a resource using GraphQL API.
        
        Args:
            resource_id: The resource ID to check
            date: The date to check (defaults to today)
        
        Returns:
            List of reservation dictionaries with beginsAt, endsAt, and affectedReservationUnits
        """
        if date is None:
            date = datetime.now()
        
        # Calculate date range (today to 2 years ahead for the query)
        begin_date = date.strftime('%Y-%m-%d')
        end_date_str = (date + timedelta(days=730)).strftime('%Y-%m-%d')
        
        # Get CSRF token
        csrf_token = self._get_csrf_token()
        
        headers = {
            'Content-Type': 'application/json',
            'Accept': '*/*',
            'Accept-Language': 'en-US,en;q=0.9',
            'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Referer': f'https://varaamo.hel.fi/en/reservation-unit/{resource_id}',
            'Origin': 'https://varaamo.hel.fi',
        }
        
        if csrf_token:
            headers['X-CSRFToken'] = csrf_token
            headers['X-CSRF-Token'] = csrf_token
        
        # GraphQL query for affecting reservations
        query = {
            "operationName": "AffectingReservations",
            "query": """
                query AffectingReservations($pk: Int!, $beginDate: Date!, $endDate: Date!, $state: [ReservationStateChoice]) {
                    affectingReservations(
                        forReservationUnits: [$pk]
                        beginDate: $beginDate
                        endDate: $endDate
                        state: $state
                    ) {
                        pk
                        id
                        state
                        isBlocked
                        beginsAt
                        endsAt
                        numPersons
                        bufferTimeBefore
                        bufferTimeAfter
                        affectedReservationUnits
                        __typename
                    }
                }
            """,
            "variables": {
                "pk": int(resource_id),
                "beginDate": begin_date,
                "endDate": end_date_str,
                "state": ["CREATED", "CONFIRMED", "REQUIRES_HANDLING", "WAITING_FOR_PAYMENT"]
            }
        }
        
        try:
            response = self.session.post(self.GRAPHQL_ENDPOINT, json=query, headers=headers, timeout=10)
            if response.status_code == 200:
                data = response.json()
                if 'data' in data:
                    reservations = data['data'].get('affectingReservations', [])
                    
                    if reservations:
                        print(f"  ✓ Found {len(reservations)} reservations via GraphQL")
                        
                        # Filter reservations for today and ensure they affect this resource
                        today_str = date.strftime('%Y-%m-%d')
                        filtered = []
                        resource_id_int = int(resource_id)
                        
                        for res in reservations:
                            begins_at = res.get('beginsAt')
                            
                            # Check if reservation is for today
                            if begins_at and today_str in str(begins_at):
                                # Verify this reservation affects our resource
                                affected_units = res.get('affectedReservationUnits', [])
                                if resource_id_int in affected_units:
                                    filtered.append(res)
                        
                        if filtered:
                            print(f"  Filtered to {len(filtered)} reservations for today affecting resource {resource_id}")
                            return filtered
                        return reservations
                elif 'errors' in data:
                    print(f"  ✗ GraphQL errors: {data['errors']}", file=sys.stderr)
        except requests.exceptions.RequestException as e:
            print(f"  ✗ GraphQL request failed: {e}", file=sys.stderr)
        except (ValueError, json.JSONDecodeError, KeyError) as e:
            print(f"  ✗ Failed to parse GraphQL response: {e}", file=sys.stderr)
        
        return []
    
    def get_reservations(self, resource_id: str, date: Optional[datetime] = None) -> List[Dict]:
        """
        Get reservations for a specific resource on a given date.
        
        Args:
            resource_id: The resource ID to check
            date: The date to check (defaults to today)
        
        Returns:
            List of reservation dictionaries
        """
        return self.get_reservations_via_graphql(resource_id, date)
    
    def _get_working_hours(self, date: datetime) -> tuple:
        """
        Get working hours for a specific day.
        
        Args:
            date: The date to check
        
        Returns:
            Tuple of (start_hour, start_minute, end_hour, end_minute)
        """
        weekday = date.weekday()  # 0=Monday, 6=Sunday
        
        if weekday == 0:  # Monday
            return (16, 0, 20, 0)  # 4pm - 8pm
        elif weekday in [1, 2, 3, 4]:  # Tuesday to Friday
            return (8, 0, 20, 30)  # 8am - 8:30pm
        else:  # Saturday (5) and Sunday (6)
            return (10, 0, 19, 30)  # 10am - 7:30pm
    
    def calculate_available_slots(
        self, 
        reservations: List[Dict], 
        date: Optional[datetime] = None,
        min_duration_hours: float = 1.0,
        max_duration_hours: float = 4.0
    ) -> List[Dict]:
        """
        Calculate available time slots based on reservations with constraints.
        
        Args:
            reservations: List of reservation dictionaries
            date: The date to check (defaults to today, used for working hours)
            min_duration_hours: Minimum reservation duration in hours (default 1.0)
            max_duration_hours: Maximum reservation duration in hours (default 4.0)
        
        Returns:
            List of available time slot dictionaries that can accommodate min-max duration
        """
        if date is None:
            date = datetime.now()
        
        # Get working hours for this day
        start_hour, start_min, end_hour, end_min = self._get_working_hours(date)
        
        # Parse reservations into time ranges
        reserved_ranges = []
        for res in reservations:
            try:
                # GraphQL uses beginsAt and endsAt
                begin_str = res.get('beginsAt')
                end_str = res.get('endsAt')
                
                if begin_str and end_str:
                    try:
                        # Parse ISO format with timezone
                        begin_iso = str(begin_str).replace('Z', '+00:00')
                        end_iso = str(end_str).replace('Z', '+00:00')
                        
                        # Parse as timezone-aware datetime
                        begin = datetime.fromisoformat(begin_iso)
                        end = datetime.fromisoformat(end_iso)
                        
                        # Convert UTC to Helsinki time (UTC+2)
                        helsinki_offset = timedelta(hours=2)
                        begin_local = begin.replace(tzinfo=timezone.utc) + helsinki_offset
                        end_local = end.replace(tzinfo=timezone.utc) + helsinki_offset
                        
                        # Remove timezone info for comparison
                        begin_local = begin_local.replace(tzinfo=None)
                        end_local = end_local.replace(tzinfo=None)
                        
                        reserved_ranges.append((begin_local, end_local))
                    except (ValueError, AttributeError) as e:
                        continue
            except (KeyError, ValueError, AttributeError):
                continue
        
        # Sort by start time
        reserved_ranges.sort(key=lambda x: x[0])
        
        # Generate working hours for this day
        target_date = date.replace(hour=0, minute=0, second=0, microsecond=0)
        work_start = target_date.replace(hour=start_hour, minute=start_min)
        work_end = target_date.replace(hour=end_hour, minute=end_min)
        
        # Convert min/max duration to minutes
        min_duration_minutes = int(min_duration_hours * 60)
        max_duration_minutes = int(max_duration_hours * 60)
        
        available_slots = []
        
        # Check for available time windows that can accommodate min-max duration
        current_time = work_start
        
        while current_time < work_end:
            # Check if current_time is within a reservation
            is_in_reservation = False
            for res_start, res_end in reserved_ranges:
                if res_start <= current_time < res_end:
                    # We're in a reservation, move to the end of it
                    current_time = res_end
                    is_in_reservation = True
                    break
            
            if is_in_reservation:
                continue
            
            # Check how much free time we have from current_time
            # Find the next reservation or end of working hours
            next_reservation_start = work_end
            for res_start, res_end in reserved_ranges:
                if res_start > current_time:
                    next_reservation_start = min(next_reservation_start, res_start)
            
            available_until = min(next_reservation_start, work_end)
            available_duration_minutes = (available_until - current_time).total_seconds() / 60
            
            # Check if we can fit at least the minimum duration
            if available_duration_minutes >= min_duration_minutes:
                # We can offer slots starting from current_time
                slot_start = current_time
                
                # Generate slots: start time + duration combinations
                # Duration can be from min_duration to max_duration (in 30-min steps)
                for duration_minutes in range(min_duration_minutes, max_duration_minutes + 1, 30):
                    slot_end = slot_start + timedelta(minutes=duration_minutes)
                    
                    # Check if this slot fits within available time and doesn't overlap reservations
                    if slot_end <= available_until:
                        # Verify it doesn't overlap with any reservation
                        overlaps = False
                        for res_start, res_end in reserved_ranges:
                            if not (slot_end <= res_start or slot_start >= res_end):
                                overlaps = True
                                break
                        
                        if not overlaps:
                            # Add this as an available slot
                            available_slots.append({
                                'start': slot_start,
                                'end': slot_end,
                                'duration_minutes': duration_minutes,
                                'duration_hours': duration_minutes / 60.0
                            })
                
                # Move to next potential start time (30-minute increments)
                current_time = slot_start + timedelta(minutes=30)
            else:
                # Not enough time, move forward
                current_time = available_until
        
        # Remove duplicates and sort
        # Group by start time and keep the longest duration option
        slots_by_start = {}
        for slot in available_slots:
            start_key = slot['start']
            if start_key not in slots_by_start or slot['duration_minutes'] > slots_by_start[start_key]['duration_minutes']:
                slots_by_start[start_key] = slot
        
        available_slots = sorted(slots_by_start.values(), key=lambda x: x['start'])
        
        # Filter out past time slots
        # If checking today, remove slots that have already passed
        now = datetime.now()
        today = now.replace(hour=0, minute=0, second=0, microsecond=0)
        check_date_start = date.replace(hour=0, minute=0, second=0, microsecond=0)
        
        if check_date_start == today:
            # Only filter if we're checking today
            filtered_slots = []
            for slot in available_slots:
                if slot['start'] >= now:
                    filtered_slots.append(slot)
            available_slots = filtered_slots
        
        return available_slots
    
    def check_available_slots_today(
        self, 
        resource_name_filter: Optional[str] = None,
        resource_type: Optional[str] = None,
        electronic_studio_only: bool = True,
        date: Optional[datetime] = None
    ) -> Dict:
        """
        Check available slots for electronic studios today.
        
        Args:
            resource_name_filter: Optional filter for resource names
            resource_type: Optional filter for resource types
            electronic_studio_only: If True, only fetch electronic studios (default: True)
            date: Optional date to check (defaults to today)
        
        Returns:
            Dictionary with resource information and available slots
        """
        print("Fetching reservation data from Varaamo...")
        print("Using GraphQL API to get accurate reservation data.\n")
        
        if date is None:
            date = datetime.now()
        
        # Build resources list from known IDs
        if electronic_studio_only and self.ELECTRONIC_STUDIO_IDS:
            resources = []
            for resource_id in self.ELECTRONIC_STUDIO_IDS:
                # Create basic resource info (name can be fetched from GraphQL if needed)
                resource = {
                    'id': str(resource_id),
                    'name': f'Electronic Studio {resource_id}',
                    'description': ''
                }
                resources.append(resource)
            
            if resources:
                print(f"Found {len(resources)} electronic studio resources")
            else:
                print("No resources found.")
                return {}
        else:
            print("Error: Resource IDs must be specified. Use ELECTRONIC_STUDIO_IDS in the script.")
            return {}
        
        # Filter resources if needed
        if resource_name_filter:
            resources = [
                r for r in resources 
                if resource_name_filter.lower() in r.get('name', '').lower()
            ]
            print(f"Filtered to {len(resources)} resources matching '{resource_name_filter}'")
        
        if resource_type:
            resources = [
                r for r in resources 
                if resource_type.lower() in r.get('type', '').lower()
            ]
            print(f"Filtered to {len(resources)} resources of type '{resource_type}'")
        
        results = {}
        print(f"\nChecking available slots for {date.strftime('%Y-%m-%d')}...\n")
        
        for resource in resources:
            resource_id = resource.get('id')
            resource_name = resource.get('name', 'Unknown')
            
            if not resource_id:
                continue
            
            print(f"Checking: {resource_name}...", end=' ')
            sys.stdout.flush()
            
            reservations = self.get_reservations(resource_id, date)
            available_slots = self.calculate_available_slots(reservations, date=date, min_duration_hours=1.0, max_duration_hours=4.0)
            
            results[resource_name] = {
                'resource_id': resource_id,
                'resource_info': resource,
                'reservations': reservations,
                'available_slots': available_slots,
                'total_available_slots': len(available_slots)
            }
            
            print(f"{len(available_slots)} available slots")
        
        return results
    
    def print_results(self, results: Dict, date: Optional[datetime] = None):
        """Print formatted results to console."""
        if not results:
            print("No results to display.")
            return
        
        if date is None:
            date = datetime.now()
        
        date_str = date.strftime('%Y-%m-%d')
        today_str = datetime.now().strftime('%Y-%m-%d')
        
        # Determine if it's today or another date
        if date_str == today_str:
            date_label = "TODAY"
        else:
            weekday = date.strftime('%A')
            date_label = f"{date_str} ({weekday})"
        
        print("\n" + "="*80)
        print(f"OODI ELECTRONIC STUDIO RESERVATION STATUS - {date_label}")
        print("="*80 + "\n")
        
        for resource_name, data in results.items():
            print(f"📚 {resource_name}")
            print(f"   Resource ID: {data['resource_id']}")
            
            available_slots = data['available_slots']
            reservations = data['reservations']
            
            if date_str == today_str:
                print(f"   Total Reservations Today: {len(reservations)}")
            else:
                print(f"   Total Reservations on {date_str}: {len(reservations)}")
            print(f"   Available Slots: {len(available_slots)}")
            
            if available_slots:
                print("\n   Available Time Slots:")
                for slot in available_slots:
                    start_str = slot['start'].strftime('%H:%M')
                    end_str = slot['end'].strftime('%H:%M')
                    duration_str = f"{slot.get('duration_hours', slot['duration_minutes']/60):.1f}h"
                    print(f"      ✓ {start_str} - {end_str} ({duration_str})")
            else:
                if date_str == today_str:
                    print("   ⚠️  No available slots for today")
                else:
                    print(f"   ⚠️  No available slots for {date_str}")
            
            if reservations:
                print("\n   Reserved Time Slots:")
                for res in reservations:
                    try:
                        begin_str = res.get('beginsAt')
                        end_str = res.get('endsAt')
                        if begin_str and end_str:
                            # Parse with timezone and convert to Helsinki time
                            begin_iso = str(begin_str).replace('Z', '+00:00')
                            end_iso = str(end_str).replace('Z', '+00:00')
                            begin = datetime.fromisoformat(begin_iso)
                            end = datetime.fromisoformat(end_iso)
                            
                            # Convert UTC to Helsinki time (UTC+2)
                            helsinki_offset = timedelta(hours=2)
                            begin_local = begin.replace(tzinfo=timezone.utc) + helsinki_offset
                            end_local = end.replace(tzinfo=timezone.utc) + helsinki_offset
                            begin_local = begin_local.replace(tzinfo=None)
                            end_local = end_local.replace(tzinfo=None)
                            
                            print(f"      ✗ {begin_local.strftime('%H:%M')} - {end_local.strftime('%H:%M')}")
                    except (KeyError, ValueError, AttributeError):
                        pass
            
            print("\n" + "-"*80 + "\n")
    
    def send_notification(self, title: str, message: str):
        """
        Send notifications via Telegram, Email, and/or system notification.
        Supports multiple recipients for both Telegram and Email.
        
        Args:
            title: Notification title
            message: Notification message
        """
        full_message = f"{title}\n\n{message}"
        sent = False
        
        # Send Telegram notifications to all chat IDs
        if self.telegram_bot_token and self.telegram_chat_ids:
            success_count = 0
            for chat_id in self.telegram_chat_ids:
                try:
                    url = f"https://api.telegram.org/bot{self.telegram_bot_token}/sendMessage"
                    payload = {
                        'chat_id': chat_id,
                        'text': full_message,
                        'parse_mode': 'HTML'
                    }
                    response = requests.post(url, json=payload, timeout=10)
                    if response.status_code == 200:
                        success_count += 1
                    else:
                        print(f"  ✗ Telegram notification failed for chat_id {chat_id}: {response.status_code}")
                except Exception as e:
                    print(f"  ✗ Telegram notification error for chat_id {chat_id}: {e}")
            
            if success_count > 0:
                print(f"  ✓ Telegram notification sent to {success_count}/{len(self.telegram_chat_ids)} recipient(s)")
                sent = True
        
        # Send Email notifications to all recipients
        if self.email_smtp_server and self.email_smtp_port and self.email_username and self.email_password and self.email_to_list:
            success_count = 0
            try:
                server = smtplib.SMTP(self.email_smtp_server, self.email_smtp_port)
                server.starttls()
                server.login(self.email_username, self.email_password)
                
                for email_to in self.email_to_list:
                    try:
                        msg = MIMEMultipart()
                        msg['From'] = self.email_username
                        msg['To'] = email_to
                        msg['Subject'] = title
                        msg.attach(MIMEText(message, 'plain'))
                        
                        server.send_message(msg)
                        success_count += 1
                    except Exception as e:
                        print(f"  ✗ Email notification error for {email_to}: {e}")
                
                server.quit()
                if success_count > 0:
                    print(f"  ✓ Email notification sent to {success_count}/{len(self.email_to_list)} recipient(s)")
                    sent = True
            except Exception as e:
                print(f"  ✗ Email server error: {e}")
        
        # Fallback: System notification
        if not sent:
            system = platform.system()
            if system == 'Darwin':  # macOS
                try:
                    script = f'''
                    display notification "{message}" with title "{title}" sound name "Glass"
                    '''
                    subprocess.run(['osascript', '-e', script], check=False)
                except Exception:
                    print(f"\n🔔 NOTIFICATION: {title}\n{message}\n")
            elif system == 'Linux':
                try:
                    subprocess.run(['notify-send', title, message], check=False)
                except Exception:
                    print(f"\n🔔 NOTIFICATION: {title}\n{message}\n")
            else:
                print(f"\n🔔 NOTIFICATION: {title}\n{message}\n")
    
    def monitor_availability(self, check_interval_minutes: int = 5, date: Optional[datetime] = None):
        """
        Monitor availability continuously and send notifications when slots become available.
        
        Args:
            check_interval_minutes: How often to check (in minutes, default 5)
            date: Date to monitor (None = always check today's date dynamically)
        """
        # If a specific date is provided, use it. Otherwise, check today's date dynamically
        use_dynamic_date = (date is None)
        
        if use_dynamic_date:
            print(f"🔍 Starting monitoring mode (checking today's date dynamically)")
        else:
            date_str = date.strftime('%Y-%m-%d')
            print(f"🔍 Starting monitoring mode for {date_str}")
        
        print(f"⏰ Checking every {check_interval_minutes} minutes...")
        print(f"🔔 Notifications will be sent when slots become available\n")
        print("Press Ctrl+C to stop monitoring\n")
        
        # Send a test notification to verify notifications are working
        print("📤 Sending test notification...")
        test_date_str = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        if use_dynamic_date:
            date_info = "checking today's date dynamically"
        else:
            date_info = f"monitoring {date.strftime('%Y-%m-%d')}"
        
        self.send_notification(
            "✅ Oodi Monitor Started",
            f"Monitoring started successfully!\n\nDate: {test_date_str}\nMode: {date_info}\nCheck interval: {check_interval_minutes} minutes\n\nYou will receive notifications when slots become available."
        )
        print("  ✓ Test notification sent\n")
        
        previous_slots = {}
        check_count = 0
        last_checked_date = None
        
        try:
            while True:
                check_count += 1
                current_time = datetime.now().strftime('%H:%M:%S')
                
                # Get the date to check (dynamic if use_dynamic_date is True)
                if use_dynamic_date:
                    check_date = datetime.now()
                    current_date_str = check_date.strftime('%Y-%m-%d')
                    
                    # If date changed, reset previous slots
                    if last_checked_date and last_checked_date != current_date_str:
                        print(f"\n📅 Date changed from {last_checked_date} to {current_date_str} - resetting state\n")
                        previous_slots = {}
                    
                    last_checked_date = current_date_str
                    print(f"[{current_time}] Check #{check_count} - Checking availability for {current_date_str}...")
                else:
                    check_date = date
                    print(f"[{current_time}] Check #{check_count} - Checking availability...")
                
                # Get current availability
                results = self.check_available_slots_today(
                    electronic_studio_only=True,
                    date=check_date
                )
                
                # Compare with previous state
                for resource_name, data in results.items():
                    resource_id = data['resource_id']
                    current_slots = data['available_slots']
                    num_slots = len(current_slots)
                    
                    # Get previous slots for this resource
                    prev_slots = previous_slots.get(resource_id, [])
                    prev_slot_starts = {slot['start'] for slot in prev_slots}
                    current_slot_starts = {slot['start'] for slot in current_slots}
                    
                    # Check if new slots appeared
                    new_slots = [slot for slot in current_slots if slot['start'] not in prev_slot_starts]
                    
                    if new_slots:
                        # New slots available!
                        slot_info = []
                        for slot in new_slots[:5]:  # Show first 5 new slots
                            start_str = slot['start'].strftime('%H:%M')
                            end_str = slot['end'].strftime('%H:%M')
                            duration_str = f"{slot.get('duration_hours', 0):.1f}h"
                            slot_info.append(f"{start_str}-{end_str} ({duration_str})")
                        
                        message = f"{resource_name} has {num_slots} available slot(s)!\n"
                        if len(new_slots) <= 5:
                            message += "\n".join(slot_info)
                        else:
                            message += "\n".join(slot_info) + f"\n... and {len(new_slots) - 5} more"
                        
                        self.send_notification(
                            "🎉 Slots Available!",
                            message
                        )
                        print(f"  ✓ {resource_name}: {num_slots} slots available ({len(new_slots)} new)")
                    elif num_slots > 0:
                        print(f"  • {resource_name}: {num_slots} slots available (no change)")
                    else:
                        print(f"  ✗ {resource_name}: No slots available")
                    
                    # Update previous state
                    previous_slots[resource_id] = current_slots
                
                # Wait before next check
                if check_count == 1:
                    print(f"\n⏳ Waiting {check_interval_minutes} minutes until next check...\n")
                else:
                    print(f"\n⏳ Next check in {check_interval_minutes} minutes...\n")
                
                time.sleep(check_interval_minutes * 60)
                
        except KeyboardInterrupt:
            print("\n\n🛑 Monitoring stopped by user")
            sys.exit(0)


def main():
    """Main entry point."""
    import argparse
    
    parser = argparse.ArgumentParser(
        description='Check available reservation slots for electronic studios at Oodi library'
    )
    parser.add_argument(
        '--filter',
        type=str,
        help='Additional filter for resources by name (e.g., "studio", "electronic")'
    )
    parser.add_argument(
        '--type',
        type=str,
        help='Filter resources by type'
    )
    parser.add_argument(
        '--all-resources',
        action='store_true',
        help='Check all resources instead of just electronic studios'
    )
    parser.add_argument(
        '--json',
        action='store_true',
        help='Output results as JSON'
    )
    parser.add_argument(
        '--date',
        type=str,
        help='Date to check (format: YYYY-MM-DD). Defaults to today. Example: --date 2026-01-24'
    )
    parser.add_argument(
        '--monitor',
        action='store_true',
        help='Enable monitoring mode: continuously check for available slots and send notifications'
    )
    parser.add_argument(
        '--interval',
        type=int,
        default=5,
        help='Monitoring interval in minutes (default: 5). Only used with --monitor'
    )
    parser.add_argument(
        '--telegram-token',
        type=str,
        dest='telegram_token',
        help='Telegram bot token (or set TELEGRAM_BOT_TOKEN env var)'
    )
    parser.add_argument(
        '--telegram-chat-id',
        type=str,
        dest='telegram_chat_id',
        action='append',
        help='Telegram chat ID (can be used multiple times for multiple recipients, or set TELEGRAM_CHAT_ID env var as comma-separated list)'
    )
    parser.add_argument(
        '--email-smtp-server',
        type=str,
        dest='email_smtp_server',
        help='SMTP server for email (e.g., smtp.gmail.com) or set EMAIL_SMTP_SERVER env var'
    )
    parser.add_argument(
        '--email-smtp-port',
        type=int,
        dest='email_smtp_port',
        help='SMTP port (e.g., 587) or set EMAIL_SMTP_PORT env var'
    )
    parser.add_argument(
        '--email-username',
        type=str,
        dest='email_username',
        help='Email username for SMTP or set EMAIL_USERNAME env var'
    )
    parser.add_argument(
        '--email-password',
        type=str,
        dest='email_password',
        help='Email password/app password or set EMAIL_PASSWORD env var'
    )
    parser.add_argument(
        '--email-to',
        type=str,
        dest='email_to',
        action='append',
        help='Email address to send notifications to (can be used multiple times for multiple recipients, or set EMAIL_TO env var as comma-separated list)'
    )
    
    args = parser.parse_args()
    
    # Parse date if provided
    check_date = None
    if args.date:
        try:
            check_date = datetime.strptime(args.date, '%Y-%m-%d')
        except ValueError:
            print(f"Error: Invalid date format '{args.date}'. Use YYYY-MM-DD format (e.g., 2026-01-24)", file=sys.stderr)
            sys.exit(1)
    
    checker = OodiReservationChecker(
        telegram_bot_token=args.telegram_token,
        telegram_chat_id=args.telegram_chat_id[0] if args.telegram_chat_id and len(args.telegram_chat_id) == 1 else None,
        telegram_chat_ids=args.telegram_chat_id if args.telegram_chat_id else None,
        email_smtp_server=args.email_smtp_server,
        email_smtp_port=args.email_smtp_port,
        email_username=args.email_username,
        email_password=args.email_password,
        email_to=args.email_to[0] if args.email_to and len(args.email_to) == 1 else None,
        email_to_list=args.email_to if args.email_to else None
    )
    
    # If monitoring mode, run the monitor function
    if args.monitor:
        checker.monitor_availability(
            check_interval_minutes=args.interval,
            date=check_date
        )
        return
    
    # Otherwise, run normal check
    results = checker.check_available_slots_today(
        resource_name_filter=args.filter,
        resource_type=args.type,
        electronic_studio_only=not args.all_resources,
        date=check_date
    )
    
    if args.json:
        # Convert datetime objects to strings for JSON serialization
        json_results = {}
        for name, data in results.items():
            json_results[name] = {
                'resource_id': data['resource_id'],
                'total_available_slots': data['total_available_slots'],
                'available_slots': [
                    {
                        'start': slot['start'].isoformat(),
                        'end': slot['end'].isoformat(),
                        'duration_minutes': slot['duration_minutes']
                    }
                    for slot in data['available_slots']
                ],
                'reservations_count': len(data['reservations'])
            }
        print(json.dumps(json_results, indent=2))
    else:
        checker.print_results(results, date=check_date)


if __name__ == '__main__':
    main()

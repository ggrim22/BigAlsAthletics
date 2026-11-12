"""
Tests for order timestamp display.

Django's default TIME_ZONE is America/Chicago, which rendered every order an
hour behind local time. The shop is in New Castle, Indiana (Eastern).
"""
import datetime
import zoneinfo

import pytest
from django.conf import settings
from django.urls import reverse
from django.utils import timezone

from order.models import Order

EASTERN = zoneinfo.ZoneInfo("America/Indiana/Indianapolis")


@pytest.fixture
def authenticated_client(client, admin_user):
    client.force_login(admin_user)
    return client


class TestTimeZoneConfiguration:

    def test_timezone_is_eastern_indiana(self):
        assert settings.TIME_ZONE == "America/Indiana/Indianapolis"

    def test_timestamps_are_stored_timezone_aware(self):
        assert settings.USE_TZ is True

    def test_not_a_fixed_offset(self):
        """A fixed offset such as "EST" would be an hour off all summer"""
        assert settings.TIME_ZONE not in ("EST", "EDT", "UTC")

    @pytest.mark.parametrize(
        "utc_moment,expected_local",
        [
            # Standard time (winter): Eastern is UTC-5
            (datetime.datetime(2026, 1, 15, 20, 30, tzinfo=datetime.timezone.utc), "03:30 PM"),
            # Daylight time (summer): Eastern is UTC-4
            (datetime.datetime(2026, 7, 15, 20, 30, tzinfo=datetime.timezone.utc), "04:30 PM"),
        ],
    )
    def test_converts_utc_correctly_across_dst(self, utc_moment, expected_local):
        local = utc_moment.astimezone(EASTERN)
        assert local.strftime("%I:%M %p") == expected_local


@pytest.mark.django_db
class TestOrderTableTimes:

    def test_order_time_renders_in_eastern(self, authenticated_client):
        """An order placed at a known UTC instant shows the Eastern wall time"""
        order = Order.objects.create(customer_name="Jane", customer_email="j@x.com")
        # 20:30 UTC on a winter date is 3:30 PM Eastern
        moment = datetime.datetime(2026, 1, 15, 20, 30, tzinfo=datetime.timezone.utc)
        Order.objects.filter(pk=order.pk).update(created_at=moment)

        content = authenticated_client.get(reverse("order:order_list")).content.decode()

        # Django's "a" format renders "p.m." with periods.
        assert "03:30 p.m." in content.lower()
        # The old Central default would have rendered this hour.
        assert "02:30 p.m." not in content.lower()

    def test_now_matches_eastern_wall_clock(self):
        """timezone.localtime must track Eastern, not the server's UTC"""
        now_utc = timezone.now()
        assert timezone.localtime(now_utc).hour == now_utc.astimezone(EASTERN).hour
